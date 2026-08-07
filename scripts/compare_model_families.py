import json
import os
from datetime import datetime, timezone

import duckdb
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary

DB_PATH = os.path.join("database", "financial_data.duckdb")
RESULT_PATH = os.path.join(
    "scripts", "results", "btc_1h_model_family_comparison.json"
)


def load_btc_1h_data(db_path=DB_PATH):
    columns = ", ".join(NEEDED_COLS)
    connection = duckdb.connect(db_path, read_only=True)
    try:
        return connection.execute(
            f"""
            SELECT {columns}
            FROM gold_crypto_features
            WHERE asset_symbol = 'BTC' AND interval = '1h'
            ORDER BY date
            """
        ).df()
    finally:
        connection.close()


def prepare_data(df):
    if df.empty:
        raise RuntimeError("No BTC 1h data found in gold_crypto_features")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = make_stationary(df)
    next_close = df["close"].shift(-1)
    df["target_direction"] = (next_close > df["close"]).astype(int)
    df = df.loc[next_close.notna()]

    features = [feature for feature in MODEL_FEATURES if feature in df.columns]
    if not features:
        raise RuntimeError("No model features are available")

    df = df.dropna(subset=features + ["target_direction"])
    split_index = int(len(df) * 0.8)
    if split_index == 0 or split_index == len(df):
        raise RuntimeError("Not enough rows for the chronological split")

    train_df = df.iloc[:split_index]
    test_df = df.iloc[split_index:]
    return (
        train_df[features],
        test_df[features],
        train_df["target_direction"],
        test_df["target_direction"],
        train_df,
        test_df,
        features,
    )


def build_models():
    return {
        "xgboost": xgb.XGBClassifier(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=3,
            subsample=1.0,
            eval_metric="logloss",
            random_state=42,
        ),
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, random_state=42),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=10,
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=42,
        ),
    }


def calculate_metrics(y_true, y_pred):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def compare_models(X_train, X_test, y_train, y_test):
    results = {}
    for name, model in build_models().items():
        model.fit(X_train, y_train)
        results[name] = calculate_metrics(y_test, model.predict(X_test))
    return results


def build_conclusion(results):
    scores = {
        name: metrics["balanced_accuracy"] for name, metrics in results.items()
    }
    best_model = max(scores, key=scores.get)
    difference = max(scores.values()) - min(scores.values())
    if difference <= 0.01:
        return (
            "The models perform similarly, suggesting that the available data "
            "is the main limitation."
        )
    return (
        f"{best_model.replace('_', ' ').title()} performs best, suggesting that "
        "the model family affects the result."
    )


def save_results(payload, result_path=RESULT_PATH):
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as result_file:
        json.dump(payload, result_file, indent=2)


def refresh_comparison(db_path=DB_PATH, result_path=RESULT_PATH):
    df = load_btc_1h_data(db_path)
    X_train, X_test, y_train, y_test, train_df, test_df, features = prepare_data(df)
    results = compare_models(X_train, X_test, y_train, y_test)
    payload = {
        "asset": "BTC",
        "interval": "1h",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_data_end_date": df["date"].max().isoformat(),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "train_start_date": train_df["date"].min().isoformat(),
        "train_end_date": train_df["date"].max().isoformat(),
        "test_start_date": test_df["date"].min().isoformat(),
        "test_end_date": test_df["date"].max().isoformat(),
        "features": features,
        "models": results,
        "conclusion": build_conclusion(results),
    }
    save_results(payload, result_path)
    return payload


def main():
    payload = refresh_comparison()

    print("BTC 1h model family comparison")
    for name, metrics in payload["models"].items():
        print(
            f"{name}: accuracy={metrics['accuracy']:.4f}, "
            f"balanced_accuracy={metrics['balanced_accuracy']:.4f}, "
            f"f1={metrics['f1_score']:.4f}"
        )
    print(payload["conclusion"])
    print(f"Results saved to {RESULT_PATH}")


if __name__ == "__main__":
    main()
