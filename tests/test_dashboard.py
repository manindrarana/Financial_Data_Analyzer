import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import os
from unittest.mock import patch, MagicMock
from dashboard.predictor import _discover_model, _INTERVAL_MINUTES, FEATURE_TABLES


class TestIntervalMinutes:
    def test_1h_is_60(self):
        assert _INTERVAL_MINUTES["1h"] == 60

    def test_4h_is_240(self):
        assert _INTERVAL_MINUTES["4h"] == 240

    def test_1d_is_1440(self):
        assert _INTERVAL_MINUTES["1d"] == 1440


class TestDiscoverModel:
    def test_exact_match_found(self):
        with patch("os.path.exists", return_value=True):
            path, interval = _discover_model("BTC", "1h", "crypto")
            assert "BTC_1h_xgboost_model.json" in path
            assert interval == "1h"

    def test_no_model_found(self):
        with patch("os.path.exists", return_value=False):
            with patch("os.path.isdir", return_value=True):
                with patch("os.listdir", return_value=[]):
                    path, interval = _discover_model("BTC", "1h", "crypto")
                    assert path is None
                    assert interval is None

    def test_fallback_to_nearest_interval(self):
        with patch("os.path.exists", side_effect=lambda p: "BTC_1h" not in p):
            with patch("os.path.isdir", return_value=True):
                with patch("os.listdir", return_value=[
                    "BTC_1d_xgboost_model.json",
                    "BTC_4h_xgboost_model.json",
                ]):
                    path, interval = _discover_model("BTC", "1h", "crypto")
                    assert path is not None
                    assert interval == "4h"


class TestFeatureTables:
    def test_crypto_table(self):
        assert FEATURE_TABLES["crypto"] == "gold_crypto_features"

    def test_stocks_table(self):
        assert FEATURE_TABLES["stocks"] == "gold_stock_features"