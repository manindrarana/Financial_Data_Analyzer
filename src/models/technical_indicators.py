import duckdb
import yaml
import os
import pandas as pd
from dotenv import load_dotenv
from src.utils import get_logger
import ta
import numpy as np

MIN_ROWS_FOR_INDICATORS = 200


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
        
        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000").replace("http://", "")
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
        
        df['returns_1p'] = df['close'].pct_change(periods=1)
        df['returns_5p'] = df['close'].pct_change(periods=5)
        df['returns_10p'] = df['close'].pct_change(periods=10)
        df['returns_20p'] = df['close'].pct_change(periods=20)
        
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        df['hl_ratio'] = (df['high'] - df['low']) / df['close'].replace(0, 1)
        
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low']).replace(0, 1)
        
        df['prev_close'] = df['close'].shift(1)
        df['prev_volume'] = df['volume'].shift(1)
        df['prev_high'] = df['high'].shift(1)
        df['prev_low'] = df['low'].shift(1)
        
        return df
    
    def generate_ml_features_table(self):
        """Generate asset-class specific gold feature tables with all technical indicators"""
        self.logger.info("=" * 60)
        self.logger.info("Building Specialized Gold Feature Stores")
        self.logger.info("=" * 60)
        query = """
            SELECT asset_symbol, asset_class, exchange, interval, date,
                   open, high, low, close, volume, daily_volatility, sma_7, sma_30
            FROM gold_crypto_analytics
            UNION ALL
            SELECT asset_symbol, asset_class, exchange, interval, date,
                   open, high, low, close, volume, daily_volatility, sma_7, sma_30
            FROM gold_stock_analytics
        """
        df_all = self.conn.execute(query).df()
        self.logger.info(f"Loaded {len(df_all)} rows from specialized intermediate layers")

        crypto_extra = self.conn.execute("""
            SELECT asset_symbol, interval, date,
                   turnover, open_interest, funding_rate
            FROM gold_crypto_analytics
        """).df()

        result_dfs = []
        total_groups = df_all.groupby(['asset_symbol', 'interval']).ngroups
        current_group = 0
        
        for (asset, interval), group_df in df_all.groupby(['asset_symbol', 'interval']):
            current_group += 1
            self.logger.info(f"[{current_group}/{total_groups}] Processing {asset} ({interval})...")
            
            if len(group_df) < MIN_ROWS_FOR_INDICATORS:
                self.logger.warning(f"  Skipping {asset} ({interval}) - only {len(group_df)} rows (need {MIN_ROWS_FOR_INDICATORS}+)")
                continue
            
            enhanced_df = self.calculate_indicators_for_asset(group_df.copy())
            result_dfs.append(enhanced_df)
        
        if not result_dfs:
            self.logger.error("No data groups had enough rows for indicator calculation!")
            return
        
        final_df = pd.concat(result_dfs, ignore_index=True)
        self.logger.info(f"Combined data from {len(result_dfs)} asset-interval groups")
        
        for asset_class in final_df['asset_class'].unique():
            class_df = final_df[final_df['asset_class'] == asset_class].copy()
            initial_rows = len(class_df)
            indicator_cols = ['rsi_14', 'macd', 'macd_signal', 'macd_histogram', 'roc_10', 'roc_20',
                              'stoch_k', 'stoch_d', 'ema_12', 'ema_26', 'ema_50', 'ema_200',
                              'sma_50', 'sma_100', 'sma_200', 'bb_upper', 'bb_middle', 'bb_lower',
                              'bb_width', 'bb_percentage', 'atr_14', 'obv', 'vwap',
                              'volume_sma_20', 'volume_ratio', 'returns_1p', 'returns_5p',
                              'returns_10p', 'returns_20p', 'log_returns', 'hl_ratio', 'close_position']
            cols_to_check = [c for c in indicator_cols if c in class_df.columns]
            class_df = class_df.dropna(subset=cols_to_check)
            
            if asset_class.lower() == 'crypto':
                merge_keys = ['asset_symbol', 'interval', 'date']
                class_df = class_df.merge(
                    crypto_extra[merge_keys + ['turnover', 'open_interest', 'funding_rate']],
                    on=merge_keys, how='left'
                )
            
            self.logger.info(f"--- Processing {asset_class.upper()} Gold Store ---")
            self.logger.info(f"Dropped {initial_rows - len(class_df)} rows with NaNs (warm-up)")
            
            class_key = asset_class.lower()
            table_name = f"gold_{class_key}_features"
            self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            
            self.conn.register('temp_class_df', class_df)
            self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM temp_class_df ORDER BY asset_symbol, interval, date")
            self.conn.unregister('temp_class_df')
            
            cnt = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            self.logger.info(f"Successfully created {table_name} with {cnt} rows!")
            
            out_path = f"s3://{self.analytics_bucket}/{class_key}_features.parquet"
            try:
                self.conn.execute(f"COPY {table_name} TO '{out_path}' (FORMAT PARQUET)")
                self.logger.info(f"Exported to MinIO: {out_path}")
            except Exception as e:
                self.logger.error(f"Failed to export {asset_class} Features to MinIO: {e}")
    
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