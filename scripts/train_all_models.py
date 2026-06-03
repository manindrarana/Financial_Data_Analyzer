"""
Generic training script: trains one XGBoost model per asset × interval combo
that has ≥ 200 rows in the gold feature table. Skips monthly intervals.

Saves to src/models/crypto/{asset}_{interval}_xgboost_model.json (or stocks/) + metadata JSON.
"""
import json
import os
import sys
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
import yaml
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

DB_PATH = os.path.join("database", "financial_data.duckdb")
MODELS_DIR = os.path.join("src", "models")
CRYPTO_MODELS_DIR = os.path.join(MODELS_DIR, "crypto")
STOCKS_MODELS_DIR = os.path.join(MODELS_DIR, "stocks")
MIN_ROWS = 200
PARAM_GRID = {
    "learning_rate": [0.01, 0.05, 0.1],
    "max_depth": [3, 5],
    "n_estimators": [100, 200],
}

CRYPTO_INTERVAL_MAP = {"60": "1h", "240": "4h", "D": "1d", "W": "1w"}
STOCK_INTERVAL_MAP = {"1h": "1h", "1d": "1d", "1wk": "1w"}

# set None to train ALL combos or set to filter specific assets
ONLY_ASSETS = {"BTC", "SOL", "XRP", "AAPL", "AMZN", "TSLA"}

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


def _make_stationary(df):
    df = df.copy()
    c = df["close"].replace(0, np.nan)

    for window in [7, 30, 50, 100, 200]:
        col = f"sma_{window}"
        if col in df.columns:
            df[f"sma_{window}_dist"] = (df["close"] / df[col]) - 1

    for window in [12, 26, 50, 200]:
        col = f"ema_{window}"
        if col in df.columns:
            df[f"ema_{window}_dist"] = (df["close"] / df[col]) - 1

    if "vwap" in df.columns:
        df["vwap_dist"] = (df["close"] / df["vwap"]) - 1

    if "macd" in df.columns:
        df["macd_pct"] = df["macd"] / c
    if "macd_signal" in df.columns:
        df["macd_sig_pct"] = df["macd_signal"] / c
    if "macd_histogram" in df.columns:
        df["macd_hist_pct"] = df["macd_histogram"] / c

    if "atr_14" in df.columns:
        df["atr_pct"] = df["atr_14"] / c

    if "daily_volatility" in df.columns:
        df["volatility_pct"] = df["daily_volatility"] / c

    return df


def load_config():
    with open(os.path.join("configs", "settings.yml"), "r") as f:
        return yaml.safe_load(f)


def build_combos(config):
    combos = []
    crypto_targets = config["ingestion"]["targets"]["bybit"]
    crypto_intervals = config["providers"]["bybit"]["intervals"]
    stock_targets = config["ingestion"]["targets"]["yfinance"]
    stock_intervals = config["providers"]["yfinance"]["intervals"]

    for symbol in crypto_targets:
        asset = symbol.replace("USDT", "")
        if ONLY_ASSETS and asset not in ONLY_ASSETS:
            continue
        for raw_interval in crypto_intervals:
            interval = CRYPTO_INTERVAL_MAP.get(raw_interval)
            if interval is None:
                continue
            combos.append((asset, interval, "crypto", "gold_crypto_features"))

    for symbol in stock_targets:
        if ONLY_ASSETS and symbol not in ONLY_ASSETS:
            continue
        for raw_interval in stock_intervals:
            interval = STOCK_INTERVAL_MAP.get(raw_interval)
            if interval is None:
                continue
            combos.append((symbol, interval, "stocks", "gold_stock_features"))

    return combos