import pandas as pd
import pytest

import scripts.run_cross_asset_experiment as cross_asset_experiment
from scripts.run_cross_asset_experiment import (
    EXPERIMENT_FEATURES,
    build_cross_asset_features,
    evaluate_experiment_model,
    load_target_features,
    merge_cross_asset_features,
    prepare_target_features,
    split_experiment_data,
    train_experiment_model,
)
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS


def test_compare_experiment_variants_uses_identical_rows_and_returns_metadata(monkeypatch):
    rows = []
    for index in range(125):
        row = {column: float(index + 1) for column in MODEL_FEATURES}
        row.update(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=index),
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
        return object()

    def fake_evaluate(search, X_test, y_test):
        return {"accuracy": len(X_test) / 100}

    monkeypatch.setattr(cross_asset_experiment, "prepare_experiment_dataset", fake_prepare)
    monkeypatch.setattr(cross_asset_experiment, "split_experiment_data", fake_split)
    monkeypatch.setattr(cross_asset_experiment, "train_experiment_model", fake_train)
    monkeypatch.setattr(cross_asset_experiment, "evaluate_experiment_model", fake_evaluate)

    result = cross_asset_experiment.compare_experiment_variants("ignored.duckdb")

    assert split_features[0] == MODEL_FEATURES
    assert split_features[1] == [*MODEL_FEATURES, *EXPERIMENT_FEATURES]
    assert trained_rows == [(100, 100), (100, 100)]
    assert result["asset"] == "BTC"
    assert result["interval"] == "1h"
    assert result["total_rows"] == 125
    assert result["train_rows"] == 100
    assert result["test_rows"] == 25
    assert result["test_start"] == pd.Timestamp("2026-01-05 04:00")
    assert result["test_end"] == pd.Timestamp("2026-01-06 04:00")
    assert result["baseline"]["accuracy"] == pytest.approx(0.25)
    assert result["cross_asset"]["accuracy"] == pytest.approx(0.25)
    assert result["test_predictions"].columns.tolist() == [
        "date",
        "actual_direction",
        "baseline_prediction",
        "cross_asset_prediction",
    ]
    assert len(result["test_predictions"]) == 25
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
        def predict(self, X):
            return [0, 1, 1, 0]

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

    assert metrics["accuracy"] == pytest.approx(0.75)
    assert metrics["balanced_accuracy"] == pytest.approx(5 / 6)
    assert metrics["f1"] == pytest.approx(2 / 3)
    assert metrics["best_cv_score"] == pytest.approx(0.6)


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
