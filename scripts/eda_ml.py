import subprocess
import pandas as pd

sql_query = """
SELECT 
    asset_symbol,
    asset_class,
    interval,
    COUNT(*) as sample_count,
    MIN(date) as first_date,
    MAX(date) as last_date
FROM gold_ml_features
GROUP BY asset_symbol, asset_class, interval
ORDER BY sample_count DESC
"""

docker_python_code = f"""
import duckdb
conn = duckdb.connect('/app/database/financial_data.duckdb', read_only=True)
data = conn.execute('''{sql_query}''').df()
print(data.to_json(orient='records'))
conn.close()
"""

output = subprocess.run(
    ['docker', 'exec', 'financial_data_pipeline', 'python3', '-c', docker_python_code],
    capture_output=True,
    text=True
)

if output.returncode == 0:
    df_volumes = pd.read_json(output.stdout)
    print("DATA VOLUME BY ASSET-INTERVAL:")
    print("=" * 100)
    print(df_volumes)
    print(f"\nTotal combinations: {len(df_volumes)}")
    print(f"Total rows: {df_volumes['sample_count'].sum():,}")
else:
    print("Error:", output.stderr)