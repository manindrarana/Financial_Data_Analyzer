import os
import duckdb
import pandas as pd
from typing import Optional, List

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database",
    "financial_data.duckdb",
)


def get_pipeline_runs(limit: int = 50) -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(columns=[
            "run_id", "start_time", "end_time", "duration_seconds",
            "status", "trigger", "error_message", "models_retrained",
            "rows_fetched", "rows_cleaned", "validator_failures",
            "checkpoint_resumed",
        ])

    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        try:
            df = conn.execute(
                """
                SELECT run_id, start_time, end_time, duration_seconds,
                       status, trigger, error_message, models_retrained,
                       rows_fetched, rows_cleaned, validator_failures,
                       checkpoint_resumed
                FROM pipeline_runs
                ORDER BY start_time DESC
                LIMIT ?
                """,
                [limit],
            ).df()
        except Exception:
            return pd.DataFrame(columns=[
                "run_id", "start_time", "end_time", "duration_seconds",
                "status", "trigger", "error_message", "models_retrained",
                "rows_fetched", "rows_cleaned", "validator_failures",
                "checkpoint_resumed",
            ])
        return df
    finally:
        conn.close()


def get_run_summary() -> dict:
    if not os.path.exists(DB_PATH):
        return {
            "total": 0, "success": 0, "failed": 0, "running": 0,
            "success_rate": 0.0, "last_status": "none", "last_error": None,
        }

    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        try:
            total = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        except Exception:
            return {
                "total": 0, "success": 0, "failed": 0, "running": 0,
                "success_rate": 0.0, "last_status": "none", "last_error": None,
            }

        if total == 0:
            return {
                "total": 0, "success": 0, "failed": 0, "running": 0,
                "success_rate": 0.0, "last_status": "none", "last_error": None,
            }

        success = conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'success'"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'failed'"
        ).fetchone()[0]
        running = conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'running'"
        ).fetchone()[0]

        last_row = conn.execute(
            """
            SELECT status, error_message
            FROM pipeline_runs
            ORDER BY start_time DESC
            LIMIT 1
            """
        ).fetchone()
        last_status = last_row[0] if last_row else "none"
        last_error = last_row[1] if last_row else None

        finished = success + failed
        success_rate = (success / finished * 100.0) if finished > 0 else 0.0

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "running": running,
            "success_rate": round(success_rate, 1),
            "last_status": last_status,
            "last_error": last_error,
        }
    finally:
        conn.close()
