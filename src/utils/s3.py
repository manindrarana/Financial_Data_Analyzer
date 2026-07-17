import os
import duckdb


def configure_s3_access(conn: duckdb.DuckDBPyConnection) -> None:
    s3_endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000").replace("http://", "")
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute(f"""
        CREATE SECRET IF NOT EXISTS (
            TYPE S3,
            KEY_ID '{os.getenv("AWS_ACCESS_KEY_ID")}',
            SECRET '{os.getenv("AWS_SECRET_ACCESS_KEY")}',
            ENDPOINT '{s3_endpoint}',
            URL_STYLE 'path',
            USE_SSL false
        );
    """)
