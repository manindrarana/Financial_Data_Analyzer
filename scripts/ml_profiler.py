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
        self.tables = [
            ("clean_yahoo_stocks", "ticker"),
            ("clean_bybit_crypto", "symbol")
        ]

    def close(self):
        """close the database connection."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

if __name__ == "__main__":
    profiler = MLProfiler()
    try:
        pass
    finally:
        profiler.close()
