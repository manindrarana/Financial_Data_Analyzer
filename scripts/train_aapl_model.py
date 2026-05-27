"""
Train an XGBoost model for AAPL 1h direction prediction.

Queries gold_stock_features from DuckDB, applies the same stationarity
transformations used in predictor.py, creates a chronologically-split
train/test set, trains XGBoost with baseline parameters, and saves the
model JSON to src/models/AAPL_1h_xgboost_model.json.

Also saves AAPL_1h_xgboost_metadata.json containing the training cutoff
date to prevent data leakage in the dashboard accuracy calculation.
"""

import json
import os
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report

DB_PATH = os.path.join("database", "financial_data.duckdb")
MODEL_PATH = os.path.join("src", "models", "AAPL_1h_xgboost_model.json")
META_PATH = os.path.join("src", "models", "AAPL_1h_xgboost_metadata.json")

MODEL_FEATURES = [
    "rsi_14", "roc_10", "roc_20", "stoch_k", "stoch_d", "bb_percentage",
    "volume_ratio", "returns_1p", "returns_5p", "returns_10p", "returns_20p",
    "log_returns", "hl_ratio", "close_position",
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct", "atr_pct", "volatility_pct",
]


def _make_stationary(df):
    """Convert raw technical indicators to stationary features."""
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


def main():
    print("=== Training AAPL 1h XGBoost Model ===\n")

    print("[1/5] Loading AAPL 1h features from gold_stock_features...")
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
        FROM gold_stock_features
        WHERE asset_symbol = 'AAPL' AND interval = '1h'
        ORDER BY date
    """).df()
    conn.close()

    print(f"   Loaded {len(df):,} rows")
    if df.empty:
        raise RuntimeError("No AAPL 1h data found in gold_stock_features!")

    df["date"] = pd.to_datetime(df["date"])
    print(f"   Date range: {df['date'].min()} --> {df['date'].max()}")

    print("\n[2/5] Applying stationarity transformations...")
    df = _make_stationary(df)

    print("[3/5] Creating target (next-bar direction)...")
    df["target_direction"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df = df.dropna(subset=["target_direction"])
    df["target_direction"] = df["target_direction"].astype(int)

    print("[4/5] Splitting train/test (80/20 chronological)...")
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    print(f"   Train: {len(train_df):,} rows ({train_df['date'].min()} --> {train_df['date'].max()})")
    print(f"   Test:  {len(test_df):,} rows ({test_df['date'].min()} --> {test_df['date'].max()})")

    y_train = train_df["target_direction"]
    y_test = test_df["target_direction"]

    available_features = [f for f in MODEL_FEATURES if f in train_df.columns]
    missing = set(MODEL_FEATURES) - set(available_features)
    if missing:
        print(f"   Warning: missing features: {missing}")

    X_train = train_df[available_features].dropna()
    X_test = test_df[available_features].dropna()

    common_train = X_train.index.intersection(y_train.index)
    common_test = X_test.index.intersection(y_test.index)
    X_train = X_train.loc[common_train]
    y_train = y_train.loc[common_train]
    X_test = X_test.loc[common_test]
    y_test = y_test.loc[common_test]

    print(f"   Train after dropna: {len(X_train):,} rows")
    print(f"   Test after dropna:  {len(X_test):,} rows")
    print(f"   Features: {X_train.shape[1]}")

    up_pct = y_train.mean() * 100
    print(f"   Train UP%: {up_pct:.1f}%")

    print("\n[5/5] Training XGBoost baseline model...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)

    print(f"\n=== Results ===")
    print(f"   Test Accuracy: {test_acc:.4f} ({test_acc*100:.2f}%)")
    print(f"\n   Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["DOWN", "UP"]))

    model.save_model(MODEL_PATH)
    print(f"\n   Model saved to: {MODEL_PATH}")

    train_end_date = train_df["date"].max().isoformat()
    metadata = {
        "asset": "AAPL",
        "interval": "1h",
        "train_end_date": train_end_date,
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "test_accuracy": float(test_acc),
        "features": available_features,
    }
    with open(META_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"   Metadata saved to: {META_PATH}")
    print(f"   Training cutoff (OOS starts after): {train_end_date}")

    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    print(f"\n   Top 10 Features:")
    for rank in range(min(10, len(available_features))):
        fname = available_features[indices[rank]]
        score = importances[indices[rank]]
        print(f"     {rank+1:2d}. {fname}: {score:.4f}")

    print("\n=== Done ===")
    return model, test_acc


if __name__ == "__main__":
    main()