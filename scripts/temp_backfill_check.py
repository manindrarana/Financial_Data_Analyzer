import os
import requests
import sqlite3
from datetime import datetime, timezone


def parse(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


url = os.environ.get("PREFECT_API_URL", "http://prefect:4200/api") + "/flow_runs/filter"
runs = []
offset = 0
while True:
    response = requests.post(
        url,
        json={
            "sort": "START_TIME_DESC",
            "limit": 200,
            "offset": offset,
            "flows": {"name": {"any_": ["financial-data-pipeline"]}},
        },
        timeout=10,
    )
    page = response.json()
    runs.extend(page)
    if len(page) < 200:
        break
    offset += 200

conn = sqlite3.connect("/app/database/pipeline_history.sqlite3")
audit = conn.execute("SELECT run_id, start_time, status FROM pipeline_runs").fetchall()
conn.close()
audit_starts = [(row[0], parse(row[1]), row[2]) for row in audit]

terminal_states = ("COMPLETED", "FAILED", "CRASHED", "CANCELLED")
missing = []
for run in runs:
    state = (run.get("state") or {}).get("type")
    if state not in terminal_states:
        continue
    start = parse(run.get("start_time"))
    if start is None:
        continue
    matched = any(
        existing[1] is not None
        and abs((start - existing[1]).total_seconds()) <= 120
        for existing in audit_starts
    )
    if not matched:
        missing.append(
            (run.get("start_time"), state, (run.get("state") or {}).get("message"))
        )

terminal_count = sum(
    1 for run in runs if (run.get("state") or {}).get("type") in terminal_states
)
print("prefect terminal runs:", terminal_count)
print("audit rows:", len(audit_starts))

from collections import defaultdict

matches = defaultdict(list)
for run in runs:
    state = (run.get("state") or {}).get("type")
    if state not in terminal_states:
        continue
    start = parse(run.get("start_time"))
    if start is None:
        continue
    for existing in audit_starts:
        if existing[1] is not None and abs((start - existing[1]).total_seconds()) <= 120:
            matches[existing[0]].append((run.get("start_time"), state))
            break

shared = {k: v for k, v in matches.items() if len(v) > 1}
print("audit rows matching multiple prefect runs:", len(shared))
for run_id, prefect_entries in sorted(shared.items()):
    print(run_id, prefect_entries)

legacy = [a for a in audit_starts if a[1] is not None and a[1] < datetime(2026, 5, 1)]
print("audit rows before 2026-05-01 (pre-prefect legacy):", len(legacy))
for entry in legacy:
    print(entry)

non_completed = []
for run in runs:
    state = (run.get("state") or {}).get("type")
    if state not in ("FAILED", "CRASHED", "CANCELLED"):
        continue
    start = parse(run.get("start_time"))
    if start is None:
        continue
    matched_status = None
    for existing in audit_starts:
        if existing[1] is not None and abs((start - existing[1]).total_seconds()) <= 120:
            matched_status = (existing[0], existing[2])
            break
    non_completed.append((run.get("start_time"), state, matched_status))

print("non-completed prefect runs and their audit row status:")
for entry in sorted(non_completed):
    print(entry)
