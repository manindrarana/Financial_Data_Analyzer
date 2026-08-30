import json

import numpy as np
import pandas as pd
import pytest

import scripts.run_cross_asset_experiment as cross_asset_experiment
from scripts.run_cross_asset_experiment import (
    COST_AWARE_SETTINGS,
    EXPERIMENT_FEATURES,
    build_cross_asset_features,
    compare_multiple_cross_asset_variants,
    evaluate_experiment_model,
    load_target_features,
    merge_cross_asset_features,
    prepare_target_features,
    save_multiple_experiment_results,
    split_experiment_data,
    train_experiment_model,
)
from scripts.run_funding_rate_experiment import (
    COST_AWARE_SETTINGS as FUNDING_COST_AWARE_SETTINGS,
)
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS


def test_compare_experiment_variants_uses_identical_rows_and_returns_metadata(monkeypatch):
    rows = []
    for index in range(125):
        row = {column: float(index + 1) for column in MODEL_FEATURES}
        row.update(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index),
                "close": 100.0 + index,
                "target_direction": index % 2,
                "eth_btc_relative_return": 0.01,
                "tracked_crypto_market_return": 0.02,
                "tracked_crypto_market_breadth": 0.5,
                "cross_asset_volatility": 0.03,
            }
        )
        rows.append(row)
    dataset = pd.DataFrame(rows)
    split_features = []
    trained_rows = []
    evaluate_calls = []
    backtest_calls = []

    def fake_prepare(*args, **kwargs):
        return dataset

    def fake_split(data, features):
        split_features.append(features)
        return (
            data.iloc[:100][features],
            data.iloc[:100]["target_direction"],
            data.iloc[100:][features],
            data.iloc[100:]["target_direction"],
            data.iloc[100:]["date"],
        )

    def fake_train(X_train, y_train):
        trained_rows.append((len(X_train), len(y_train)))

        class FixedSearch:
            pass

        return FixedSearch()

    def fake_evaluate(search, X_test, y_test):
        evaluate_calls.append(list(y_test))
        if len(evaluate_calls) == 1:
            predictions = np.zeros(len(y_test), dtype=int)
        else:
            predictions = (np.asarray(y_test) == 1).astype(int)
        accuracy = float(np.mean(predictions == np.asarray(y_test)))
        return {
            "accuracy": accuracy,
            "balanced_accuracy": accuracy,
            "f1": accuracy,
            "best_cv_score": 0.5,
            "best_params": {
                "learning_rate": 0.05,
                "max_depth": 3,
                "n_estimators": 100,
            },
            "predictions": predictions,
            "probabilities": np.full(len(y_test), 0.6),
        }

    def fake_backtest(test_predictions, variant, interval):
        backtest_calls.append((variant, interval, len(test_predictions)))
        return {
            "total_return_pct": 10.0,
            "total_pnl": 1000.0,
            "total_cost": 5.0,
            "sharpe_ratio": 1.0,
            "volatility_pct": 20.0,
            "max_drawdown_pct": 5.0,
            "win_rate": 0.6,
            "profit_factor": 1.5,
            "total_trades": 9,
        }

    monkeypatch.setattr(cross_asset_experiment, "prepare_experiment_dataset", fake_prepare)
    monkeypatch.setattr(cross_asset_experiment, "split_experiment_data", fake_split)
    monkeypatch.setattr(cross_asset_experiment, "train_experiment_model", fake_train)
    monkeypatch.setattr(cross_asset_experiment, "evaluate_experiment_model", fake_evaluate)
    monkeypatch.setattr(cross_asset_experiment, "backtest_variant_costs", fake_backtest)

    result = cross_asset_experiment.compare_experiment_variants("ignored.duckdb")

    assert split_features[0] == MODEL_FEATURES
    assert split_features[1] == [*MODEL_FEATURES, *EXPERIMENT_FEATURES]
    assert trained_rows == [(100, 100), (100, 100)]
    assert result["asset"] == "BTC"
    assert result["interval"] == "1h"
    assert result["total_rows"] == 125
    assert result["train_rows"] == 100
    assert result["test_rows"] == 25
    assert result["train_start"] == pd.Timestamp("2026-01-01 00:00")
    assert result["train_end"] == pd.Timestamp("2026-01-05 03:00")
    assert result["test_start"] == pd.Timestamp("2026-01-05 04:00")
    assert result["test_end"] == pd.Timestamp("2026-01-06 04:00")

    baseline = result["variants"]["baseline"]
    cross_asset = result["variants"]["cross_asset"]
    assert baseline["accuracy"] == pytest.approx(0.52)
    assert cross_asset["accuracy"] == pytest.approx(1.0)
    assert baseline["cost_aware"]["total_pnl"] == 1000.0
    assert cross_asset["cost_aware"]["total_trades"] == 9
    assert backtest_calls == [("baseline", "1h", 25), ("cross_asset", "1h", 25)]

    significance = cross_asset["significance"]
    assert significance["difference"] == pytest.approx(0.48)
    assert significance["model_only"] == 12
    assert significance["baseline_only"] == 0
    assert significance["mcnemar_p_value"] == pytest.approx(2 / 4096)
    assert significance["difference_interval"][0] <= 0.48
    assert significance["difference_interval"][1] >= 0.48
    baseline_interval = baseline["significance"]["model_accuracy_interval"]
    assert baseline["significance"]["baseline_accuracy_interval"] == baseline_interval
    assert baseline_interval[0] <= 0.52 <= baseline_interval[1]

    assert result["test_predictions"].columns.tolist() == [
        "date",
        "close",
        "actual_direction",
        "baseline_prediction",
        "baseline_up_probability",
        "cross_asset_prediction",
        "cross_asset_up_probability",
    ]
    assert len(result["test_predictions"]) == 25
    assert result["test_predictions"]["close"].tolist() == [
        100.0 + index for index in range(100, 125)
    ]
    assert result["test_predictions"]["date"].tolist() == list(
        pd.date_range("2026-01-05 04:00", periods=25, freq="h")
    )


