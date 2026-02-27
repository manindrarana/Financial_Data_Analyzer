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
        self.logger.info("=" * 60)
        self.logger.info("Cleaning yahoo_stocks ...> clean_yahoo_stocks")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        self.conn.execute("""
            CREATE TABLE clean_yahoo_stocks AS
            SELECT 
                ticker,
                CAST(date AS DATE) AS date,
                open, high, low, close, volume
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY ticker, date ORDER BY volume DESC) AS rn
                FROM yahoo_stocks
                WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
                  AND date IS NOT NULL
            ) sub
            WHERE rn = 1
        """)
        cnt = self.conn.execute("SELECT COUNT(*) FROM clean_yahoo_stocks").fetchone()[0]
        self.logger.info(f"Rows in clean_yahoo_stocks: {cnt}")
        
        result = self.conn.execute("""
            SELECT ticker, COUNT(*) as rows, MIN(date) as start, MAX(date) as end
            FROM clean_yahoo_stocks
            GROUP BY ticker
            ORDER BY ticker
        """).fetchall()
        
        self.logger.info("Summary by ticker:")
        for row in result:
            self.logger.info(f"  {row[0]}: {row[1]} rows ({row[2]} to {row[3]})")
    
    def clean_bybit(self):
        self.logger.info("=" * 60)
        self.logger.info("Cleaning bybit_crypto ...> clean_bybit_crypto")
        self.logger.info("=" * 60)
        
        self.conn.execute("DROP TABLE IF EXISTS clean_bybit_crypto")
        self.conn.execute("""
            CREATE TABLE clean_bybit_crypto AS
            SELECT 
                symbol,
                CAST(date AS TIMESTAMP) AS date,
                open, high, low, close, volume
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY symbol, date ORDER BY volume DESC) AS rn
                FROM bybit_crypto
                WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
                  AND date IS NOT NULL
            ) sub
            WHERE rn = 1
        """)
        cnt = self.conn.execute("SELECT COUNT(*) FROM clean_bybit_crypto").fetchone()[0]
        self.logger.info(f"Rows in clean_bybit_crypto: {cnt}")
        
        result = self.conn.execute("""
            SELECT symbol, COUNT(*) as rows, MIN(date) as start, MAX(date) as end
            FROM clean_bybit_crypto
            GROUP BY symbol
            ORDER BY symbol
        """).fetchall()
        
        self.logger.info("Summary by symbol:")
        for row in result:
            self.logger.info(f"  {row[0]}: {row[1]} rows ({row[2]} to {row[3]})")
    
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