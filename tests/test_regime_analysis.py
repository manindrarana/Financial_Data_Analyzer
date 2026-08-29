import json

import numpy as np
import pandas as pd
import pytest

from scripts.run_regime_analysis import (
    MIN_REGIME_ROWS,
    analyze_regimes,
    compute_dynamic_baselines,
    compute_volatility_threshold,
    evaluate_regime_rows,
    label_trend_regimes,
    label_volatility_regimes,
    run_regime_analysis,
)
from src.models.feature_engineering import NEEDED_COLS


def test_label_trend_regimes_matches_known_values():
    frame = pd.DataFrame(
        {
            "close": [105.0, 95.0, 100.9, 99.1, 100.0],
            "sma_200": [100.0, 100.0, 100.0, 100.0, np.nan],
        }
    )

    result = label_trend_regimes(frame)

    assert list(result) == ["bull", "bear", "sideways", "sideways", "sideways"]


def test_compute_volatility_threshold_uses_train_median():
    train = pd.DataFrame({"volatility_pct": [0.1, 0.2, 0.3, 0.4]})
    odd_train = pd.DataFrame({"volatility_pct": [1.0, 2.0, 3.0]})

    assert compute_volatility_threshold(train) == pytest.approx(0.25)
    assert compute_volatility_threshold(odd_train) == pytest.approx(2.0)


def test_label_volatility_regimes_splits_on_threshold():
    frame = pd.DataFrame({"volatility_pct": [0.3, 0.25, 0.2, np.nan]})

    result = label_volatility_regimes(frame, threshold=0.25)

    assert list(result) == [
        "high_volatility",
        "low_volatility",
        "low_volatility",
        "low_volatility",
    ]


def test_evaluate_regime_rows_reports_known_accuracy_and_best_baseline():
    actual = [1, 0, 1, 1, 0, 1]
    predictions = [1, 0, 1, 1, 0, 0]
    baselines = pd.DataFrame(
        {
            "always_up": [1, 1, 1, 1, 1, 1],
            "always_down": [0, 0, 0, 0, 0, 0],
            "previous_direction": [np.nan, 1, 0, 1, 1, 0],
        }
    )

    result = evaluate_regime_rows(predictions, actual, baselines)

    assert result["rows"] == 6
    assert result["accuracy"] == pytest.approx(5 / 6)
    assert result["best_baseline_rule"] == "always_up"
    assert result["best_baseline_accuracy"] == pytest.approx(4 / 6)
    assert result["accuracy_difference_from_baseline"] == pytest.approx(1 / 6)
    assert result["actual_up_pct"] == pytest.approx(4 / 6)
    assert result["accuracy_interval_low"] < result["accuracy"]
    assert result["accuracy_interval_high"] > result["accuracy"]


def test_evaluate_regime_rows_handles_all_nan_baselines():
    baselines = pd.DataFrame({"previous_direction": [np.nan, np.nan]})

    result = evaluate_regime_rows([1, 0], [1, 0], baselines)

    assert result["accuracy"] == pytest.approx(1.0)
    assert result["best_baseline_rule"] is None
    assert result["best_baseline_accuracy"] is None
    assert result["accuracy_difference_from_baseline"] is None


def make_regime_frame(rows):
    records = []
    for j in range(rows):
        close = 100.0 + j + (j % 2)
        if j < 36:
            sma_200 = close * 2
        elif j < 56:
            sma_200 = close
        else:
            sma_200 = close / 1.05
        records.append(
            {
                "date": pd.Timestamp("2026-03-01") + pd.Timedelta(hours=j),
                "close": close,
                "sma_200": sma_200,
                "volatility_pct": 3.0 if j % 2 == 0 else 0.5,
                "target_direction": 1 if j % 2 == 0 else 0,
            }
        )
    return pd.DataFrame(records)


def test_analyze_regimes_computes_known_per_regime_values():
    train = pd.DataFrame({"volatility_pct": [1.0, 2.0, 3.0]})
    test = make_regime_frame(80)
    predictions = [1, 0, 1, 1] * 20

    result = analyze_regimes(train, test, predictions)
    rows = result["results"].set_index(["regime_type", "regime"])

    assert result["skipped"] == []
    assert rows.loc[("trend", "bull"), "rows"] == 24
    assert rows.loc[("trend", "bear"), "rows"] == 36
    assert rows.loc[("trend", "sideways"), "rows"] == 20
    assert rows.loc[("trend", "bull"), "accuracy"] == pytest.approx(0.75)
    assert rows.loc[("trend", "bear"), "accuracy"] == pytest.approx(0.75)
    assert rows.loc[("trend", "sideways"), "accuracy"] == pytest.approx(0.75)
    assert rows.loc[("trend", "bear"), "best_baseline_accuracy"] == pytest.approx(0.5)
    assert rows.loc[("trend", "bear"), "accuracy_difference_from_baseline"] == pytest.approx(0.25)
    assert rows.loc[("trend", "bear"), "actual_up_pct"] == pytest.approx(0.5)

    assert rows.loc[("volatility", "high_volatility"), "rows"] == 40
    assert rows.loc[("volatility", "high_volatility"), "accuracy"] == pytest.approx(1.0)
    assert rows.loc[("volatility", "high_volatility"), "best_baseline_rule"] == "always_up"
    assert rows.loc[("volatility", "high_volatility"), "accuracy_difference_from_baseline"] == pytest.approx(0.0)

    assert rows.loc[("volatility", "low_volatility"), "rows"] == 40
    assert rows.loc[("volatility", "low_volatility"), "accuracy"] == pytest.approx(0.5)
    assert rows.loc[("volatility", "low_volatility"), "best_baseline_rule"] == "always_down"
    assert rows.loc[("volatility", "low_volatility"), "accuracy_difference_from_baseline"] == pytest.approx(-0.5)
    assert rows.loc[("volatility", "low_volatility"), "actual_up_pct"] == pytest.approx(0.0)


