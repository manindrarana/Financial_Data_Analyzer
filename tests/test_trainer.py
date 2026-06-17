import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()
sys.modules["mlflow"] = MagicMock()
sys.modules["mlflow.xgboost"] = MagicMock()

import pytest
import json
import os
import tempfile
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