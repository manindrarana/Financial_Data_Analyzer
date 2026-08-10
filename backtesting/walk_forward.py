import json
import os
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "financial_data.duckdb")
OUTPUT_DIR = os.path.join("backtesting", "results")

XGB_PARAMS = {
    "subsample": 1.0,
    "eval_metric": "logloss",
    "random_state": 42,
}

XGB_PARAM_GRID = {
    "learning_rate": [0.01, 0.05, 0.1],
    "max_depth": [3, 5],
    "n_estimators": [100, 200],
}


def _tune_initial_parameters(X_train, y_train):
    search = GridSearchCV(
        estimator=xgb.XGBClassifier(**XGB_PARAMS),
        param_grid=XGB_PARAM_GRID,
        cv=TimeSeriesSplit(n_splits=2),
        scoring="accuracy",
        n_jobs=-1,
    )
    search.fit(X_train, y_train)
    return search.best_params_


def _load_data(asset="BTC", interval="1h", date_start=None, date_end=None, asset_class="crypto"):
    conn = duckdb.connect(DB_PATH, read_only=True)
    cols = NEEDED_COLS
    if asset_class.lower() != "crypto":
        cols = [c for c in NEEDED_COLS if c != "fear_greed"]
    col_list = ", ".join(cols)

    table = "gold_crypto_features" if asset_class.lower() == "crypto" else "gold_stock_features"

    query = f"""
        SELECT {col_list}
        FROM {table}
        WHERE asset_symbol = '{asset}' AND interval = '{interval}'
    """
    if date_start:
        query += f" AND date >= '{date_start}'"
    if date_end:
        query += f" AND date <= '{date_end}'"
    query += " ORDER BY date"

    df = conn.execute(query).df()
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
    train_df = make_stationary(train_df)
    test_df = make_stationary(test_df)

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


