import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.models.technical_indicators import TechnicalIndicatorProcessor


def _make_price_df(n=500, start_price=100.0):
    np.random.seed(42)
    dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
    close = start_price + np.cumsum(np.random.randn(n) * 0.5)
    close = np.maximum(close, 1.0)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    low = np.maximum(low, 0.01)
    open_p = low + np.random.rand(n) * (high - low)
    volume = np.abs(np.random.randn(n) * 1000) + 100

    return pd.DataFrame({
        "date": dates,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def _make_processor():
    processor = TechnicalIndicatorProcessor.__new__(TechnicalIndicatorProcessor)
    processor.logger = MagicMock()
    return processor


class TestCalculateIndicators:
    def test_returns_same_row_count(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        assert len(result) == len(df)

    def test_adds_rsi_column(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        assert "rsi_14" in result.columns
        assert result["rsi_14"].notna().sum() > 0

    def test_adds_macd_columns(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        for col in ["macd", "macd_signal", "macd_histogram"]:
            assert col in result.columns
            assert result[col].notna().sum() > 0

    def test_adds_bollinger_bands(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        for col in ["bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_percentage"]:
            assert col in result.columns
            assert result[col].notna().sum() > 0

    def test_adds_ema_columns(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        for col in ["ema_12", "ema_26", "ema_50", "ema_200"]:
            assert col in result.columns

    def test_adds_sma_columns(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        for col in ["sma_50", "sma_100", "sma_200"]:
            assert col in result.columns

    def test_adds_return_columns(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        for col in ["returns_1p", "returns_5p", "returns_10p", "returns_20p"]:
            assert col in result.columns

    def test_adds_log_returns(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        assert "log_returns" in result.columns
        assert result["log_returns"].iloc[1] is not None

    def test_adds_prev_columns(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        for col in ["prev_close", "prev_volume", "prev_high", "prev_low"]:
            assert col in result.columns

    def test_adds_atr_volume_vwap(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        for col in ["atr_14", "obv", "vwap", "stoch_k", "stoch_d", "roc_10", "roc_20"]:
            assert col in result.columns

    def test_first_row_has_nan_for_windowed_indicators(self):
        processor = _make_processor()
        df = _make_price_df(500)
        result = processor.calculate_indicators_for_asset(df.copy())
        assert pd.isna(result["rsi_14"].iloc[0])
        assert pd.isna(result["returns_1p"].iloc[0])

    def test_sorts_by_date(self):
        processor = _make_processor()
        df = _make_price_df(500)
        shuffled = df.sample(frac=1).reset_index(drop=True)
        result = processor.calculate_indicators_for_asset(shuffled.copy())
        dates = result["date"].tolist()
        assert dates == sorted(dates)

    def test_handles_minimal_data(self):
        processor = _make_processor()
        df = _make_price_df(300)
        result = processor.calculate_indicators_for_asset(df.copy())
        assert len(result) == 300