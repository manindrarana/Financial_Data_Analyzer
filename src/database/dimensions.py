import duckdb
import yaml
import os
from dotenv import load_dotenv
from src.utils import get_logger


class DimensionBuilder:
    """Builds and maintains dimension tables for star schema"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.db_path = self.config["paths"]["database"]
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.conn = duckdb.connect(self.db_path)
        self.logger.info(f"Connected to persistent DuckDB at {self.db_path}")
        
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
    
    def create_dimension_tables(self):
        """Create all dimension tables if they don't exist"""
        self.logger.info("=" * 60)
        self.logger.info("Creating Dimension Tables")
        self.logger.info("=" * 60)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_assets (
                asset_id INTEGER PRIMARY KEY,
                asset_symbol VARCHAR UNIQUE NOT NULL,
                asset_name VARCHAR,
                asset_class VARCHAR NOT NULL,
                exchange VARCHAR,
                sector VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.logger.info(" dim_assets table is ready")
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_date (
                date_id INTEGER PRIMARY KEY,
                date DATE UNIQUE NOT NULL,
                year INTEGER,
                quarter INTEGER,
                month INTEGER,
                month_name VARCHAR,
                week INTEGER,
                day_of_week INTEGER,
                day_name VARCHAR,
                is_business_day BOOLEAN,
                is_weekend BOOLEAN
            );
        """)
        self.logger.info(" dim_date table is ready")
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_interval (
                interval_id INTEGER PRIMARY KEY,
                interval_code VARCHAR UNIQUE NOT NULL,
                interval_minutes INTEGER,
                interval_description VARCHAR
            );
        """)
        self.logger.info(" dim_interval table is ready")
        
    def populate_dim_assets(self):
        """Extract and load unique assets from Silver layer"""
        self.logger.info("=" * 60)
        self.logger.info("Populating dim_assets (incremental)")
        self.logger.info("=" * 60)
        
        max_id = self.conn.execute("""
            SELECT COALESCE(MAX(asset_id), 0) FROM dim_assets
        """).fetchone()[0]
        
        self.conn.execute(f"""
            INSERT INTO dim_assets (asset_id, asset_symbol, asset_name, asset_class, exchange)
            SELECT 
                ROW_NUMBER() OVER (ORDER BY asset_symbol) + {max_id} AS asset_id,
                asset_symbol,
                asset_symbol AS asset_name,
                asset_class,
                exchange
            FROM (
                SELECT DISTINCT 
                    ticker AS asset_symbol,
                    'Stock' AS asset_class,
                    'Yahoo Finance' AS exchange
                FROM clean_yahoo_stocks
                WHERE ticker NOT IN (SELECT asset_symbol FROM dim_assets)
                
                UNION ALL
                
                SELECT DISTINCT 
                    REPLACE(symbol, 'USDT', '') AS asset_symbol,
                    'Crypto' AS asset_class,
                    'Bybit' AS exchange
                FROM clean_bybit_crypto
                WHERE REPLACE(symbol, 'USDT', '') NOT IN (SELECT asset_symbol FROM dim_assets)
            ) new_assets
            WHERE asset_symbol IS NOT NULL;
        """)
        
        count = self.conn.execute("SELECT COUNT(*) FROM dim_assets").fetchone()[0]
        self.logger.info(f"dim_assets now contains {count} assets")
    