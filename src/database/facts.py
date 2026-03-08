import duckdb
import yaml
import os
from dotenv import load_dotenv
from src.utils import get_logger


class FactLoader:
    """Loads fact tables from Silver layer with dimension lookups"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.db_path = self.config["paths"]["database"]
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
    
    def create_fact_table(self):
        """Create fact_price_history table with foreign keys"""
        self.logger.info("=" * 60)
        self.logger.info("Creating Fact Table: fact_price_history")
        self.logger.info("=" * 60)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fact_price_history (
                price_id INTEGER PRIMARY KEY,
                asset_id INTEGER NOT NULL,
                date_id INTEGER NOT NULL,
                interval_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                daily_volatility DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_asset 
            ON fact_price_history(asset_id);
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_date 
            ON fact_price_history(date_id);
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_timestamp 
            ON fact_price_history(timestamp);
        """)
        
        self.logger.info(" fact_price_history table and indexes are ready")
    
    
    def load_fact_price_history(self):
        """Load facts from Silver layer with incremental logic"""
        self.logger.info("=" * 60)
        self.logger.info("Loading fact_price_history (incremental)")
        self.logger.info("=" * 60)
        
        max_id = self.conn.execute("""
            SELECT COALESCE(MAX(price_id), 0) FROM fact_price_history
        """).fetchone()[0]
        
        self.logger.info(f"Current max price_id: {max_id}")
        
        self.logger.info("Loading Yahoo Finance stock data...")
        self.conn.execute(f"""
            INSERT INTO fact_price_history (
                price_id, asset_id, date_id, interval_id, timestamp,
                open, high, low, close, volume, daily_volatility
            )
            SELECT 
                ROW_NUMBER() OVER (ORDER BY s.date) + {max_id} AS price_id,
                da.asset_id,
                dd.date_id,
                di.interval_id,
                s.date AS timestamp,
                s.open,
                s.high,
                s.low,
                s.close,
                s.volume,
                (s.high - s.low) AS daily_volatility
            FROM clean_yahoo_stocks s
            JOIN dim_assets da ON s.ticker = da.asset_symbol
            JOIN dim_date dd ON CAST(s.date AS DATE) = dd.date
            JOIN dim_interval di ON s.interval = di.interval_code
            WHERE NOT EXISTS (
                SELECT 1 FROM fact_price_history f
                WHERE f.asset_id = da.asset_id
                  AND f.timestamp = s.date
                  AND f.interval_id = di.interval_id
            );
        """)