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
        
        for file in yahoo_files:
            try:
                ticker = file.split('_')[0]
                file_path = os.path.join(self.raw_path, file)
                
                self.conn.execute(f"""
                    INSERT INTO yahoo_stocks 
                    SELECT 
                        '{ticker}' as ticker,
                        date,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        adj_close
                    FROM read_parquet('{file_path}')
                """)
                
                self.logger.info(f"Done Loading {ticker} from {file}")
            except Exception as e:
                self.logger.error(f"Failed to Load {file}: {e}")
                
        result = self.conn.execute("""
            SELECT 
                ticker, 
                COUNT(*) as row_count,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM yahoo_stocks 
            GROUP BY ticker
            ORDER BY ticker
        """).fetchall()

        self.logger.info("Yahoo Finance Data Summary:")
        for row in result:
            self.logger.info(f"  {row[0]}: {row[1]} rows ({row[2]} to {row[3]})")
        
        total = self.conn.execute("SELECT COUNT(*) FROM yahoo_stocks").fetchone()[0]
        self.logger.info(f"Total rows in yahoo_stocks: {total}")
    
    def load_bybit_data(self):
        """Load all Bybit parquet files into bybit_crypto table"""
        self.logger.info("=" * 60)
        self.logger.info("Loading Bybit data into DuckDB...")
        self.logger.info("=" * 60)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bybit_crypto (
                symbol VARCHAR,
                date TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE
            )
        """)
        self.logger.info("Created/verified bybit_crypto table")
        
        if not os.path.exists(self.raw_path):
            self.logger.warning(f"Raw data path does not exist: {self.raw_path}")
            return
        
        bybit_files = [f for f in os.listdir(self.raw_path) 
                       if f.endswith('.parquet') and 'USDT' in f]
        
        if not bybit_files:
            self.logger.warning("No Bybit parquet files found")
            return
        
        self.conn.execute("DELETE FROM bybit_crypto")
        self.logger.info("Cleared existing data from bybit_crypto table")
        
        
        for file in bybit_files:
            try:
                symbol = file.split('_')[0]
                file_path = os.path.join(self.raw_path, file)
                
                self.conn.execute(f"""
                    INSERT INTO bybit_crypto 
                    SELECT 
                        '{symbol}' as symbol,
                        date,
                        open,
                        high,
                        low,
                        close,
                        volume
                    FROM read_parquet('{file_path}')
                """)
                
                self.logger.info(f"Loaded {symbol} from {file}")
            except Exception as e:
                self.logger.error(f"Failed to load {file}: {e}")