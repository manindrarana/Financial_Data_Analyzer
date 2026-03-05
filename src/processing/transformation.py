import duckdb
import yaml
import os
from src.utils import get_logger
from dotenv import load_dotenv

class DataCleaner:
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            cfg = yaml.safe_load(f)
        self.db_path = cfg["paths"]["database"]
        self.conn = duckdb.connect(self.db_path)
        
        s3_endpoint = os.getenv("S3_ENDPOINT_URL").replace("http://", "")
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
        self.logger.info(f"Connected to DuckDB at {self.db_path} with S3 access")
    
    def clean_yahoo(self):
        self.logger.info("=" * 60)
        self.logger.info("Cleaning yahoo_stocks ...> clean_yahoo_stocks")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        self.conn.execute("""
            CREATE TABLE clean_yahoo_stocks AS
            SELECT 
                ticker,
                interval,
                CAST(date AS TIMESTAMP) AS date,
                open, high, low, close, volume
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY ticker, interval, date ORDER BY volume DESC) AS rn
                FROM yahoo_stocks
                WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
                  AND date IS NOT NULL
            ) sub
            WHERE rn = 1
            ORDER BY ticker, interval, date
        """)
        cnt = self.conn.execute("SELECT COUNT(*) FROM clean_yahoo_stocks").fetchone()[0]
        self.logger.info(f"Rows in clean_yahoo_stocks: {cnt}")
        
        self.logger.info("Exporting clean_yahoo_stocks to MinIO (processed-data)...")
        self.conn.execute("""
            COPY clean_yahoo_stocks 
            TO 's3://processed-data/clean_yahoo_stocks.parquet' (FORMAT PARQUET)
        """)
        self.logger.info("Export successful!")

    def clean_bybit(self):
        self.logger.info("=" * 60)
        self.logger.info("Cleaning bybit_crypto ...> clean_bybit_crypto")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS clean_bybit_crypto")
        self.conn.execute("""
            CREATE TABLE clean_bybit_crypto AS
            SELECT 
                symbol,
                interval,
                CAST(date AS TIMESTAMP) AS date,
                open, high, low, close, volume
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY symbol, interval, date ORDER BY volume DESC) AS rn
                FROM bybit_crypto
                WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
                  AND date IS NOT NULL
            ) sub
            WHERE rn = 1
            ORDER BY symbol, interval, date
        """)
        cnt = self.conn.execute("SELECT COUNT(*) FROM clean_bybit_crypto").fetchone()[0]
        self.logger.info(f"Rows in clean_bybit_crypto: {cnt}")
        
        self.logger.info("Exporting clean_bybit_crypto to MinIO (processed-data)...")
        self.conn.execute("""
            COPY clean_bybit_crypto 
            TO 's3://processed-data/clean_bybit_crypto.parquet' (FORMAT PARQUET)
        """)
        self.logger.info("Export successful!")

    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("Starting Data Cleaning Process")
        self.logger.info("*" * 60)
        
        self.clean_yahoo()
        self.clean_bybit()
        
        self.logger.info("*" * 60)
        self.logger.info("Data Cleaning Completed")
        self.logger.info("*" * 60)

if __name__ == "__main__":
    cleaner = DataCleaner()
    cleaner.run()
    cleaner.conn.close()