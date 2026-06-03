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

def fetch_data(asset, interval, table_name):
    col_list = ", ".join(NEEDED_COLS)
    conn = duckdb.connect(DB_PATH, read_only=True)
    df = conn.execute(f"""
        SELECT {col_list}
        FROM {table_name}
        WHERE asset_symbol = '{asset}' AND interval = '{interval}'
        ORDER BY date
    """).df()
    conn.close()
    return df


def train_one(asset, interval, asset_class, table_name):
    print(f"\n{'='*60}")
    print(f"  {asset} {interval} ({asset_class})")
    print(f"{'='*60}")

    df = fetch_data(asset, interval, table_name)
    print(f"  Rows fetched: {len(df)}")

    if len(df) < MIN_ROWS:
        print(f"  SKIP: only {len(df)} rows (< {MIN_ROWS})")
        return {"asset": asset, "interval": interval, "status": "skipped",
                "reason": f"insufficient rows ({len(df)} < {MIN_ROWS})"}

    df["date"] = pd.to_datetime(df["date"])
    df = _make_stationary(df)
    df["target_direction"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df = df.dropna(subset=["target_direction"])
    df["target_direction"] = df["target_direction"].astype(int)

    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    y_train = train_df["target_direction"]
    y_test = test_df["target_direction"]

    available_features = [f for f in MODEL_FEATURES if f in train_df.columns]
    X_train = train_df[available_features].dropna()
    X_test = test_df[available_features].dropna()

    common_train = X_train.index.intersection(y_train.index)
    common_test = X_test.index.intersection(y_test.index)
    X_train = X_train.loc[common_train]
    y_train = y_train.loc[common_train]
    X_test = X_test.loc[common_test]
    y_test = y_test.loc[common_test]

    if len(X_train) < 100 or len(X_test) < 20:
        print(f"  SKIP: train={len(X_train)}, test={len(X_test)} after dropna")
        return {"asset": asset, "interval": interval, "status": "skipped",
                "reason": f"insufficient clean rows (train={len(X_train)}, test={len(X_test)})"}

    print(f"  GridSearchCV: {len(PARAM_GRID['learning_rate'])} lr × "
          f"{len(PARAM_GRID['max_depth'])} depth × "
          f"{len(PARAM_GRID['n_estimators'])} n_est = "
          f"{len(PARAM_GRID['learning_rate']) * len(PARAM_GRID['max_depth']) * len(PARAM_GRID['n_estimators'])} combos × 2-fold CV")

    base_model = xgb.XGBClassifier(
        subsample=1.0, eval_metric="logloss", random_state=42,
    )
    tscv = TimeSeriesSplit(n_splits=2)
    grid = GridSearchCV(
        base_model, PARAM_GRID, cv=tscv, scoring="accuracy",
        n_jobs=-1, verbose=0,
    )
    grid.fit(X_train, y_train)
    model = grid.best_estimator_
    best_params = grid.best_params_
    best_params["subsample"] = 1.0
    best_params["eval_metric"] = "logloss"
    best_params["random_state"] = 42

    print(f"  Best params: {grid.best_params_}")
    print(f"  Best CV score: {grid.best_score_:.4f}")

    y_pred = model.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)
    print(f"  Test accuracy: {test_acc:.4f} ({test_acc*100:.2f}%)")

    model_filename = f"{asset}_{interval}_xgboost_model.json"
    meta_filename = f"{asset}_{interval}_xgboost_metadata.json"
    out_dir = CRYPTO_MODELS_DIR if asset_class == "crypto" else STOCKS_MODELS_DIR
    os.makedirs(out_dir, exist_ok=True)
    model_path = os.path.join(out_dir, model_filename)
    meta_path = os.path.join(out_dir, meta_filename)

    model.save_model(model_path)
    train_end_date = train_df["date"].max().isoformat()
    metadata = {
        "asset": asset,
        "interval": interval,
        "asset_class": asset_class,
        "train_end_date": train_end_date,
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "test_accuracy": float(test_acc),
        "features": available_features,
        "best_params": best_params,
        "best_cv_score": float(grid.best_score_),
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  Saved: {model_path}")
    return {"asset": asset, "interval": interval, "status": "trained",
            "accuracy": round(test_acc, 4), "train_rows": len(train_df),
            "test_rows": len(test_df)}


def main():
    print("=== Train All Models ===\n")
    config = load_config()
    combos = build_combos(config)
    print(f"Total combos to attempt: {len(combos)}\n")

    os.makedirs(CRYPTO_MODELS_DIR, exist_ok=True)
    os.makedirs(STOCKS_MODELS_DIR, exist_ok=True)
    results = []
    trained = 0
    skipped = 0

    for asset, interval, asset_class, table_name in combos:
        result = train_one(asset, interval, asset_class, table_name)
        results.append(result)
        if result["status"] == "trained":
            trained += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"  SUMMARY: {trained} trained, {skipped} skipped")
    print(f"{'='*60}")
    for r in results:
        if r["status"] == "trained":
            print(f"  [OK]  {r['asset']:10s} {r['interval']:4s}  acc={r['accuracy']:.4f}  "
                  f"train={r['train_rows']:,}  test={r['test_rows']:,}")
        else:
            print(f"  [SKIP] {r['asset']:10s} {r['interval']:4s}  {r['reason']}")

    return results


if __name__ == "__main__":
    main()