import os
import pytest
import duckdb
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")
MINIO_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")


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