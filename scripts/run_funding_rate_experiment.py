import json
import math
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    matthews_corrcoef,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtesting.metrics import compute_metrics
from backtesting.strategy import simulate_trades
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
RAW_FUNDING_FEATURES = ["funding_rate"]
DERIVED_FUNDING_FEATURES = [
    "funding_rate_change",
    "funding_rate_rolling_mean",
    "funding_rate_zscore",
    "hours_since_funding_change",
]
VARIANT_FEATURES = {
    "baseline": list(MODEL_FEATURES),
    "raw_funding": [*MODEL_FEATURES, *RAW_FUNDING_FEATURES],
    "derived_funding": [
        *MODEL_FEATURES,
        *RAW_FUNDING_FEATURES,
        *DERIVED_FUNDING_FEATURES,
    ],
}


def load_crypto_features(db_path, asset, interval):
    connection = duckdb.connect(db_path, read_only=True)
    try:
        columns = ", ".join([*NEEDED_COLS, "funding_rate"])
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


def build_funding_features(df):
    if df.empty:
        return df.copy()

    prepared = df.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    prepared["funding_rate"] = pd.to_numeric(
        prepared["funding_rate"], errors="coerce"
    )
    prepared["funding_rate_change"] = prepared["funding_rate"].diff()
    prepared["funding_rate_rolling_mean"] = prepared["funding_rate"].rolling(
        window=30, min_periods=5
    ).mean()
    rolling_std = prepared["funding_rate"].rolling(window=30, min_periods=5).std()
    prepared["funding_rate_zscore"] = (
        prepared["funding_rate"] - prepared["funding_rate_rolling_mean"]
    ) / rolling_std.replace(0, np.nan)

    changed = prepared["funding_rate"].ne(prepared["funding_rate"].shift())
    last_change = prepared["date"].where(changed).ffill()
    prepared["hours_since_funding_change"] = (
        prepared["date"] - last_change
    ).dt.total_seconds() / 3600
    return prepared


def prepare_experiment_dataset(df):
    if df.empty:
        raise ValueError("no crypto feature data found")

    prepared = make_stationary(df)
    prepared = build_funding_features(prepared)
    prepared["target_direction"] = (
        prepared["close"].shift(-1) > prepared["close"]
    ).astype(int)
    prepared = prepared.iloc[:-1].copy()
    required = list(
        dict.fromkeys([*MODEL_FEATURES, *RAW_FUNDING_FEATURES, *DERIVED_FUNDING_FEATURES])
    )
    return prepared.dropna(subset=required).sort_values("date").reset_index(drop=True)


def split_experiment_data(df):
    if df.empty:
        raise ValueError("no complete funding experiment rows found")

    split_index = int(len(df) * 0.8)
    train = df.iloc[:split_index]
    test = df.iloc[split_index:]
    if len(train) < 100 or len(test) < 20:
        raise ValueError(
            f"insufficient funding experiment rows: train={len(train)}, test={len(test)}"
        )
    return train, test


def train_variant(train, features):
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
    search.fit(train[features], train["target_direction"])
    return search


def evaluate_variant(search, test, features):
    probabilities = search.best_estimator_.predict_proba(test[features])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    actual = test["target_direction"]
    return {
        "accuracy": float(accuracy_score(actual, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, predictions)),
        "f1": float(f1_score(actual, predictions, zero_division=0)),
        "mcc": float(matthews_corrcoef(actual, predictions)),
        "brier_score": float(brier_score_loss(actual, probabilities)),
        "best_cv_score": float(search.best_score_),
        "best_params": dict(search.best_params_),
        "predictions": predictions,
        "probabilities": probabilities,
    }


def wilson_accuracy_interval(correct, total):
    if total <= 0:
        return None
    z = 1.959963984540054
    proportion = correct / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = z * np.sqrt(
        (proportion * (1 - proportion) + z**2 / (4 * total)) / total
    ) / denominator
    return [
        max(0.0, centre - margin),
        min(1.0, centre + margin),
    ]


def paired_bootstrap_interval(model_correct, baseline_correct, iterations=2000, seed=42):
    values = np.asarray(model_correct, dtype=float) - np.asarray(
        baseline_correct, dtype=float
    )
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(iterations, len(values)), replace=True)
    interval = np.quantile(samples.mean(axis=1), [0.025, 0.975])
    return [float(interval[0]), float(interval[1])]


def exact_mcnemar_p_value(model_only, baseline_only):
    discordant = model_only + baseline_only
    if discordant == 0:
        return 1.0
    smaller = min(model_only, baseline_only)
    probability = sum(
        math.comb(discordant, successes)
        for successes in range(smaller + 1)
    ) / (2**discordant)
    return float(min(1.0, 2 * probability))


