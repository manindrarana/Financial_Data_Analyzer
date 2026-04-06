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

    def run(self):
        """profiling process."""
        self.logger.info("ML PROFILER - STARTING...")
        self.logger.info(f"ML Table: {self.ml_table}")
        
        summary = self.get_summary()
        print("\nML FEATURES SUMMARY (GOLD LAYER):")
        print(summary.to_string(index=False))
        
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
