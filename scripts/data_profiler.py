import pandas as pd
import duckdb
import yaml
import os
from src.utils import get_logger

logger = get_logger("DataProfiler")

def get_db_connection():
    """Shared logic to connect to the Medallion DuckDB."""
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    db_path = config["paths"]["database"]
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}!")
        return None
        
    return duckdb.connect(db_path, read_only=True)

class DataProfiler:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = logger

    def get_tickers(self, table_name, symbol_col):
        """Discovers all unique symbols in a specific table."""
        if not self.conn:
            return []
        df = self.conn.execute(f"SELECT DISTINCT {symbol_col} FROM {table_name}").df()
        return df[symbol_col].tolist()

    def calculate_returns(self, df):
        """Calculates Daily and Percentage returns for a specific asset dataframe."""
        if df.empty or 'close' not in df.columns:
            return pd.DataFrame()
        
        df = df.sort_values('date').copy()
        df['prev_close'] = df['close'].shift(1)
        df['change_pct'] = ((df['close'] - df['prev_close']) / df['prev_close']) * 100
        return df.dropna(subset=['change_pct'])
    
    def find_top_gainers(self, table_name, symbol_col, limit=10):
        """Finds the biggest single-day gains in the specified table."""
        self.logger.info(f"Finding top performers in {table_name}...")
        tickers = self.get_tickers(table_name, symbol_col)
        
        all_results = []
        for t in tickers:
            df = self.conn.execute(f"SELECT date, {symbol_col}, close FROM {table_name} WHERE {symbol_col} = '{t}' ORDER BY date").df()
            df_returns = self.calculate_returns(df)
            all_results.append(df_returns)
            
        if not all_results:
            return pd.DataFrame()
            
        master_df = pd.concat(all_results, ignore_index=True)
        return master_df.sort_values('change_pct', ascending=False).head(limit)
    
    def find_top_losers(self, table_name, symbol_col, limit=10):
        """Finds the biggest single-day drops across the collection."""
        self.logger.info(f"Finding top losers in {table_name}...")
        tickers = self.get_tickers(table_name, symbol_col)
        
        all_results = []
        for t in tickers:
            df = self.conn.execute(f"SELECT date, {symbol_col}, close FROM {table_name} WHERE {symbol_col}='{t}' ORDER BY date").df()
            df_returns = self.calculate_returns(df)
            all_results.append(df_returns)
            
        if not all_results:
            return pd.DataFrame()
            
        master_df = pd.concat(all_results, ignore_index=True)
        return master_df.sort_values('change_pct', ascending=True).head(limit)

    def volatility_scan(self, table_name, symbol_col):
        """Calculates standard deviation of returns for each asset to find high-risk tickers."""
        self.logger.info(f"Scanning risk profiles in {table_name}...")
        tickers = self.get_tickers(table_name, symbol_col)
        
        risk_results = []
        for t in tickers:
            df = self.conn.execute(f"SELECT date, {symbol_col}, close FROM {table_name} WHERE {symbol_col}='{t}' ORDER BY date").df()
            df_returns = self.calculate_returns(df)
            if not df_returns.empty:
                vol = df_returns['change_pct'].std()
                risk_results.append({symbol_col: t, "Volatility": f"{vol:.2f}%"})
        
        return pd.DataFrame(risk_results).sort_values('Volatility', ascending=False)
    
    def anomaly_detector(self, table_name):
        """Finds any clearly broken or impossible data rows (price <= 0 or volume < 0)."""
        self.logger.info(f"Checking {table_name} for impossible data...")
        anomalies = self.conn.execute(f"SELECT * FROM {table_name} WHERE close <= 0 OR volume < 0").df()
        return anomalies

    def run(self):
        """Consolidates all analyses into one diagnostic report."""
        self.logger.info("*"*60)
        self.logger.info("STARTING DATA PROFILING AND OUTLIER SCAN")
        self.logger.info("*"*60)
        
        yahoo_gainers = self.find_top_gainers("clean_yahoo_stocks", "ticker")
        yahoo_losers = self.find_top_losers("clean_yahoo_stocks", "ticker")
        yahoo_risk = self.volatility_scan("clean_yahoo_stocks", "ticker")
        
        bybit_gainers = self.find_top_gainers("clean_bybit_crypto", "symbol")
        bybit_losers = self.find_top_losers("clean_bybit_crypto", "symbol")
        bybit_risk = self.volatility_scan("clean_bybit_crypto", "symbol")
        
        yahoo_gainers['Asset'] = yahoo_gainers['ticker']
        bybit_gainers['Asset'] = bybit_gainers['symbol']
        final_gainers = pd.concat([yahoo_gainers, bybit_gainers])
        
        print("\n" + "="*80)
        print("TOP 10 MARKET GAINERS (HISTORICAL)")
        print("="*80)
        cols_to_show = ['date', 'Asset', 'close', 'prev_close', 'change_pct']
        print(final_gainers[cols_to_show].sort_values('change_pct', ascending=False).head(10).to_string(index=False))
        
        yahoo_risk['Asset'] = yahoo_risk['ticker']
        bybit_risk['Asset'] = bybit_risk['symbol']
        final_risk = pd.concat([yahoo_risk[['Asset', 'Volatility']], bybit_risk[['Asset', 'Volatility']]])
        
        print("\n" + "="*80)
        print("HIGHEST RISK ASSETS (VOLATILITY)")
        print("="*80)
        print(final_risk.sort_values('Volatility', ascending=False).head(10).to_string(index=False))
        print("="*80)

    def close(self):
        """Closes the connection safely."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.logger.info("Profiler connection closed.")

if __name__ == "__main__":
    profiler = DataProfiler()
    try:
        profiler.run()
    finally:
        profiler.close()
