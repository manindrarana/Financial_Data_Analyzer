import duckdb
conn = duckdb.connect("database/financial_data.duckdb", read_only=True)
tables = [r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()]
print("pipeline_runs exists:", "pipeline_runs" in tables)
print("matching tables:", [t for t in tables if "pipeline" in t.lower() or "run" in t.lower()])
if "pipeline_runs" in tables:
    print("row count:", conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0])
    print("sample rows:")
    for row in conn.execute("SELECT run_id, status, start_time FROM pipeline_runs ORDER BY start_time DESC LIMIT 5").fetchall():
        print(" ", row)
conn.close()
