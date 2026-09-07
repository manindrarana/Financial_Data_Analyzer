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
print("unmatched prefect runs:", len(missing))
for entry in missing[:15]:
    print(entry)
