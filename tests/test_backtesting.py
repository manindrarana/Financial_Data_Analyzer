import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from backtesting.strategy import simulate_trades, simulate_portfolio_trades
from backtesting.metrics import (
    compute_metrics,
    ANNUALIZATION_FACTORS,
    CRYPTO_ANNUALIZATION_FACTORS,
    STOCK_ANNUALIZATION_FACTORS,
    CRYPTO_TRADING_DAYS,
    STOCK_TRADING_DAYS,
)


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

    def test_equity_reflects_unrealized_loss_on_open_trade(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 95.0, "prediction": 0, "confidence": 0.5},
            {"date": datetime(2024, 1, 1, 12, 0), "close": 95.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, equity = simulate_trades(
            df, confidence_threshold=0.52, stop_loss_pct=0.10, take_profit_pct=0.04, max_hold_bars=24
        )
        assert len(trades) == 1
        assert trades.iloc[0]["exit_reason"] == "force_close"
        assert 9999.0 < equity.iloc[0]["equity"] < 10000.0
        assert equity.iloc[1]["equity"] < 9995.0
        assert equity.iloc[1]["drawdown_pct"] > 0.0
        assert equity.iloc[2]["equity"] < 9995.0


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
    def test_stock_hourly_factor(self):
        assert STOCK_ANNUALIZATION_FACTORS["1h"] == 252 * 24

    def test_stock_daily_factor(self):
        assert STOCK_ANNUALIZATION_FACTORS["1d"] == 252

    def test_stock_weekly_factor(self):
        assert STOCK_ANNUALIZATION_FACTORS["1wk"] == 52

    def test_crypto_hourly_factor(self):
        assert CRYPTO_ANNUALIZATION_FACTORS["1h"] == 365 * 24

    def test_crypto_daily_factor(self):
        assert CRYPTO_ANNUALIZATION_FACTORS["1d"] == 365

    def test_crypto_weekly_factor(self):
        assert CRYPTO_ANNUALIZATION_FACTORS["1wk"] == 52

    def test_backward_compat_alias(self):
        assert ANNUALIZATION_FACTORS is STOCK_ANNUALIZATION_FACTORS

    def test_crypto_uses_more_days_than_stock(self):
        assert CRYPTO_TRADING_DAYS == 365
        assert STOCK_TRADING_DAYS == 252
        assert CRYPTO_ANNUALIZATION_FACTORS["1h"] > STOCK_ANNUALIZATION_FACTORS["1h"]
        assert CRYPTO_ANNUALIZATION_FACTORS["1d"] > STOCK_ANNUALIZATION_FACTORS["1d"]


class TestSharpeAnnualization:
    def _make_equity_curve(self, n=200, seed=42):
        np.random.seed(seed)
        dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
        returns = np.random.randn(n) * 0.005 + 0.002
        equity = 10000 * np.cumprod(1 + returns)
        equity = np.concatenate([[10000], equity[:-1]])
        return pd.DataFrame({
            "date": dates,
            "equity": equity,
            "drawdown_pct": 0.0,
        })

    def _make_trades(self):
        return pd.DataFrame([
            {"entry_time": datetime(2024, 1, 1), "exit_time": datetime(2024, 1, 2),
             "pnl": 10.0, "exit_reason": "take_profit"},
        ])

    def test_crypto_sharpe_higher_than_stock_same_interval(self):
        equity = self._make_equity_curve()
        trades = self._make_trades()
        crypto_metrics = compute_metrics(trades, equity, interval="1h", asset_class="crypto")
        stock_metrics = compute_metrics(trades, equity, interval="1h", asset_class="stock")
        assert crypto_metrics["sharpe_ratio"] > stock_metrics["sharpe_ratio"]

    def test_crypto_stock_sharpe_ratio_matches_trading_days(self):
        equity = self._make_equity_curve()
        trades = self._make_trades()
        crypto_metrics = compute_metrics(trades, equity, interval="1h", asset_class="crypto")
        stock_metrics = compute_metrics(trades, equity, interval="1h", asset_class="stock")
        if stock_metrics["sharpe_ratio"] != 0:
            ratio = crypto_metrics["sharpe_ratio"] / stock_metrics["sharpe_ratio"]
            expected = np.sqrt(CRYPTO_TRADING_DAYS / STOCK_TRADING_DAYS)
            assert abs(ratio - expected) < 0.01

    def test_default_asset_class_is_stock(self):
        equity = self._make_equity_curve()
        trades = self._make_trades()
        default_metrics = compute_metrics(trades, equity, interval="1h")
        stock_metrics = compute_metrics(trades, equity, interval="1h", asset_class="stock")
        assert default_metrics["sharpe_ratio"] == stock_metrics["sharpe_ratio"]

    def test_none_asset_class_uses_stock(self):
        equity = self._make_equity_curve()
        trades = self._make_trades()
        none_metrics = compute_metrics(trades, equity, interval="1h", asset_class=None)
        stock_metrics = compute_metrics(trades, equity, interval="1h", asset_class="stock")
        assert none_metrics["sharpe_ratio"] == stock_metrics["sharpe_ratio"]

    def test_daily_crypto_sharpe_higher_than_daily_stock(self):
        np.random.seed(42)
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(200)]
        returns = np.random.randn(200) * 0.01 + 0.001
        equity = 10000 * np.cumprod(1 + returns)
        equity = np.concatenate([[10000], equity[:-1]])
        equity_df = pd.DataFrame({"date": dates, "equity": equity, "drawdown_pct": 0.0})
        trades = self._make_trades()
        crypto_metrics = compute_metrics(trades, equity_df, interval="1d", asset_class="crypto")
        stock_metrics = compute_metrics(trades, equity_df, interval="1d", asset_class="stock")
        assert crypto_metrics["sharpe_ratio"] > stock_metrics["sharpe_ratio"]


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


