import json
import os
from datetime import datetime, timezone

import duckdb
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, balanced_accuracy_score

from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary

DB_PATH = os.path.join("database", "financial_data.duckdb")
RESULT_PATH = os.path.join(
    "scripts", "results", "btc_1h_4h_multitimeframe_comparison.json"
)
INTERVAL_HOURS = {"1h": 1, "4h": 4}


def load_interval_data(interval, db_path=DB_PATH):
    columns = ", ".join(NEEDED_COLS)
    connection = duckdb.connect(db_path, read_only=True)
    try:
        return connection.execute(
            f"""
            SELECT {columns}
            FROM gold_crypto_features
            WHERE asset_symbol = 'BTC' AND interval = ?
            ORDER BY date
            """,
            [interval],
        ).df()
    finally:
        connection.close()


def prepare_interval_data(df, interval):
    if interval not in INTERVAL_HOURS:
        raise ValueError(f"Unsupported interval: {interval}")
    if df.empty:
        raise RuntimeError(f"No BTC {interval} data found in gold_crypto_features")

    prepared = make_stationary(df.copy())
    prepared["date"] = pd.to_datetime(prepared["date"], utc=True)
    prepared["available_at"] = prepared["date"] + pd.Timedelta(
        hours=INTERVAL_HOURS[interval]
    )
    features = [feature for feature in MODEL_FEATURES if feature in prepared.columns]
    if not features:
        raise RuntimeError(f"No BTC {interval} model features are available")

    prepared = prepared.dropna(subset=features).sort_values("available_at")
    return prepared[["date", "available_at", "close"] + features], features


def build_paired_dataset(one_hour_df, four_hour_df):
    one_hour, one_hour_features = prepare_interval_data(one_hour_df, "1h")
    four_hour, four_hour_features = prepare_interval_data(four_hour_df, "4h")

    next_four_hour_close = four_hour["close"].shift(-1)
    four_hour = four_hour.loc[next_four_hour_close.notna()].copy()
    four_hour["target_direction"] = (
        next_four_hour_close.loc[four_hour.index] > four_hour["close"]
    ).astype(int)

    one_hour_columns = ["available_at"] + one_hour_features
    paired = pd.merge_asof(
        four_hour.sort_values("available_at"),
        one_hour[one_hour_columns].sort_values("available_at"),
        on="available_at",
        direction="backward",
        allow_exact_matches=True,
        suffixes=("_4h", "_1h"),
    )

    one_hour_feature_columns = [
        f"{feature}_1h" if feature in four_hour_features else feature
        for feature in one_hour_features
    ]
    four_hour_feature_columns = [
        f"{feature}_4h" if feature in one_hour_features else feature
        for feature in four_hour_features
    ]
    paired = paired.dropna(
        subset=one_hour_feature_columns
        + four_hour_feature_columns
        + ["target_direction"]
    )
    if len(paired) < 2:
        raise RuntimeError("Not enough overlapping BTC 1h and 4h rows")

    return paired, one_hour_feature_columns, four_hour_feature_columns


def chronological_split(paired):
    split_index = int(len(paired) * 0.8)
    if split_index == 0 or split_index == len(paired):
        raise RuntimeError("Not enough paired rows for the chronological split")
    return paired.iloc[:split_index], paired.iloc[split_index:]


def build_model():
    return xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=3,
        subsample=1.0,
        eval_metric="logloss",
        random_state=42,
    )


def calculate_metrics(y_true, probabilities):
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "coverage": 1.0,
    }


def compare_timeframes(train_df, test_df, one_hour_features, four_hour_features):
    y_train = train_df["target_direction"]
    y_test = test_df["target_direction"]

    one_hour_model = build_model()
    four_hour_model = build_model()
    one_hour_model.fit(train_df[one_hour_features], y_train)
    four_hour_model.fit(train_df[four_hour_features], y_train)

    one_hour_probabilities = one_hour_model.predict_proba(
        test_df[one_hour_features]
    )[:, 1]
    four_hour_probabilities = four_hour_model.predict_proba(
        test_df[four_hour_features]
    )[:, 1]
    ensemble_probabilities = (one_hour_probabilities + four_hour_probabilities) / 2

    results = {
        "1h": calculate_metrics(y_test, one_hour_probabilities),
        "4h": calculate_metrics(y_test, four_hour_probabilities),
        "ensemble": calculate_metrics(y_test, ensemble_probabilities),
    }
    best_individual = max(
        results["1h"]["balanced_accuracy"],
        results["4h"]["balanced_accuracy"],
    )
    results["ensemble"]["difference_from_best_individual"] = (
        results["ensemble"]["balanced_accuracy"] - best_individual
    )
    return results


def save_results(payload, result_path=RESULT_PATH):
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    temporary_path = f"{result_path}.tmp"
    with open(temporary_path, "w", encoding="utf-8") as result_file:
        json.dump(payload, result_file, indent=2)
    os.replace(temporary_path, result_path)


def refresh_multitimeframe_comparison(db_path=DB_PATH, result_path=RESULT_PATH):
    one_hour_df = load_interval_data("1h", db_path)
    four_hour_df = load_interval_data("4h", db_path)
    paired, one_hour_features, four_hour_features = build_paired_dataset(
        one_hour_df, four_hour_df
    )
    train_df, test_df = chronological_split(paired)
    results = compare_timeframes(
        train_df, test_df, one_hour_features, four_hour_features
    )
    payload = {
        "asset": "BTC",
        "intervals": ["1h", "4h"],
        "target": "next_4h_direction",
        "ensemble_method": "mean_probability",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_data_end_date": max(
            pd.to_datetime(one_hour_df["date"], utc=True).max(),
            pd.to_datetime(four_hour_df["date"], utc=True).max(),
        ).isoformat(),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "test_start_date": test_df["available_at"].min().isoformat(),
        "test_end_date": test_df["available_at"].max().isoformat(),
        "models": results,
    }
    save_results(payload, result_path)
    return payload


def main():
    payload = refresh_multitimeframe_comparison()
    print("BTC 1h and 4h multi-timeframe comparison")
    for name, metrics in payload["models"].items():
        print(
            f"{name}: accuracy={metrics['accuracy']:.4f}, "
            f"balanced_accuracy={metrics['balanced_accuracy']:.4f}, "
            f"coverage={metrics['coverage']:.4f}"
        )
    print(f"Results saved to {RESULT_PATH}")


if __name__ == "__main__":
    main()
