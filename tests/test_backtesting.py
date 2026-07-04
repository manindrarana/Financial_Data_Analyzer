import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from backtesting.strategy import simulate_trades
from backtesting.metrics import compute_metrics, ANNUALIZATION_FACTORS


def _make_predictions(n=200, seed=42):
    np.random.seed(seed)
    dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
    close = 100 + np.cumsum(np.random.randn(n) * 0.3)
    close = np.maximum(close, 1.0)
    pred = np.random.choice([0, 1], size=n, p=[0.45, 0.55])
    conf = np.where(pred == 1, 0.5 + np.random.rand(n) * 0.3, 0.5 + np.random.rand(n) * 0.2)
    actual = np.random.choice([0, 1], size=n)
    return pd.DataFrame({
        "date": dates,
        "close": close,
        "prediction": pred,
        "confidence": conf,
        "actual_direction": actual,
        "fold_id": [1] * (n // 2) + [2] * (n - n // 2),
    })


class TestSimulateTrades:
    def test_returns_trades_and_equity(self):
        df = _make_predictions(200)
        trades, equity = simulate_trades(df, confidence_threshold=0.52)
        assert isinstance(trades, pd.DataFrame)
        assert isinstance(equity, pd.DataFrame)

    def test_equity_has_required_columns(self):
        df = _make_predictions(200)
        trades, equity = simulate_trades(df, confidence_threshold=0.52)
        for col in ["date", "equity", "drawdown_pct"]:
            assert col in equity.columns

    def test_trades_has_required_columns(self):
        df = _make_predictions(200)
        trades, equity = simulate_trades(df, confidence_threshold=0.52)
        if not trades.empty:
            for col in ["entry_time", "exit_time", "entry_price", "exit_price", "pnl", "exit_reason"]:
                assert col in trades.columns

    def test_stop_loss_triggers(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 97.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, equity = simulate_trades(df, confidence_threshold=0.52, stop_loss_pct=0.02)
        assert len(trades) == 1
        assert trades.iloc[0]["exit_reason"] == "stop_loss"

    def test_take_profit_triggers(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, equity = simulate_trades(df, confidence_threshold=0.52, take_profit_pct=0.04)
        assert len(trades) == 1
        assert trades.iloc[0]["exit_reason"] == "take_profit"

    def test_no_trades_below_confidence(self):
        df = _make_predictions(200)
        df["confidence"] = 0.50
        trades, equity = simulate_trades(df, confidence_threshold=0.95)
        assert trades.empty


class TestComputeMetrics:
    def test_returns_all_expected_keys(self):
        df = _make_predictions(200)
        trades, equity = simulate_trades(df, confidence_threshold=0.52)
        if trades.empty:
            pytest.skip("No trades generated")
        metrics = compute_metrics(trades, equity, interval="1h")
        expected = ["total_return_pct", "total_pnl", "sharpe_ratio", "max_drawdown_pct",
                    "win_rate", "profit_factor", "avg_win", "avg_loss", "total_trades"]
        for key in expected:
            assert key in metrics

    def test_empty_trades_returns_zeros(self):
        metrics = compute_metrics(pd.DataFrame(), pd.DataFrame({"date": [], "equity": [], "drawdown_pct": []}))
        assert metrics["total_trades"] == 0
        assert metrics["sharpe_ratio"] == 0.0

    def test_win_rate_calculation(self):
        trades = pd.DataFrame([
            {"entry_time": datetime(2024, 1, 1), "exit_time": datetime(2024, 1, 2),
             "pnl": 10.0, "exit_reason": "take_profit"},
            {"entry_time": datetime(2024, 1, 3), "exit_time": datetime(2024, 1, 4),
             "pnl": -5.0, "exit_reason": "stop_loss"},
        ])
        equity = pd.DataFrame([
            {"date": datetime(2024, 1, 1), "equity": 10000, "drawdown_pct": 0.0},
            {"date": datetime(2024, 1, 2), "equity": 10010, "drawdown_pct": 0.0},
            {"date": datetime(2024, 1, 3), "equity": 10005, "drawdown_pct": 0.05},
        ])
        metrics = compute_metrics(trades, equity)
        assert metrics["win_rate"] == 50.0
        assert metrics["total_trades"] == 2
        assert metrics["total_pnl"] == 5.0


class TestAnnualizationFactors:
    def test_hourly_factor(self):
        assert ANNUALIZATION_FACTORS["1h"] == 252 * 24

    def test_daily_factor(self):
        assert ANNUALIZATION_FACTORS["1d"] == 252

    def test_weekly_factor(self):
        assert ANNUALIZATION_FACTORS["1wk"] == 52


class TestTransactionCosts:
    def test_take_profit_cost_deducted(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, take_profit_pct=0.04,
            transaction_cost_pct=0.001,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["exit_reason"] == "take_profit"
        assert trades.iloc[0]["exit_price"] == 104.0
        entry_cost = 100.0 * 0.001
        exit_cost = 104.0 * 0.001
        expected_cost = round(entry_cost + exit_cost, 6)
        expected_pnl = round(104.0 - 100.0 - expected_cost, 4)
        assert trades.iloc[0]["total_cost"] == expected_cost
        assert trades.iloc[0]["pnl"] == expected_pnl
        assert trades.iloc[0]["pnl"] < 4.0

    def test_stop_loss_cost_deducted(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 97.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, stop_loss_pct=0.02,
            transaction_cost_pct=0.001,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["exit_reason"] == "stop_loss"
        assert trades.iloc[0]["exit_price"] == 98.0
        entry_cost = 100.0 * 0.001
        exit_cost = 98.0 * 0.001
        expected_cost = round(entry_cost + exit_cost, 6)
        expected_pnl = round(98.0 - 100.0 - expected_cost, 4)
        assert trades.iloc[0]["total_cost"] == expected_cost
        assert trades.iloc[0]["pnl"] == expected_pnl
        assert trades.iloc[0]["pnl"] < -2.0

    def test_zero_cost_matches_raw_pnl(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, take_profit_pct=0.04,
            transaction_cost_pct=0.0,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["pnl"] == 4.0
        assert trades.iloc[0]["total_cost"] == 0.0

    def test_total_cost_in_metrics(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, equity = simulate_trades(
            df, confidence_threshold=0.52, take_profit_pct=0.04,
            transaction_cost_pct=0.001,
        )
        metrics = compute_metrics(trades, equity, interval="1h")
        assert "total_cost" in metrics
        assert metrics["total_cost"] == round(trades["total_cost"].sum(), 2)

    def test_higher_cost_reduces_pnl(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5},
        ])
        trades_low, _ = simulate_trades(
            df, confidence_threshold=0.52, take_profit_pct=0.04,
            transaction_cost_pct=0.001,
        )
        trades_high, _ = simulate_trades(
            df, confidence_threshold=0.52, take_profit_pct=0.04,
            transaction_cost_pct=0.005,
        )
        assert trades_high.iloc[0]["pnl"] < trades_low.iloc[0]["pnl"]
        assert trades_high.iloc[0]["total_cost"] > trades_low.iloc[0]["total_cost"]