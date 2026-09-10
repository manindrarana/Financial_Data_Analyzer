import asyncio
import os
import sqlite3
import sys
import uuid
from collections import Counter, defaultdict
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


import json


def json_text(value):
    if value is None or value == "":
        return None
    return value


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


def load_flow_id_map(db_path):
    conn = sqlite3.connect("file:{}?mode=ro".format(db_path), uri=True)
    try:
        rows = conn.execute("SELECT id, name FROM flow_run").fetchall()
    finally:
        conn.close()
    return {name: old_id for old_id, name in rows}


def load_task_runs(db_path):
    conn = sqlite3.connect("file:{}?mode=ro".format(db_path), uri=True)
    try:
        rows = conn.execute(
            """
            SELECT id, created, updated, name, state_type, run_count,
                   expected_start_time, next_scheduled_start_time, start_time, end_time,
                   total_run_time, task_key, dynamic_key, cache_key, cache_expiration,
                   task_version, empirical_policy, task_inputs, tags, flow_run_id,
                   state_id, state_name, state_timestamp, flow_run_run_count, labels
            FROM task_run ORDER BY created ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


def load_task_states(db_path):
    conn = sqlite3.connect("file:{}?mode=ro".format(db_path), uri=True)
    try:
        rows = conn.execute(
            """
            SELECT id, created, updated, type, timestamp, name, message,
                   state_details, data, task_run_id, result_artifact_id
            FROM task_run_state ORDER BY created ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


def load_logs(db_path):
    conn = sqlite3.connect("file:{}?mode=ro".format(db_path), uri=True)
    try:
        rows = conn.execute(
            """
            SELECT id, created, updated, name, level, flow_run_id, task_run_id, message, timestamp
            FROM log ORDER BY created ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


async def copy_details(dsn, db_path, flow_map):
    tasks = load_task_runs(db_path)
    states = load_task_states(db_path)
    logs = load_logs(db_path)
    states_by_task = defaultdict(list)
    for s in states:
        states_by_task[s[9]].append(s)

    conn = await asyncpg.connect(dsn)
    try:
        existing_tasks = {
            (r[0], r[1], r[2])
            for r in await conn.fetch("SELECT flow_run_id, task_key, dynamic_key FROM task_run")
        }
        done_log_flows = {r[0] for r in await conn.fetch("SELECT DISTINCT flow_run_id FROM log")}
        task_map = {}
        copied_tasks = 0
        copied_states = 0
        copied_logs = 0
        skipped_tasks = 0

        for t in tasks:
            (t_id, t_created, t_updated, t_name, t_state_type, t_run_count,
             t_expected, t_next, t_start, t_end, t_total, t_key, t_dynamic,
             t_cache_key, t_cache_exp, t_version, t_policy, t_inputs, t_tags,
             t_flow_id, t_state_id, t_state_name, t_state_ts, t_run_count2, t_labels) = t

            new_flow_id = flow_map.get(t_flow_id)
            if new_flow_id is None:
                continue
            if (new_flow_id, t_key, t_dynamic) in existing_tasks:
                skipped_tasks += 1
                continue

            new_task_id = str(uuid.uuid4())
            task_map[t_id] = new_task_id
            try:
                await conn.execute(
                    """
                    INSERT INTO task_run
                    (id, created, updated, name, state_type, run_count,
                     expected_start_time, next_scheduled_start_time, start_time, end_time,
                     total_run_time, task_key, dynamic_key, cache_key, cache_expiration,
                     task_version, empirical_policy, task_inputs, tags, flow_run_id,
                     state_id, state_name, state_timestamp, flow_run_run_count, labels)
                    VALUES ($1::uuid, $2::timestamptz, $3::timestamptz, $4, $5::state_type, $6::int,
                            $7::timestamptz, $8::timestamptz, $9::timestamptz, $10::timestamptz,
                            make_interval(secs => $11::double precision), $12, $13, $14, $15::timestamptz,
                            $16, $17::jsonb, $18::jsonb, $19::jsonb, $20::uuid,
                            NULL, $21, $22::timestamptz, $23::int, $24::jsonb)
                    """,
                    new_task_id, to_dt(t_created), to_dt(t_updated), t_name,
                    t_state_type, t_run_count, to_dt(t_expected), to_dt(t_next),
                    to_dt(t_start), to_dt(t_end), parse_duration(t_total), t_key,
                    t_dynamic, t_cache_key, to_dt(t_cache_exp), t_version,
                    json_text(t_policy), json_text(t_inputs), json_text(t_tags),
                    new_flow_id, t_state_name, to_dt(t_state_ts), t_run_count2,
                    json_text(t_labels),
                )
                copied_tasks += 1
            except Exception as exc:
                print("failed to copy task run {} ({}): {}".format(t_id, t_name, exc))
                continue

            new_state_id = None
            for s in states_by_task.get(t_id, []):
                (s_id, s_created, s_updated, s_type, s_ts, s_name, s_message,
                 s_details, s_data, s_task_id, s_artifact) = s
                new_s_id = str(uuid.uuid4())
                if t_state_id == s_id:
                    new_state_id = new_s_id
                try:
                    await conn.execute(
                        """
                        INSERT INTO task_run_state
                        (id, created, updated, type, timestamp, name, message,
                         state_details, data, task_run_id, result_artifact_id)
                        VALUES ($1::uuid, $2::timestamptz, $3::timestamptz, $4::state_type,
                                $5::timestamptz, $6, $7, $8::jsonb, $9::jsonb,
                                $10::uuid, $11::uuid)
                        """,
                        new_s_id, to_dt(s_created), to_dt(s_updated), s_type,
                        to_dt(s_ts), s_name, s_message, json_text(s_details),
                        json_text(s_data), new_task_id, s_artifact,
                    )
                    copied_states += 1
                except Exception as exc:
                    print("failed to copy task run state {} ({}): {}".format(s_id, s_name, exc))

            if new_state_id is not None:
                await conn.execute(
                    "UPDATE task_run SET state_id = $1::uuid WHERE id = $2::uuid",
                    new_state_id, new_task_id,
                )

        log_rows = []
        for l in logs:
            (l_id, l_created, l_updated, l_name, l_level, l_flow_id, l_task_id,
             l_message, l_ts) = l
            new_flow_id = flow_map.get(l_flow_id)
            if new_flow_id is None:
                continue
            if new_flow_id in done_log_flows:
                continue
            new_task_id = task_map.get(l_task_id)
            log_rows.append((
                str(uuid.uuid4()), to_dt(l_created), to_dt(l_updated), l_name,
                l_level, new_flow_id, new_task_id, l_message, to_dt(l_ts),
            ))
        if log_rows:
            await conn.executemany(
                """
                INSERT INTO log
                (id, created, updated, name, level, flow_run_id, task_run_id, message, timestamp)
                VALUES ($1::uuid, $2::timestamptz, $3::timestamptz, $4, $5::int,
                        $6::uuid, $7::uuid, $8, $9::timestamptz)
                """,
                log_rows,
            )
            copied_logs = len(log_rows)

        return copied_tasks, copied_states, copied_logs, skipped_tasks
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
    flow_map = {}

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

            flow_map[old_id] = new_id
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

    copied_tasks, copied_states, copied_logs, skipped_tasks = asyncio.run(
        copy_details(dsn, db_path, flow_map))
    print("Copied {} task run(s), {} state(s), {} log line(s), skipped {} existing task run(s)".format(
        copied_tasks, copied_states, copied_logs, skipped_tasks))

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