def test_save_experiment_results_writes_metadata_and_predictions(tmp_path):
    result = {
        "asset": "BTC",
        "interval": "1h",
        "total_rows": 3,
        "train_rows": 2,
        "test_rows": 1,
        "test_start": pd.Timestamp("2026-01-01 02:00"),
        "test_end": pd.Timestamp("2026-01-01 02:00"),
        "baseline_features": ["feature"],
        "cross_asset_features": ["market_feature"],
        "baseline": {"accuracy": 0.5},
        "cross_asset": {"accuracy": 0.4},
        "test_predictions": pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-01-01 02:00")],
                "actual_direction": [1],
                "baseline_prediction": [1],
                "cross_asset_prediction": [0],
            }
        ),
    }

    paths = cross_asset_experiment.save_experiment_results(result, tmp_path)

    metadata = __import__("json").loads(
        paths["metadata"].read_text(encoding="utf-8")
    )
    assert "test_predictions" not in metadata
    assert metadata["asset"] == "BTC"
    assert metadata["test_start"] == "2026-01-01T02:00:00"
    assert pd.read_csv(paths["predictions"]).to_dict("records") == [
        {
            "date": "2026-01-01T02:00:00",
            "actual_direction": 1,
            "baseline_prediction": 1,
            "cross_asset_prediction": 0,
        }
    ]


def test_compare_experiment_variants_passes_market_asset_threshold(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        cross_asset_experiment,
        "prepare_experiment_dataset",
        lambda *args, **kwargs: captured.update(kwargs) or pd.DataFrame(),
    )

    with pytest.raises(ValueError, match="no complete experiment rows found"):
        cross_asset_experiment.compare_experiment_variants(
            "ignored.duckdb",
            asset="ETH",
            interval="1h",
            min_market_assets=7,
        )

    assert captured == {"min_market_assets": 7}


def test_split_experiment_data_preserves_chronological_shared_rows():
    data = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=125, freq="h"),
            "feature": range(125),
            "target_direction": [index % 2 for index in range(125)],
        }
    )

    X_train, y_train, X_test, y_test, test_dates = split_experiment_data(
        data,
        ["feature"],
    )

    assert X_train["feature"].tolist() == list(range(100))
    assert y_train.tolist() == [index % 2 for index in range(100)]
    assert X_test["feature"].tolist() == list(range(100, 125))
    assert y_test.tolist() == [index % 2 for index in range(100, 125)]
    assert test_dates.tolist() == list(
        pd.date_range("2026-01-05 04:00", periods=25, freq="h")
    )


