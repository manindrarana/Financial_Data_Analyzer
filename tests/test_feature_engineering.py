import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import numpy as np
import pandas as pd
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary


class TestModelFeatures:
    def test_has_29_features(self):
        assert len(MODEL_FEATURES) == 29

    def test_contains_key_indicators(self):
        for col in ["rsi_14", "stoch_k", "stoch_d", "macd_pct", "returns_1p", "log_returns", "hl_ratio"]:
            assert col in MODEL_FEATURES

    def test_contains_distance_features(self):
        for col in ["sma_7_dist", "ema_12_dist", "vwap_dist"]:
            assert col in MODEL_FEATURES

    def test_all_model_features_are_derived_from_needed_cols(self):
        derived = [f for f in MODEL_FEATURES if f not in NEEDED_COLS]
        for f in derived:
            assert "dist" in f or "pct" in f or f == "close_position"


class TestNeededCols:
    def test_has_31_columns(self):
        assert len(NEEDED_COLS) == 31

    def test_contains_close_and_date(self):
        assert "date" in NEEDED_COLS
        assert "close" in NEEDED_COLS

    def test_contains_all_sma_cols(self):
        for col in ["sma_7", "sma_30", "sma_50", "sma_100", "sma_200"]:
            assert col in NEEDED_COLS


class TestMakeStationary:
    def _make_test_df(self):
        np.random.seed(42)
        n = 500
        close = pd.Series(100 + np.cumsum(np.random.randn(n) * 0.5))
        close = close.clip(lower=0.01)
        return pd.DataFrame({
            "close": close,
            "sma_7": close.rolling(7).mean(),
            "sma_30": close.rolling(30).mean(),
            "sma_50": close.rolling(50).mean(),
            "sma_100": close.rolling(100).mean(),
            "sma_200": close.rolling(200).mean(),
            "ema_12": close.ewm(span=12).mean(),
            "ema_26": close.ewm(span=26).mean(),
            "ema_50": close.ewm(span=50).mean(),
            "ema_200": close.ewm(span=200).mean(),
            "vwap": close * 0.99,
            "macd": close * 0.01,
            "macd_signal": close * 0.005,
            "macd_histogram": close * 0.002,
            "atr_14": close * 0.02,
            "daily_volatility": close * 0.015,
        })

    def test_adds_sma_distance_columns(self):
        df = self._make_test_df()
        result = make_stationary(df)
        for col in ["sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist"]:
            assert col in result.columns

    def test_adds_ema_distance_columns(self):
        df = self._make_test_df()
        result = make_stationary(df)
        for col in ["ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist"]:
            assert col in result.columns

    def test_adds_vwap_dist(self):
        df = self._make_test_df()
        result = make_stationary(df)
        assert "vwap_dist" in result.columns

    def test_adds_macd_pct_columns(self):
        df = self._make_test_df()
        result = make_stationary(df)
        for col in ["macd_pct", "macd_sig_pct", "macd_hist_pct"]:
            assert col in result.columns

    def test_adds_atr_and_volatility_pct(self):
        df = self._make_test_df()
        result = make_stationary(df)
        assert "atr_pct" in result.columns
        assert "volatility_pct" in result.columns

    def test_returns_same_row_count(self):
        df = self._make_test_df()
        result = make_stationary(df)
        assert len(result) == len(df)

    def test_does_not_modify_original(self):
        df = self._make_test_df()
        original_cols = set(df.columns)
        result = make_stationary(df)
        assert set(df.columns) == original_cols

    def test_distance_values_are_reasonable(self):
        df = self._make_test_df()
        result = make_stationary(df)
        valid = result["sma_50_dist"].dropna()
        assert (valid.abs() < 1.0).all()

    def test_pct_values_are_reasonable(self):
        df = self._make_test_df()
        result = make_stationary(df)
        valid = result["atr_pct"].dropna()
        assert (valid.abs() < 1.0).all()