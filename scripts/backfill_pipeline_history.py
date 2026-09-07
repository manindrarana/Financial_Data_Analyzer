import os
import sqlite3
from collections import Counter

import yaml

from src.utils import get_logger
from src.utils.pipeline_audit import (
    backfill_pipeline_runs,
    fetch_prefect_flow_runs,
    normalize_prefect_run,
    reconcile_running_runs,
)

AUDIT_DB_NAME = "pipeline_history.sqlite3"


def get_audit_db_path():
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    return os.path.join(os.path.dirname(config["paths"]["database"]), AUDIT_DB_NAME)


def summarize_audit(db_path):
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM pipeline_runs GROUP BY status"
        ).fetchall()
    finally:
        conn.close()
    return dict(rows)


def main():
    logger = get_logger("PipelineHistoryBackfill")
    audit_db_path = get_audit_db_path()

    prefect_runs = fetch_prefect_flow_runs()
    prefect_states = Counter(
        normalize_prefect_run(run)["state_type"] for run in prefect_runs
    )
    logger.info(f"Fetched {len(prefect_runs)} Prefect flow runs: {dict(prefect_states)}")

    finalized = reconcile_running_runs(audit_db_path, prefect_runs)
    inserted = backfill_pipeline_runs(audit_db_path, prefect_runs)

    logger.info(f"Finalized {finalized} stale running run(s) from Prefect states")
    logger.info(f"Inserted {inserted} missing run(s) from Prefect history")
    logger.info(f"Audit totals by status: {summarize_audit(audit_db_path)}")


if __name__ == "__main__":
    main()
