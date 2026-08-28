import json

import numpy as np
import pandas as pd
import pytest

from scripts.run_funding_rate_experiment import (
    DERIVED_FUNDING_FEATURES,
    VARIANT_FEATURES,
    backtest_variant_costs,
    build_funding_features,
    compare_funding_variants,
    compare_multiple_funding_variants,
    compare_variant_significance,
    exact_mcnemar_p_value,
    paired_bootstrap_interval,
    prepare_experiment_dataset,
    save_experiment_results,
    save_multiple_experiment_results,
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


def test_wilson_accuracy_interval_matches_known_values():
    interval = wilson_accuracy_interval(60, 100)

    assert interval == pytest.approx([0.5020025868, 0.6905987136])
    assert wilson_accuracy_interval(0, 0) is None


def test_exact_mcnemar_p_value_matches_known_discordant_counts():
    assert exact_mcnemar_p_value(10, 0) == pytest.approx(0.001953125)
    assert exact_mcnemar_p_value(4, 4) == pytest.approx(1.0)
    assert exact_mcnemar_p_value(0, 0) == pytest.approx(1.0)


def test_paired_bootstrap_interval_is_zero_for_identical_results():
    correct = np.array([True, False, True, True, False])

    assert paired_bootstrap_interval(correct, correct) == pytest.approx([0.0, 0.0])


def test_compare_variant_significance_reports_clear_improvement():
    actual = np.array([1] * 20)
    baseline_predictions = np.array([0] * 10 + [1] * 10)
    model_predictions = np.array([1] * 20)

    result = compare_variant_significance(
        model_predictions,
        baseline_predictions,
        actual,
    )

    assert result["difference"] == pytest.approx(0.5)
    assert result["difference_interval"][0] > 0
    assert result["model_only"] == 10
    assert result["baseline_only"] == 0
    assert result["mcnemar_p_value"] == pytest.approx(0.001953125)
    assert result["model_accuracy_interval"][1] == pytest.approx(1.0)


def test_backtest_variant_costs_matches_manual_trade_calculation():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=3, freq="h"),
            "close": [100.0, 101.0, 104.5],
            "baseline_prediction": [1, 1, 1],
            "baseline_up_probability": [0.9, 0.9, 0.4],
        }
    )

    result = backtest_variant_costs(frame, "baseline", "1h")

    entry_cost = 100.0 * 0.001
    exit_cost = 104.0 * 0.001
    expected_pnl = 104.0 - 100.0 - entry_cost - exit_cost
    assert result["total_trades"] == 1
    assert result["winning_trades"] == 1
    assert result["total_pnl"] == pytest.approx(expected_pnl, abs=0.01)
    assert result["total_return_pct"] == pytest.approx(
        expected_pnl / 10000 * 100, abs=0.01
    )
    assert result["win_rate"] == 100.0
    assert result["max_drawdown_pct"] == 0.0


def test_backtest_variant_costs_charges_both_variants_same_cost_rate():
    dates = pd.date_range("2026-01-01", periods=5, freq="h")
    frame = pd.DataFrame(
        {
            "date": dates,
            "close": [100.0, 102.0, 100.5, 103.0, 104.0],
            "baseline_prediction": [1, 1, 1, 1, 1],
            "baseline_up_probability": [0.9, 0.9, 0.9, 0.9, 0.4],
            "raw_funding_prediction": [1, 1, 1, 1, 1],
            "raw_funding_up_probability": [0.4, 0.4, 0.4, 0.4, 0.4],
        }
    )

    baseline = backtest_variant_costs(frame, "baseline", "1h")
    raw_funding = backtest_variant_costs(frame, "raw_funding", "1h")

    assert baseline["total_trades"] == 1
    assert raw_funding["total_trades"] == 0
    assert raw_funding["total_pnl"] == 0.0
    assert raw_funding["sharpe_ratio"] == 0.0


