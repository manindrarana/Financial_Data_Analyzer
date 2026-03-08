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
        
    def generate_unified_gold_layer(self):
        """Build Gold layer from fact_price_history with dimension"""
        self.logger.info("=" * 60)
        self.logger.info("Building Unified Gold Layer: gold_financial_analytics")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS gold_financial_analytics")
        
        self.conn.execute("""
            CREATE TABLE gold_financial_analytics AS
            SELECT 
                da.asset_symbol,
                da.asset_class,
                da.exchange,
                di.interval_code AS interval,
                f.timestamp AS date,
                f.open,
                f.high,
                f.low,
                f.close,
                f.volume,
                f.daily_volatility,
                
                -- 7-Period Simple Moving Average (partitioned by asset + interval)
                AVG(f.close) OVER (
                    PARTITION BY da.asset_symbol, di.interval_code 
                    ORDER BY f.timestamp 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS sma_7,
                
                -- 30-Period Simple Moving Average (partitioned by asset + interval)
                AVG(f.close) OVER (
                    PARTITION BY da.asset_symbol, di.interval_code 
                    ORDER BY f.timestamp 
                    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                ) AS sma_30
                
            FROM fact_price_history f
            JOIN dim_assets da ON f.asset_id = da.asset_id
            JOIN dim_date dd ON f.date_id = dd.date_id
            JOIN dim_interval di ON f.interval_id = di.interval_id
            ORDER BY da.asset_class, da.asset_symbol, di.interval_code, f.timestamp;
        """)
        
        cnt = self.conn.execute("SELECT COUNT(*) FROM gold_financial_analytics").fetchone()[0]
        self.logger.info(f"Successfully generated Unified Gold Table with {cnt} rows!")
        
        out_path = f"s3://{self.analytics_bucket}/gold_financial_analytics.parquet"
        try:
            self.conn.execute(f"COPY gold_financial_analytics TO '{out_path}' (FORMAT PARQUET)")
            self.logger.info(f"Successfully exported Unified Gold Layer to MinIO: {out_path}")
        except Exception as e:
            self.logger.error(f"Failed to export Unified Gold Layer to MinIO: {e}")

    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("Starting Gold/Analytics Generation Process")
        self.logger.info("*" * 60)
        
        self.generate_unified_gold_layer()
        
        self.logger.info("*" * 60)
        self.logger.info("Analytics Processing Completed")
        self.logger.info("*" * 60)

if __name__ == "__main__":
    processor = GoldLayerProcessor()
    processor.run()
    processor.conn.close()

