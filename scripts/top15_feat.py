import duckdb
import subprocess
import pandas as pd

sql_query = """
SELECT 
    feature_name,
    importance_score,
    target_correlation,
    quality_flag
FROM gold_feature_statistics
WHERE quality_flag = 'PASS'
ORDER BY importance_score DESC
LIMIT 15
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
    df_top15 = pd.read_json(output.stdout)
    print("TOP 15 FEATURES FOR ML:")
    print("=" * 80)
    for idx, row in df_top15.iterrows():
        print(f"{idx+1:2d}. {row['feature_name']:20s} | Importance: {row['importance_score']:.4f} | Correlation: {row['target_correlation']:+.4f}")
    print(f"\nThese {len(df_top15)} features are validated and ready for ML!")
else:
    print("Error:", output.stderr)

