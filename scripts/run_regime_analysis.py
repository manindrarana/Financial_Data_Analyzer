import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_funding_rate_experiment import (
    evaluate_variant,
    load_crypto_features,
    prepare_experiment_dataset,
    split_experiment_data,
    train_variant,
    wilson_accuracy_interval,
)
from src.models.feature_engineering import MODEL_FEATURES

TREND_BAND = 0.01
MIN_REGIME_ROWS = 20
VOLATILITY_QUANTILE = 0.5
TREND_REGIMES = ["bull", "bear", "sideways"]
VOLATILITY_REGIMES = ["high_volatility", "low_volatility"]
REGIME_RESULT_COLUMNS = [
    "regime_type",
    "regime",
    "rows",
    "accuracy",
    "accuracy_interval_low",
    "accuracy_interval_high",
    "best_baseline_rule",
    "best_baseline_accuracy",
    "accuracy_difference_from_baseline",
    "actual_up_pct",
]


def label_trend_regimes(df, band=TREND_BAND):
    above = df["close"] > df["sma_200"] * (1 + band)
    below = df["close"] < df["sma_200"] * (1 - band)
    return np.select([above, below], ["bull", "bear"], default="sideways")


def compute_volatility_threshold(train, quantile=VOLATILITY_QUANTILE):
    return float(train["volatility_pct"].quantile(quantile))


def label_volatility_regimes(df, threshold):
    return np.where(df["volatility_pct"] > threshold, "high_volatility", "low_volatility")


def compute_dynamic_baselines(df):
    sma_20 = df["close"].rolling(window=20).mean()
    sma_50 = df["close"].rolling(window=50).mean()
    return pd.DataFrame(
        {
            "always_up": 1,
            "always_down": 0,
            "previous_direction": (df["close"].diff() > 0).astype(int).shift(1),
            "sma_crossover": (sma_20 > sma_50)
            .astype(float)
            .where(sma_20.notna() & sma_50.notna()),
        },
        index=df.index,
    )


def evaluate_regime_rows(predictions, actual, baselines):
    predictions = np.asarray(predictions, dtype=int)
    actual = np.asarray(actual, dtype=int)
    model_correct = predictions == actual
    accuracy = float(model_correct.mean())
    interval = wilson_accuracy_interval(int(model_correct.sum()), len(model_correct))

    baseline_results = {}
    for name in baselines.columns:
        rule_values = baselines[name].to_numpy(dtype=float)
        valid = ~np.isnan(rule_values)
        if valid.any():
            baseline_results[name] = float(
                np.mean(rule_values[valid].astype(int) == actual[valid])
            )
    best_rule = (
        max(baseline_results, key=baseline_results.get) if baseline_results else None
    )
    best_baseline = baseline_results[best_rule] if best_rule else None

    return {
        "rows": int(len(actual)),
        "accuracy": accuracy,
        "accuracy_interval_low": interval[0] if interval else None,
        "accuracy_interval_high": interval[1] if interval else None,
        "best_baseline_rule": best_rule,
        "best_baseline_accuracy": best_baseline,
        "accuracy_difference_from_baseline": (
            accuracy - best_baseline if best_baseline is not None else None
        ),
        "actual_up_pct": float(np.mean(actual == 1)),
    }


def analyze_regimes(train, test, predictions):
    threshold = compute_volatility_threshold(train)
    labeled = test.copy().reset_index(drop=True)
    labeled["trend_regime"] = label_trend_regimes(labeled)
    labeled["volatility_regime"] = label_volatility_regimes(labeled, threshold)
    predictions = np.asarray(predictions)
    actual = labeled["target_direction"].to_numpy()
    baselines = compute_dynamic_baselines(labeled)

    results = []
    skipped = []
    regime_groups = [
        ("trend", "trend_regime", TREND_REGIMES),
        ("volatility", "volatility_regime", VOLATILITY_REGIMES),
    ]
    for regime_type, column, expected in regime_groups:
        for regime in expected:
            mask = (labeled[column] == regime).to_numpy()
            rows = int(mask.sum())
            if rows < MIN_REGIME_ROWS:
                skipped.append(
                    {
                        "regime_type": regime_type,
                        "regime": regime,
                        "rows": rows,
                        "reason": f"insufficient rows: {rows} < {MIN_REGIME_ROWS}",
                    }
                )
                continue
            metrics = evaluate_regime_rows(
                predictions[mask], actual[mask], baselines[mask]
            )
            results.append({"regime_type": regime_type, "regime": regime, **metrics})

    return {
        "results": pd.DataFrame(results, columns=REGIME_RESULT_COLUMNS),
        "skipped": skipped,
        "volatility_threshold": threshold,
    }


def save_regime_results(asset, interval, results, summary, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stem = f"{asset.lower()}_{interval}"

    results_path = output_path / f"{stem}_regime_accuracy.csv"
    results.to_csv(results_path, index=False)

    for key in [
        "source_data_start",
        "source_data_end",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
    ]:
        summary[key] = pd.Timestamp(summary[key]).isoformat()
    summary_path = output_path / f"{stem}_regime_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {"results": results_path, "summary": summary_path}


def run_regime_analysis(
    db_path,
    asset="BTC",
    interval="1h",
    output_dir="reports/regime",
):
    dataset = prepare_experiment_dataset(
        load_crypto_features(db_path, asset, interval)
    )
    train, test = split_experiment_data(dataset)
    search = train_variant(train, list(MODEL_FEATURES))
    evaluation = evaluate_variant(search, test, list(MODEL_FEATURES))
    analysis = analyze_regimes(train, test, evaluation["predictions"])

    summary = {
        "asset": asset,
        "interval": interval,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_data_start": dataset["date"].iloc[0],
        "source_data_end": dataset["date"].iloc[-1],
        "train_start": train["date"].iloc[0],
        "train_end": train["date"].iloc[-1],
        "test_start": test["date"].iloc[0],
        "test_end": test["date"].iloc[-1],
        "total_rows": len(dataset),
        "train_rows": len(train),
        "test_rows": len(test),
        "overall_test_accuracy": evaluation["accuracy"],
        "trend_band": TREND_BAND,
        "volatility_quantile": VOLATILITY_QUANTILE,
        "volatility_threshold": analysis["volatility_threshold"],
        "min_regime_rows": MIN_REGIME_ROWS,
        "skipped": analysis["skipped"],
    }
    paths = save_regime_results(
        asset, interval, analysis["results"], summary, output_dir
    )
    for row in analysis["skipped"]:
        print(f"skipped {row['regime_type']} {row['regime']}: {row['reason']}")
    print(f"results saved: {paths['results']}")
    print(f"summary saved: {paths['summary']}")
    return {
        "results": analysis["results"],
        "skipped": analysis["skipped"],
        "summary": summary,
        "paths": paths,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="analyze out-of-sample accuracy across trend and volatility regimes"
    )
    parser.add_argument("db_path")
    parser.add_argument("--asset", default="BTC")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--output-dir", default="reports/regime")
    arguments = parser.parse_args()
    run_regime_analysis(
        arguments.db_path,
        arguments.asset,
        arguments.interval,
        arguments.output_dir,
    )
