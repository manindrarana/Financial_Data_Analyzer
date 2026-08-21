import sqlite3
import time
from datetime import datetime, timedelta

import duckdb

from src.utils.pipeline_audit import (
    connect_audit_db,
    insert_pipeline_run,
    migrate_pipeline_runs,
    update_pipeline_run,
)


PIPELINE_RUN_SCHEMA = """
CREATE TABLE pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds DOUBLE,
    status VARCHAR,
    trigger VARCHAR,
    error_message VARCHAR,
    models_retrained VARCHAR,
    rows_fetched INTEGER,
    rows_cleaned INTEGER,
    validator_failures INTEGER,
    checkpoint_resumed BOOLEAN
)
"""


def test_connect_audit_db_creates_wal_database_and_table(tmp_path):
    db_path = tmp_path / "database" / "pipeline_history.sqlite3"

    conn = connect_audit_db(str(db_path))
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'pipeline_runs'"
    ).fetchone()
    conn.close()

    assert db_path.exists()
    assert journal_mode == "wal"
    assert table == ("pipeline_runs",)


def test_insert_and_update_pipeline_run_save_known_values(tmp_path):
    db_path = str(tmp_path / "pipeline_history.sqlite3")
    start_time = datetime(2026, 8, 21, 8, 20, 0)
    insert_pipeline_run(
        db_path,
        (
            "run_1",
            start_time,
            None,
            None,
            "running",
            "manual",
            None,
            None,
            None,
            None,
            0,
            1,
        ),
    )

    update_pipeline_run(
        db_path,
        "run_1",
        "success",
        None,
        {
            "models_retrained": ["BTC_1h", "ETH_4h"],
            "rows_fetched": 120,
            "rows_cleaned": 115,
            "validator_failures": 2,
        },
        datetime.now() - timedelta(seconds=5),
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT status, models_retrained, rows_fetched, rows_cleaned,
               validator_failures, checkpoint_resumed, duration_seconds
        FROM pipeline_runs
        WHERE run_id = 'run_1'
        """
    ).fetchone()
    conn.close()

    assert row[:6] == ("success", "BTC_1h,ETH_4h", 120, 115, 2, 1)
    assert 4.0 <= row[6] <= 6.0


def test_update_pipeline_run_accepts_production_float_start_time(tmp_path):
    db_path = str(tmp_path / "pipeline_history.sqlite3")
    insert_pipeline_run(
        db_path,
        (
            "run_float",
            datetime.now(),
            None,
            None,
            "running",
            "cron",
            None,
            None,
            None,
            None,
            0,
            False,
        ),
    )

    update_pipeline_run(
        db_path,
        "run_float",
        "success",
        None,
        {"rows_fetched": 10, "rows_cleaned": 9},
        time.time() - 3,
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, rows_fetched, rows_cleaned, duration_seconds FROM pipeline_runs"
    ).fetchone()
    conn.close()

    assert row[:3] == ("success", 10, 9)
    assert 2.0 <= row[3] <= 4.0


def test_migrate_pipeline_runs_preserves_values_and_is_idempotent(tmp_path):
    duckdb_path = str(tmp_path / "financial_data.duckdb")
    audit_db_path = str(tmp_path / "pipeline_history.sqlite3")
    source = duckdb.connect(duckdb_path)
    source.execute(PIPELINE_RUN_SCHEMA)
    source.execute(
        """
        INSERT INTO pipeline_runs VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "run_success",
            datetime(2026, 8, 20, 8, 0, 0),
            datetime(2026, 8, 20, 8, 5, 0),
            300.0,
            "success",
            "cron",
            None,
            "BTC_1h",
            100,
            95,
            0,
            False,
            "run_skipped",
            datetime(2026, 8, 20, 8, 1, 0),
            datetime(2026, 8, 20, 8, 1, 0),
            0.0,
            "skipped",
            "manual",
            "Pipeline run skipped because another run is active (PID 69).",
            None,
            None,
            None,
            0,
            True,
        ],
    )
    source.close()

    first_count = migrate_pipeline_runs(duckdb_path, audit_db_path)
    second_count = migrate_pipeline_runs(duckdb_path, audit_db_path)

    conn = sqlite3.connect(audit_db_path)
    rows = conn.execute(
        """
        SELECT run_id, status, duration_seconds, error_message,
               models_retrained, rows_fetched, rows_cleaned,
               validator_failures, checkpoint_resumed
        FROM pipeline_runs
        ORDER BY run_id
        """
    ).fetchall()
    conn.close()

    assert first_count == 2
    assert second_count == 0
    assert rows == [
        (
            "run_skipped",
            "skipped",
            0.0,
            "Pipeline run skipped because another run is active (PID 69).",
            None,
            None,
            None,
            0,
            1,
        ),
        ("run_success", "success", 300.0, None, "BTC_1h", 100, 95, 0, 0),
    ]


def test_new_skipped_run_does_not_require_duckdb_access(tmp_path):
    duckdb_path = str(tmp_path / "financial_data.duckdb")
    audit_db_path = str(tmp_path / "pipeline_history.sqlite3")
    locked_source = duckdb.connect(duckdb_path)
    locked_source.execute(PIPELINE_RUN_SCHEMA)
    locked_source.execute("BEGIN TRANSACTION")
    locked_source.execute(
        """
        INSERT INTO pipeline_runs VALUES
        ('active', CURRENT_TIMESTAMP, NULL, NULL, 'running', 'manual',
         NULL, NULL, NULL, NULL, 0, FALSE)
        """
    )

    reason = "Pipeline run skipped because another run is active (PID 69)."
    insert_pipeline_run(
        audit_db_path,
        (
            "run_skipped",
            datetime(2026, 8, 21, 8, 20, 15),
            datetime(2026, 8, 21, 8, 20, 15),
            0.0,
            "skipped",
            "manual",
            reason,
            None,
            None,
            None,
            0,
            False,
        ),
    )

    conn = sqlite3.connect(audit_db_path)
    row = conn.execute(
        "SELECT status, error_message, duration_seconds FROM pipeline_runs"
    ).fetchone()
    conn.close()
    locked_source.rollback()
    locked_source.close()

    assert row == ("skipped", reason, 0.0)
