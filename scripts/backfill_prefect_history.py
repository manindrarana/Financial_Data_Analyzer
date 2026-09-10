import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import get_logger
from src.utils.pipeline_audit import get_prefect_api_url

FLOW_NAME = "financial-data-pipeline"
OLD_DB_FILE = "prefect_old_backup.db"
MAP_FILE = "prefect_backfill_map.json"


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def to_prefect_ts(value):
    if not value:
        return None
    ts = value.replace(" ", "T")
    if ts.endswith("Z") or "+" in ts[10:]:
        return ts
    return ts + "+00:00"


def parse_duration(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace(" ", "T"))
        return round((dt - datetime(1970, 1, 1)).total_seconds(), 6)
    except ValueError:
        return None


def parse_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def api_post(url, payload):
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def api_patch(url, payload):
    response = requests.patch(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def resolve_targets(api_url):
    flows = api_post(api_url + "/flows/filter", {"limit": 100})
    flow_id = next((f["id"] for f in flows if f["name"] == FLOW_NAME), None)
    deployments = api_post(api_url + "/deployments/filter", {"limit": 100})
    deployment = next((d for d in deployments if d["name"] == FLOW_NAME), None)
    return flow_id, deployment


def load_old_runs(db_path):
    conn = sqlite3.connect("file:{}?mode=ro".format(db_path.replace("\\", "/")), uri=True)
    try:
        rows = conn.execute(
            """
            SELECT fr.id, fr.name, fr.state_type, fr.state_name, fr.state_timestamp,
                   fr.expected_start_time, fr.start_time, fr.end_time, fr.total_run_time,
                   fr.parameters, fr.tags, fr.flow_version, frs.message
            FROM flow_run fr
            LEFT JOIN flow_run_state frs ON fr.state_id = frs.id
            ORDER BY fr.created ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


def backfill_runs(api_url, db_path, map_path, flow_id, deployment_id):
    done = {}
    if os.path.exists(map_path):
        with open(map_path, "r") as f:
            done = json.load(f)

    rows = load_old_runs(db_path)
    inserted = 0
    skipped = 0
    failed = 0
    states = Counter()

    for row in rows:
        (old_id, name, state_type, state_name, state_timestamp,
         expected_start_time, start_time, end_time, total_run_time,
         parameters, tags, flow_version, message) = row

        if old_id in done:
            skipped += 1
            continue

        payload = {
            "flow_id": flow_id,
            "name": name,
            "expected_start_time": to_prefect_ts(expected_start_time) or to_prefect_ts(state_timestamp),
            "parameters": parse_json(parameters, {}),
            "tags": parse_json(tags, []),
            "state": {
                "type": state_type,
                "name": state_name or state_type.title(),
                "timestamp": to_prefect_ts(state_timestamp) or to_prefect_ts(expected_start_time),
                "message": message,
            },
        }
        if deployment_id:
            payload["deployment_id"] = deployment_id
        if flow_version:
            payload["flow_version"] = flow_version

        try:
            created = api_post(api_url + "/flow_runs/", payload)
            new_id = created["id"]
            patch = {}
            if start_time:
                patch["start_time"] = to_prefect_ts(start_time)
            if end_time:
                patch["end_time"] = to_prefect_ts(end_time)
            duration = parse_duration(total_run_time)
            if duration is not None:
                patch["total_run_time"] = duration
            if patch:
                api_patch("{}/flow_runs/{}".format(api_url, new_id), patch)
            done[old_id] = new_id
            inserted += 1
            states[state_type] += 1
            with open(map_path, "w") as f:
                json.dump(done, f, indent=2)
        except Exception as exc:
            failed += 1
            print("failed to backfill run {} ({}): {}".format(old_id, name, exc))

    return inserted, skipped, failed, states


def ensure_schedule_active(api_url, deployment):
    if not deployment:
        return "no deployment found"
    schedules = deployment.get("schedules") or []
    if not any(not s.get("active") for s in schedules):
        return "schedule already active"
    response = requests.post(
        "{}/deployments/{}/set_schedule_active".format(api_url, deployment["id"]),
        timeout=30,
    )
    response.raise_for_status()
    return "schedule reactivated"


def main():
    logger = get_logger("PrefectHistoryBackfill")
    api_url = get_prefect_api_url()
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo_root(), "database", OLD_DB_FILE)
    map_path = os.path.join(repo_root(), "database", MAP_FILE)

    if not os.path.exists(db_path):
        logger.info("Old Prefect database not found at {}".format(db_path))
        return

    flow_id, deployment = resolve_targets(api_url)
    if not flow_id:
        logger.info("Flow {} not found on the Prefect server".format(FLOW_NAME))
        return

    inserted, skipped, failed, states = backfill_runs(
        api_url, db_path, map_path, flow_id, deployment["id"] if deployment else None
    )
    logger.info(
        "Backfilled {} run(s), skipped {} already-mapped run(s), {} failure(s): {}".format(
            inserted, skipped, failed, dict(states)
        )
    )
    logger.info(ensure_schedule_active(api_url, deployment))


if __name__ == "__main__":
    main()