def test_analyze_regimes_skips_small_regimes_with_reasons():
    test = make_regime_frame(100)
    sma = [
        test.loc[j, "close"] / 2 if j < 60 else test.loc[j, "close"] * 2 if j < 65 else test.loc[j, "close"]
        for j in range(100)
    ]
    test["sma_200"] = sma
    predictions = test["target_direction"].to_numpy()

    result = analyze_regimes(
        pd.DataFrame({"volatility_pct": [1.0, 2.0, 3.0]}), test, predictions
    )

    assert result["skipped"] == [
        {
            "regime_type": "trend",
            "regime": "bear",
            "rows": 5,
            "reason": f"insufficient rows: 5 < {MIN_REGIME_ROWS}",
        }
    ]
    kept = set(
        map(tuple, result["results"][["regime_type", "regime"]].to_numpy())
    )
    assert kept == {
        ("trend", "bull"),
        ("trend", "sideways"),
        ("volatility", "high_volatility"),
        ("volatility", "low_volatility"),
    }
    bull = result["results"].set_index(["regime_type", "regime"]).loc[("trend", "bull")]
    assert bull["rows"] == 60
    assert bull["accuracy"] == pytest.approx(1.0)


def make_full_feature_frame(count=405):
    records = []
    for index in range(count):
        close = 100.0 + index + (index % 2)
        if 324 <= index <= 359:
            sma_200 = close * 2
        elif 360 <= index <= 379:
            sma_200 = close
        else:
            sma_200 = close / 1.05
        row = {column: float(index + 1) for column in NEEDED_COLS}
        row.update(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index),
                "close": close,
                "sma_200": sma_200,
                "daily_volatility": (3.0 if index % 2 == 0 else 0.5) * close,
                "funding_rate": 0.0001 + (index % 8) * 0.00001,
            }
        )
        records.append(row)
    return pd.DataFrame(records)


def test_run_regime_analysis_end_to_end_reuses_funding_pipeline(monkeypatch, tmp_path):
    frame = make_full_feature_frame()

    class FakeEstimator:
        def predict_proba(self, features):
            up_probability = np.where(features.index % 4 != 1, 0.9, 0.1)
            return np.column_stack([1 - up_probability, up_probability])

    class FakeSearch:
        best_estimator_ = FakeEstimator()
        best_score_ = 0.6
        best_params_ = {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 100}

    monkeypatch.setattr(
        "scripts.run_regime_analysis.load_crypto_features",
        lambda db_path, asset, interval: frame,
    )
    monkeypatch.setattr(
        "scripts.run_regime_analysis.train_variant",
        lambda train, features: FakeSearch(),
    )

    result = run_regime_analysis("unused.duckdb", output_dir=tmp_path)

    rows = result["results"].set_index(["regime_type", "regime"])
    assert result["skipped"] == []
    assert rows.loc[("trend", "bear"), "rows"] == 36
    assert rows.loc[("trend", "bear"), "accuracy"] == pytest.approx(0.75)
    assert rows.loc[("trend", "sideways"), "rows"] == 20
    assert rows.loc[("trend", "sideways"), "accuracy"] == pytest.approx(0.75)
    assert rows.loc[("trend", "bull"), "rows"] == 24
    assert rows.loc[("trend", "bull"), "accuracy"] == pytest.approx(0.75)
    assert rows.loc[("volatility", "high_volatility"), "accuracy"] == pytest.approx(1.0)
    assert rows.loc[("volatility", "low_volatility"), "accuracy"] == pytest.approx(0.5)
    assert rows.loc[("volatility", "low_volatility"), "best_baseline_rule"] == "always_down"

    summary = result["summary"]
    assert summary["overall_test_accuracy"] == pytest.approx(0.75)
    assert summary["volatility_threshold"] == pytest.approx(1.75)
    assert summary["total_rows"] == 400
    assert summary["train_rows"] == 320
    assert summary["test_rows"] == 80
    assert summary["test_start"] == pd.Timestamp("2026-01-14T12:00:00")
    assert summary["test_end"] == pd.Timestamp("2026-01-17T19:00:00")

    saved = pd.read_csv(result["paths"]["results"])
    assert len(saved) == 5
    assert set(saved["regime_type"]) == {"trend", "volatility"}
    loaded = json.loads(result["paths"]["summary"].read_text(encoding="utf-8"))
    assert loaded["test_start"] == "2026-01-14T12:00:00"
    assert loaded["test_end"] == "2026-01-17T19:00:00"
    assert loaded["source_data_start"] == "2026-01-01T04:00:00"
    assert loaded["generated_at_utc"]
    assert loaded["skipped"] == []
