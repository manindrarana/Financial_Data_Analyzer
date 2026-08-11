import argparse
import os

import duckdb
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary


TREND_FEATURES = [
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct",
]
MOMENTUM_FEATURES = [
    "rsi_14", "roc_10", "roc_20", "stoch_k", "stoch_d",
    "returns_1p", "returns_5p", "returns_10p", "returns_20p", "log_returns",
]
VOLATILITY_FEATURES = [
    "bb_percentage", "atr_pct", "volatility_pct", "hl_ratio", "close_position",
]
VOLUME_FEATURES = ["volume_ratio"]
FEAR_GREED_FEATURES = ["fear_greed"]
PARAM_GRID = {
    "learning_rate": [0.01, 0.05, 0.1],
    "max_depth": [3, 5],
    "n_estimators": [100, 200],
}
TABLES = {
    "crypto": "gold_crypto_features",
    "stocks": "gold_stock_features",
}


def build_feature_sets():
    return {
        "baseline": MODEL_FEATURES.copy(),
        "without_trend": [
            feature for feature in MODEL_FEATURES if feature not in TREND_FEATURES
        ],
        "without_momentum": [
            feature for feature in MODEL_FEATURES if feature not in MOMENTUM_FEATURES
        ],
        "without_volatility": [
            feature for feature in MODEL_FEATURES if feature not in VOLATILITY_FEATURES
        ],
        "without_volume": [
            feature for feature in MODEL_FEATURES if feature not in VOLUME_FEATURES
        ],
        "without_fear_greed": [
            feature for feature in MODEL_FEATURES if feature not in FEAR_GREED_FEATURES
        ],
    }


def calculate_baseline_differences(results):
    if not results:
        return []

    baseline = next(
        result["balanced_accuracy"]
        for result in results
        if result["experiment"] == "baseline"
    )
    compared = []
    for result in results:
        row = result.copy()
        row["balanced_accuracy_difference"] = row["balanced_accuracy"] - baseline
        compared.append(row)
    return compared


def load_data(db_path, asset, interval, asset_class):
    columns = NEEDED_COLS
    if asset_class == "stocks":
        columns = [column for column in NEEDED_COLS if column != "fear_greed"]
    table = TABLES[asset_class]
    connection = duckdb.connect(db_path, read_only=True)
    try:
        return connection.execute(
            f"""
            SELECT {", ".join(columns)}
            FROM {table}
            WHERE asset_symbol = ? AND interval = ?
            ORDER BY date
            """,
            [asset, interval],
        ).df()
    finally:
        connection.close()


def prepare_data(df):
    if df.empty:
        raise ValueError("no feature data found for the selected asset and interval")

    prepared = make_stationary(df)
    prepared["date"] = pd.to_datetime(prepared["date"])
    prepared["target_direction"] = (
        prepared["close"].shift(-1) > prepared["close"]
    ).astype(int)
    return prepared.iloc[:-1].copy()


def split_data(df, features):
    split_index = int(len(df) * 0.8)
    train_df = df.iloc[:split_index]
    test_df = df.iloc[split_index:]
    available_features = [feature for feature in features if feature in df.columns]
    if not available_features:
        raise ValueError("no selected model features are available")

    train = train_df[available_features + ["target_direction"]].dropna()
    test = test_df[available_features + ["target_direction"]].dropna()
    if len(train) < 100 or len(test) < 20:
        raise ValueError(
            f"insufficient complete rows after preprocessing: train={len(train)}, test={len(test)}"
        )

    return (
        train[available_features],
        train["target_direction"],
        test[available_features],
        test["target_direction"],
        available_features,
    )


def run_experiment(experiment, features, df):
    X_train, y_train, X_test, y_test, available_features = split_data(df, features)
    search = GridSearchCV(
        xgb.XGBClassifier(
            subsample=1.0,
            eval_metric="logloss",
            random_state=42,
        ),
        PARAM_GRID,
        cv=TimeSeriesSplit(n_splits=2),
        scoring="balanced_accuracy",
        n_jobs=-1,
        verbose=0,
    )
    search.fit(X_train, y_train)
    predictions = search.best_estimator_.predict(X_test)
    removed_features = [
        feature for feature in MODEL_FEATURES if feature not in features
    ]

    return {
        "experiment": experiment,
        "removed_features": ",".join(removed_features),
        "feature_count": len(available_features),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "accuracy": accuracy_score(y_test, predictions),
        "balanced_accuracy": balanced_accuracy_score(y_test, predictions),
        "precision": precision_score(y_test, predictions, zero_division=0),
        "recall": recall_score(y_test, predictions, zero_division=0),
        "f1": f1_score(y_test, predictions, zero_division=0),
        "best_cv_score": search.best_score_,
        "learning_rate": search.best_params_["learning_rate"],
        "max_depth": search.best_params_["max_depth"],
        "n_estimators": search.best_params_["n_estimators"],
    }


def run_feature_ablation(db_path, asset, interval, asset_class, output_path):
    prepared = prepare_data(load_data(db_path, asset, interval, asset_class))
    feature_sets = build_feature_sets()
    if asset_class == "stocks":
        feature_sets.pop("without_fear_greed")

    results = []
    for experiment, features in feature_sets.items():
        print(f"running {experiment} with {len(features)} features")
        results.append(run_experiment(experiment, features, prepared))

    compared = calculate_baseline_differences(results)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    pd.DataFrame(compared).to_csv(output_path, index=False)
    return compared


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default=os.path.join("database", "financial_data.duckdb"))
    parser.add_argument("--asset", default="BTC")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--asset-class", choices=TABLES, default="crypto")
    parser.add_argument(
        "--output",
        default=os.path.join("reports", "feature_ablation_results.csv"),
    )
    args = parser.parse_args()
    results = run_feature_ablation(
        args.db_path,
        args.asset,
        args.interval,
        args.asset_class,
        args.output,
    )
    print(pd.DataFrame(results).to_string(index=False))
    print(f"saved results to {args.output}")


if __name__ == "__main__":
    main()
