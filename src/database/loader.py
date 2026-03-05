import duckdb
import os
import yaml
from dotenv import load_dotenv
from src.utils import get_logger


class DatabaseLoader:
    def __init__(self):
        """Initialize database connection, S3 secrets, and configuration"""
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
        
        self.db_path = self.config["paths"]["database"]
        self.s3_bucket = self.config["paths"].get("s3_bucket", "raw-data")
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.conn = duckdb.connect(self.db_path)
        self.logger.info(f"Connected to DuckDB at {self.db_path}")

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

    def load_yahoo_data(self):
        """Load configured Yahoo Finance parquet files from S3 into yahoo_stocks table"""
        self.logger.info("=" * 60)
        self.logger.info("Loading Yahoo Finance data into DuckDB from S3...")
        self.logger.info("=" * 60)

        self.conn.execute("DROP TABLE IF EXISTS yahoo_stocks")
        self.conn.execute("""
            CREATE TABLE yahoo_stocks (
                ticker VARCHAR,
                interval VARCHAR,
                date TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE
            )
        """)
        
        targets = self.config["ingestion"]["targets"].get("yfinance", [])
        intervals = self.config["providers"]["yfinance"].get("intervals", ["1h"])
        
        for ticker in targets:
            for interval in intervals:
                file_path = f"s3://{self.s3_bucket}/{ticker}_{interval}.parquet"
                try:
                    self.conn.execute(f"""
                        INSERT INTO yahoo_stocks 
                        SELECT 
                            '{ticker}' as ticker,
                            '{interval}' as interval,
                            date, open, high, low, close, volume
                        FROM read_parquet('{file_path}')
                    """)
                    self.logger.info(f"Loaded {ticker} [{interval}] from S3")
                except Exception as e:
                    self.logger.warning(f"Skipped {file_path}: File might not exist yet.")

    def load_bybit_data(self):
        """Load configured Bybit parquet files from S3 into bybit_crypto table"""
        self.logger.info("=" * 60)
        self.logger.info("Loading Bybit data into DuckDB from S3...")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS bybit_crypto")
        self.conn.execute("""
            CREATE TABLE bybit_crypto (
                symbol VARCHAR,
                interval VARCHAR,
                date TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE
            )
        """)
        
        targets = self.config["ingestion"]["targets"].get("bybit", [])
        intervals = self.config["providers"]["bybit"].get("intervals", ["60"])
        
        for symbol in targets:
            for interval in intervals:
                readable_interval = "1h" if interval == "60" else ("1d" if interval == "D" else interval)
                
                file_path = f"s3://{self.s3_bucket}/{symbol}_{readable_interval}.parquet"
                try:
                    self.conn.execute(f"""
                        INSERT INTO bybit_crypto 
                        SELECT 
                            '{symbol}' as symbol,
                            '{readable_interval}' as interval,
                            date, open, high, low, close, volume
                        FROM read_parquet('{file_path}')
                    """)
                    self.logger.info(f"Loaded {symbol} [{interval}] from S3")
                except Exception as e:
                    self.logger.error(f"Failed to load {file_path}: {e}")

    def load_all(self):
        self.load_yahoo_data()
        self.load_bybit_data()

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    loader = DatabaseLoader()
    loader.load_all()
    loader.close()