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
        