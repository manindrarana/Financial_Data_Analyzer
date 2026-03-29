import pandas as pd
import duckdb
import yaml
import os
from src.utils import get_logger

logger = get_logger("HealthCheck")


def get_db_connection():
    """Loads config and returns the DuckDB connection."""
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    
    db_path = config["paths"]["database"]
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}!")
        return None
        
    return duckdb.connect(db_path, read_only=True)


class DataHealthScanner:
    def __init__(self):
        """Initializes the scanner with its database connection and configuration."""
        self.conn = get_db_connection()
        self.logger = get_logger(__name__)
        
    def get_assets_to_check(self, table_name, symbol_col):
        """Fetches unique symbols and intervals from a table."""
        if not self.conn:
            return pd.DataFrame()
            
        return self.conn.execute(f"SELECT DISTINCT {symbol_col}, interval FROM {table_name}").df()
