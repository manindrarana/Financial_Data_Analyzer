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
        """Analyzes percentage of missing values (NaNs) across all feature columns."""
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
