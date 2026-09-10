import asyncio
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone

import requests

import asyncpg

FLOW_NAME = "financial-data-pipeline"
DEFAULT_API_URL = "http://localhost:4200/api"
DEFAULT_OLD_DB = "/root/.prefect/prefect.db"


def to_dt(value):
    if not value:
        return None
    ts = value.replace(" ", "T")
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


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


def resolve_targets(api_url):
    flows = api_post(api_url + "/flows/filter", {"limit": 100})
    flow_id = next((f["id"] for f in flows if f["name"] == FLOW_NAME), None)
    deployments = api_post(api_url + "/deployments/filter", {"limit": 100})
    deployment = next((d for d in deployments if d["name"] == FLOW_NAME), None)
    return flow_id, deployment


def load_old_runs(db_path):
    conn = sqlite3.connect("file:{}?mode=ro".format(db_path), uri=True)
    try:
        rows = conn.execute(
            """
            SELECT fr.id, fr.name, fr.state_type, fr.state_name, fr.state_timestamp,
                   fr.expected_start_time, fr.start_time, fr.end_time, fr.total_run_time,
                   fr.parameters, fr.tags, fr.flow_version, fr.created, frs.message
            FROM flow_run fr
            LEFT JOIN flow_run_state frs ON fr.state_id = frs.id
            WHERE fr.state_type IS NOT NULL AND fr.state_type != 'PENDING'
            ORDER BY fr.created ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


def existing_runs(api_url):
    runs = api_post(api_url + "/flow_runs/filter", {"flows": {"name": {"any_": [FLOW_NAME]}}, "limit": 200})
    return {r["name"]: r["id"] for r in runs}


def dsn_from_env():
    dsn = os.environ.get("PREFECT_API_DATABASE_CONNECTION_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return dsn


async def restore_timing(dsn, run_id, created, expected, start, end, duration, state_ts):
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE flow_run
                SET created = $2::timestamptz,
                    expected_start_time = COALESCE($3::timestamptz, $2::timestamptz),
                    start_time = $4::timestamptz, end_time = $5::timestamptz,
                    total_run_time = make_interval(secs => $6::double precision),
                    state_timestamp = $7::timestamptz, run_count = 1
                WHERE id = $1::uuid
                """,
                run_id, created, expected, start, end, duration, state_ts,
            )
            await conn.execute(
                """
                UPDATE flow_run_state
                SET timestamp = $2::timestamptz, created = $3::timestamptz
                WHERE flow_run_id = $1::uuid
                """,
                run_id, state_ts, created,
            )
    finally:
        await conn.close()


def main():
    api_url = DEFAULT_API_URL
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OLD_DB

    if not os.path.exists(db_path):
        print("Old Prefect database not found at {}".format(db_path))
        return
    dsn = dsn_from_env()
    if not dsn:
        print("PREFECT_API_DATABASE_CONNECTION_URL is not set")
        return

    flow_id, deployment = resolve_targets(api_url)
    if not flow_id:
        print("Flow {} not found on the Prefect server".format(FLOW_NAME))
        return
    deployment_id = deployment["id"] if deployment else None
    done_runs = existing_runs(api_url)

    rows = load_old_runs(db_path)
    inserted = 0
    repaired = 0
    failed = 0
    states = Counter()

    for row in rows:
        (old_id, name, state_type, state_name, state_timestamp,
         expected_start_time, start_time, end_time, total_run_time,
         parameters, tags, flow_version, created, message) = row

        try:
            if name in done_runs:
                new_id = done_runs[name]
            else:
                payload = {
                    "flow_id": flow_id,
                    "name": name,
                    "parameters": parse_json(parameters, {}),
                    "tags": parse_json(tags, []),
                    "state": {
                        "type": state_type,
                        "name": state_name or state_type.title(),
                        "message": message,
                    },
                }
                if deployment_id:
                    payload["deployment_id"] = deployment_id
                if flow_version:
                    payload["flow_version"] = flow_version
                created_run = api_post(api_url + "/flow_runs/", payload)
                new_id = created_run["id"]
                done_runs[name] = new_id
                inserted += 1

            asyncio.run(restore_timing(
                dsn,
                new_id,
                to_dt(created),
                to_dt(expected_start_time),
                to_dt(start_time),
                to_dt(end_time),
                parse_duration(total_run_time),
                to_dt(state_timestamp) or to_dt(created),
            ))
            repaired += 1
            states[state_type] += 1
        except Exception as exc:
            failed += 1
            print("failed to backfill run {} ({}): {}".format(old_id, name, exc))

    print("Created {} new run(s), restored timing on {} run(s), {} failure(s): {}".format(
        inserted, repaired, failed, dict(states)))

    if deployment:
        schedules = deployment.get("schedules") or []
        inactive = [s for s in schedules if not s.get("active")]
        for s in inactive:
            r = requests.patch(
                "{}/deployments/{}/schedules/{}".format(api_url, deployment["id"], s["id"]),
                json={"active": True}, timeout=30,
            )
            print("schedule {} reactivated: {}".format(s["id"], r.status_code))
        if not inactive and schedules:
            print("schedule already active")


if __name__ == "__main__":
    main()