def compare_variant_significance(model_predictions, baseline_predictions, actual):
    model_correct = (
        np.asarray(model_predictions).astype(int) == np.asarray(actual).astype(int)
    )
    baseline_correct = (
        np.asarray(baseline_predictions).astype(int) == np.asarray(actual).astype(int)
    )
    model_only = int(np.sum(model_correct & ~baseline_correct))
    baseline_only = int(np.sum(~model_correct & baseline_correct))
    return {
        "difference": float(model_correct.mean() - baseline_correct.mean()),
        "difference_interval": paired_bootstrap_interval(
            model_correct, baseline_correct
        ),
        "model_only": model_only,
        "baseline_only": baseline_only,
        "mcnemar_p_value": exact_mcnemar_p_value(model_only, baseline_only),
        "model_accuracy_interval": wilson_accuracy_interval(
            int(model_correct.sum()), len(model_correct)
        ),
        "baseline_accuracy_interval": wilson_accuracy_interval(
            int(baseline_correct.sum()), len(baseline_correct)
        ),
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


def compare_funding_variants(db_path, asset="BTC", interval="1h"):
    dataset = prepare_experiment_dataset(
        load_crypto_features(db_path, asset, interval)
    )
    train, test = split_experiment_data(dataset)
    variants = {}
    prediction_data = {
        "date": test["date"].to_numpy(),
        "close": test["close"].to_numpy(),
        "actual_direction": test["target_direction"].to_numpy(),
    }

    for name, features in VARIANT_FEATURES.items():
        search = train_variant(train, features)
        evaluation = evaluate_variant(search, test, features)
        prediction_data[f"{name}_prediction"] = evaluation.pop("predictions")
        prediction_data[f"{name}_up_probability"] = evaluation.pop("probabilities")
        variants[name] = {
            "features": features,
            **evaluation,
        }

    baseline_accuracy = variants["baseline"]["accuracy"]
    baseline_predictions = prediction_data["baseline_prediction"]
    actual = prediction_data["actual_direction"]
    for name, metrics in variants.items():
        metrics["accuracy_difference_from_baseline"] = (
            metrics["accuracy"] - baseline_accuracy
        )
        if name == "baseline":
            metrics["significance"] = {
                "difference": 0.0,
                "difference_interval": [0.0, 0.0],
                "model_only": 0,
                "baseline_only": 0,
                "mcnemar_p_value": 1.0,
                "model_accuracy_interval": wilson_accuracy_interval(
                    int(np.sum(prediction_data["baseline_prediction"] == actual)),
                    len(actual),
                ),
                "baseline_accuracy_interval": wilson_accuracy_interval(
                    int(np.sum(prediction_data["baseline_prediction"] == actual)),
                    len(actual),
                ),
            }
        else:
            metrics["significance"] = compare_variant_significance(
                prediction_data[f"{name}_prediction"],
                baseline_predictions,
                actual,
            )

    test_predictions = pd.DataFrame(prediction_data)
    for name, metrics in variants.items():
        metrics["cost_aware"] = backtest_variant_costs(
            test_predictions, name, interval
        )

    return {
        "asset": asset,
        "interval": interval,
        "total_rows": len(dataset),
        "train_rows": len(train),
        "test_rows": len(test),
        "coverage_percent": 100.0,
        "train_start": train["date"].iloc[0],
        "train_end": train["date"].iloc[-1],
        "test_start": test["date"].iloc[0],
        "test_end": test["date"].iloc[-1],
        "variants": variants,
        "test_predictions": pd.DataFrame(prediction_data),
    }


def save_experiment_results(result, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stem = f"{result['asset'].lower()}_{result['interval']}"

    predictions = result["test_predictions"].copy()
    predictions["date"] = pd.to_datetime(predictions["date"]).dt.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    predictions_path = output_path / f"{stem}_predictions.csv"
    predictions.to_csv(predictions_path, index=False)

    metadata = {
        key: value for key, value in result.items() if key != "test_predictions"
    }
    for key in ["train_start", "train_end", "test_start", "test_end"]:
        metadata[key] = pd.Timestamp(metadata[key]).isoformat()
    metadata_path = output_path / f"{stem}_comparison.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return {"metadata": metadata_path, "predictions": predictions_path}


def compare_multiple_funding_variants(
    db_path,
    assets=("BTC", "ETH", "SOL"),
    intervals=("1h", "4h", "1d"),
):
    results = []
    skipped = []
    for asset in assets:
        for interval in intervals:
            try:
                result = compare_funding_variants(db_path, asset, interval)
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
                        "test_start": result["test_start"],
                        "test_end": result["test_end"],
                        "accuracy": metrics["accuracy"],
                        "balanced_accuracy": metrics["balanced_accuracy"],
                        "f1": metrics["f1"],
                        "mcc": metrics["mcc"],
                        "brier_score": metrics["brier_score"],
                        "accuracy_difference_from_baseline": metrics[
                            "accuracy_difference_from_baseline"
                        ],
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
    for column in ["test_start", "test_end"]:
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
    output_dir="reports/funding/experiment",
    assets=("BTC", "ETH", "SOL"),
    intervals=("1h", "4h", "1d"),
):
    result = compare_multiple_funding_variants(db_path, assets, intervals)
    paths = save_multiple_experiment_results(result, output_dir)
    for row in result["skipped"]:
        print(f"skipped {row['asset']} {row['interval']}: {row['reason']}")
    print(f"results saved: {paths['results']}")
    print(f"skipped saved: {paths['skipped']}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="compare funding variants with cost-aware backtests"
    )
    parser.add_argument("db_path")
    parser.add_argument("--output-dir", default="reports/funding/experiment")
    parser.add_argument("--assets", nargs="+", default=["BTC", "ETH", "SOL"])
    parser.add_argument("--intervals", nargs="+", default=["1h", "4h", "1d"])
    arguments = parser.parse_args()
    run_experiment(
        arguments.db_path,
        arguments.output_dir,
        tuple(arguments.assets),
        tuple(arguments.intervals),
    )
