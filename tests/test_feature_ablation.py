import os

import pandas as pd
import pytest

from scripts.run_feature_ablation import (
    build_feature_sets,
    calculate_baseline_differences,
    prepare_data,
    save_results,
)
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS


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


def test_baseline_uses_all_model_features():
    feature_sets = build_feature_sets()

    assert feature_sets["baseline"] == MODEL_FEATURES


def test_trend_ablation_removes_only_trend_features():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature not in TREND_FEATURES]

    assert feature_sets["without_trend"] == expected


def test_momentum_ablation_removes_only_momentum_features():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature not in MOMENTUM_FEATURES]

    assert feature_sets["without_momentum"] == expected


def test_volatility_ablation_removes_only_volatility_features():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature not in VOLATILITY_FEATURES]

    assert feature_sets["without_volatility"] == expected


def test_volume_ablation_removes_only_volume_ratio():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature != "volume_ratio"]

    assert feature_sets["without_volume"] == expected


def test_fear_greed_ablation_removes_only_fear_greed():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature != "fear_greed"]

    assert feature_sets["without_fear_greed"] == expected


def test_calculates_balanced_accuracy_differences_from_baseline():
    results = [
        {"experiment": "baseline", "balanced_accuracy": 0.52},
        {"experiment": "without_trend", "balanced_accuracy": 0.50},
        {"experiment": "without_momentum", "balanced_accuracy": 0.53},
        {"experiment": "without_volume", "balanced_accuracy": 0.52},
    ]

    compared = calculate_baseline_differences(results)

    assert compared[0]["balanced_accuracy_difference"] == pytest.approx(0.0)
    assert compared[1]["balanced_accuracy_difference"] == pytest.approx(-0.02)
    assert compared[2]["balanced_accuracy_difference"] == pytest.approx(0.01)
    assert compared[3]["balanced_accuracy_difference"] == pytest.approx(0.0)


def test_empty_results_return_empty_baseline_comparison():
    assert calculate_baseline_differences([]) == []


def test_save_results_writes_values_and_cleans_temporary_file(tmp_path):
    output_path = tmp_path / "feature_ablation_results.csv"
    results = [
        {"experiment": "baseline", "balanced_accuracy": 0.5275},
        {
            "experiment": "without_trend",
            "balanced_accuracy": 0.5295,
            "balanced_accuracy_difference": 0.002,
        },
    ]

    save_results(results, str(output_path))

    saved = pd.read_csv(output_path)
    assert saved.loc[0, "balanced_accuracy"] == pytest.approx(0.5275)
    assert saved.loc[1, "balanced_accuracy_difference"] == pytest.approx(0.002)
    assert not os.path.exists(f"{output_path}.tmp")


def test_prepare_data_uses_shared_complete_model_rows():
    rows = []
    for index in range(4):
        row = {column: 1.0 for column in NEEDED_COLS}
        row["date"] = pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index)
        row["close"] = 100.0 + index
        rows.append(row)
    rows[1]["fear_greed"] = None

    prepared = prepare_data(pd.DataFrame(rows))

    assert prepared["date"].tolist() == [
        pd.Timestamp("2026-01-01 00:00:00"),
        pd.Timestamp("2026-01-01 02:00:00"),
    ]
    assert prepared[MODEL_FEATURES].notna().all().all()
