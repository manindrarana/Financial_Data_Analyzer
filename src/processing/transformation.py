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
        self.db_path = os.getenv("DATABASE_PATH", cfg["paths"]["database"])
        self.processed_bucket = cfg["paths"].get("processed_bucket", "processed-data")
        self.conn = duckdb.connect(self.db_path)
        
        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000").replace("http://", "")
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
        
        self.logger.info(f"Exporting clean_yahoo_stocks to MinIO ({self.processed_bucket})...")
        self.conn.execute(f"""
            COPY clean_yahoo_stocks 
            TO 's3://{self.processed_bucket}/clean_yahoo_stocks.parquet' (FORMAT PARQUET)
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
        
        self.logger.info(f"Exporting clean_bybit_crypto to MinIO ({self.processed_bucket})...")
        self.conn.execute(f"""
            COPY clean_bybit_crypto 
            TO 's3://{self.processed_bucket}/clean_bybit_crypto.parquet' (FORMAT PARQUET)
        """)
        self.logger.info("Export successful!")

    def clean_macro(self):
        """Build a universal macro table for all intervals (1h, 1d, 1wk, 1mo)."""
        self.logger.info("=" * 60)
        self.logger.info("Building clean_macro_features for all intervals...")
        self.logger.info("=" * 60)

        self.conn.execute("DROP TABLE IF EXISTS clean_macro_features")
        self.conn.execute("""
            CREATE TABLE clean_macro_features (
                interval VARCHAR,
                date TIMESTAMP,
                dxy_close DOUBLE,
                vix_close DOUBLE,
                tnx_close DOUBLE
            )
        """)

        intervals = ["1h", "1d", "1wk", "1mo"]
        for interval in intervals:
            try:
                self.logger.info(f"  Processing macro data for interval: {interval}")
                self.conn.execute(f"""
                    INSERT INTO clean_macro_features
                    WITH dxy AS (
                        SELECT CAST(date AS TIMESTAMP) AS date, close AS dxy_close
                        FROM read_parquet('s3://raw-data/DX-Y.NYB_{interval}.parquet')
                        WHERE close IS NOT NULL AND close > 0
                    ),
                    vix AS (
                        SELECT CAST(date AS TIMESTAMP) AS date, close AS vix_close
                        FROM read_parquet('s3://raw-data/^VIX_{interval}.parquet')
                        WHERE close IS NOT NULL AND close > 0
                    ),
                    tnx AS (
                        SELECT CAST(date AS TIMESTAMP) AS date, close AS tnx_close
                        FROM read_parquet('s3://raw-data/^TNX_{interval}.parquet')
                        WHERE close IS NOT NULL AND close > 0
                    )
                    SELECT
                        '{interval}' AS interval,
                        COALESCE(dxy.date, vix.date, tnx.date) AS date,
                        dxy.dxy_close,
                        vix.vix_close,
                        tnx.tnx_close
                    FROM dxy
                    FULL OUTER JOIN vix ON dxy.date = vix.date
                    FULL OUTER JOIN tnx ON dxy.date = tnx.date
                """)
            except Exception as e:
                self.logger.warning(f"  Skipped interval {interval} for macro features: {e}")

        cnt = self.conn.execute("SELECT COUNT(*) FROM clean_macro_features").fetchone()[0]
        self.logger.info(f"Total rows in clean_macro_features: {cnt}")

        self.logger.info(f"Exporting clean_macro_features to MinIO...")
        self.conn.execute(f"""
            COPY clean_macro_features 
            TO 's3://{self.processed_bucket}/clean_macro_features.parquet' (FORMAT PARQUET)
        """)
        self.logger.info("Export successful!")

    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("Starting Data Cleaning Process")
        self.logger.info("*" * 60)

        self.clean_yahoo()
        self.clean_bybit()
        self.clean_macro()

        self.logger.info("*" * 60)
        self.logger.info("Data Cleaning Completed")
        self.logger.info("*" * 60)

    def close(self):
        """Close DuckDB connection"""
        if self.conn:
            self.conn.close()

if __name__ == "__main__":
    cleaner = DataCleaner()
    cleaner.run()
    cleaner.close()