def test_backtest_variant_costs_exits_at_stop_loss_with_known_loss():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=3, freq="h"),
            "close": [100.0, 97.9, 99.0],
            "baseline_prediction": [1, 1, 1],
            "baseline_up_probability": [0.9, 0.4, 0.4],
        }
    )

    result = backtest_variant_costs(frame, "baseline", "1h")

    entry_cost = 100.0 * 0.001
    exit_cost = 98.0 * 0.001
    expected_pnl = 98.0 - 100.0 - entry_cost - exit_cost
    assert result["total_trades"] == 1
    assert result["losing_trades"] == 1
    assert result["total_pnl"] == pytest.approx(expected_pnl, abs=0.01)


def make_variant_metrics(accuracy, cost_pnl, cost_trades):
    return {
        "accuracy": accuracy,
        "balanced_accuracy": accuracy,
        "f1": accuracy,
        "mcc": 0.0,
        "brier_score": 0.25,
        "best_cv_score": 0.5,
        "best_params": {"max_depth": 3},
        "features": list(MODEL_FEATURES),
        "accuracy_difference_from_baseline": 0.0,
        "significance": {
            "difference": 0.0,
            "difference_interval": [0.0, 0.0],
            "model_only": 0,
            "baseline_only": 0,
            "mcnemar_p_value": 1.0,
            "model_accuracy_interval": [0.4, 0.6],
            "baseline_accuracy_interval": [0.4, 0.6],
        },
        "cost_aware": {
            "total_return_pct": cost_pnl / 100,
            "total_pnl": cost_pnl,
            "total_cost": 0.4,
            "sharpe_ratio": 1.2,
            "volatility_pct": 20.0,
            "max_drawdown_pct": 5.0,
            "win_rate": 60.0,
            "profit_factor": 1.5,
            "total_trades": cost_trades,
        },
    }


def test_compare_multiple_funding_variants_includes_cost_aware_columns(monkeypatch):
    fake_result = {
        "total_rows": 200,
        "train_rows": 160,
        "test_rows": 40,
        "test_start": pd.Timestamp("2026-02-01"),
        "test_end": pd.Timestamp("2026-03-01"),
        "variants": {
            "baseline": make_variant_metrics(0.55, 120.0, 8),
            "raw_funding": make_variant_metrics(0.56, 180.0, 11),
        },
    }

    def fake_compare(db_path, asset, interval):
        if (asset, interval) == ("BTC", "1h"):
            return fake_result
        raise ValueError("insufficient funding experiment rows: train=90, test=23")

    monkeypatch.setattr(
        "scripts.run_funding_rate_experiment.compare_funding_variants",
        fake_compare,
    )

    result = compare_multiple_funding_variants("unused.duckdb")

    frame = result["results"]
    raw = frame[frame["variant"] == "raw_funding"].iloc[0]
    assert frame["cost_aware_total_pnl"].tolist() == [120.0, 180.0]
    assert frame["cost_aware_total_trades"].tolist() == [8, 11]
    assert raw["cost_aware_sharpe_ratio"] == 1.2
    assert raw["cost_aware_win_rate"] == 60.0
    assert result["skipped"] == [
        {
            "asset": "ETH",
            "interval": "1h",
            "reason": "insufficient funding experiment rows: train=90, test=23",
        }
    ]


def test_save_multiple_experiment_results_writes_cost_aware_csv(tmp_path):
    result = {
        "results": pd.DataFrame(
            [
                {
                    "asset": "BTC",
                    "interval": "1h",
                    "variant": "baseline",
                    "test_start": pd.Timestamp("2026-02-01"),
                    "test_end": pd.Timestamp("2026-03-01"),
                    "cost_aware_total_pnl": 120.0,
                    "cost_aware_total_trades": 8,
                }
            ]
        ),
        "skipped": [],
    }

    paths = save_multiple_experiment_results(result, tmp_path)
    saved = pd.read_csv(paths["results"])

    assert saved.loc[0, "cost_aware_total_pnl"] == pytest.approx(120.0)
    assert saved.loc[0, "cost_aware_total_trades"] == 8
    assert saved.loc[0, "test_start"] == "2026-02-01T00:00:00"
    assert json.loads(paths["skipped"].read_text(encoding="utf-8")) == []
