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

    def calculate_rsi(self, table_name, symbol_col, window=14):
        """Calculates current RSI for all assets in a table."""
        self.logger.info(f"Calculating RSI for {table_name}...")
        tickers = self.get_tickers(table_name, symbol_col)
        
        rsi_results = []
        for t in tickers:
            df = self.conn.execute(f"SELECT date, close FROM {table_name} WHERE {symbol_col}='{t}' ORDER BY date DESC LIMIT 30").df()
            if len(df) < window + 1: continue
            
            df = df.iloc[::-1]
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = gain / (loss + 1e-9)
            rsi_val = (100 - (100 / (1 + rs))).iloc[-1]
            
            rsi_results.append({symbol_col: t, "RSI": round(rsi_val, 2)})
            
        return pd.DataFrame(rsi_results).sort_values('RSI', ascending=False)

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
        
        self.logger.info("Generating Global Market View...")
        sector_results = self.sector_analysis()
        
        yahoo_corr = self.scan_top_correlations("clean_yahoo_stocks", "ticker")
        bybit_corr = self.scan_top_correlations("clean_bybit_crypto", "symbol")
        full_corr = pd.concat([yahoo_corr, bybit_corr])
        
        print("\n" + "="*80)
        print("TOP 10 MARKET GAINERS (HISTORICAL)")
        print("="*80)
        cols_to_show = ['date', 'Asset', 'close', 'prev_close', 'change_pct']
        top_gainers_display = final_gainers[cols_to_show].sort_values('change_pct', ascending=False).head(10)
        print(top_gainers_display.to_string(index=False))
        
        yahoo_risk['Asset'] = yahoo_risk['ticker']
        bybit_risk['Asset'] = bybit_risk['symbol']
        final_risk = pd.concat([yahoo_risk[['Asset', 'Volatility']], bybit_risk[['Asset', 'Volatility']]])
        top_risk_display = final_risk.sort_values('Volatility', ascending=False).head(10)
        
        print("\n" + "="*80)
        print("HIGHEST RISK ASSETS (VOLATILITY)")
        print("="*80)
        print(top_risk_display.to_string(index=False))
        
        print("\n" + "="*80)
        print("ASSET CORRELATIONS (TOP PAIRS)")
        print("="*80)
        print(full_corr.to_string(index=False))
        
        print("\n" + "="*80)
        print("SECTOR COMPARISON (STOCKS vs CRYPTO)")
        print("="*80)
        print(sector_results.to_string(index=False))
        print("="*80)
        
        dead_list = self.detect_dead_assets("clean_yahoo_stocks", "ticker") + self.detect_dead_assets("clean_bybit_crypto", "symbol")
        spikes_df = pd.concat([self.volume_spike_detector("clean_yahoo_stocks", "ticker"), self.volume_spike_detector("clean_bybit_crypto", "symbol")])
        
        if dead_list:
            print(f"\n[WARNING]: {len(dead_list)} Dead Assets identified (Prices frozen).")
            print(f"Examples: {', '.join(dead_list[:5])}")
            
        if not spikes_df.empty:
            print("\n" + "="*80)
            print("SIGNIFICANT VOLUME SPIKES DETECTED")
            print("="*80)
            print(spikes_df.to_string(index=False))
            print("="*80)
            
        spread_df = pd.concat([self.calculate_spread_outliers("clean_yahoo_stocks", "ticker"), self.calculate_spread_outliers("clean_bybit_crypto", "symbol")])
        print("\n" + "="*80)
        print("TOP INTRADAY PRICE SWINGS (HIGH-LOW SPREAD)")
        print("="*80)
        print(spread_df.sort_values('spread_pct', ascending=False).head(10).to_string(index=False))
        print("="*80)

        gap_df = pd.concat([self.find_overnight_gaps("clean_yahoo_stocks", "ticker"), self.find_overnight_gaps("clean_bybit_crypto", "symbol")])
        print("\n" + "="*80)
        print("SIGNIFICANT OVERNIGHT GAPS (OPEN vs PREV_CLOSE)")
        print("="*80)
        print(gap_df.sort_values('gap_pct', ascending=False).head(10).to_string(index=False))
        print("="*80)

        self.export_markdown_report(top_gainers_display, top_risk_display, sector_results, full_corr, dead_list, spikes_df, spread_df, gap_df)


    def calculate_correlation(self, asset1, asset2, table_name, symbol_col):
        """Calculates the correlation between two assets over time."""
        self.logger.info(f"Calculating Correlation: {asset1} vs {asset2}")
        
        query1 = f"SELECT date, close as p1 FROM {table_name} WHERE {symbol_col} = '{asset1}'"
        query2 = f"SELECT date, close as p2 FROM {table_name} WHERE {symbol_col} = '{asset2}'"
        
        df1 = self.conn.execute(query1).df()
        df2 = self.conn.execute(query2).df()
        
        if df1.empty or df2.empty:
            return 0.0
            
        merged = pd.merge(df1, df2, on='date')
        if len(merged) < 5:
            return 0.0
            
        return merged['p1'].corr(merged['p2'])

    def sector_analysis(self):
        """Compares overall performance and risk stats for different sectors (Yahoo vs Bybit)."""
        self.logger.info("Comparing Sectors (Stocks vs Crypto)...")
        yahoo_risk = self.volatility_scan("clean_yahoo_stocks", "ticker")
        bybit_risk = self.volatility_scan("clean_bybit_crypto", "symbol")
        
        yahoo_risk['Asset'] = yahoo_risk['ticker']
        bybit_risk['Asset'] = bybit_risk['symbol']
        
        yahoo_risk['Vol'] = yahoo_risk['Volatility'].str.rstrip('%').astype(float)
        bybit_risk['Vol'] = bybit_risk['Volatility'].str.rstrip('%').astype(float)
        
        summary = [
            {"Sector": "Yahoo Stocks", "Avg_Vol": f"{yahoo_risk['Vol'].mean():.2f}%", "Max_Risk": yahoo_risk['Asset'].iloc[0]},
            {"Sector": "Bybit Crypto", "Avg_Vol": f"{bybit_risk['Vol'].mean():.2f}%", "Max_Risk": bybit_risk['Asset'].iloc[0]}
        ]
        return pd.DataFrame(summary)


    def export_markdown_report(self, gainers, risk, sector, correlations, dead_list, spikes, spread, gaps):
        """Saves a summary report of today's profiling results to a markdown file."""
        report_path = "reports/market_profile.md"
        os.makedirs("reports", exist_ok=True)
        
        with open(report_path, "w") as f:
            f.write("# Market Profiling Report\n\n")
            f.write("## Top 10 Gainers\n\n")
            f.write(gainers.to_markdown(index=False) + "\n\n")
            f.write("## Highest Risk Assets\n\n")
            f.write(risk.to_markdown(index=False) + "\n\n")
            f.write("## Top Asset Correlations\n\n")
            f.write(correlations.to_markdown(index=False) + "\n\n")
            f.write("## Overnight Gaps (Open vs Prev Close)\n\n")
            f.write(gaps.to_markdown(index=False) + "\n\n")
            f.write("## Intraday Price Swings (High-Low Spread)\n\n")
            f.write(spread.to_markdown(index=False) + "\n\n")
            f.write("## Market Anomalies (Frozen Prices)\n\n")
            f.write(f"The following assets have 0 price movement: {', '.join(dead_list) if dead_list else 'None'}\n\n")
            f.write("## Significant Volume Spikes\n\n")
            f.write(spikes.to_markdown(index=False) + "\n\n")
            f.write("## Sector Summary\n\n")
            f.write(sector.to_markdown(index=False) + "\n")
            
        self.logger.info(f"Report exported to {report_path}")

    def detect_dead_assets(self, table_name, symbol_col, window=7):
        """Finds assets with zero price movement over a window of data."""
        self.logger.info(f"Scanning {table_name} for dead/frozen assets...")
        tickers = self.get_tickers(table_name, symbol_col)
        
        dead_list = []
        for t in tickers:
            df = self.conn.execute(f"SELECT close FROM {table_name} WHERE {symbol_col}='{t}' ORDER BY date DESC LIMIT {window}").df()
            if len(df) >= window and df['close'].nunique() == 1:
                dead_list.append(t)
        
        return dead_list

    def volume_spike_detector(self, table_name, symbol_col, threshold=10):
        """Finds days where volume is significantly higher than the rolling average."""
        self.logger.info(f"Scanning {table_name} for Volume Spikes...")
        query = f"""
            SELECT date, {symbol_col}, volume, avg_vol
            FROM (
                SELECT date, {symbol_col}, volume,
                       AVG(volume) OVER(PARTITION BY {symbol_col} ORDER BY date ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) as avg_vol
                FROM {table_name}
            )
            WHERE volume > {threshold} * avg_vol AND avg_vol > 0
            LIMIT 10
        """
        return self.conn.execute(query).df()

    def calculate_spread_outliers(self, table_name, symbol_col, limit=10):
        """Finds days where the High-Low spread is exceptionally wide."""
        self.logger.info(f"Scanning {table_name} for high-low spread outliers...")
        query = f"""
            SELECT date, {symbol_col}, high, low, close,
                   ((high - low) / close) * 100 as spread_pct
            FROM {table_name}
            WHERE close > 0
            ORDER BY spread_pct DESC
            LIMIT {limit}
        """
        return self.conn.execute(query).df()

    def find_overnight_gaps(self, table_name, symbol_col, threshold=2.0):
        """Finds assets that opened >N% away from previous close."""
        self.logger.info(f"Scanning {table_name} for overnight gaps...")
        query = f"""
            SELECT date, {symbol_col}, open, prev_close, 
                   ((open - prev_close) / prev_close) * 100 as gap_pct
            FROM (
                SELECT date, {symbol_col}, open, 
                       LAG(close) OVER(PARTITION BY {symbol_col} ORDER BY date) as prev_close
                FROM {table_name}
            )
            WHERE prev_close IS NOT NULL AND ABS(gap_pct) > {threshold}
            ORDER BY ABS(gap_pct) DESC
            LIMIT 10
        """
        return self.conn.execute(query).df()

    def scan_top_correlations(self, table_name, symbol_col, limit=5):
        """Scans the top 10 most volatile assets to find the strongest correlations."""
        self.logger.info(f"Scanning {table_name} for top correlations...")
        
        top_assets = self.volatility_scan(table_name, symbol_col).head(10)['Asset'].tolist()
        
        results = []
        for i in range(len(top_assets)):
            for j in range(i + 1, len(top_assets)):
                a1, a2 = top_assets[i], top_assets[j]
                corr = self.calculate_correlation(a1, a2, table_name, symbol_col)
                results.append({"Pair": f"{a1} / {a2}", "Correlation": f"{corr:.3f}"})
                
        return pd.DataFrame(results).sort_values('Correlation', ascending=False).head(limit)

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
