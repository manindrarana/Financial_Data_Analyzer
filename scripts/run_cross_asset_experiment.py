import duckdb
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtesting.metrics import compute_metrics
from backtesting.strategy import simulate_trades
from scripts.run_funding_rate_experiment import (
    compare_variant_significance,
    wilson_accuracy_interval,
)
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary


PARAM_GRID = {
    "learning_rate": [0.01, 0.05, 0.1],
    "max_depth": [3, 5],
    "n_estimators": [100, 200],
}
COST_AWARE_SETTINGS = {
    "confidence_threshold": 0.52,
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.04,
    "max_hold_bars": 24,
    "initial_capital": 10000,
    "transaction_cost_pct": 0.001,
}
CROSS_ASSET_COLUMNS = [
    "eth_btc_relative_return",
    "tracked_crypto_market_return",
    "tracked_crypto_market_breadth",
    "cross_asset_volatility",
    "market_asset_count",
]
EXPERIMENT_FEATURES = [
    "eth_btc_relative_return",
    "tracked_crypto_market_return",
    "tracked_crypto_market_breadth",
    "cross_asset_volatility",
]
RESULT_COLUMNS = [
    "date",
    "asset_symbol",
    "interval",
    "close",
    *CROSS_ASSET_COLUMNS,
]


def load_crypto_candles(db_path, interval):
    connection = duckdb.connect(db_path, read_only=True)
    try:
        return connection.execute(
            """
            SELECT date, asset_symbol, interval, close
            FROM gold_crypto_features
            WHERE interval = ?
            ORDER BY date, asset_symbol
            """,
            [interval],
        ).df()
    finally:
        connection.close()


def load_target_features(db_path, asset, interval):
    connection = duckdb.connect(db_path, read_only=True)
    try:
        columns = ", ".join(NEEDED_COLS)
        return connection.execute(
            f"""
            SELECT {columns}
            FROM gold_crypto_features
            WHERE asset_symbol = ? AND interval = ?
            ORDER BY date
            """,
            [asset, interval],
        ).df()
    finally:
        connection.close()


def prepare_target_features(df):
    if df.empty:
        raise ValueError("no target feature data found")

    prepared = make_stationary(df)
    prepared["date"] = pd.to_datetime(prepared["date"])
    prepared["target_direction"] = (
        prepared["close"].shift(-1) > prepared["close"]
    ).astype(int)
    prepared = prepared.iloc[:-1].copy()
    return prepared.dropna(subset=MODEL_FEATURES).copy()


def merge_cross_asset_features(target_df, cross_asset_df):
    if target_df.empty:
        return target_df.copy()

    merged = target_df.merge(
        cross_asset_df[["date", *EXPERIMENT_FEATURES]],
        on="date",
        how="inner",
        validate="one_to_one",
    )
    return merged.dropna(subset=EXPERIMENT_FEATURES).copy()


def prepare_experiment_dataset(db_path, asset, interval, min_market_assets=5):
    target = prepare_target_features(load_target_features(db_path, asset, interval))
    candles = load_crypto_candles(db_path, interval)
    cross_asset = build_cross_asset_features(
        candles,
        asset,
        interval,
        min_market_assets=min_market_assets,
    )
    return merge_cross_asset_features(target, cross_asset).sort_values("date").reset_index(
        drop=True
    )


def split_experiment_data(df, features):
    if df.empty:
        raise ValueError("no complete experiment rows found")

    split_index = int(len(df) * 0.8)
    train = df.iloc[:split_index]
    test = df.iloc[split_index:]
    if len(train) < 100 or len(test) < 20:
        raise ValueError(
            f"insufficient experiment rows: train={len(train)}, test={len(test)}"
        )

    return (
        train[features],
        train["target_direction"],
        test[features],
        test["target_direction"],
        test["date"],
    )


