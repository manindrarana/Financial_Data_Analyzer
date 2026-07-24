import json
import os
import numpy as np
import pandas as pd

OUTPUT_DIR = os.path.join("backtesting", "results")

CRYPTO_TRADING_DAYS = 365
STOCK_TRADING_DAYS = 252

CRYPTO_ANNUALIZATION_FACTORS = {
    "1h": CRYPTO_TRADING_DAYS * 24,
    "4h": CRYPTO_TRADING_DAYS * 6,
    "1d": CRYPTO_TRADING_DAYS,
    "1wk": 52,
    "1mo": 12,
    "W": 52,
    "M": 12,
    "60": CRYPTO_TRADING_DAYS * 24,
    "240": CRYPTO_TRADING_DAYS * 6,
    "D": CRYPTO_TRADING_DAYS,
}

STOCK_ANNUALIZATION_FACTORS = {
    "1h": STOCK_TRADING_DAYS * 24,
    "4h": STOCK_TRADING_DAYS * 6,
    "1d": STOCK_TRADING_DAYS,
    "1wk": 52,
    "1mo": 12,
    "W": 52,
    "M": 12,
    "60": STOCK_TRADING_DAYS * 24,
    "240": STOCK_TRADING_DAYS * 6,
    "D": STOCK_TRADING_DAYS,
}

ANNUALIZATION_FACTORS = STOCK_ANNUALIZATION_FACTORS


def _infer_periods_per_year(equity_df, asset_class=None):
    """Infer the annualization factor from the median time delta between rows.

    Falls back to 252 (daily stocks) or 365 (daily crypto) when detection is ambiguous.
    """
    base_days = CRYPTO_TRADING_DAYS if asset_class == "crypto" else STOCK_TRADING_DAYS
    dates = pd.to_datetime(equity_df["date"]).sort_values()
    deltas = dates.diff().dropna()
    if deltas.empty:
        return base_days
    median_seconds = deltas.median().total_seconds()
    hours = median_seconds / 3600
    if hours <= 1.5:
        return base_days * 24
    elif hours <= 5:
        return base_days * 6
    elif hours <= 30:
        return base_days
    elif hours <= 200:
        return 52
    else:
        return 12


