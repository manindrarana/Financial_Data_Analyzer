"""
Prediction inference module for the Dash dashboard.
Loads the trained XGBoost model, queries gold_crypto_features,
applies stationarity transformations, and runs inference.
"""

import os
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join("database", "financial_data.duckdb")
MODEL_PATH = os.path.join("src", "models", "BTC_1h_xgboost_model.json")

MODEL_FEATURES = [
    "rsi_14", "roc_10", "roc_20", "stoch_k", "stoch_d", "bb_percentage",
    "volume_ratio", "returns_1p", "returns_5p", "returns_10p", "returns_20p",
    "log_returns", "hl_ratio", "close_position",
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct", "atr_pct", "volatility_pct",
]


def _make_stationary(df):
    """Convert raw technical indicators to stationary features expected by the model.

    The XGBoost model was trained on stationary distance/ratio features to avoid
    memorizing absolute price levels. Raw indicators (sma_7, ema_12, macd, atr_14, etc.)
    are transformed into relative measures (distance from close or percentage of close).
    """
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


_model_cache = None
def _get_model():
    """Return the cached XGBoost model, loading it once on first call."""
    global _model_cache
    if _model_cache is None:
        model = xgb.XGBClassifier()
        model.load_model(MODEL_PATH)
        _model_cache = model
    return _model_cache


def run_prediction(asset="BTC", interval="1h"):
    """Run the full prediction pipeline for a given asset and interval.

    Returns a DataFrame with columns:
        date, close, prediction, confidence, actual_direction
    or None if no data is available.
    """
    conn = duckdb.connect(DB_PATH, read_only=True)
    needed_cols = [
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
    col_list = ", ".join(needed_cols)

    df = conn.execute(f"""
        SELECT {col_list}
        FROM gold_crypto_features
        WHERE asset_symbol = '{asset}' AND interval = '{interval}'
        ORDER BY date
    """).df()

    conn.close()

    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"])

    df = _make_stationary(df)

    available_features = [f for f in MODEL_FEATURES if f in df.columns]
    if len(available_features) < len(MODEL_FEATURES):
        missing = set(MODEL_FEATURES) - set(available_features)
        print(f"Warning: missing features for prediction: {missing}")

    df_clean = df.dropna(subset=available_features)

    if df_clean.empty:
        return None

    model = _get_model()
    X = df_clean[available_features]
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)

    up_prob = probabilities[:, 1]

    results = df_clean[["date", "close"]].copy()
    results["prediction"] = predictions
    results["confidence"] = np.where(predictions == 1, up_prob, 1 - up_prob)

    results["actual_direction"] = (
        results["close"].shift(-1) > results["close"]
    ).astype(int)

    results = results.dropna(subset=["actual_direction"])
    results["actual_direction"] = results["actual_direction"].astype(int)

    return results