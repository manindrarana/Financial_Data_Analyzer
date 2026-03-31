import pandas as pd
import duckdb
import yaml
import os
from src.utils import get_logger

logger = get_logger("DataProfiler")

def get_db_connection():
    """Shared logic to connect to the Medallion DuckDB."""
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    db_path = config["paths"]["database"]
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}!")
        return None
        
    return duckdb.connect(db_path, read_only=True)

class DataProfiler:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = logger
        
    def close(self):
        """Closes the connection safely."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.logger.info("Profiler connection closed.")

if __name__ == "__main__":
    profiler = DataProfiler()
    try:
        profiler.logger.info("Profiler ready for analysiss.")
    finally:
        profiler.close()