def train_experiment_model(X_train, y_train):
    search = GridSearchCV(
        xgb.XGBClassifier(
            subsample=1.0,
            eval_metric="logloss",
            random_state=42,
        ),
        PARAM_GRID,
        cv=TimeSeriesSplit(n_splits=2),
        scoring="balanced_accuracy",
        n_jobs=1,
        verbose=0,
    )
    search.fit(X_train, y_train)
    return search


def evaluate_experiment_model(search, X_test, y_test):
    probabilities = search.best_estimator_.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, predictions)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "best_cv_score": float(search.best_score_),
        "best_params": dict(search.best_params_),
        "predictions": predictions,
        "probabilities": probabilities,
    }


def backtest_variant_costs(test_predictions, variant, interval):
    prediction = test_predictions[f"{variant}_prediction"].astype(int)
    up_probability = test_predictions[f"{variant}_up_probability"].astype(float)
    confidence = np.where(prediction == 1, up_probability, 1 - up_probability)
    frame = pd.DataFrame(
        {
            "date": test_predictions["date"],
            "close": test_predictions["close"],
            "prediction": prediction,
            "confidence": confidence,
        }
    )
    trades, equity = simulate_trades(frame, **COST_AWARE_SETTINGS)
    return compute_metrics(
        trades,
        equity,
        initial_capital=COST_AWARE_SETTINGS["initial_capital"],
        interval=interval,
        asset_class="crypto",
    )


def compare_experiment_variants(
    db_path,
    asset="BTC",
    interval="1h",
    min_market_assets=5,
):
    dataset = prepare_experiment_dataset(
        db_path,
        asset,
        interval,
        min_market_assets=min_market_assets,
    )
    baseline_split = split_experiment_data(dataset, MODEL_FEATURES)
    cross_asset_split = split_experiment_data(
        dataset,
        [*MODEL_FEATURES, *EXPERIMENT_FEATURES],
    )

    prediction_data = {
        "date": baseline_split[4].to_numpy(),
        "close": dataset.set_index("date").loc[baseline_split[4], "close"].to_numpy(),
        "actual_direction": baseline_split[3].to_numpy(),
    }
    variants = {
        "baseline": {
            "features": list(MODEL_FEATURES),
            "split": baseline_split,
        },
        "cross_asset": {
            "features": [*MODEL_FEATURES, *EXPERIMENT_FEATURES],
            "split": cross_asset_split,
        },
    }

    for name, variant in variants.items():
        search = train_experiment_model(variant["split"][0], variant["split"][1])
        evaluation = evaluate_experiment_model(
            search,
            variant["split"][2],
            variant["split"][3],
        )
        prediction_data[f"{name}_prediction"] = evaluation.pop("predictions")
        prediction_data[f"{name}_up_probability"] = evaluation.pop("probabilities")
        variant["metrics"] = evaluation

    actual = prediction_data["actual_direction"]
    baseline_predictions = prediction_data["baseline_prediction"]
    for name, variant in variants.items():
        if name == "baseline":
            variant["metrics"]["significance"] = {
                "difference": 0.0,
                "difference_interval": [0.0, 0.0],
                "model_only": 0,
                "baseline_only": 0,
                "mcnemar_p_value": 1.0,
                "model_accuracy_interval": wilson_accuracy_interval(
                    int(np.sum(baseline_predictions == actual)),
                    len(actual),
                ),
                "baseline_accuracy_interval": wilson_accuracy_interval(
                    int(np.sum(baseline_predictions == actual)),
                    len(actual),
                ),
            }
        else:
            variant["metrics"]["significance"] = compare_variant_significance(
                prediction_data[f"{name}_prediction"],
                baseline_predictions,
                actual,
            )

    test_predictions = pd.DataFrame(prediction_data)
    for name, variant in variants.items():
        variant["metrics"]["cost_aware"] = backtest_variant_costs(
            test_predictions,
            name,
            interval,
        )

    return {
        "asset": asset,
        "interval": interval,
        "total_rows": len(dataset),
        "train_rows": len(baseline_split[0]),
        "test_rows": len(baseline_split[2]),
        "train_start": dataset["date"].iloc[0],
        "train_end": dataset["date"].iloc[len(baseline_split[0]) - 1],
        "test_start": baseline_split[4].iloc[0],
        "test_end": baseline_split[4].iloc[-1],
        "baseline_features": list(MODEL_FEATURES),
        "cross_asset_features": list(EXPERIMENT_FEATURES),
        "variants": {
            name: {
                "features": variant["features"],
                **variant["metrics"],
            }
            for name, variant in variants.items()
        },
        "test_predictions": test_predictions,
    }