def test_train_experiment_model_returns_selected_parameters(monkeypatch):
    monkeypatch.setattr(
        cross_asset_experiment,
        "PARAM_GRID",
        {"learning_rate": [0.1], "max_depth": [1], "n_estimators": [10]},
    )
    X_train = pd.DataFrame({"feature": range(100)})
    y_train = pd.Series([0, 1] * 50)

    search = train_experiment_model(X_train, y_train)

    assert search.best_params_ == {
        "learning_rate": 0.1,
        "max_depth": 1,
        "n_estimators": 10,
    }
    assert search.best_estimator_.get_xgb_params()["random_state"] == 42


def test_evaluate_experiment_model_returns_known_metrics():
    class FixedModel:
        def predict_proba(self, X):
            return np.array(
                [[0.6, 0.4], [0.2, 0.8], [0.3, 0.7], [0.9, 0.1]]
            )

    class FixedSearch:
        best_estimator_ = FixedModel()
        best_score_ = 0.6
        best_params_ = {
            "learning_rate": 0.05,
            "max_depth": 3,
            "n_estimators": 100,
        }

    metrics = evaluate_experiment_model(
        FixedSearch(),
        pd.DataFrame({"feature": [1, 2, 3, 4]}),
        pd.Series([0, 1, 0, 0]),
    )

    assert metrics["predictions"].tolist() == [0, 1, 1, 0]
    assert metrics["probabilities"].tolist() == pytest.approx(
        [0.4, 0.8, 0.7, 0.1]
    )
    assert metrics["accuracy"] == pytest.approx(0.75)
    assert metrics["balanced_accuracy"] == pytest.approx(0.75)
    assert metrics["f1"] == pytest.approx(2 / 3)
    assert metrics["best_cv_score"] == pytest.approx(0.6)
    assert metrics["best_params"] == {
        "learning_rate": 0.05,
        "max_depth": 3,
        "n_estimators": 100,
    }


def test_backtest_variant_costs_uses_shared_settings_and_known_metrics():
    rows = []
    price = 100.0
    for index in range(30):
        row = {
            "date": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index),
            "close": price,
            "prediction": 1,
            "confidence": 0.9,
        }
        rows.append(row)
        price *= 1.01
    frame = pd.DataFrame(rows)

    trades, equity = __import__(
        "backtesting.strategy", fromlist=["simulate_trades"]
    ).simulate_trades(frame, **COST_AWARE_SETTINGS)
    expected = __import__(
        "backtesting.metrics", fromlist=["compute_metrics"]
    ).compute_metrics(
        trades,
        equity,
        initial_capital=COST_AWARE_SETTINGS["initial_capital"],
        interval="1h",
        asset_class="crypto",
    )

    test_predictions = pd.DataFrame(
        {
            "date": frame["date"],
            "close": frame["close"],
            "baseline_prediction": frame["prediction"],
            "baseline_up_probability": frame["confidence"],
        }
    )
    result = cross_asset_experiment.backtest_variant_costs(
        test_predictions, "baseline", "1h"
    )

    assert result["total_trades"] == expected["total_trades"]
    assert result["total_pnl"] == pytest.approx(expected["total_pnl"])
    assert result["total_cost"] == pytest.approx(expected["total_cost"])
    assert result["total_return_pct"] == pytest.approx(expected["total_return_pct"])
    assert result["total_trades"] >= 1
    assert result["total_cost"] > 0


def test_cost_aware_settings_match_funding_experiment():
    assert COST_AWARE_SETTINGS == FUNDING_COST_AWARE_SETTINGS