class TestShortSelling:
    def test_short_enters_on_down_prediction(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 1, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            stop_loss_pct=0.02, take_profit_pct=0.04,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["direction"] == "short"

    def test_no_short_when_disabled(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 95.0, "prediction": 1, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=False,
        )
        assert trades.empty

    def test_short_take_profit_when_price_drops(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 94.0, "prediction": 1, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            take_profit_pct=0.04, transaction_cost_pct=0.0,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["exit_reason"] == "take_profit"
        assert trades.iloc[0]["exit_price"] == 96.0
        assert trades.iloc[0]["pnl"] == 4.0

    def test_short_stop_loss_when_price_rises(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 103.0, "prediction": 1, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            stop_loss_pct=0.02, transaction_cost_pct=0.0,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["exit_reason"] == "stop_loss"
        assert trades.iloc[0]["exit_price"] == 102.0
        assert trades.iloc[0]["pnl"] == -2.0

    def test_short_pnl_inverted(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 90.0, "prediction": 1, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            take_profit_pct=0.10, transaction_cost_pct=0.0,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["pnl"] == 10.0

    def test_short_cost_deducted(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 94.0, "prediction": 1, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            take_profit_pct=0.04, transaction_cost_pct=0.001,
        )
        assert len(trades) == 1
        entry_cost = 100.0 * 0.001
        exit_cost = 96.0 * 0.001
        expected_cost = round(entry_cost + exit_cost, 6)
        expected_pnl = round(100.0 - 96.0 - expected_cost, 4)
        assert trades.iloc[0]["total_cost"] == expected_cost
        assert trades.iloc[0]["pnl"] == expected_pnl

    def test_direction_column_present(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            take_profit_pct=0.04,
        )
        assert len(trades) == 1
        assert trades.iloc[0]["direction"] == "long"

    def test_both_long_and_short_trades(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 95.0, "prediction": 0, "confidence": 0.50},
            {"date": datetime(2024, 1, 1, 12, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 13, 0), "close": 105.0, "prediction": 0, "confidence": 0.50},
        ])
        trades, _ = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            take_profit_pct=0.04, stop_loss_pct=0.05,
            transaction_cost_pct=0.0,
        )
        assert len(trades) == 2
        assert trades.iloc[0]["direction"] == "short"
        assert trades.iloc[1]["direction"] == "long"

    def test_direction_breakdown_in_metrics(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 0, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 95.0, "prediction": 0, "confidence": 0.50},
            {"date": datetime(2024, 1, 1, 12, 0), "close": 100.0, "prediction": 1, "confidence": 0.6},
            {"date": datetime(2024, 1, 1, 13, 0), "close": 105.0, "prediction": 0, "confidence": 0.50},
        ])
        trades, equity = simulate_trades(
            df, confidence_threshold=0.52, allow_short=True,
            take_profit_pct=0.04, stop_loss_pct=0.05,
            transaction_cost_pct=0.0,
        )
        metrics = compute_metrics(trades, equity, interval="1h")
        assert "direction_breakdown" in metrics
        assert len(metrics["direction_breakdown"]) == 2
        directions = [d["direction"] for d in metrics["direction_breakdown"]]
        assert "long" in directions
        assert "short" in directions


