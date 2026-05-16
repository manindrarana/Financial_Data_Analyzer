import duckdb
import yaml
import os
from dotenv import load_dotenv
from src.utils import get_logger

class GoldLayerProcessor:
    """Builds analytics Gold layer from fact tables and dimensions"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.db_path = self.config["paths"]["database"]
        self.analytics_bucket = self.config["paths"].get("analytics_bucket", "analytics-data")
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
        
    def generate_intermediate_gold_layers(self):
        """Build specialized intermediate tables for Crypto and Stocks"""
        self.logger.info("=" * 60)
        self.logger.info("Building Specialized Intermediate Gold Layers")
        self.logger.info("=" * 60)
        
        self.logger.info("--- Generating gold_crypto_analytics ---")
        self.conn.execute("DROP TABLE IF EXISTS gold_crypto_analytics")
        self.conn.execute("""
            CREATE TABLE gold_crypto_analytics AS
            SELECT
                da.asset_symbol, da.asset_class, da.exchange,
                di.interval_code AS interval, f.timestamp AS date,
                f.open, f.high, f.low, f.close, f.volume, f.turnover,
                f.open_interest, f.open_interest_value, f.funding_rate, f.daily_volatility,
                AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS sma_7,
                AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS sma_30
            FROM fact_price_history f
            JOIN dim_assets da ON f.asset_id = da.asset_id
            JOIN dim_interval di ON f.interval_id = di.interval_id
            WHERE da.asset_class = 'Crypto'
            ORDER BY da.asset_symbol, di.interval_code, f.timestamp;
        """)
        
        self.logger.info("--- Generating gold_stock_analytics ---")
        self.conn.execute("DROP TABLE IF EXISTS gold_stock_analytics")
        self.conn.execute("""
            CREATE TABLE gold_stock_analytics AS
            SELECT
                da.asset_symbol, da.asset_class, da.exchange,
                di.interval_code AS interval, f.timestamp AS date,
                f.open, f.high, f.low, f.close, f.volume, f.daily_volatility,
                AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS sma_7,
                AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS sma_30
            FROM fact_price_history f
            JOIN dim_assets da ON f.asset_id = da.asset_id
            JOIN dim_interval di ON f.interval_id = di.interval_id
            WHERE da.asset_class = 'Stock'
            ORDER BY da.asset_symbol, di.interval_code, f.timestamp;
        """)

        self.logger.info("Successfully generated specialized Intermediate Gold Layers!")

    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("Starting Gold/Analytics Generation Process")
        self.logger.info("*" * 60)
        
        self.generate_intermediate_gold_layers()
        
        self.logger.info("*" * 60)
        self.logger.info("Analytics Processing Completed")
        self.logger.info("*" * 60)

    def close(self):
        """Close DuckDB connection"""
        if self.conn:
            self.conn.close()

if __name__ == "__main__":
    processor = GoldLayerProcessor()
    processor.run()
    processor.close()