def run_walk_forward(asset="BTC", interval="1h", train_months=6, test_months=1, step_months=1, date_start=None, date_end=None, return_data=False, asset_class="crypto"):
    print(f"\n=== Walk-Forward Backtest: {asset} {interval} ===")
    print(f"   Train window: {train_months} months")
    print(f"   Test window:  {test_months} months")
    print(f"   Step:         {step_months} months")
    print(f"   Asset class:  {asset_class}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"[1/4] Loading data from gold_{asset_class}_features...")
    df = _load_data(asset, interval, date_start, date_end, asset_class)
    print(f"   Loaded {len(df):,} rows ({df['date'].min().date()} to {df['date'].max().date()})")

    print("\n[2/4] Generating walk-forward folds...")
    folds = _generate_folds(df, train_months, test_months, step_months)
    print(f"   Created {len(folds)} folds")

    if len(folds) == 0:
        raise RuntimeError(f"Not enough data. Need at least {train_months + test_months} months.")

    all_predictions = []
    fold_summaries = []
    selected_params = None

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

        if selected_params is None:
            print("      Tuning parameters on initial training window...")
            selected_params = _tune_initial_parameters(X_train, y_train)
            print(f"      Selected parameters: {selected_params}")

        model = xgb.XGBClassifier(**XGB_PARAMS, **selected_params)
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

    if return_data:
        overall_acc = (combined["prediction"] == combined["actual_direction"]).mean()
        summary = {
            "asset": asset,
            "interval": interval,
            "train_months": train_months,
            "test_months": test_months,
            "step_months": step_months,
            "selected_parameters": selected_params,
            "total_folds": len(folds),
            "total_predictions": len(combined),
            "overall_accuracy": round(overall_acc, 4),
            "folds": fold_summaries,
        }
        print(f"\n=== Done ===")
        print(f"   Folds completed: {len(fold_summaries)}")
        print(f"   Total OOS predictions: {len(combined):,}")
        print(f"   Overall accuracy: {overall_acc:.4f} ({overall_acc*100:.2f}%)")
        return combined, summary

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
            "selected_parameters": selected_params,
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


def run_walk_forward_pretrained(
    asset="BTC", interval="1h", train_months=6, test_months=1, step_months=1,
    date_start=None, date_end=None, return_data=False, asset_class="crypto",
):
    subdir = "crypto" if asset_class.lower() == "crypto" else "stocks"
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src", "models", subdir, f"{asset}_{interval}_xgboost_model.json",
    )
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"No pre-trained model found for {asset} {interval} at {model_path}. "
            f"Train it first with scripts/train_all_models.py"
        )

    print(f"\n=== Pre-trained Model Backtest: {asset} {interval} ===")
    print(f"   Model: {model_path}")
    print(f"   Train window: {train_months} months (used only for fold boundaries)")
    print(f"   Test window:  {test_months} months")
    print(f"   Step:         {step_months} months")
    print(f"   Asset class:  {asset_class}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"[1/4] Loading pre-trained model...")
    pt_model = xgb.XGBClassifier()
    pt_model.load_model(model_path)
    print(f"   Loaded from {model_path}")

    print(f"[2/4] Loading data from gold_{asset_class}_features...")
    df = _load_data(asset, interval, date_start, date_end, asset_class)
    print(f"   Loaded {len(df):,} rows ({df['date'].min().date()} to {df['date'].max().date()})")

    print("\n[3/4] Generating walk-forward folds...")
    folds = _generate_folds(df, train_months, test_months, step_months)
    print(f"   Created {len(folds)} folds")

    if len(folds) == 0:
        raise RuntimeError(f"Not enough data. Need at least {train_months + test_months} months.")

    all_predictions = []
    fold_summaries = []

    print("\n[4/4] Running pre-trained model on each fold...")
    for fold in folds:
        fid = fold["fold_id"]
        test_df = fold["test_df"]

        test_df = make_stationary(test_df)
        test_df["target_direction"] = (test_df["close"].shift(-1) > test_df["close"]).astype(int)
        test_df = test_df.dropna(subset=["target_direction"])

        available_feats = [f for f in MODEL_FEATURES if f in test_df.columns]
        X_test = test_df[available_feats].dropna()
        y_test = test_df.loc[X_test.index, "target_direction"]

        if len(X_test) < 20:
            print(f"   Fold {fid}: SKIP (only {len(X_test)} rows after dropna)")
            continue

        y_pred = pt_model.predict(X_test)
        probs = pt_model.predict_proba(X_test)
        up_prob = probs[:, 1]
        confidence = np.where(y_pred == 1, up_prob, 1 - up_prob)

        fold_acc = accuracy_score(y_test, y_pred)

        predictions = test_df.loc[X_test.index, ["date", "close"]].copy()
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
            "features_used": available_feats,
        })

        print(f"   Fold {fid}: {fold['test_start'].date()} to {fold['test_end'].date()}"
              f" ({len(X_test):,} rows) | Accuracy: {fold_acc:.4f} ({fold_acc*100:.2f}%)")

    if not all_predictions:
        raise RuntimeError("No folds produced valid predictions. Check date range and data.")

    combined = pd.concat(all_predictions, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)

    overall_acc = (combined["prediction"] == combined["actual_direction"]).mean()
    summary = {
        "asset": asset,
        "interval": interval,
        "model_path": model_path,
        "train_months": train_months,
        "test_months": test_months,
        "step_months": step_months,
        "total_folds": len(fold_summaries),
        "total_predictions": len(combined),
        "overall_accuracy": round(overall_acc, 4),
        "folds": fold_summaries,
    }

    print(f"\n=== Done ===")
    print(f"   Folds completed: {len(fold_summaries)}")
    print(f"   Total OOS predictions: {len(combined):,}")
    print(f"   Overall accuracy: {overall_acc:.4f} ({overall_acc*100:.2f}%)")

    if return_data:
        return combined, summary

    pred_path = os.path.join(OUTPUT_DIR, "walk_forward_predictions_pretrained.parquet")
    combined.to_parquet(pred_path)
    print(f"   Predictions saved: {pred_path}")

    summary_path = os.path.join(OUTPUT_DIR, "walk_forward_summary_pretrained.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"   Summary saved: {summary_path}")

    return combined, fold_summaries


def run_portfolio_backtest(
    assets,
    interval="1h",
    train_months=6,
    test_months=1,
    step_months=1,
    date_start=None,
    date_end=None,
    mode="walk_forward",
    asset_class="crypto",
):
    if not assets or len(assets) < 2:
        raise ValueError("Portfolio backtest requires at least 2 assets")

    print(f"\n=== Portfolio Walk-Forward Backtest ===")
    print(f"   Assets: {assets}")
    print(f"   Interval: {interval}")
    print(f"   Mode: {mode}")
    print(f"   Asset class: {asset_class}\n")

    predictions_dict = {}
    summaries = {}

    for idx, asset in enumerate(assets, 1):
        print(f"\n[{idx}/{len(assets)}] Processing {asset}...")

        if mode == "pretrained":
            preds, summary = run_walk_forward_pretrained(
                asset=asset,
                interval=interval,
                train_months=train_months,
                test_months=test_months,
                step_months=step_months,
                date_start=date_start,
                date_end=date_end,
                return_data=True,
                asset_class=asset_class,
            )
        else:
            preds, summary = run_walk_forward(
                asset=asset,
                interval=interval,
                train_months=train_months,
                test_months=test_months,
                step_months=step_months,
                date_start=date_start,
                date_end=date_end,
                return_data=True,
                asset_class=asset_class,
            )

        if preds.empty:
            print(f"   WARNING: No predictions for {asset}, skipping")
            continue

        predictions_dict[asset] = preds
        summaries[asset] = summary

    if len(predictions_dict) < 2:
        raise RuntimeError(
            f"Only {len(predictions_dict)} asset(s) produced predictions. "
            f"Need at least 2 for portfolio backtest."
        )

    print(f"\n=== Portfolio Predictions Complete ===")
    print(f"   Assets with predictions: {list(predictions_dict.keys())}")
    for asset, preds in predictions_dict.items():
        acc = (preds["prediction"] == preds["actual_direction"]).mean()
        print(f"   {asset}: {len(preds):,} predictions, accuracy {acc:.4f}")

    return predictions_dict, summaries


if __name__ == "__main__":
    run_walk_forward()