import duckdb
import yaml
from src.utils import get_logger

class DataCleaner:
    def __init__(self):
        self.logger = get_logger(__name__)
        with open("configs/settings.yml", "r") as f:
            cfg = yaml.safe_load(f)
        self.db_path = cfg["paths"]["database"]
        self.conn = duckdb.connect(self.db_path)
        self.logger.info(f"Connected to DuckDB at {self.db_path}")
    
    def clean_yahoo(self):
        self.logger.info("Cleaning yahoo_stocks ...> clean_yahoo_stocks")
        self.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        self.conn.execute("""
            CREATE TABLE clean_yahoo_stocks AS
            SELECT DISTINCT ON (ticker, date)
                   ticker,
                   CAST(date AS DATE) AS date,
                   open, high, low, close, volume
            FROM yahoo_stocks
            WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
              AND date IS NOT NULL
        """)
        cnt = self.conn.execute("SELECT COUNT(*) FROM clean_yahoo_stocks").fetchone()[0]
        self.logger.info(f"Rows in clean_yahoo_stocks: {cnt}")
    def clean_bybit(self):
        self.logger.info("Cleaning bybit_crypto ...> clean_bybit_crypto")
        self.conn.execute("DROP TABLE IF EXISTS clean_bybit_crypto")
        self.conn.execute("""
            CREATE TABLE clean_bybit_crypto AS
            SELECT DISTINCT ON (symbol, date)
                   symbol,
                   CAST(date AS TIMESTAMP) AS date,
                   open, high, low, close, volume
            FROM bybit_crypto
            WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
              AND date IS NOT NULL
        """)
        cnt = self.conn.execute("SELECT COUNT(*) FROM clean_bybit_crypto").fetchone()[0]
        self.logger.info(f"Rows in clean_bybit_crypto: {cnt}")