def save_experiment_results(result, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    predictions = result["test_predictions"].copy()
    predictions["date"] = pd.to_datetime(predictions["date"]).dt.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    predictions_path = output_path / "test_predictions.csv"
    predictions.to_csv(predictions_path, index=False)

    metadata = {
        key: value
        for key, value in result.items()
        if key != "test_predictions"
    }
    for key in ["train_start", "train_end", "test_start", "test_end"]:
        metadata[key] = pd.Timestamp(metadata[key]).isoformat()
    metadata_path = output_path / "comparison.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, default=lambda value: value.item()),
        encoding="utf-8",
    )
    return {"metadata": metadata_path, "predictions": predictions_path}


def compare_multiple_cross_asset_variants(
    db_path,
    assets=("BTC", "ETH", "SOL"),
    intervals=("1h", "4h"),
    min_market_assets=5,
):
    results = []
    skipped = []
    for asset in assets:
        for interval in intervals:
            try:
                result = compare_experiment_variants(
                    db_path,
                    asset=asset,
                    interval=interval,
                    min_market_assets=min_market_assets,
                )
            except ValueError as error:
                skipped.append(
                    {"asset": asset, "interval": interval, "reason": str(error)}
                )
                continue

            for variant, metrics in result["variants"].items():
                cost_aware = metrics["cost_aware"]
                results.append(
                    {
                        "asset": asset,
                        "interval": interval,
                        "variant": variant,
                        "total_rows": result["total_rows"],
                        "train_rows": result["train_rows"],
                        "test_rows": result["test_rows"],
                        "train_start": result["train_start"],
                        "test_start": result["test_start"],
                        "test_end": result["test_end"],
                        "accuracy": metrics["accuracy"],
                        "balanced_accuracy": metrics["balanced_accuracy"],
                        "f1": metrics["f1"],
                        "accuracy_difference_from_baseline": (
                            metrics["accuracy"]
                            - result["variants"]["baseline"]["accuracy"]
                        ),
                        "significance_difference": metrics["significance"][
                            "difference"
                        ],
                        "significance_interval_low": metrics["significance"][
                            "difference_interval"
                        ][0],
                        "significance_interval_high": metrics["significance"][
                            "difference_interval"
                        ][1],
                        "mcnemar_p_value": metrics["significance"][
                            "mcnemar_p_value"
                        ],
                        "model_only": metrics["significance"]["model_only"],
                        "baseline_only": metrics["significance"]["baseline_only"],
                        "cost_aware_total_return_pct": cost_aware[
                            "total_return_pct"
                        ],
                        "cost_aware_total_pnl": cost_aware["total_pnl"],
                        "cost_aware_total_cost": cost_aware["total_cost"],
                        "cost_aware_sharpe_ratio": cost_aware["sharpe_ratio"],
                        "cost_aware_volatility_pct": cost_aware[
                            "volatility_pct"
                        ],
                        "cost_aware_max_drawdown_pct": cost_aware[
                            "max_drawdown_pct"
                        ],
                        "cost_aware_win_rate": cost_aware["win_rate"],
                        "cost_aware_profit_factor": cost_aware["profit_factor"],
                        "cost_aware_total_trades": cost_aware["total_trades"],
                    }
                )

    return {
        "results": pd.DataFrame(results),
        "skipped": skipped,
    }


