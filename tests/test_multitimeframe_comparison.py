import numpy as np
import pandas as pd

import scripts.compare_multitimeframe_models as multitimeframe
from scripts.compare_multitimeframe_models import (
    build_paired_dataset,
    calculate_metrics,
    prepare_interval_data,
)


def test_prepare_interval_data_uses_candle_close_as_availability_time():
    source = pd.DataFrame({
        "date": [pd.Timestamp("2026-01-01 00:00:00", tz="UTC")],
        "close": [100.0],
        "rsi_14": [50.0],
    })

    prepared, features = prepare_interval_data(source, "1h")

    assert features == ["rsi_14"]
    assert prepared.loc[0, "available_at"] == pd.Timestamp(
        "2026-01-01 01:00:00", tz="UTC"
    )


def test_paired_dataset_does_not_use_future_one_hour_candle():
    one_hour = pd.DataFrame({
        "date": pd.to_datetime([
            "2026-01-01 02:00:00+00:00",
            "2026-01-01 04:00:00+00:00",
        ]),
        "close": [100.0, 101.0],
        "rsi_14": [30.0, 50.0],
    })
    four_hour = pd.DataFrame({
        "date": pd.to_datetime([
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 04:00:00+00:00",
            "2026-01-01 08:00:00+00:00",
        ]),
        "close": [100.0, 104.0, 102.0],
        "rsi_14": [40.0, 45.0, 42.0],
    })

    paired, one_hour_features, _ = build_paired_dataset(one_hour, four_hour)

    assert one_hour_features == ["rsi_14_1h"]
    assert paired.iloc[0]["rsi_14_1h"] == 30.0


def test_paired_dataset_uses_next_four_hour_close_as_common_target():
    one_hour = pd.DataFrame({
        "date": pd.to_datetime([
            "2026-01-01 02:00:00+00:00",
            "2026-01-01 06:00:00+00:00",
        ]),
        "close": [100.0, 103.0],
        "rsi_14": [30.0, 50.0],
    })
    four_hour = pd.DataFrame({
        "date": pd.to_datetime([
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 04:00:00+00:00",
            "2026-01-01 08:00:00+00:00",
        ]),
        "close": [100.0, 104.0, 102.0],
        "rsi_14": [40.0, 45.0, 42.0],
    })

    paired, _, _ = build_paired_dataset(one_hour, four_hour)

    assert paired["target_direction"].tolist() == [1, 0]


def test_calculate_metrics_returns_known_accuracy_values():
    metrics = calculate_metrics(
        pd.Series([1, 0, 1, 0]),
        pd.Series([0.9, 0.2, 0.4, 0.8]),
    )

    assert metrics["accuracy"] == 0.5
    assert metrics["balanced_accuracy"] == 0.5
    assert metrics["coverage"] == 1.0


def test_compare_timeframes_averages_probabilities_and_reports_improvement(monkeypatch):
    class FixedModel:
        def __init__(self, probabilities):
            self.probabilities = np.array(probabilities)

        def fit(self, features, target):
            return self

        def predict_proba(self, features):
            return np.column_stack((1 - self.probabilities, self.probabilities))

    models = iter([
        FixedModel([0.9, 0.6, 0.4, 0.1]),
        FixedModel([0.4, 0.1, 0.6, 0.6]),
    ])
    monkeypatch.setattr(multitimeframe, "build_model", lambda: next(models))
    train = pd.DataFrame({
        "one_hour_feature": [1.0, 2.0, 3.0, 4.0],
        "four_hour_feature": [4.0, 3.0, 2.0, 1.0],
        "target_direction": [1, 0, 1, 0],
    })

    results = multitimeframe.compare_timeframes(
        train,
        train,
        ["one_hour_feature"],
        ["four_hour_feature"],
    )

    assert results["1h"]["balanced_accuracy"] == 0.5
    assert results["4h"]["balanced_accuracy"] == 0.5
    assert results["ensemble"]["balanced_accuracy"] == 1.0
    assert results["ensemble"]["difference_from_best_individual"] == 0.5
