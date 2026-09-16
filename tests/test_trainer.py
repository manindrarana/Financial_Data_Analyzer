import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()
sys.modules["mlflow"] = MagicMock()
sys.modules["mlflow.xgboost"] = MagicMock()

import pytest
import json
import os
import tempfile
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from src.models.trainer import PipelineModelTrainer


def _mock_trainer(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr(PipelineModelTrainer, "__init__", lambda self: (
        setattr(self, "logger", MagicMock()),
        setattr(self, "conn", mock_conn),
        setattr(self, "config", {
            "paths": {"database": "/tmp/test.duckdb"},
            "ingestion": {
                "targets": {"bybit": ["BTCUSDT"], "yfinance": ["AAPL"]},
            },
            "providers": {
                "bybit": {"intervals": ["60", "D"]},
                "yfinance": {"intervals": ["1h", "1d"]},
            },
        }),
        setattr(self, "models_dir", "/tmp/model_store"),
        setattr(self, "crypto_dir", "/tmp/model_store/crypto"),
        setattr(self, "stocks_dir", "/tmp/model_store/stocks"),
        None
    )[-1])


class TestBuildCombos:
    def test_builds_crypto_combos(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        combos = trainer._build_combos()
        crypto = [c for c in combos if c[2] == "crypto"]
        assert len(crypto) == 2
        assert ("BTC", "1h", "crypto", "gold_crypto_features") in crypto
        assert ("BTC", "1d", "crypto", "gold_crypto_features") in crypto

    def test_builds_stock_combos(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        combos = trainer._build_combos()
        stocks = [c for c in combos if c[2] == "stocks"]
        assert len(stocks) == 2
        assert ("AAPL", "1h", "stocks", "gold_stock_features") in stocks
        assert ("AAPL", "1d", "stocks", "gold_stock_features") in stocks


class TestReadMetadata:
    def test_returns_none_when_no_files(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        with patch("os.path.exists", return_value=False):
            result = trainer._read_metadata("BTC", "1h", "crypto")
        assert result is None

    def test_raises_on_corrupt_json(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", side_effect=json.JSONDecodeError("bad", "", 0)):
                    with pytest.raises(json.JSONDecodeError):
                        trainer._read_metadata("BTC", "1h", "crypto")


class TestGetMetadataPath:
    def test_returns_crypto_path(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        meta_path, model_path = trainer._get_metadata_path("BTC", "1h", "crypto")
        assert "crypto" in meta_path
        assert "BTC_1h_xgboost_metadata.json" in meta_path
        assert "BTC_1h_xgboost_model.json" in model_path

    def test_returns_stock_path(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        meta_path, model_path = trainer._get_metadata_path("AAPL", "1d", "stocks")
        assert "stocks" in meta_path
        assert "AAPL_1d_xgboost_metadata.json" in meta_path
        assert "AAPL_1d_xgboost_model.json" in model_path


def _promotion_trainer(monkeypatch, tmp_path):
    trainer = PipelineModelTrainer.__new__(PipelineModelTrainer)
    trainer.logger = MagicMock()
    trainer.conn = MagicMock()
    trainer.config = {"paths": {"database": "/tmp/test.duckdb"}}
    trainer.db_path = "/tmp/test.duckdb"
    trainer.models_dir = str(tmp_path)
    trainer.crypto_dir = str(tmp_path / "crypto")
    trainer.stocks_dir = str(tmp_path / "stocks")
    (tmp_path / "crypto").mkdir(parents=True, exist_ok=True)
    (tmp_path / "stocks").mkdir(parents=True, exist_ok=True)
    trainer.last_retrained_models = []
    return trainer


def _fake_feature_frame(n=300):
    close = np.arange(n, dtype=float) + 100.0
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="h"),
        "close": close,
        "f1": np.linspace(0.0, 1.0, n),
        "f2": np.linspace(1.0, 0.0, n),
    })


class _FakeModel:
    def __init__(self, *args, **kwargs):
        pass

    def save_model(self, path):
        with open(path, "w") as f:
            f.write("new-model")

    def predict_proba(self, X):
        n = len(X)
        probs = np.array([0.9 if i < n - 1 else 0.1 for i in range(n)])
        return np.column_stack([1 - probs, probs])


class _FakeCalibrator:
    def __init__(self, *args, **kwargs):
        self.coef_ = np.array([[0.5]])
        self.intercept_ = np.array([0.1])

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        probs = np.asarray(X).ravel()
        return np.column_stack([1 - probs, probs])


class _FakeGrid:
    def __init__(self, *args, **kwargs):
        self.best_estimator_ = _FakeModel()
        self.best_params_ = {"max_depth": 3}
        self.best_score_ = 0.52

    def fit(self, X, y):
        return self


class TestModelPromotion:
    def _prepare(self, monkeypatch, tmp_path, existing_meta=None, corrupt=False):
        trainer = _promotion_trainer(monkeypatch, tmp_path)
        monkeypatch.setattr(trainer, "_fetch_data", lambda *a, **k: _fake_feature_frame())
        monkeypatch.setattr("src.models.trainer.make_stationary", lambda df: df)
        monkeypatch.setattr("src.models.trainer.MODEL_FEATURES", ["f1", "f2"])
        monkeypatch.setattr("src.models.trainer.GridSearchCV", _FakeGrid)
        monkeypatch.setattr("src.models.trainer.LogisticRegression", _FakeCalibrator)
        monkeypatch.setattr("src.models.trainer.xgb", MagicMock())
        monkeypatch.setattr("src.models.trainer.os.makedirs", MagicMock())
        monkeypatch.setattr("src.models.trainer.shutil.copy2", MagicMock())
        mlflow_mock = MagicMock()
        mlflow_mock.active_run.return_value.info.run_id = "run-123"
        monkeypatch.setattr("src.models.trainer.mlflow", mlflow_mock)

        meta_path, model_path = trainer._get_metadata_path("BTC", "1h", "crypto")
        if corrupt:
            with open(meta_path, "w") as f:
                f.write("{broken json")
            with open(model_path, "w") as f:
                f.write("old-model")
        elif existing_meta is not None:
            with open(meta_path, "w") as f:
                json.dump(existing_meta, f)
            with open(model_path, "w") as f:
                f.write("old-model")
        return trainer, meta_path, model_path

    def test_equal_accuracy_keeps_existing_model_files(self, monkeypatch, tmp_path):
        trainer, meta_path, model_path = self._prepare(
            monkeypatch, tmp_path, existing_meta={"test_accuracy": 1.0, "trained_at": "old"}
        )
        before_meta = open(meta_path).read()
        result = trainer._train_one("BTC", "1h", "crypto", "gold_crypto_features")

        assert result["decision"] == "kept_existing"
        assert result["accuracy"] == pytest.approx(1.0)
        assert result["previous_accuracy"] == pytest.approx(1.0)
        assert open(meta_path).read() == before_meta
        assert open(model_path).read() == "old-model"
        assert trainer.last_retrained_models == []

    def test_lower_new_accuracy_keeps_existing_model_files(self, monkeypatch, tmp_path):
        trainer, meta_path, model_path = self._prepare(
            monkeypatch, tmp_path, existing_meta={"test_accuracy": 0.9}
        )
        monkeypatch.setattr("src.models.trainer.accuracy_score", lambda y_t, y_p: 0.4123)
        result = trainer._train_one("BTC", "1h", "crypto", "gold_crypto_features")

        assert result["decision"] == "kept_existing"
        assert result["accuracy"] == pytest.approx(0.4123)
        assert result["previous_accuracy"] == pytest.approx(0.9)
        assert open(model_path).read() == "old-model"
        assert json.load(open(meta_path))["test_accuracy"] == pytest.approx(0.9)

    def test_better_new_accuracy_replaces_both_files(self, monkeypatch, tmp_path):
        trainer, meta_path, model_path = self._prepare(
            monkeypatch, tmp_path, existing_meta={"test_accuracy": 0.9, "trained_at": "old"}
        )
        result = trainer._train_one("BTC", "1h", "crypto", "gold_crypto_features")

        assert result["decision"] == "replaced"
        assert result["accuracy"] == pytest.approx(1.0)
        assert result["previous_accuracy"] == pytest.approx(0.9)
        saved = json.load(open(meta_path))
        assert saved["test_accuracy"] == pytest.approx(1.0)
        assert saved["trained_at"] != "old"
        assert saved["mlflow_run_id"] == "run-123"
        assert open(model_path).read() == "new-model"
        assert trainer.last_retrained_models == ["BTC_1h"]

    def test_first_train_without_saved_model_is_created(self, monkeypatch, tmp_path):
        trainer, meta_path, model_path = self._prepare(monkeypatch, tmp_path)
        assert not os.path.exists(meta_path)
        result = trainer._train_one("BTC", "1h", "crypto", "gold_crypto_features")

        assert result["decision"] == "created"
        assert result["previous_accuracy"] is None
        assert json.load(open(meta_path))["test_accuracy"] == pytest.approx(1.0)
        assert open(model_path).read() == "new-model"

    def test_unreadable_metadata_falls_back_to_saving(self, monkeypatch, tmp_path):
        trainer, meta_path, model_path = self._prepare(monkeypatch, tmp_path, corrupt=True)
        result = trainer._train_one("BTC", "1h", "crypto", "gold_crypto_features")

        assert result["decision"] == "created"
        assert result["previous_accuracy"] is None
        assert json.load(open(meta_path))["test_accuracy"] == pytest.approx(1.0)


class TestReadExistingAccuracy:
    def test_missing_metadata_returns_none(self, monkeypatch, tmp_path):
        trainer = _promotion_trainer(monkeypatch, tmp_path)
        assert trainer._read_existing_accuracy("BTC", "1h", "crypto") is None

    def test_returns_saved_accuracy_value(self, monkeypatch, tmp_path):
        trainer = _promotion_trainer(monkeypatch, tmp_path)
        meta_path, model_path = trainer._get_metadata_path("BTC", "1h", "crypto")
        with open(meta_path, "w") as f:
            json.dump({"test_accuracy": 0.5312}, f)
        with open(model_path, "w") as f:
            f.write("model")

        assert trainer._read_existing_accuracy("BTC", "1h", "crypto") == pytest.approx(0.5312)

    def test_corrupt_metadata_returns_none(self, monkeypatch, tmp_path):
        trainer = _promotion_trainer(monkeypatch, tmp_path)
        meta_path, model_path = trainer._get_metadata_path("BTC", "1h", "crypto")
        with open(meta_path, "w") as f:
            f.write("{broken json")
        with open(model_path, "w") as f:
            f.write("model")

        assert trainer._read_existing_accuracy("BTC", "1h", "crypto") is None

    def test_non_numeric_accuracy_returns_none(self, monkeypatch, tmp_path):
        trainer = _promotion_trainer(monkeypatch, tmp_path)
        meta_path, model_path = trainer._get_metadata_path("BTC", "1h", "crypto")
        with open(meta_path, "w") as f:
            json.dump({"test_accuracy": "high"}, f)
        with open(model_path, "w") as f:
            f.write("model")

        assert trainer._read_existing_accuracy("BTC", "1h", "crypto") is None