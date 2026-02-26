import duckdb
import os
import yaml
from src.utils import get_logger


class DatabaseLoader:
    def __init__(self):
        """Initialize database connection and configuration"""
        self.logger = get_logger(__name__)
        
        with open("configs/settings.yml", "r") as f:
            config = yaml.safe_load(f)
        
        self.db_path = config["paths"]["database"]
        self.raw_path = config["paths"]["raw_data"]
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.conn = duckdb.connect(self.db_path)
        self.logger.info(f"Connected to DuckDB at {self.db_path}")
    
    def load_yahoo_data(self):
        """Load all Yahoo Finance parquet files into yahoo_stocks table"""
        self.logger.info("=" * 60)
        self.logger.info("Loading Yahoo Finance data into DuckDB...")
        self.logger.info("=" * 60)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS yahoo_stocks (
                ticker VARCHAR,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                adj_close DOUBLE
            )
        """)
        self.logger.info("Created/verified yahoo_stocks table")
        
        if not os.path.exists(self.raw_path):
            self.logger.warning(f"Raw data path does not exist: {self.raw_path}")
            return
        
        yahoo_files = [f for f in os.listdir(self.raw_path) 
                       if f.endswith('.parquet') and 'USDT' not in f]
        
        if not yahoo_files:
            self.logger.warning("No Yahoo Finance parquet files found")
            return
        self.conn.execute("DELETE FROM yahoo_stocks")
        self.logger.info("Cleared existing data from yahoo_stocks table")
        
         