def compute_metrics(trades_df, equity_df, initial_capital=10000, interval=None, asset_class=None):
    if trades_df.empty or equity_df.empty:
        return {
            "total_return_pct": 0.0,
            "total_pnl": 0.0,
            "total_cost": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
        }

    total_trades = int(len(trades_df))
    winning_trades = int((trades_df["pnl"] > 0).sum())
    losing_trades = int((trades_df["pnl"] <= 0).sum())
    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    total_pnl = trades_df["pnl"].sum()
    total_return_pct = (total_pnl / initial_capital) * 100
    total_cost = trades_df["total_cost"].sum() if "total_cost" in trades_df.columns else 0.0

    gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(trades_df[trades_df["pnl"] <= 0]["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
    avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0

    max_drawdown_pct = equity_df["drawdown_pct"].max()

    equity_df = equity_df.copy()
    equity_df["date"] = pd.to_datetime(equity_df["date"])
    equity_df = equity_df.sort_values("date")

    equity_df["period_return"] = equity_df["equity"].pct_change()

    period_returns = equity_df["period_return"].dropna()

    factors = CRYPTO_ANNUALIZATION_FACTORS if asset_class == "crypto" else STOCK_ANNUALIZATION_FACTORS

    if interval is not None:
        periods_per_year = factors.get(interval)
        if periods_per_year is None:
            periods_per_year = _infer_periods_per_year(equity_df, asset_class=asset_class)
    else:
        periods_per_year = _infer_periods_per_year(equity_df, asset_class=asset_class)

    if len(period_returns) > 1 and period_returns.std() > 0:
        sharpe_ratio = (period_returns.mean() / period_returns.std()) * np.sqrt(periods_per_year)
    else:
        sharpe_ratio = 0.0

    exit_reasons = {}
    if not trades_df.empty and "exit_reason" in trades_df.columns:
        for reason in trades_df["exit_reason"].value_counts().index:
            exit_reasons[reason] = int(trades_df["exit_reason"].value_counts()[reason])

    if "fold_id" in trades_df.columns:
        fold_metrics = []
        for fid in sorted(trades_df["fold_id"].dropna().unique()):
            fold_trades = trades_df[trades_df["fold_id"] == fid]
            fold_metrics.append({
                "fold_id": int(fid),
                "trades": len(fold_trades),
                "pnl": round(fold_trades["pnl"].sum(), 2),
                "win_rate": round(
                    (fold_trades["pnl"] > 0).sum() / len(fold_trades) * 100, 1
                ) if len(fold_trades) > 0 else 0.0,
            })
    else:
        fold_metrics = []

    direction_breakdown = []
    if "direction" in trades_df.columns:
        for dirn in sorted(trades_df["direction"].dropna().unique()):
            dir_trades = trades_df[trades_df["direction"] == dirn]
            dir_wins = int((dir_trades["pnl"] > 0).sum())
            direction_breakdown.append({
                "direction": dirn,
                "trades": len(dir_trades),
                "pnl": round(dir_trades["pnl"].sum(), 2),
                "win_rate": round(dir_wins / len(dir_trades) * 100, 1) if len(dir_trades) > 0 else 0.0,
            })

    asset_breakdown = []
    if "asset" in trades_df.columns:
        for asset in sorted(trades_df["asset"].dropna().unique()):
            asset_trades = trades_df[trades_df["asset"] == asset]
            asset_wins = int((asset_trades["pnl"] > 0).sum())
            asset_cost = asset_trades["total_cost"].sum() if "total_cost" in asset_trades.columns else 0.0
            asset_breakdown.append({
                "asset": asset,
                "trades": len(asset_trades),
                "pnl": round(asset_trades["pnl"].sum(), 2),
                "win_rate": round(asset_wins / len(asset_trades) * 100, 1) if len(asset_trades) > 0 else 0.0,
                "total_cost": round(asset_cost, 2),
            })

    return {
        "total_return_pct": round(total_return_pct, 2),
        "total_pnl": round(total_pnl, 2),
        "total_cost": round(total_cost, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "win_rate": round(win_rate * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "exit_reasons": exit_reasons,
        "fold_breakdown": fold_metrics,
        "direction_breakdown": direction_breakdown,
        "asset_breakdown": asset_breakdown,
    }   
    
def run_metrics(
    trades_path=None,
    equity_path=None,
    initial_capital=10000,
    return_data=False,
    trades_df=None,
    equity_df=None,
    interval=None,
):
    if trades_df is None or equity_df is None:
        if trades_path is None:
            trades_path = os.path.join(OUTPUT_DIR, "backtest_trades.parquet")
        if equity_path is None:
            equity_path = os.path.join(OUTPUT_DIR, "backtest_equity.parquet")

        if not os.path.exists(trades_path):
            raise FileNotFoundError(f"Trades file not found: {trades_path}")
        if not os.path.exists(equity_path):
            raise FileNotFoundError(f"Equity file not found: {equity_path}")

        print(f"\n=== Performance Metrics ===\n")

        trades_df = pd.read_parquet(trades_path)
        equity_df = pd.read_parquet(equity_path)
    else:
        print(f"\n=== Performance Metrics ===\n")

    metrics = compute_metrics(trades_df, equity_df, initial_capital, interval=interval)

    print(f"   Total Return:     {metrics['total_return_pct']:+.2f}%")
    print(f"   Total PnL:        ${metrics['total_pnl']:+,.2f}")
    print(f"   Total Cost:       ${metrics['total_cost']:,.2f}")
    print(f"   Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown:     {metrics['max_drawdown_pct']:.2f}%")
    print(f"   Win Rate:         {metrics['win_rate']:.1f}%")
    print(f"   Profit Factor:    {metrics['profit_factor']:.2f}")
    print(f"   Avg Win:          ${metrics['avg_win']:,.2f}")
    print(f"   Avg Loss:         ${metrics['avg_loss']:,.2f}")
    print(f"   Total Trades:     {metrics['total_trades']}")
    print(f"   Winning: {metrics['winning_trades']}  |  Losing: {metrics['losing_trades']}")

    if metrics["exit_reasons"]:
        print(f"\n   Exit reasons:")
        for reason, count in metrics["exit_reasons"].items():
            print(f"     {reason}: {count}")

    if metrics["fold_breakdown"]:
        print(f"\n   Per-fold breakdown:")
        for fm in metrics["fold_breakdown"]:
            print(f"     Fold {fm['fold_id']}: {fm['trades']} trades, "
                  f"PnL ${fm['pnl']:+,.2f}, Win {fm['win_rate']:.1f}%")

    if metrics.get("direction_breakdown"):
        print(f"\n   Direction breakdown:")
        for dm in metrics["direction_breakdown"]:
            print(f"     {dm['direction']}: {dm['trades']} trades, "
                  f"PnL ${dm['pnl']:+,.2f}, Win {dm['win_rate']:.1f}%")

    if metrics.get("asset_breakdown"):
        print(f"\n   Per-asset breakdown:")
        for am in metrics["asset_breakdown"]:
            print(f"     {am['asset']}: {am['trades']} trades, "
                  f"PnL ${am['pnl']:+,.2f}, Win {am['win_rate']:.1f}%, "
                  f"Cost ${am['total_cost']:.2f}")

    if return_data:
        return metrics

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    metrics_path = os.path.join(OUTPUT_DIR, "backtest_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n   Metrics saved: {metrics_path}")

    return metrics


if __name__ == "__main__":
    run_metrics()    