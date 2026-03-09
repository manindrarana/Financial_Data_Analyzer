import duckdb
import yaml
import os
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from src.utils import get_logger


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
        df['rsi_14'] = ta.rsi(df['close'], length=14)
        
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['macd'] = macd['MACD_12_26_9']
            df['macd_signal'] = macd['MACDs_12_26_9']
            df['macd_histogram'] = macd['MACDh_12_26_9']
        
        df['roc_10'] = ta.roc(df['close'], length=10)
        df['roc_20'] = ta.roc(df['close'], length=20)
        
        stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3, smooth_k=3)
        if stoch is not None:
            df['stoch_k'] = stoch['STOCHk_14_3_3']
            df['stoch_d'] = stoch['STOCHd_14_3_3']
        
        df['ema_12'] = ta.ema(df['close'], length=12)
        df['ema_26'] = ta.ema(df['close'], length=26)
        df['ema_50'] = ta.ema(df['close'], length=50)
        df['ema_200'] = ta.ema(df['close'], length=200)
        
        df['sma_50'] = ta.sma(df['close'], length=50)
        df['sma_100'] = ta.sma(df['close'], length=100)
        df['sma_200'] = ta.sma(df['close'], length=200)
        
        bbands = ta.bbands(df['close'], length=20, std=2)
        if bbands is not None:
            df['bb_upper'] = bbands['BBU_20_2.0']
            df['bb_middle'] = bbands['BBM_20_2.0']
            df['bb_lower'] = bbands['BBL_20_2.0']
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_percentage'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        df['atr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        df['volume_sma_20'] = ta.sma(df['volume'], length=20)
        df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, 1)
        
        df['obv'] = ta.obv(df['close'], df['volume'])
        
        if len(df) > 0:
            df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        
        df['returns_1d'] = df['close'].pct_change(periods=1)
        df['returns_5d'] = df['close'].pct_change(periods=5)
        df['returns_10d'] = df['close'].pct_change(periods=10)
        df['returns_20d'] = df['close'].pct_change(periods=20)
        
        df['log_returns'] = (df['close'] / df['close'].shift(1)).apply(lambda x: 0 if x <= 0 else pd.np.log(x) if hasattr(pd, 'np') else __import__('numpy').log(x))
        
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
        
        
