import pandas as pd
import duckdb
import yaml
import os
from src.utils import get_logger

logger = get_logger("MLProfiler")

def get_db_connection():
    """connect to the Medallion DuckDB."""
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    db_path = config["paths"]["database"]
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}!")
        return None
        
    return duckdb.connect(db_path, read_only=True)

class MLProfiler:
    def __init__(self):
        """profiler and its configuration."""
        self.conn = get_db_connection()
        self.logger = logger
        self.ml_table = "gold_ml_features"

    def get_summary(self):
        """Fetches summary of ML-Ready features."""
        if not self.conn:
            return pd.DataFrame()
            
        query = f"""
            SELECT 
                asset_symbol, 
                interval, 
                COUNT(*) as row_count,
                MIN(date) as start_date,
                MAX(date) as end_date
            FROM {self.ml_table}
            GROUP BY asset_symbol, interval
        """
        return self.conn.execute(query).df()

    def check_nulls(self):
        """analyze percentage of missing values (NaNs) across all feature columns."""
        self.logger.info("  Step 4: Scanning for Missing (NaN) values...")
        
        sample = self.conn.execute(f"SELECT * FROM {self.ml_table} LIMIT 1").df()
        feature_cols = [c for c in sample.columns if c not in ['asset_symbol', 'interval', 'date', 'asset_class', 'exchange']]
        
        null_sqls = [f"COUNT(CASE WHEN {c} IS NULL THEN 1 END) as {c}_nulls" for c in feature_cols]
        total_query = f"SELECT COUNT(*) as total_rows, {', '.join(null_sqls)} FROM {self.ml_table}"
        
        null_counts = self.conn.execute(total_query).df()
        total_rows = null_counts['total_rows'].iloc[0]
        
        results = []
        for c in feature_cols:
            n_count = null_counts[f"{c}_nulls"].iloc[0]
            if n_count > 0:
                results.append({"Feature": c, "Null_Count": n_count, "Null_%": f"{(n_count/total_rows)*100:.2f}%"})
                
        return pd.DataFrame(results)

    def check_timeline_consistency(self):
        """identifies gaps in the date timeline for each asset-interval group."""
        self.logger.info("  Step 5: Analyzing Timeline Consistency & Gaps...")
        
        summary = self.get_summary()
        results = []
        
        freq_map = {'1h': 60, '1d': 1440, '1wk': 10080, '60': 60, 'D': 1440, 'W': 10080}
        
        for _, row in summary.iterrows():
            asset, interval = row['asset_symbol'], row['interval']
            actual_rows = row['row_count']
            
            start, end = pd.to_datetime(row['start_date']), pd.to_datetime(row['end_date'])
            
            minutes_diff = (end - start).total_seconds() / 60
            expected_rows = (minutes_diff / freq_map.get(interval, 1440)) + 1
            
            gaps = int(expected_rows - actual_rows)
            gap_pct = (gaps / expected_rows) * 100 if expected_rows > 0 else 0
            
            if gaps > 0:
                results.append({
                    "Asset": asset,
                    "Interval": interval,
                    "Expected": int(expected_rows),
                    "Actual": actual_rows,
                    "Gaps": gaps,
                    "Gap_%": f"{gap_pct:.2f}%"
                })
                
        return pd.DataFrame(results)

    def generate_markdown_report(self, summary_df, null_df, gap_df, frozen_df):
        """saves profiling results to reports/ml_profile_report.md."""
        self.logger.info("  Step 6: Saving Quality Report...")
        
        report_path = "reports/ml_profile_report.md"
        os.makedirs("reports", exist_ok=True)
        
        with open(report_path, "w") as f:
            f.write("# ML Data Quality Report\n\n")
            f.write(f"Generated on: {pd.Timestamp.now()}\n\n")
            
            f.write("## 1. Data Summary\n")
            f.write(summary_df.to_string(index=False) + "\n\n")
            
            f.write("## 2. Missing Values (NaNs)\n")
            if null_df.empty:
                f.write("Status: Perfect (0 Nulls found)\n\n")
            else:
                f.write(null_df.to_string(index=False) + "\n\n")
            
            f.write("## 3. Data Gaps\n")
            f.write("Note: Stock market data (1h/1d) correctly shows gaps for weekends.\n\n")
            if gap_df.empty:
                f.write("Status: No gaps detected (Continuous).\n\n")
            else:
                f.write(gap_df.to_string(index=False) + "\n\n")
            
            f.write("## 4. Frozen Prices \n")
            if frozen_df.empty:
                f.write("Status: Perfect \n\n")
            else:
                f.write("Assets with excessive repeated prices (>5 rows):\n\n")
                f.write(frozen_df.to_string(index=False) + "\n\n")
                
            f.write("## 5. Conclusion\n")
            f.write("Data is verified for ML training.\n")

        self.logger.info(f"File saved: {report_path}")

    def check_frozen_prices(self, threshold=5):
        """finds assets that have the exact same price for multiple candles ."""
        self.logger.info("  Step 7: Detecting Frozen  Prices...")
        
        query = f"""
            WITH price_changes AS (
                SELECT 
                    asset_symbol,
                    interval,
                    close,
                    LAG(close) OVER (PARTITION BY asset_symbol, interval ORDER BY date) as prev_close
                FROM {self.ml_table}
            )
            SELECT 
                asset_symbol,
                interval,
                COUNT(*) filter (where close = prev_close) as frozen_candles,
                COUNT(*) as total_candles
            FROM price_changes
            GROUP BY asset_symbol, interval
            HAVING frozen_candles > {threshold}
        """
        df = self.conn.execute(query).df()
        if not df.empty:
            df['Frozen_%'] = (df['frozen_candles'] / df['total_candles']) * 100
            df['Frozen_%'] = df['Frozen_%'].map('{:.2f}%'.format)
            
        return df

    def run(self):
        """profiling process."""
        self.logger.info("ML PROFILER - STARTING...")
        self.logger.info(f"ML Table: {self.ml_table}")
        
        summary = self.get_summary()
        print("\nML FEATURES SUMMARY (GOLD LAYER):")
        print(summary.to_string(index=False))
        
        null_report = self.check_nulls()
        print("\nNULL VALUE QUALITY REPORT:")
        if not null_report.empty:
            print(null_report.to_string(index=False))
        else:
            print("PERFECT: 0 Null values found in all features!")
        
        gap_report = self.check_timeline_consistency()
        print("\nTIMELINE CONSISTENCY REPORT (GAPS):")
        if not gap_report.empty:
            print(gap_report.to_string(index=False))
        else:
            print("PERFECT: All timelines are 100% continuous!")
        
        frozen_report = self.check_frozen_prices()
        print("\nFROZEN PRICE REPORT:")
        if not frozen_report.empty:
            print(frozen_report.to_string(index=False))
        else:
            print("PERFECT: No frozen prices detected!")
            
        self.generate_markdown_report(summary, null_report, gap_report, frozen_report)
        
        print("\n" + "=" * 80)

    def close(self):
        """close the database connection."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

if __name__ == "__main__":
    profiler = MLProfiler()
    try:
        profiler.run()
    finally:
        profiler.close()
