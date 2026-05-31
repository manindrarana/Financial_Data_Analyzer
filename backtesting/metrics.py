import json
import os
import numpy as np
import pandas as pd

OUTPUT_DIR = os.path.join("backtesting", "results")


def compute_metrics(trades_df, equity_df, initial_capital=10000):
    if trades_df.empty or equity_df.empty:
        return {
            "total_return_pct": 0.0,
            "total_pnl": 0.0,
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

    total_trades = len(trades_df)
    winning_trades = (trades_df["pnl"] > 0).sum()
    losing_trades = (trades_df["pnl"] <= 0).sum()
    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    total_pnl = trades_df["pnl"].sum()
    total_return_pct = (total_pnl / initial_capital) * 100

    gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(trades_df[trades_df["pnl"] <= 0]["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
    avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0

    max_drawdown_pct = equity_df["drawdown_pct"].max()

    equity_df = equity_df.copy()
    equity_df["date"] = pd.to_datetime(equity_df["date"])
    equity_df = equity_df.sort_values("date")

    equity_df["daily_return"] = equity_df["equity"].pct_change()

    daily_returns = equity_df["daily_return"].dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
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

    return {
        "total_return_pct": round(total_return_pct, 2),
        "total_pnl": round(total_pnl, 2),
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
    }