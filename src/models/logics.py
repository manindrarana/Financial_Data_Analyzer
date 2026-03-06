import duckdb
import yaml
import os
from src.utils import get_logger
from dotenv import load_dotenv

class GoldLayerProcessor:
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.db_path = self.config["paths"]["database"]
        self.analytics_bucket = self.config["paths"].get("analytics_bucket", "analytics-data")
        self.conn = duckdb.connect(self.db_path)
        
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

    def generate_stocks_gold(self):
        """Calculates 7-period & 30-period Moving Averages and daily spread/volatility."""
        self.logger.info("=" * 60)
        self.logger.info("Building Gold Layer: gold_yahoo_analytics")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS gold_yahoo_analytics")
        
        self.conn.execute("""
            CREATE TABLE gold_yahoo_analytics AS
            SELECT 
                ticker,
                interval,
                date,
                close,
                volume,
                (high - low) AS spread_volatility,
                AVG(close) OVER (
                    PARTITION BY ticker, interval 
                    ORDER BY date 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS sma_7,
                AVG(close) OVER (
                    PARTITION BY ticker, interval 
                    ORDER BY date 
                    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                ) AS sma_30
            FROM clean_yahoo_stocks
            ORDER BY ticker, interval, date;
        """)

        out_path = f"s3://{self.analytics_bucket}/gold_yahoo_analytics.parquet"
        try:
            self.conn.execute(f"COPY gold_yahoo_analytics TO '{out_path}' (FORMAT PARQUET)")
            self.logger.info(f"Successfully exported Yahoo analytic metrics to {out_path}")
        except Exception as e:
            self.logger.error(f"Failed to export Yahoo Gold Layer: {e}")

    def generate_crypto_gold(self):
        """Calculates same analytics for Cryptos"""
        self.logger.info("=" * 60)
        self.logger.info("Building Gold Layer: gold_bybit_analytics")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS gold_bybit_analytics")
        
        self.conn.execute("""
            CREATE TABLE gold_bybit_analytics AS
            SELECT 
                symbol,
                interval,
                date,
                close,
                volume,
                (high - low) AS spread_volatility,
                AVG(close) OVER (
                    PARTITION BY symbol, interval 
                    ORDER BY date 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS sma_7,
                AVG(close) OVER (
                    PARTITION BY symbol, interval 
                    ORDER BY date 
                    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                ) AS sma_30
            FROM clean_bybit_crypto
            ORDER BY symbol, interval, date;
        """)
        
        out_path = f"s3://{self.analytics_bucket}/gold_bybit_analytics.parquet"
        try:
            self.conn.execute(f"COPY gold_bybit_analytics TO '{out_path}' (FORMAT PARQUET)")
            self.logger.info(f"Successfully exported Bybit analytic metrics to {out_path}")
        except Exception as e:
             self.logger.error(f"Failed to export Bybit Gold Layer: {e}")

    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("Starting Gold/Analytics Generation Process")
        self.logger.info("*" * 60)
        
        self.generate_stocks_gold()
        self.generate_crypto_gold()
        
        self.logger.info("*" * 60)
        self.logger.info("Analytics Processing Completed")
        self.logger.info("*" * 60)

if __name__ == "__main__":
    processor = GoldLayerProcessor()
    processor.run()

