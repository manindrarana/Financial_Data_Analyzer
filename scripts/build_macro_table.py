"""
Script to build macro_features_1h table in DuckDB from S3 parquets.
Run from project root: python scripts/build_macro_table.py
"""
import duckdb
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH      = "database/financial_data.duckdb"
S3_ENDPOINT  = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000").replace("http://", "")
ACCESS_KEY   = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY   = os.getenv("AWS_SECRET_ACCESS_KEY")

print(f"Connecting to DuckDB: {DB_PATH}")
conn = duckdb.connect(DB_PATH)

conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute(f"""
    CREATE SECRET IF NOT EXISTS (
        TYPE S3,
        KEY_ID '{ACCESS_KEY}',
        SECRET '{SECRET_KEY}',
        ENDPOINT '{S3_ENDPOINT}',
        URL_STYLE 'path',
        USE_SSL false
    );
""")
print("S3 access configured")

print("Building macro_features_1h table...")
conn.execute("DROP TABLE IF EXISTS macro_features_1h")
conn.execute("""
    CREATE TABLE macro_features_1h AS
    WITH dxy AS (
        SELECT
            CAST(date AS TIMESTAMP) AS date,
            close AS dxy_close
        FROM read_parquet('s3://raw-data/DX-Y.NYB_1h.parquet')
        WHERE close IS NOT NULL AND close > 0
    ),
    vix AS (
        SELECT
            CAST(date AS TIMESTAMP) AS date,
            close AS vix_close
        FROM read_parquet('s3://raw-data/^VIX_1h.parquet')
        WHERE close IS NOT NULL AND close > 0
    ),
    tnx AS (
        SELECT
            CAST(date AS TIMESTAMP) AS date,
            close AS tnx_close
        FROM read_parquet('s3://raw-data/^TNX_1h.parquet')
        WHERE close IS NOT NULL AND close > 0
    )
    SELECT
        COALESCE(dxy.date, vix.date, tnx.date) AS date,
        dxy.dxy_close,
        vix.vix_close,
        tnx.tnx_close
    FROM dxy
    FULL OUTER JOIN vix ON dxy.date = vix.date
    FULL OUTER JOIN tnx ON dxy.date = tnx.date
    ORDER BY date
""")

cnt = conn.execute("SELECT COUNT(*) FROM macro_features_1h").fetchone()[0]
sample = conn.execute("SELECT MIN(date), MAX(date) FROM macro_features_1h").fetchone()
print(f"Rows in macro_features_1h : {cnt}")
print(f"Date range                : {sample[0]} -> {sample[1]}")

print("\nSample rows:")
print(conn.execute("SELECT * FROM macro_features_1h LIMIT 5").df().to_string())

nulls = conn.execute("""
    SELECT
        COUNT(*) FILTER (WHERE dxy_close IS NULL) AS dxy_nulls,
        COUNT(*) FILTER (WHERE vix_close IS NULL) AS vix_nulls,
        COUNT(*) FILTER (WHERE tnx_close IS NULL) AS tnx_nulls
    FROM macro_features_1h
""").fetchone()
print(f"\nNull check -> DXY: {nulls[0]}, VIX: {nulls[1]}, TNX: {nulls[2]}")

conn.close()
print("\nDone! macro_features_1h is ready in DuckDB.")
