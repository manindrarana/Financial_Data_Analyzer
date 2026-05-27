"""
Prediction inference module for the Dash dashboard.
Loads trained XGBoost models, queries gold_crypto_features or gold_stock_features,
applies stationarity transformations, and runs inference.

Also loads per-model metadata (train_end_date) to enable out-of-sample
accuracy calculation and prevent training data leakage in the dashboard.
"""
import json
import os
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join("database", "financial_data.duckdb")

MODEL_PATHS = {
    "crypto": os.path.join("src", "models", "BTC_1h_xgboost_model.json"),
    "stocks": os.path.join("src", "models", "AAPL_1h_xgboost_model.json"),
}

META_PATHS = {
    "crypto": os.path.join("src", "models", "BTC_1h_xgboost_metadata.json"),
    "stocks": os.path.join("src", "models", "AAPL_1h_xgboost_metadata.json"),
}

_train_cutoffs = {}


def get_train_cutoff(asset_class="crypto"):
    """Return the training end date (pd.Timestamp) for the given asset class.

    Reads the per-model metadata JSON to find the last date used in training.
    Returns None if no metadata file exists (e.g., BTC model trained before
    metadata tracking was added or training script hasn't been re-run).

    The cutoff is cached in _train_cutoffs to avoid re-reading JSON on every
    Dash callback invocation.
    """
    if asset_class in _train_cutoffs:
        return _train_cutoffs[asset_class]

    meta_path = META_PATHS.get(asset_class)
    if meta_path and os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        cutoff = pd.Timestamp(meta["train_end_date"])
        _train_cutoffs[asset_class] = cutoff
        return cutoff

    _train_cutoffs[asset_class] = None
    return None


FEATURE_TABLES = {
    "crypto": "gold_crypto_features",
    "stocks": "gold_stock_features",
}

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


_model_cache = {}
def _get_model(asset_class="crypto"):
    """Return the cached XGBoost model for the given asset class, loading once."""
    if asset_class not in _model_cache:
        model_path = MODEL_PATHS.get(asset_class)
        if model_path is None or not os.path.exists(model_path):
            raise FileNotFoundError(
                f"No model found for asset_class='{asset_class}'. "
                f"Expected at: {model_path}. Run scripts/train_aapl_model.py first."
            )
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        _model_cache[asset_class] = model
    return _model_cache[asset_class]


def run_prediction(asset="BTC", interval="1h", asset_class="crypto"):
    """Run the full prediction pipeline for a given asset, interval, and asset class.

    Args:
        asset: Asset symbol (e.g., "BTC", "AAPL").
        interval: Candle interval (e.g., "1h", "4h").
        asset_class: "crypto" or "stocks" — determines which gold features table
                     and which XGBoost model to use.

    Returns a DataFrame with columns:
        date, close, prediction, confidence, actual_direction
    or None if no data is available.
    """
    table_name = FEATURE_TABLES.get(asset_class, "gold_crypto_features")

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
        FROM {table_name}
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

    model = _get_model(asset_class)
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

    train_cutoff = get_train_cutoff(asset_class)
    if train_cutoff is not None:
        results["is_oos"] = results["date"] > train_cutoff
    else:
        results["is_oos"] = True

    return results