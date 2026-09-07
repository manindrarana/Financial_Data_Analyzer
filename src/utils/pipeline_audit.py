import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone

import duckdb
import requests


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

PREFECT_FLOW_NAME = "financial-data-pipeline"
DEFAULT_PREFECT_API_URL = "http://prefect:4200/api"
PREFECT_PAGE_SIZE = 200
PREFECT_MATCH_TOLERANCE_SECONDS = 120
TERMINAL_PREFECT_STATES = ("COMPLETED", "FAILED", "CRASHED", "CANCELLED")


def get_prefect_api_url():
    return os.environ.get("PREFECT_API_URL", DEFAULT_PREFECT_API_URL).rstrip("/")


def fetch_prefect_flow_runs(
    api_url=None,
    flow_name=PREFECT_FLOW_NAME,
    page_size=PREFECT_PAGE_SIZE,
    timeout=10,
):
    url = (api_url or get_prefect_api_url()) + "/flow_runs/filter"
    runs = []
    offset = 0
    while True:
        response = requests.post(
            url,
            json={
                "sort": "START_TIME_DESC",
                "limit": page_size,
                "offset": offset,
                "flows": {"name": {"any_": [flow_name]}},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        page = response.json()
        runs.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return runs


def parse_timestamp(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def normalize_prefect_run(run):
    state = run.get("state") or {}
    state_type = str(state.get("type") or run.get("state_type") or "").upper()
    start_time = parse_timestamp(run.get("start_time"))
    end_time = parse_timestamp(run.get("end_time"))
    if end_time is None:
        end_time = parse_timestamp(state.get("timestamp"))
    duration = run.get("total_run_time")
    if duration is None and start_time is not None and end_time is not None:
        duration = (end_time - start_time).total_seconds()
    return {
        "id": run.get("id"),
        "state_type": state_type,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration,
        "message": state.get("message"),
        "deployment_id": run.get("deployment_id"),
    }


def map_prefect_state(state_type, message=None):
    if state_type == "COMPLETED":
        return "success", None
    if state_type in ("FAILED", "CRASHED", "CANCELLED"):
        label = state_type.capitalize()
        error = f"Reconciled from Prefect state: {label}"
        if message:
            error = f"{error} ({str(message)[:400]})"
        return "failed", error[:500]
    return None, None


def _nearest_prefect_match(audit_start, available_runs):
    if audit_start is None:
        return None
    best_run = None
    best_delta = None
    for run in available_runs:
        run_start = run["start_time"]
        if run_start is None:
            continue
        delta = abs((run_start - audit_start).total_seconds())
        if delta <= PREFECT_MATCH_TOLERANCE_SECONDS and (
            best_delta is None or delta < best_delta
        ):
            best_run = run
            best_delta = delta
    return best_run


def reconcile_running_runs(audit_db_path, prefect_runs):
    normalized = [normalize_prefect_run(run) for run in prefect_runs]
    terminal = [
        run
        for run in normalized
        if run["state_type"] in TERMINAL_PREFECT_STATES
        and run["start_time"] is not None
    ]
    finalized = 0
    with closing(connect_audit_db(audit_db_path)) as conn:
        rows = conn.execute(
            "SELECT run_id, start_time FROM pipeline_runs WHERE status = 'running'"
        ).fetchall()
        pending = [
            {"run_id": row[0], "start_time": parse_timestamp(row[1])}
            for row in rows
        ]
        for audit_row in pending:
            match = _nearest_prefect_match(audit_row["start_time"], terminal)
            if match is None:
                continue
            terminal.remove(match)
            status, error_message = map_prefect_state(
                match["state_type"], match["message"]
            )
            duration = match["duration_seconds"]
            if duration is None:
                duration = 0.0
            conn.execute(
                """
                UPDATE pipeline_runs
                SET end_time = ?, duration_seconds = ?, status = ?,
                    error_message = ?
                WHERE run_id = ?
                """,
                (
                    match["end_time"],
                    duration,
                    status,
                    error_message,
                    audit_row["run_id"],
                ),
            )
            finalized += 1
        if finalized:
            conn.commit()
    return finalized


def backfill_pipeline_runs(audit_db_path, prefect_runs):
    normalized = [normalize_prefect_run(run) for run in prefect_runs]
    insertable = []
    for run in normalized:
        status, error_message = map_prefect_state(run["state_type"], run["message"])
        if status is None or run["start_time"] is None:
            continue
        insertable.append({**run, "status": status, "error_message": error_message})

    inserted = 0
    placeholders = ", ".join("?" for _ in PIPELINE_RUN_COLUMNS)
    columns = ", ".join(PIPELINE_RUN_COLUMNS)
    with closing(connect_audit_db(audit_db_path)) as conn:
        existing = conn.execute(
            "SELECT start_time FROM pipeline_runs"
        ).fetchall()
        existing_starts = [parse_timestamp(row[0]) for row in existing]
        for run in insertable:
            already_present = any(
                existing_start is not None
                and abs((run["start_time"] - existing_start).total_seconds())
                <= PREFECT_MATCH_TOLERANCE_SECONDS
                for existing_start in existing_starts
            )
            if already_present:
                continue
            run_id_suffix = str(run["id"] or "").replace("-", "")[:8] or "prefect"
            run_id = f"run_{run['start_time'].strftime('%Y%m%d_%H%M%S')}_{run_id_suffix}"
            trigger = "cron" if run["deployment_id"] else "manual"
            cursor = conn.execute(
                f"INSERT OR IGNORE INTO pipeline_runs ({columns}) VALUES ({placeholders})",
                (
                    run_id,
                    run["start_time"],
                    run["end_time"],
                    run["duration_seconds"],
                    run["status"],
                    trigger,
                    run["error_message"],
                    None,
                    None,
                    None,
                    0,
                    0,
                ),
            )
            inserted += cursor.rowcount
            existing_starts.append(run["start_time"])
        conn.commit()
    return inserted


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
