import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime

import duckdb


PIPELINE_RUN_COLUMNS = (
    "run_id",
    "start_time",
    "end_time",
    "duration_seconds",
    "status",
    "trigger",
    "error_message",
    "models_retrained",
    "rows_fetched",
    "rows_cleaned",
    "validator_failures",
    "checkpoint_resumed",
)


def connect_audit_db(db_path):
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration_seconds REAL,
            status TEXT,
            trigger TEXT,
            error_message TEXT,
            models_retrained TEXT,
            rows_fetched INTEGER,
            rows_cleaned INTEGER,
            validator_failures INTEGER,
            checkpoint_resumed INTEGER
        )
        """
    )
    conn.commit()
    return conn


def insert_pipeline_run(db_path, values):
    placeholders = ", ".join("?" for _ in PIPELINE_RUN_COLUMNS)
    columns = ", ".join(PIPELINE_RUN_COLUMNS)
    with closing(connect_audit_db(db_path)) as conn:
        conn.execute(
            f"INSERT INTO pipeline_runs ({columns}) VALUES ({placeholders})",
            values,
        )
        conn.commit()


def update_pipeline_run(db_path, run_id, status, error_message, stats, run_start):
    end_time = datetime.now()
    if isinstance(run_start, datetime):
        duration = (end_time - run_start).total_seconds()
    else:
        duration = time.time() - run_start
    models = stats.get("models_retrained") or []
    models_str = ",".join(models) if models else None
    with closing(connect_audit_db(db_path)) as conn:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET end_time = ?, duration_seconds = ?, status = ?,
                error_message = ?, models_retrained = ?, rows_fetched = ?,
                rows_cleaned = ?, validator_failures = ?
            WHERE run_id = ?
            """,
            (
                end_time,
                duration,
                status,
                error_message,
                models_str,
                stats.get("rows_fetched"),
                stats.get("rows_cleaned"),
                stats.get("validator_failures", 0),
                run_id,
            ),
        )
        conn.commit()


def migrate_pipeline_runs(duckdb_path, audit_db_path):
    if not os.path.exists(duckdb_path):
        return 0

    source = duckdb.connect(duckdb_path, read_only=True)
    try:
        table_exists = source.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'pipeline_runs'
            """
        ).fetchone()[0]
        if not table_exists:
            return 0
        columns = ", ".join(PIPELINE_RUN_COLUMNS)
        rows = source.execute(f"SELECT {columns} FROM pipeline_runs").fetchall()
    finally:
        source.close()

    if not rows:
        return 0

    placeholders = ", ".join("?" for _ in PIPELINE_RUN_COLUMNS)
    columns = ", ".join(PIPELINE_RUN_COLUMNS)
    with closing(connect_audit_db(audit_db_path)) as conn:
        before = conn.total_changes
        conn.executemany(
            f"INSERT OR IGNORE INTO pipeline_runs ({columns}) VALUES ({placeholders})",
            rows,
        )
        conn.commit()
        return conn.total_changes - before
