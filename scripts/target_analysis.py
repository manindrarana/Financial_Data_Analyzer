import subprocess
import pandas as pd

PIPELINE_CONTAINER = "financial_data_pipeline"

sql_query = """
SELECT
    COUNT(*) as total_samples,
    AVG(returns_1p) as mean_return,
    STDDEV(returns_1p) as std_return,
    MIN(returns_1p) as min_return,
    MAX(returns_1p) as max_return,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY returns_1p) as q25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY returns_1p) as median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY returns_1p) as q75
FROM (
    SELECT returns_1p, interval FROM gold_crypto_features
    UNION ALL
    SELECT returns_1p, interval FROM gold_stock_features
)
WHERE interval IN ('1d', '1h')
"""

docker_python_code = f"""
import duckdb
conn = duckdb.connect('/app/database/financial_data.duckdb', read_only=True)
data = conn.execute('''{sql_query}''').df()
print(data.to_json(orient='records'))
conn.close()
"""

output = subprocess.run(
    ['docker', 'exec', PIPELINE_CONTAINER, 'python3', '-c', docker_python_code],
    capture_output=True,
    text=True
)

if output.returncode == 0:
    df_target = pd.read_json(output.stdout)
    print("TARGET VARIABLE (returns_1d) STATS:")
    print("=" * 80)
    for col in df_target.columns:
        print(f"{col:20s}: {df_target[col].iloc[0]:.6f}")
else:
    print("Error:", output.stderr)