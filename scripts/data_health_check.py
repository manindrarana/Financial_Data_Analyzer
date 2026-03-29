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


    def _calculate_gaps(self, df, symbol, interval):
        """Engine to compare actual vs. ideal timestamps."""
        if df.empty:
            return {"Symbol": symbol, "Interval": interval, "Health": "No Data Found"}

        freq_map = {'1h': 'H', '60': 'H', '1d': 'D', 'D': 'D'}
        freq = freq_map.get(str(interval), 'H')
        
        start, end = df['date'].min(), df['date'].max()
        ideal_timeline = pd.date_range(start=start, end=end, freq=freq)
        
        actual_dates = set(df['date'])
        missing = [d for d in ideal_timeline if d not in actual_dates]
        
        completeness = (len(df) / len(ideal_timeline)) * 100 if len(ideal_timeline) > 0 else 0
        
        return {
            "Symbol": symbol,
            "Interval": interval,
            "Total Rows": len(df),
            "Gap Count": len(missing),
            "Completeness": f"{completeness:.2f}%"
        }

def check_gold_layer(self):
        """Continuity scan for the final gold_ml_features layer."""