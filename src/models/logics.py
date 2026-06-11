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
        
    def _build_analytics_table(self, asset_class: str):
        table_name = f"gold_{asset_class.lower()}_analytics"
        before = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0] if self._table_exists(table_name) else 0

        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                asset_symbol VARCHAR,
                asset_class VARCHAR,
                exchange VARCHAR,
                interval VARCHAR,
                date TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                turnover DOUBLE,
                open_interest DOUBLE,
                funding_rate DOUBLE,
                daily_volatility DOUBLE,
                sma_7 DOUBLE,
                sma_30 DOUBLE
            )
        """)

        for col in ('turnover', 'open_interest', 'funding_rate'):
            try:
                self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} DOUBLE")
            except Exception:
                pass

        if asset_class == 'Crypto':
            insert_sql = f"""
                WITH all_rows AS (
                    SELECT
                        da.asset_symbol, da.asset_class, da.exchange,
                        di.interval_code AS interval, f.timestamp AS date,
                        f.open, f.high, f.low, f.close, f.volume, f.turnover,
                        f.open_interest, f.funding_rate, f.daily_volatility,
                        AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS sma_7,
                        AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS sma_30
                    FROM fact_price_history f
                    JOIN dim_assets da ON f.asset_id = da.asset_id
                    JOIN dim_interval di ON f.interval_id = di.interval_id
                    WHERE da.asset_class = '{asset_class}'
                )
                INSERT INTO {table_name}
                SELECT * FROM all_rows a
                WHERE NOT EXISTS (
                    SELECT 1 FROM {table_name} g
                    WHERE g.asset_symbol = a.asset_symbol
                      AND g.interval = a.interval
                      AND g.date = a.date
                )
            """
        else:
            insert_sql = f"""
                WITH all_rows AS (
                    SELECT
                        da.asset_symbol, da.asset_class, da.exchange,
                        di.interval_code AS interval, f.timestamp AS date,
                        f.open, f.high, f.low, f.close, f.volume,
                        NULL AS turnover, NULL AS open_interest, NULL AS funding_rate,
                        f.daily_volatility,
                        AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS sma_7,
                        AVG(f.close) OVER (PARTITION BY da.asset_symbol, di.interval_code ORDER BY f.timestamp ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS sma_30
                    FROM fact_price_history f
                    JOIN dim_assets da ON f.asset_id = da.asset_id
                    JOIN dim_interval di ON f.interval_id = di.interval_id
                    WHERE da.asset_class = '{asset_class}'
                )
                INSERT INTO {table_name}
                SELECT * FROM all_rows a
                WHERE NOT EXISTS (
                    SELECT 1 FROM {table_name} g
                    WHERE g.asset_symbol = a.asset_symbol
                      AND g.interval = a.interval
                      AND g.date = a.date
                )
            """

        self.conn.execute(insert_sql)

        after = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        self.logger.info(f"{table_name}: {before} -> {after} rows ({after - before} new)")

    def _table_exists(self, table_name: str) -> bool:
        result = self.conn.execute(f"""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = '{table_name}'
        """).fetchone()[0]
        return result > 0

    def generate_intermediate_gold_layers(self):
        self.logger.info("=" * 60)
        self.logger.info("Building Specialized Intermediate Gold Layers (incremental)")
        self.logger.info("=" * 60)

        self.logger.info("--- Updating gold_crypto_analytics ---")
        self._build_analytics_table('Crypto')

        self.logger.info("--- Updating gold_stock_analytics ---")
        self._build_analytics_table('Stock')

        self.logger.info("Specialized Intermediate Gold Layers updated!")

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