def test_compare_multiple_cross_asset_variants_aggregates_and_skips(monkeypatch):
    calls = []

    def fake_compare(db_path, asset, interval, min_market_assets):
        calls.append((asset, interval))
        if asset == "ETH":
            raise ValueError("insufficient experiment rows: train=90, test=10")
        return {
            "asset": asset,
            "interval": interval,
            "total_rows": 125,
            "train_rows": 100,
            "test_rows": 25,
            "train_start": pd.Timestamp("2026-01-01"),
            "test_start": pd.Timestamp("2026-02-01"),
            "test_end": pd.Timestamp("2026-02-02"),
            "variants": {
                "baseline": {
                    "accuracy": 0.5,
                    "balanced_accuracy": 0.5,
                    "f1": 0.5,
                    "significance": {
                        "difference": 0.0,
                        "difference_interval": [0.0, 0.0],
                        "mcnemar_p_value": 1.0,
                        "model_only": 0,
                        "baseline_only": 0,
                    },
                    "cost_aware": {
                        "total_return_pct": 1.0,
                        "total_pnl": 100.0,
                        "total_cost": 2.0,
                        "sharpe_ratio": 0.5,
                        "volatility_pct": 10.0,
                        "max_drawdown_pct": 4.0,
                        "win_rate": 0.55,
                        "profit_factor": 1.2,
                        "total_trades": 5,
                    },
                },
                "cross_asset": {
                    "accuracy": 0.52,
                    "balanced_accuracy": 0.51,
                    "f1": 0.53,
                    "significance": {
                        "difference": 0.02,
                        "difference_interval": [-0.01, 0.05],
                        "mcnemar_p_value": 0.4,
                        "model_only": 3,
                        "baseline_only": 2,
                    },
                    "cost_aware": {
                        "total_return_pct": 2.0,
                        "total_pnl": 200.0,
                        "total_cost": 3.0,
                        "sharpe_ratio": 0.6,
                        "volatility_pct": 11.0,
                        "max_drawdown_pct": 5.0,
                        "win_rate": 0.6,
                        "profit_factor": 1.3,
                        "total_trades": 6,
                    },
                },
            },
        }

    monkeypatch.setattr(
        cross_asset_experiment, "compare_experiment_variants", fake_compare
    )

    result = compare_multiple_cross_asset_variants(
        "ignored.duckdb", assets=("BTC", "ETH", "SOL"), intervals=("1h", "4h")
    )

    assert calls == [
        ("BTC", "1h"),
        ("BTC", "4h"),
        ("ETH", "1h"),
        ("ETH", "4h"),
        ("SOL", "1h"),
        ("SOL", "4h"),
    ]
    assert result["skipped"] == [
        {
            "asset": "ETH",
            "interval": "1h",
            "reason": "insufficient experiment rows: train=90, test=10",
        },
        {
            "asset": "ETH",
            "interval": "4h",
            "reason": "insufficient experiment rows: train=90, test=10",
        },
    ]
    results = result["results"]
    assert len(results) == 8
    btc_cross_asset = results.loc[
        (results["asset"] == "BTC")
        & (results["interval"] == "1h")
        & (results["variant"] == "cross_asset")
    ].iloc[0]
    assert btc_cross_asset["accuracy"] == pytest.approx(0.52)
    assert btc_cross_asset["accuracy_difference_from_baseline"] == pytest.approx(
        0.02
    )
    assert btc_cross_asset["significance_difference"] == pytest.approx(0.02)
    assert btc_cross_asset["significance_interval_low"] == pytest.approx(-0.01)
    assert btc_cross_asset["significance_interval_high"] == pytest.approx(0.05)
    assert btc_cross_asset["mcnemar_p_value"] == pytest.approx(0.4)
    assert btc_cross_asset["model_only"] == 3
    assert btc_cross_asset["baseline_only"] == 2
    assert btc_cross_asset["cost_aware_total_pnl"] == pytest.approx(200.0)
    assert btc_cross_asset["cost_aware_total_trades"] == 6
    btc_baseline = results.loc[
        (results["asset"] == "BTC")
        & (results["interval"] == "1h")
        & (results["variant"] == "baseline")
    ].iloc[0]
    assert btc_baseline["accuracy_difference_from_baseline"] == pytest.approx(0.0)
    assert btc_baseline["mcnemar_p_value"] == pytest.approx(1.0)
    assert not results.loc[results["asset"] == "ETH"].shape[0]


