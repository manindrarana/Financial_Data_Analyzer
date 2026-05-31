import json
import os
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
from sklearn.metrics import accuracy_score

DB_PATH = os.path.join("database", "financial_data.duckdb")
OUTPUT_DIR = os.path.join("backtesting", "results")

MODEL_FEATURES = [
    "rsi_14", "roc_10", "roc_20", "stoch_k", "stoch_d", "bb_percentage",
    "volume_ratio", "returns_1p", "returns_5p", "returns_10p", "returns_20p",
    "log_returns", "hl_ratio", "close_position",
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct", "atr_pct", "volatility_pct",
]

XGB_PARAMS = {
    "n_estimators": 100,
    "learning_rate": 0.05,
    "max_depth": 3,
    "subsample": 1.0,
    "eval_metric": "logloss",
    "random_state": 42,
}


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


def _load_data(asset="BTC", interval="1h"):
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
        raise RuntimeError(f"No data found for {asset} {interval}")

    df["date"] = pd.to_datetime(df["date"])
    return df


def _generate_folds(df, train_months=6, test_months=1, step_months=1):
    df = df.sort_values("date").reset_index(drop=True)
    min_date = df["date"].min()
    max_date = df["date"].max()

    folds = []
    current_start = min_date

    while True:
        train_end = current_start + pd.DateOffset(months=train_months)
        test_end = train_end + pd.DateOffset(months=test_months)

        if test_end > max_date:
            break

        train_mask = (df["date"] >= current_start) & (df["date"] < train_end)
        test_mask = (df["date"] >= train_end) & (df["date"] < test_end)

        train_df = df[train_mask]
        test_df = df[test_mask]

        if len(train_df) < 100 or len(test_df) < 20:
            current_start += pd.DateOffset(months=step_months)
            continue

        folds.append({
            "fold_id": len(folds) + 1,
            "train_start": current_start,
            "train_end": train_end,
            "test_start": train_end,
            "test_end": test_end,
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "train_df": train_df,
            "test_df": test_df,
        })

        current_start += pd.DateOffset(months=step_months)

    return folds


def _prepare_fold_data(train_df, test_df):
    train_df = _make_stationary(train_df)
    test_df = _make_stationary(test_df)

    train_df["target_direction"] = (train_df["close"].shift(-1) > train_df["close"]).astype(int)
    test_df["target_direction"] = (test_df["close"].shift(-1) > test_df["close"]).astype(int)

    train_df = train_df.dropna(subset=["target_direction"])
    test_df = test_df.dropna(subset=["target_direction"])

    available_feats = [f for f in MODEL_FEATURES if f in train_df.columns]

    X_train = train_df[available_feats].dropna()
    y_train = train_df.loc[X_train.index, "target_direction"]

    X_test = test_df[available_feats].dropna()
    y_test = test_df.loc[X_test.index, "target_direction"]

    return X_train, y_train, X_test, y_test, test_df.loc[X_test.index], available_feats


def run_walk_forward(asset="BTC", interval="1h", train_months=6, test_months=1, step_months=1):
    print(f"\n=== Walk-Forward Backtest: {asset} {interval} ===")
    print(f"   Train window: {train_months} months")
    print(f"   Test window:  {test_months} months")
    print(f"   Step:         {step_months} months\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("[1/4] Loading data from gold_crypto_features...")
    df = _load_data(asset, interval)
    print(f"   Loaded {len(df):,} rows ({df['date'].min().date()} to {df['date'].max().date()})")

    print("\n[2/4] Generating walk-forward folds...")
    folds = _generate_folds(df, train_months, test_months, step_months)
    print(f"   Created {len(folds)} folds")

    if len(folds) == 0:
        raise RuntimeError(f"Not enough data. Need at least {train_months + test_months} months.")

    all_predictions = []
    fold_summaries = []

    print("\n[3/4] Running folds...")
    for fold in folds:
        fid = fold["fold_id"]
        print(f"   Fold {fid}: train {fold['train_start'].date()} to {fold['train_end'].date()}"
              f" ({fold['train_rows']:,} rows)"
              f" | test {fold['test_start'].date()} to {fold['test_end'].date()}"
              f" ({fold['test_rows']:,} rows)")

        X_train, y_train, X_test, y_test, test_df_out, feats = _prepare_fold_data(
            fold["train_df"], fold["test_df"]
        )

        if len(X_train) == 0 or len(X_test) == 0:
            print(f"      SKIP: insufficient data after dropna")
            continue

        model = xgb.XGBClassifier(**XGB_PARAMS)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        probs = model.predict_proba(X_test)
        up_prob = probs[:, 1]
        confidence = np.where(y_pred == 1, up_prob, 1 - up_prob)

        fold_acc = accuracy_score(y_test, y_pred)

        predictions = test_df_out[["date", "close"]].copy()
        predictions["prediction"] = y_pred
        predictions["confidence"] = confidence
        predictions["actual_direction"] = y_test.values
        predictions["fold_id"] = fid
        predictions["train_start"] = fold["train_start"]
        predictions["train_end"] = fold["train_end"]
        predictions["test_start"] = fold["test_start"]
        predictions["test_end"] = fold["test_end"]

        all_predictions.append(predictions)

        fold_summaries.append({
            "fold_id": fid,
            "train_start": str(fold["train_start"].date()),
            "train_end": str(fold["train_end"].date()),
            "test_start": str(fold["test_start"].date()),
            "test_end": str(fold["test_end"].date()),
            "train_rows": fold["train_rows"],
            "test_rows": fold["test_rows"],
            "test_rows_after_dropna": len(X_test),
            "accuracy": round(fold_acc, 4),
            "features_used": feats,
        })

        print(f"      Accuracy: {fold_acc:.4f} ({fold_acc*100:.2f}%)")

    print("\n[4/4] Saving results...")
    combined = pd.concat(all_predictions, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)

    pred_path = os.path.join(OUTPUT_DIR, "walk_forward_predictions.parquet")
    combined.to_parquet(pred_path)
    print(f"   Predictions saved: {pred_path} ({len(combined):,} rows)")

    summary_path = os.path.join(OUTPUT_DIR, "walk_forward_summary.json")
    with open(summary_path, "w") as f:
        json.dump({
            "asset": asset,
            "interval": interval,
            "train_months": train_months,
            "test_months": test_months,
            "step_months": step_months,
            "total_folds": len(folds),
            "total_predictions": len(combined),
            "overall_accuracy": round(
                (combined["prediction"] == combined["actual_direction"]).mean(), 4
            ),
            "folds": fold_summaries,
        }, f, indent=2)
    print(f"   Summary saved: {summary_path}")

    overall_acc = (combined["prediction"] == combined["actual_direction"]).mean()
    print(f"\n=== Done ===")
    print(f"   Folds completed: {len(fold_summaries)}")
    print(f"   Total OOS predictions: {len(combined):,}")
    print(f"   Overall accuracy: {overall_acc:.4f} ({overall_acc*100:.2f}%)")

    return combined, fold_summaries


if __name__ == "__main__":
    run_walk_forward()