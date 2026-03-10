import duckdb
import yaml
import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from src.utils import get_logger
from sklearn.ensemble import RandomForestRegressor


class FeatureAnalyzer:
    """Analyzes gold_ml_features quality and selects best indicators for ML"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.db_path = self.config["paths"]["database"]
        self.analytics_bucket = self.config["paths"].get("analytics_bucket", "analytics-data")
        self.conn = duckdb.connect(self.db_path)
        
        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "").replace("http://", "")
        self.conn.execute("INSTALL httpfs; LOAD httpfs;")
        self.conn.execute(f"""
            CREATE SECRET IF NOT EXISTS (
                TYPE S3,
                KEY_ID '{os.getenv("AWS_ACCESS_KEY_ID")}',
                SECRET '{os.getenv("AWS_SECRET_ACCESS_KEY")}',
                ENDPOINT '{s3_endpoint}',
                URL_STYLE 'path',
                USE_SSL false
            );
        """)
    
    
    def analyze_features(self):
        """Run complete feature analysis and create gold_feature_statistics table"""
        self.logger.info("=" * 60)
        self.logger.info("Feature Quality Analysis: gold_ml_features")
        self.logger.info("=" * 60)
        
        df = self.conn.execute("SELECT * FROM gold_ml_features").df()
        self.logger.info(f"Loaded {len(df)} rows from gold_ml_features")
        
        metadata_cols = ['asset_symbol', 'asset_class', 'exchange', 'interval', 'date']
        indicator_cols = [col for col in df.columns if col not in metadata_cols]
        self.logger.info(f"Analyzing {len(indicator_cols)} indicator columns")
        
        self.logger.info("\n--- Calculating Feature Statistics ---")
        stats_df = df[indicator_cols].describe().T
        stats_df['feature_name'] = stats_df.index
        stats_df = stats_df.reset_index(drop=True)
        
        has_inf_list = [np.isinf(df[col]).any() for col in indicator_cols]
        null_count_list = [df[col].isnull().sum() for col in indicator_cols]
        stats_df['has_inf'] = has_inf_list
        stats_df['null_count'] = null_count_list
        
        self.logger.info(f"Statistics calculated for {len(stats_df)} features")
        
        self.logger.info("\n--- Correlation Analysis ---")
        corr_matrix = df[indicator_cols].corr()
        
        high_corr_pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                if abs(corr_matrix.iloc[i, j]) > 0.9:
                    high_corr_pairs.append({
                        'feature_1': corr_matrix.columns[i],
                        'feature_2': corr_matrix.columns[j],
                        'correlation': corr_matrix.iloc[i, j]
                    })
        
        if high_corr_pairs:
            self.logger.warning(f"Found {len(high_corr_pairs)} highly correlated pairs (>0.9)")
        else:
            self.logger.info("No highly correlated pairs found")
        
        if 'returns_1d' in indicator_cols:
            target_corr = corr_matrix['returns_1d'].drop('returns_1d').sort_values(key=abs, ascending=False)
            stats_df['target_correlation'] = stats_df['feature_name'].map(target_corr)
            
            self.logger.info("\nTop 10 features correlated with returns_1d:")
            for feat, corr in target_corr.head(10).items():
                self.logger.info(f"  {feat}: {corr:.4f}")
        
        self.logger.info("\n--- Feature Importance Ranking ---")
        
        leakage_cols = ['returns_1d', 'returns_5d', 'returns_10d', 'returns_20d', 'log_returns']
        feature_cols = [col for col in indicator_cols if col not in leakage_cols]
        
        self.logger.info(f"Excluded {len(leakage_cols)} leakage features (returns-based)")
        self.logger.info(f"Analyzing {len(feature_cols)} valid predictive features")
        
        df_clean = df[feature_cols + ['returns_1d']].dropna()
        
        if len(df_clean) < 1000:
            self.logger.warning("Not enough data for importance analysis")
            stats_df['importance_score'] = 0.0
        else:
            X = df_clean[feature_cols]
            y = df_clean['returns_1d']
            
            sample_size = min(10000, len(X))
            self.logger.info(f"Training RandomForest on {sample_size} samples...")
            X_sample = X.sample(n=sample_size, random_state=42)
            y_sample = y.loc[X_sample.index]
            
            rf = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
            rf.fit(X_sample, y_sample)
            
            importance_df = pd.DataFrame({
                'feature_name': feature_cols,
                'importance_score': rf.feature_importances_
            }).sort_values('importance_score', ascending=False)
            
            stats_df = stats_df.merge(importance_df, on='feature_name', how='left')
            stats_df['importance_score'] = stats_df['importance_score'].fillna(0.0)
            
            self.logger.info("\nTop 15 Most Important Features:")
            for idx, row in importance_df.head(15).iterrows():
                self.logger.info(f"  {row['feature_name']}: {row['importance_score']:.4f}")
            
        self.logger.info("\n--- Data Quality Checks ---")
        quality_flags = []
        for idx, row in stats_df.iterrows():
            if row['has_inf']:
                quality_flags.append('FAIL_INF')
            elif row['null_count'] > 0:
                quality_flags.append('FAIL_NULL')
            elif row['feature_name'] in leakage_cols:
                quality_flags.append('LEAKAGE')
            else:
                quality_flags.append('PASS')
        
        stats_df['quality_flag'] = quality_flags
        
        fail_count = sum(1 for flag in quality_flags if flag not in ['PASS', 'LEAKAGE'])
        leakage_count = sum(1 for flag in quality_flags if flag == 'LEAKAGE')
        
        if fail_count > 0:
            self.logger.error(f"Quality check: {fail_count} features FAILED")
        else:
            self.logger.info("Quality check: All features PASSED ✓")
        
        if leakage_count > 0:
            self.logger.warning(f"Flagged {leakage_count} features as LEAKAGE (should not use for prediction)")
        
        self.conn.execute("DROP TABLE IF EXISTS gold_feature_statistics")
        self.conn.execute("CREATE TABLE gold_feature_statistics AS SELECT * FROM stats_df ORDER BY importance_score DESC")
        
        cnt = self.conn.execute("SELECT COUNT(*) FROM gold_feature_statistics").fetchone()[0]
        self.logger.info(f"\nCreated gold_feature_statistics with {cnt} features")
        