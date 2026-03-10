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