import os
import pytest
import duckdb
import yaml
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")
MINIO_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")

PARQUET_PATH = "s3://analytics-data/ml_features.parquet"
CORE_OHLCV_COLUMNS = ["date", "asset_symbol", "asset_class", "interval", "open", "high", "low", "close", "volume"]
MIN_EXPECTED_COLUMNS = 40


def get_duckdb_connection():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"""
        CREATE SECRET IF NOT EXISTS (
            TYPE S3,
            KEY_ID '{MINIO_USER}',
            SECRET '{MINIO_PASSWORD}',
            ENDPOINT '{MINIO_ENDPOINT}',
            URL_STYLE 'path',
            USE_SSL false
        );
    """)
    return con


class TestDuckDBConnection:
    def test_duckdb_connects_successfully(self):
        con = get_duckdb_connection()
        result = con.execute("SELECT 1 AS test").fetchone()
        assert result[0] == 1
        con.close()

class TestMlFeaturesParquet:
    def setup_method(self):
        self.con = get_duckdb_connection()
        
    def teardown_method(self):
        self.con.close()
        
    def test_parquet_file_is_accessible(self):
        result = self.con.execute(
            "SELECT COUNT(*) FROM read_parquet('s3://analytics-data/ml_features.parquet')"
        ).fetchone()
        assert result[0] > 0, "ml_features.parquet is empty or inaccessible"
        
    def test_parquet_has_expected_assets(self):
        with open("configs/settings.yml", "r") as f:
            config = yaml.safe_load(f)

        yfinance_targets = config["ingestion"]["targets"]["yfinance"]
        bybit_targets = [s.replace("USDT", "") for s in config["ingestion"]["targets"]["bybit"]]
        all_expected = yfinance_targets + bybit_targets

        symbols = self.con.execute(
            "SELECT DISTINCT asset_symbol FROM read_parquet('s3://analytics-data/ml_features.parquet')"
        ).df()["asset_symbol"].tolist()

        for symbol in all_expected:
            assert symbol in symbols, f"Expected asset {symbol} not found in ml_features"
    
    def test_parquet_has_core_ohlcv_columns(self):
        columns = self.con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{PARQUET_PATH}')"
        ).df()["column_name"].tolist()
        for col in CORE_OHLCV_COLUMNS:
            assert col in columns, f"Missing core OHLCV column: {col}"

    def test_parquet_has_sufficient_feature_columns(self):
        column_count = self.con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{PARQUET_PATH}')"
        ).df().shape[0]
        assert column_count >= MIN_EXPECTED_COLUMNS, (
            f"Only {column_count} columns found, expected at least {MIN_EXPECTED_COLUMNS}. "
            f"Gold Layer processing may have failed."
        )

    def test_parquet_has_no_negative_prices(self):
        result = self.con.execute(f"""
            SELECT COUNT(*) FROM read_parquet('{PARQUET_PATH}')
            WHERE close <= 0 OR open <= 0
        """).fetchone()
        assert result[0] == 0, "Negative or zero prices found in ml_features.parquet"