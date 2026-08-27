import json

import numpy as np
import pandas as pd
import pytest

from scripts.run_funding_rate_experiment import (
    DERIVED_FUNDING_FEATURES,
    VARIANT_FEATURES,
    build_funding_features,
    compare_funding_variants,
    compare_variant_significance,
    exact_mcnemar_p_value,
    paired_bootstrap_interval,
    prepare_experiment_dataset,
    save_experiment_results,
    split_experiment_data,
    wilson_accuracy_interval,
)
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS


def make_feature_rows(count=160):
    rows = []
    for index in range(count):
        close = 100.0 + index
        row = {column: float(index + 1) for column in NEEDED_COLS}
        row.update(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index),
                "close": close,
                "sma_7": close / 1.01,
                "sma_30": close / 1.02,
                "sma_50": close / 1.03,
                "sma_100": close / 1.04,
                "sma_200": close / 1.05,
                "ema_12": close / 1.01,
                "ema_26": close / 1.02,
                "ema_50": close / 1.03,
                "ema_200": close / 1.04,
                "vwap": close / 1.01,
                "macd": 1.0,
                "macd_signal": 0.8,
                "macd_histogram": 0.2,
                "atr_14": 2.0,
                "daily_volatility": 3.0,
                "funding_rate": 0.0001 + (index % 8) * 0.00001,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def test_build_funding_features_calculates_known_values():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=6, freq="h"),
            "funding_rate": [0.01, 0.01, 0.02, 0.02, 0.02, 0.03],
        }
    )

    result = build_funding_features(frame)

    assert result.loc[2, "funding_rate_change"] == pytest.approx(0.01)
    assert result.loc[4, "funding_rate_rolling_mean"] == pytest.approx(0.016)
    expected_zscore = (0.02 - 0.016) / np.std(
        [0.01, 0.01, 0.02, 0.02, 0.02], ddof=1
    )
    assert result.loc[4, "funding_rate_zscore"] == pytest.approx(expected_zscore)
    assert result["hours_since_funding_change"].tolist() == [0, 1, 0, 1, 2, 0]


def test_prepare_experiment_dataset_uses_only_complete_identical_rows():
    frame = make_feature_rows()

    result = prepare_experiment_dataset(frame)

    assert not result.empty
    assert result.index.tolist() == list(range(len(result)))
    assert result[[*MODEL_FEATURES, "funding_rate", *DERIVED_FUNDING_FEATURES]].notna().all().all()
    assert result.iloc[-1]["date"] == frame.iloc[-2]["date"]


def test_prepare_experiment_dataset_labels_next_candle_direction():
    frame = make_feature_rows()
    frame.loc[150, "close"] = frame.loc[149, "close"] - 5

    result = prepare_experiment_dataset(frame)
    row = result.loc[result["date"] == frame.loc[149, "date"]].iloc[0]

    assert row["target_direction"] == 0


def test_split_experiment_data_rejects_insufficient_rows():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=100, freq="h"),
            "target_direction": [0, 1] * 50,
        }
    )

    with pytest.raises(
        ValueError,
        match="insufficient funding experiment rows: train=80, test=20",
    ):
        split_experiment_data(frame)


def test_compare_funding_variants_uses_same_rows_for_every_variant(monkeypatch):
    frame = make_feature_rows()
    seen_indices = []

    monkeypatch.setattr(
        "scripts.run_funding_rate_experiment.load_crypto_features",
        lambda db_path, asset, interval: frame,
    )

    class FakeEstimator:
        def predict_proba(self, features):
            seen_indices.append(features.index.tolist())
            up_probability = np.where(features.index % 2 == 0, 0.6, 0.4)
            return np.column_stack([1 - up_probability, up_probability])

    class FakeSearch:
        best_estimator_ = FakeEstimator()
        best_score_ = 0.55
        best_params_ = {
            "learning_rate": 0.05,
            "max_depth": 3,
            "n_estimators": 100,
        }

    monkeypatch.setattr(
        "scripts.run_funding_rate_experiment.train_variant",
        lambda train, features: FakeSearch(),
    )

    result = compare_funding_variants("unused.duckdb")

    assert set(result["variants"]) == set(VARIANT_FEATURES)
    assert seen_indices[0] == seen_indices[1] == seen_indices[2]
    assert result["test_rows"] == len(seen_indices[0])
    assert result["coverage_percent"] == 100.0
    assert len(result["test_predictions"]) == result["test_rows"]


def test_save_experiment_results_writes_metric_and_prediction_values(tmp_path):
    result = {
        "asset": "BTC",
        "interval": "1h",
        "total_rows": 120,
        "train_rows": 96,
        "test_rows": 24,
        "coverage_percent": 100.0,
        "train_start": pd.Timestamp("2026-01-01"),
        "train_end": pd.Timestamp("2026-01-04"),
        "test_start": pd.Timestamp("2026-01-05"),
        "test_end": pd.Timestamp("2026-01-06"),
        "variants": {
            "baseline": {
                "accuracy": 0.5,
                "balanced_accuracy": 0.5,
                "f1": 0.5,
                "mcc": 0.0,
                "brier_score": 0.25,
                "best_cv_score": 0.51,
                "best_params": {"max_depth": 3},
                "accuracy_difference_from_baseline": 0.0,
                "features": list(MODEL_FEATURES),
            }
        },
        "test_predictions": pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-01-05")],
                "actual_direction": [1],
                "baseline_prediction": [1],
                "baseline_up_probability": [0.6],
            }
        ),
    }

    paths = save_experiment_results(result, tmp_path)
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    predictions = pd.read_csv(paths["predictions"])

    assert metadata["variants"]["baseline"]["brier_score"] == 0.25
    assert metadata["test_start"] == "2026-01-05T00:00:00"
    assert predictions.loc[0, "baseline_up_probability"] == pytest.approx(0.6)