def test_save_multiple_experiment_results_writes_csv_and_skipped(tmp_path):
    result = {
        "results": pd.DataFrame(
            [
                {
                    "asset": "BTC",
                    "interval": "1h",
                    "variant": "cross_asset",
                    "accuracy": 0.52,
                    "train_start": pd.Timestamp("2026-01-01 00:00"),
                    "test_start": pd.Timestamp("2026-02-01 00:00"),
                    "test_end": pd.Timestamp("2026-02-02 00:00"),
                }
            ]
        ),
        "skipped": [
            {"asset": "ETH", "interval": "4h", "reason": "insufficient rows"}
        ],
    }

    paths = save_multiple_experiment_results(result, tmp_path)

    saved = pd.read_csv(paths["results"])
    assert saved["train_start"].tolist() == ["2026-01-01T00:00:00"]
    assert saved["test_start"].tolist() == ["2026-02-01T00:00:00"]
    assert saved["test_end"].tolist() == ["2026-02-02T00:00:00"]
    assert saved["accuracy"].tolist() == pytest.approx([0.52])
    assert json.loads(paths["skipped"].read_text(encoding="utf-8")) == [
        {"asset": "ETH", "interval": "4h", "reason": "insufficient rows"}
    ]


def test_prepare_target_features_creates_next_candle_labels_and_drops_last_row():
    rows = []
    for index, close in enumerate([100.0, 110.0, 105.0]):
        row = {column: 1.0 for column in NEEDED_COLS}
        row["date"] = pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index)
        row["close"] = close
        rows.append(row)

    prepared = prepare_target_features(pd.DataFrame(rows))

    assert prepared["date"].tolist() == [
        pd.Timestamp("2026-01-01 00:00:00"),
        pd.Timestamp("2026-01-01 01:00:00"),
    ]
    assert prepared["target_direction"].tolist() == [1, 0]
    assert prepared[MODEL_FEATURES].notna().all().all()


def test_merge_cross_asset_features_keeps_complete_shared_rows():
    target = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 01:00"]),
            "target_direction": [1, 0],
        }
    )
    cross_asset = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 01:00"]),
            "eth_btc_relative_return": [0.01, 0.02],
            "tracked_crypto_market_return": [0.03, 0.04],
            "tracked_crypto_market_breadth": [0.5, 1.0],
            "cross_asset_volatility": [0.02, 0.03],
        }
    )

    merged = merge_cross_asset_features(target, cross_asset)

    assert merged["target_direction"].tolist() == [1, 0]
    assert merged["tracked_crypto_market_return"].tolist() == [0.03, 0.04]
    assert merged[EXPERIMENT_FEATURES].notna().all().all()


def test_merge_cross_asset_features_drops_rows_with_missing_experiment_values():
    target = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 01:00"]),
            "target_direction": [1, 0],
        }
    )
    cross_asset = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 01:00"]),
            "eth_btc_relative_return": [0.01, None],
            "tracked_crypto_market_return": [0.03, 0.04],
            "tracked_crypto_market_breadth": [0.5, 1.0],
            "cross_asset_volatility": [0.02, 0.03],
        }
    )

    merged = merge_cross_asset_features(target, cross_asset)

    assert len(merged) == 1
    assert merged.iloc[0]["target_direction"] == 1
    assert merged.iloc[0]["date"] == pd.Timestamp("2026-01-01 00:00")


def test_builds_known_cross_asset_values_for_btc():
    candles = pd.DataFrame(
        [
            {"date": "2026-01-01 00:00:00", "asset_symbol": "BTC", "interval": "1h", "close": 100.0},
            {"date": "2026-01-01 00:00:00", "asset_symbol": "ETH", "interval": "1h", "close": 50.0},
            {"date": "2026-01-01 00:00:00", "asset_symbol": "SOL", "interval": "1h", "close": 20.0},
            {"date": "2026-01-01 01:00:00", "asset_symbol": "BTC", "interval": "1h", "close": 110.0},
            {"date": "2026-01-01 01:00:00", "asset_symbol": "ETH", "interval": "1h", "close": 60.0},
            {"date": "2026-01-01 01:00:00", "asset_symbol": "SOL", "interval": "1h", "close": 18.0},
        ]
    )

    result = build_cross_asset_features(candles, "BTC", "1h", min_market_assets=2)
    row = result.loc[result["date"] == pd.Timestamp("2026-01-01 01:00:00")].iloc[0]

    assert row["eth_btc_relative_return"] == pytest.approx(0.10)
    assert row["tracked_crypto_market_return"] == pytest.approx(0.05)
    assert row["tracked_crypto_market_breadth"] == pytest.approx(0.5)
    assert row["cross_asset_volatility"] == pytest.approx(0.15)
    assert row["market_asset_count"] == 2


