import pandas as pd
import duckdb
import yaml
import os
from src.utils import get_logger

logger = get_logger("HealthCheck")


def get_db_connection():
    """Loads config and returns the DuckDB connection."""
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    
    db_path = config["paths"]["database"]
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}!")
        return None
        
    return duckdb.connect(db_path, read_only=True)


class DataHealthScanner:
    def __init__(self):
        """Initializes the scanner with its database connection and configuration."""
        self.conn = get_db_connection()
        self.logger = get_logger(__name__)
        
    def get_assets_to_check(self, table_name, symbol_col):
        """Fetches unique symbols and intervals from a table."""
        if not self.conn:
            return pd.DataFrame()
            
        return self.conn.execute(f"SELECT DISTINCT {symbol_col}, interval FROM {table_name}").df()


    def _calculate_gaps(self, df, symbol, interval):
        """Engine to compare actual vs. ideal timestamps."""
        if df.empty:
            return {"Symbol": symbol, "Interval": interval, "Health": "No Data Found"}

        freq_map = {
            '1h': 'H', '60': 'H', 
            '1d': 'D', 'D': 'D',
            '1wk': 'W', 'W': 'W',
            '1mo': 'M', 'M': 'ME'
        }
        freq = freq_map.get(str(interval), 'D')

        
        start, end = df['date'].min(), df['date'].max()
        ideal_timeline = pd.date_range(start=start, end=end, freq=freq)
        
        actual_dates = set(df['date'])
        missing = [d for d in ideal_timeline if d not in actual_dates]
        
        if missing:
            self.logger.warning(f"GAP DETECTED: {symbol} [{interval}] is missing {len(missing)} points")
            sample = [d.strftime('%Y-%m-%d %H:%M') for d in missing[:5]]
            self.logger.warning(f"First few gaps found at: {', '.join(sample)}")

        completeness = (len(df) / len(ideal_timeline)) * 100 if len(ideal_timeline) > 0 else 0

        
        return {
            "Symbol": symbol,
            "Interval": interval,
            "Total Rows": len(df),
            "Gap Count": len(missing),
            "Completeness": f"{completeness:.2f}%"
        }

    def check_gold_layer(self):
        """Continuity scan for the final gold_ml_features layer."""
        self.logger.info("Initializing scan for Gold Layer (gold_ml_features)...")
        assets = self.get_assets_to_check("gold_ml_features", "asset_symbol")
        all_results = []

        for _, row in assets.iterrows():
            symbol, interval = row['asset_symbol'], row['interval']
            
            df = self.conn.execute(f"""
                SELECT date FROM gold_ml_features 
                WHERE asset_symbol = '{symbol}' AND interval = '{interval}'
                ORDER BY date
            """).df()

            stats = self._calculate_gaps(df, symbol, interval)
            all_results.append(stats)
            
        return pd.DataFrame(all_results)

    def check_yahoo_silver(self):
        """Scans the clean_yahoo_stocks table for gaps."""
        self.logger.info("Scanning Yahoo Silver Layer (clean_yahoo_stocks)...")
        assets = self.get_assets_to_check("clean_yahoo_stocks", "ticker")
        
        results = []
        for _, row in assets.iterrows():
            symbol, interval = row['ticker'], row['interval']
            df = self.conn.execute(f"SELECT date FROM clean_yahoo_stocks WHERE ticker = '{symbol}' AND interval = '{interval}' ORDER BY date").df()
            
            stats = self._calculate_gaps(df, f"Yahoo_{symbol}", interval)
            results.append(stats)
            
        return pd.DataFrame(results)

    def check_bybit_silver(self):
        """Scans the clean_bybit_crypto table for gaps."""
        self.logger.info("Scanning Bybit Silver Layer (clean_bybit_crypto)...")
        assets = self.get_assets_to_check("clean_bybit_crypto", "symbol")
        
        results = []
        for _, row in assets.iterrows():
            symbol, interval = row['symbol'], row['interval']
            df = self.conn.execute(f"SELECT date FROM clean_bybit_crypto WHERE symbol = '{symbol}' AND interval = '{interval}' ORDER BY date").df()
            
            stats = self._calculate_gaps(df, f"Bybit_{symbol}", interval)
            results.append(stats)
            
        return pd.DataFrame(results)

    def run(self):
        """Orchestrates all checks and displays a unified report."""
        self.logger.info("*" * 60)
        self.logger.info("STARTING FULL DATA CONTINUITY HEALTH CHECK")
        self.logger.info("*" * 60)
        
        yahoo_results = self.check_yahoo_silver()
        bybit_results = self.check_bybit_silver()
        gold_results = self.check_gold_layer()

        all_checks = pd.concat([yahoo_results, bybit_results, gold_results], ignore_index=True)
        
        print("\n" + "="*80)
        print("DATA PIPELINE CONTINUITY REPORT")
        print("="*80)
        print(all_checks.to_string(index=False))
        print("="*80)
        print(f"Total Assets Checked: {len(all_checks)}")
        print("*" * 60)

    def close(self):
        """Closes the DuckDB connection."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.logger.info("DuckDB connection closed safely.")

if __name__ == "__main__":
    scanner = DataHealthScanner()
    try:
        scanner.run()
    finally:
        scanner.close()
    