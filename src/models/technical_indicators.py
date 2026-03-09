import duckdb
import yaml
import os
import pandas as pd
from dotenv import load_dotenv
from src.utils import get_logger
import ta


class TechnicalIndicatorProcessor:
    """Calculates technical indicators for ML feature engineering"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.db_path = self.config["paths"]["database"]
        self.analytics_bucket = self.config["paths"].get("analytics_bucket", "analytics-data")
        self.conn = duckdb.connect(self.db_path)
        
        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "").replace("http://", "")
        self.conn.execute("INSTALL httpfs; LOAD httpfs;")
        self.conn.execute(f"""
            CREATE SECRET IF NOT EXISTS (
                TYPE S3,
                KEY_ID '{os.getenv("AWS_ACCESS_KEY_ID")}',
                SECRET '{os.getenv("AWS_SECRET_ACCESS_KEY")}',
                ENDPOINT '{s3_endpoint}',
                URL_STYLE 'path',
                USE_SSL false
            );
        """)
    
    def calculate_indicators_for_asset(self, df):
        """Calculate all technical indicators for a single asset's data"""
        
        df = df.sort_values('date').reset_index(drop=True)
        
        self.logger.info(f"  Calculating indicators for {len(df)} data points...")
        
        df['rsi_14'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        
        macd_indicator = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['macd'] = macd_indicator.macd()
        df['macd_signal'] = macd_indicator.macd_signal()
        df['macd_histogram'] = macd_indicator.macd_diff()
        
        df['roc_10'] = ta.momentum.ROCIndicator(close=df['close'], window=10).roc()
        df['roc_20'] = ta.momentum.ROCIndicator(close=df['close'], window=20).roc()
        
        stoch = ta.momentum.StochasticOscillator(high=df['high'], low=df['low'], close=df['close'], 
                                              window=14, smooth_window=3)
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        df['ema_12'] = ta.trend.EMAIndicator(close=df['close'], window=12).ema_indicator()
        df['ema_26'] = ta.trend.EMAIndicator(close=df['close'], window=26).ema_indicator()
        df['ema_50'] = ta.trend.EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['ema_200'] = ta.trend.EMAIndicator(close=df['close'], window=200).ema_indicator()
        
        df['sma_50'] = ta.trend.SMAIndicator(close=df['close'], window=50).sma_indicator()
        df['sma_100'] = ta.trend.SMAIndicator(close=df['close'], window=100).sma_indicator()
        df['sma_200'] = ta.trend.SMAIndicator(close=df['close'], window=200).sma_indicator()
        
        bollinger = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_upper'] = bollinger.bollinger_hband()
        df['bb_middle'] = bollinger.bollinger_mavg()
        df['bb_lower'] = bollinger.bollinger_lband()
        df['bb_width'] = bollinger.bollinger_wband()
        df['bb_percentage'] = bollinger.bollinger_pband()
        
        df['atr_14'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], 
                                                    close=df['close'], window=14).average_true_range()
        
        df['obv'] = ta.volume.OnBalanceVolumeIndicator(close=df['close'], volume=df['volume']).on_balance_volume()
        
        df['vwap'] = ta.volume.VolumeWeightedAveragePrice(high=df['high'], low=df['low'], 
                                                        close=df['close'], volume=df['volume']).volume_weighted_average_price()
        
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, 1)
        
        df['returns_1d'] = df['close'].pct_change(periods=1)
        df['returns_5d'] = df['close'].pct_change(periods=5)
        df['returns_10d'] = df['close'].pct_change(periods=10)
        df['returns_20d'] = df['close'].pct_change(periods=20)
        
        import numpy as np
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        df['hl_ratio'] = (df['high'] - df['low']) / df['close'].replace(0, 1)
        
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low']).replace(0, 1)
        
        df['prev_close'] = df['close'].shift(1)
        df['prev_volume'] = df['volume'].shift(1)
        df['prev_high'] = df['high'].shift(1)
        df['prev_low'] = df['low'].shift(1)
        
        return df
    
    def generate_ml_features_table(self):
        """Generate gold_ml_features table with all technical indicators"""
        self.logger.info("=" * 60)
        self.logger.info("Building ML Features Table: gold_ml_features")
        self.logger.info("=" * 60)
        
        query = """
            SELECT 
                asset_symbol,
                asset_class,
                exchange,
                interval,
                date,
                open,
                high,
                low,
                close,
                volume,
                daily_volatility,
                sma_7,
                sma_30
            FROM gold_financial_analytics
            ORDER BY asset_symbol, interval, date
        """
        df_all = self.conn.execute(query).df()
        self.logger.info(f"Loaded {len(df_all)} rows from gold_financial_analytics")

        result_dfs = []
        total_groups = df_all.groupby(['asset_symbol', 'interval']).ngroups
        current_group = 0
        
        for (asset, interval), group_df in df_all.groupby(['asset_symbol', 'interval']):
            current_group += 1
            self.logger.info(f"[{current_group}/{total_groups}] Processing {asset} ({interval})...")
            
            if len(group_df) < 200:
                self.logger.warning(f"  Skipping {asset} ({interval}) - only {len(group_df)} rows (need 200+)")
                continue
            
            enhanced_df = self.calculate_indicators_for_asset(group_df.copy())
            result_dfs.append(enhanced_df)
        
        if not result_dfs:
            self.logger.error("No data groups had enough rows for indicator calculation!")
            return
        
        final_df = pd.concat(result_dfs, ignore_index=True)
        self.logger.info(f"Combined data from {len(result_dfs)} asset-interval groups")
        
        initial_rows = len(final_df)
        final_df = final_df.dropna()
        dropped_rows = initial_rows - len(final_df)
        self.logger.info(f"Dropped {dropped_rows} rows with NaN values (indicator warm-up period)")
        
        self.conn.execute("DROP TABLE IF EXISTS gold_ml_features")
        self.conn.execute("""
            CREATE TABLE gold_ml_features AS 
            SELECT * FROM final_df
            ORDER BY asset_class, asset_symbol, interval, date
        """)
        
        cnt = self.conn.execute("SELECT COUNT(*) FROM gold_ml_features").fetchone()[0]
        self.logger.info(f"Successfully created gold_ml_features with {cnt} rows!")
        
        indicator_cols = [col for col in final_df.columns if col not in 
                         ['asset_symbol', 'asset_class', 'exchange', 'interval', 'date', 
                          'open', 'high', 'low', 'close', 'volume']]
        self.logger.info(f"Total indicators calculated: {len(indicator_cols)}")
        self.logger.info(f"Indicators: {', '.join(indicator_cols[:10])}...")
        
        out_path = f"s3://{self.analytics_bucket}/ml_features.parquet"
        try:
            self.conn.execute(f"COPY gold_ml_features TO '{out_path}' (FORMAT PARQUET)")
            self.logger.info(f"Successfully exported ML Features to MinIO: {out_path}")
        except Exception as e:
            self.logger.error(f"Failed to export ML Features to MinIO: {e}")
    
    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("Starting Technical Indicator Calculation Process")
        self.logger.info("*" * 60)
        
        self.generate_ml_features_table()
        
        self.logger.info("*" * 60)
        self.logger.info("Technical Indicators Completed")
        self.logger.info("*" * 60)
    
    def close(self):
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    processor = TechnicalIndicatorProcessor()
    processor.run()
    processor.close()