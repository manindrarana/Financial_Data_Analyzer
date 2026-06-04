import json
import os
import sys
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
import yaml
from datetime import datetime
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from src.utils import get_logger

MIN_ROWS = 200
PARAM_GRID = {
    "learning_rate": [0.01, 0.05, 0.1],
    "max_depth": [3, 5],
    "n_estimators": [100, 200],
}

CRYPTO_INTERVAL_MAP = {"60": "1h", "240": "4h", "D": "1d", "W": "1w"}
STOCK_INTERVAL_MAP = {"1h": "1h", "1d": "1d", "1wk": "1w"}

MODEL_FEATURES = [
    "rsi_14", "roc_10", "roc_20", "stoch_k", "stoch_d", "bb_percentage",
    "volume_ratio", "returns_1p", "returns_5p", "returns_10p", "returns_20p",
    "log_returns", "hl_ratio", "close_position",
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct", "atr_pct", "volatility_pct",
]

NEEDED_COLS = [
    "date", "close",
    "sma_7", "sma_30", "sma_50", "sma_100", "sma_200",
    "ema_12", "ema_26", "ema_50", "ema_200",
    "vwap", "macd", "macd_signal", "macd_histogram",
    "atr_14", "daily_volatility",
    "rsi_14", "roc_10", "roc_20", "stoch_k", "stoch_d",
    "bb_percentage", "volume_ratio",
    "returns_1p", "returns_5p", "returns_10p", "returns_20p",
    "log_returns", "hl_ratio", "close_position",
]


class PipelineModelTrainer:

    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()

        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)

        self.db_path = os.getenv("DB_PATH", self.config["paths"]["database"])
        if not os.path.exists(self.db_path):
            self.db_path = os.path.join("database", "financial_data.duckdb")
        self.conn = duckdb.connect(self.db_path)

        self.models_dir = os.path.join("src", "models")
        self.crypto_dir = os.path.join(self.models_dir, "crypto")
        self.stocks_dir = os.path.join(self.models_dir, "stocks")
        os.makedirs(self.crypto_dir, exist_ok=True)
        os.makedirs(self.stocks_dir, exist_ok=True)

    