def test_excludes_target_asset_from_market_features():
    candles = pd.DataFrame(
        [
            {"date": "2026-01-01 00:00:00", "asset_symbol": asset, "interval": "1h", "close": close}
            for asset, close in [("BTC", 100.0), ("ETH", 100.0), ("SOL", 100.0)]
        ]
        + [
            {"date": "2026-01-01 01:00:00", "asset_symbol": asset, "interval": "1h", "close": close}
            for asset, close in [("BTC", 200.0), ("ETH", 90.0), ("SOL", 80.0)]
        ]
    )

    result = build_cross_asset_features(candles, "BTC", "1h", min_market_assets=2)
    row = result.iloc[-1]

    assert row["tracked_crypto_market_return"] == pytest.approx(-0.15)
    assert row["tracked_crypto_market_breadth"] == pytest.approx(0.0)


def test_does_not_use_other_intervals_or_future_candles():
    candles = pd.DataFrame(
        [
            {"date": "2026-01-01 00:00:00", "asset_symbol": "BTC", "interval": "1h", "close": 100.0},
            {"date": "2026-01-01 00:00:00", "asset_symbol": "ETH", "interval": "1h", "close": 50.0},
            {"date": "2026-01-01 00:00:00", "asset_symbol": "SOL", "interval": "1h", "close": 20.0},
            {"date": "2026-01-01 01:00:00", "asset_symbol": "BTC", "interval": "1h", "close": 101.0},
            {"date": "2026-01-01 01:00:00", "asset_symbol": "ETH", "interval": "4h", "close": 55.0},
            {"date": "2026-01-01 02:00:00", "asset_symbol": "ETH", "interval": "1h", "close": 60.0},
            {"date": "2026-01-01 02:00:00", "asset_symbol": "SOL", "interval": "1h", "close": 22.0},
        ]
    )

    result = build_cross_asset_features(candles, "BTC", "1h", min_market_assets=2)
    row = result.loc[result["date"] == pd.Timestamp("2026-01-01 01:00:00")].iloc[0]

    assert pd.isna(row["tracked_crypto_market_return"])
    assert pd.isna(row["tracked_crypto_market_breadth"])
    assert pd.isna(row["cross_asset_volatility"])
    assert row["market_asset_count"] == 0


def test_requires_minimum_market_asset_coverage():
    candles = pd.DataFrame(
        [
            {"date": "2026-01-01 00:00:00", "asset_symbol": "BTC", "interval": "1h", "close": 100.0},
            {"date": "2026-01-01 00:00:00", "asset_symbol": "ETH", "interval": "1h", "close": 50.0},
            {"date": "2026-01-01 01:00:00", "asset_symbol": "BTC", "interval": "1h", "close": 101.0},
            {"date": "2026-01-01 01:00:00", "asset_symbol": "ETH", "interval": "1h", "close": 55.0},
        ]
    )

    result = build_cross_asset_features(candles, "BTC", "1h", min_market_assets=2)
    row = result.iloc[-1]

    assert pd.isna(row["tracked_crypto_market_return"])
    assert pd.isna(row["tracked_crypto_market_breadth"])
    assert pd.isna(row["cross_asset_volatility"])
    assert row["market_asset_count"] == 1


def test_returns_empty_result_for_empty_input():
    candles = pd.DataFrame(columns=["date", "asset_symbol", "interval", "close"])

    result = build_cross_asset_features(candles, "BTC", "1h", min_market_assets=2)

    assert result.empty
    assert result.columns.tolist() == [
        "date",
        "asset_symbol",
        "interval",
        "close",
        "eth_btc_relative_return",
        "tracked_crypto_market_return",
        "tracked_crypto_market_breadth",
        "cross_asset_volatility",
        "market_asset_count",
    ]