class TestPortfolioBacktest:
    def _make_asset_predictions(self, asset, n=100, seed=42, start_price=100.0):
        np.random.seed(seed)
        dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
        close = start_price + np.cumsum(np.random.randn(n) * 0.5)
        close = np.maximum(close, 1.0)
        pred = np.random.choice([0, 1], size=n, p=[0.4, 0.6])
        conf = np.where(pred == 1, 0.55 + np.random.rand(n) * 0.2, 0.55 + np.random.rand(n) * 0.15)
        return pd.DataFrame({
            "date": dates,
            "close": close,
            "prediction": pred,
            "confidence": conf,
            "actual_direction": np.random.choice([0, 1], size=n),
            "fold_id": 1,
        })

    def test_portfolio_returns_trades_and_equity(self):
        preds = {
            "BTC": self._make_asset_predictions("BTC", 100, seed=42),
            "ETH": self._make_asset_predictions("ETH", 100, seed=99),
        }
        trades, equity = simulate_portfolio_trades(preds, confidence_threshold=0.52)
        assert isinstance(trades, pd.DataFrame)
        assert isinstance(equity, pd.DataFrame)

    def test_portfolio_trades_have_asset_column(self):
        preds = {
            "BTC": self._make_asset_predictions("BTC", 100, seed=42),
            "ETH": self._make_asset_predictions("ETH", 100, seed=99),
        }
        trades, _ = simulate_portfolio_trades(preds, confidence_threshold=0.52)
        if not trades.empty:
            assert "asset" in trades.columns
            assert set(trades["asset"].unique()).issubset({"BTC", "ETH"})

    def test_portfolio_max_positions_respected(self):
        preds = {
            "BTC": self._make_asset_predictions("BTC", 50, seed=42),
            "ETH": self._make_asset_predictions("ETH", 50, seed=99),
            "SOL": self._make_asset_predictions("SOL", 50, seed=7, start_price=50.0),
        }
        trades, _ = simulate_portfolio_trades(
            preds, confidence_threshold=0.50, max_positions=1,
        )
        if not trades.empty:
            trades_sorted = trades.sort_values("entry_time")
            for _, row in trades_sorted.iterrows():
                overlapping = trades_sorted[
                    (trades_sorted["entry_time"] < row["exit_time"]) &
                    (trades_sorted["exit_time"] > row["entry_time"])
                ]
                assert len(overlapping) <= 1

    def test_portfolio_equal_allocation(self):
        preds = {
            "BTC": self._make_asset_predictions("BTC", 100, seed=42),
            "ETH": self._make_asset_predictions("ETH", 100, seed=99),
        }
        trades, _ = simulate_portfolio_trades(
            preds, confidence_threshold=0.52,
            initial_capital=10000, max_positions=2,
        )
        if not trades.empty:
            expected_alloc = 10000 / 2
            for alloc in trades["allocation"]:
                assert abs(alloc - expected_alloc) < 0.01

    def test_portfolio_pnl_sums_correctly(self):
        preds = {
            "BTC": self._make_asset_predictions("BTC", 100, seed=42),
            "ETH": self._make_asset_predictions("ETH", 100, seed=99),
        }
        trades, equity = simulate_portfolio_trades(
            preds, confidence_threshold=0.52,
            initial_capital=10000, max_positions=2,
            transaction_cost_pct=0.0,
        )
        if not trades.empty:
            total_pnl = trades["pnl"].sum()
            final_equity = equity.iloc[-1]["equity"]
            initial = 10000.0
            assert abs((final_equity - initial) - total_pnl) < 1.0

    def test_portfolio_asset_breakdown_in_metrics(self):
        preds = {
            "BTC": self._make_asset_predictions("BTC", 100, seed=42),
            "ETH": self._make_asset_predictions("ETH", 100, seed=99),
        }
        trades, equity = simulate_portfolio_trades(preds, confidence_threshold=0.52)
        metrics = compute_metrics(trades, equity, interval="1h")
        assert "asset_breakdown" in metrics
        if not trades.empty:
            assert len(metrics["asset_breakdown"]) > 0
            for am in metrics["asset_breakdown"]:
                assert "asset" in am
                assert "trades" in am
                assert "pnl" in am
                assert "win_rate" in am

    def test_portfolio_empty_dict_returns_empty(self):
        trades, equity = simulate_portfolio_trades({})
        assert trades.empty
        assert equity.empty

    def test_portfolio_single_asset_take_profit(self):
        df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6, "fold_id": 1},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5, "fold_id": 1},
        ])
        preds = {"BTC": df, "ETH": df.copy()}
        trades, _ = simulate_portfolio_trades(
            preds, confidence_threshold=0.52,
            take_profit_pct=0.04, transaction_cost_pct=0.0,
            max_positions=2, initial_capital=10000,
        )
        assert len(trades) == 2
        assert trades.iloc[0]["exit_reason"] == "take_profit"
        assert trades.iloc[0]["exit_price"] == 104.0
        expected_alloc = 10000 / 2
        expected_size = expected_alloc / 100.0
        expected_pnl = expected_size * (104.0 - 100.0)
        assert trades.iloc[0]["pnl"] == round(expected_pnl, 4)

    def test_portfolio_two_assets_different_pnl(self):
        btc_df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 100.0, "prediction": 1, "confidence": 0.6, "fold_id": 1},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 105.0, "prediction": 0, "confidence": 0.5, "fold_id": 1},
        ])
        eth_df = pd.DataFrame([
            {"date": datetime(2024, 1, 1, 10, 0), "close": 200.0, "prediction": 1, "confidence": 0.6, "fold_id": 1},
            {"date": datetime(2024, 1, 1, 11, 0), "close": 210.0, "prediction": 0, "confidence": 0.5, "fold_id": 1},
        ])
        preds = {"BTC": btc_df, "ETH": eth_df}
        trades, _ = simulate_portfolio_trades(
            preds, confidence_threshold=0.52,
            take_profit_pct=0.04, transaction_cost_pct=0.0,
            max_positions=2, initial_capital=10000,
        )
        assert len(trades) == 2
        btc_trade = trades[trades["asset"] == "BTC"].iloc[0]
        eth_trade = trades[trades["asset"] == "ETH"].iloc[0]
        alloc = 10000 / 2
        btc_size = alloc / 100.0
        eth_size = alloc / 200.0
        assert btc_trade["pnl"] == round(btc_size * (104.0 - 100.0), 4)
        assert eth_trade["pnl"] == round(eth_size * (208.0 - 200.0), 4)
        assert eth_trade["pnl"] == btc_trade["pnl"]