def save_multiple_experiment_results(result, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results = result["results"].copy()
    for column in ["train_start", "test_start", "test_end"]:
        if column in results:
            results[column] = pd.to_datetime(results[column]).dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
    results_path = output_path / "multi_asset_interval_comparison.csv"
    results.to_csv(results_path, index=False)

    skipped_path = output_path / "multi_asset_interval_skipped.json"
    skipped_path.write_text(
        json.dumps(result["skipped"], indent=2),
        encoding="utf-8",
    )
    return {"results": results_path, "skipped": skipped_path}


def run_experiment(
    db_path,
    output_dir="reports/cross_asset/experiment",
    assets=("BTC", "ETH", "SOL"),
    intervals=("1h", "4h"),
):
    result = compare_multiple_cross_asset_variants(db_path, assets, intervals)
    paths = save_multiple_experiment_results(result, output_dir)
    for row in result["skipped"]:
        print(f"skipped {row['asset']} {row['interval']}: {row['reason']}")
    print(f"results saved: {paths['results']}")
    print(f"skipped saved: {paths['skipped']}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="compare cross-asset variants with significance tests and cost-aware backtests"
    )
    parser.add_argument("db_path")
    parser.add_argument(
        "--output-dir", default="reports/cross_asset/experiment"
    )
    parser.add_argument("--assets", nargs="+", default=["BTC", "ETH", "SOL"])
    parser.add_argument("--intervals", nargs="+", default=["1h", "4h"])
    arguments = parser.parse_args()
    run_experiment(
        arguments.db_path,
        arguments.output_dir,
        tuple(arguments.assets),
        tuple(arguments.intervals),
    )


def calculate_asset_returns(candles):
    if candles.empty:
        return candles.assign(asset_return=pd.Series(dtype=float))

    prepared = candles.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    prepared = prepared.sort_values(["asset_symbol", "date"])
    prepared["asset_return"] = prepared.groupby(
        ["asset_symbol", "interval"],
        sort=False,
    )["close"].pct_change(fill_method=None)
    return prepared


def build_cross_asset_features(candles, target_asset, interval, min_market_assets=5):
    if candles.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    returns = calculate_asset_returns(
        candles.loc[candles["interval"] == interval].copy()
    )
    target_rows = returns.loc[
        returns["asset_symbol"] == target_asset,
        ["date", "asset_symbol", "interval", "close"],
    ].copy()
    market_rows = returns.loc[returns["asset_symbol"] != target_asset].copy()

    market = market_rows.groupby("date")["asset_return"].agg(
        tracked_crypto_market_return="mean",
        tracked_crypto_market_breadth=lambda values: (values.dropna() > 0).mean(),
        cross_asset_volatility=lambda values: values.std(ddof=0),
        market_asset_count="count",
    )
    insufficient = market["market_asset_count"] < min_market_assets
    market.loc[
        insufficient,
        [
            "tracked_crypto_market_return",
            "tracked_crypto_market_breadth",
            "cross_asset_volatility",
        ],
    ] = np.nan

    relative_returns = returns.loc[
        returns["asset_symbol"].isin(["BTC", "ETH"]),
        ["date", "asset_symbol", "asset_return"],
    ].pivot(index="date", columns="asset_symbol", values="asset_return")
    if {"BTC", "ETH"}.issubset(relative_returns.columns):
        relative_returns["eth_btc_relative_return"] = (
            relative_returns["ETH"] - relative_returns["BTC"]
        )
    else:
        relative_returns["eth_btc_relative_return"] = np.nan

    result = target_rows.merge(market, on="date", how="left")
    result["market_asset_count"] = result["market_asset_count"].fillna(0).astype(int)
    result = result.merge(
        relative_returns[["eth_btc_relative_return"]],
        on="date",
        how="left",
    )
    return result[RESULT_COLUMNS].sort_values("date").reset_index(drop=True)
