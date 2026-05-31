import os
import numpy as np
import pandas as pd

OUTPUT_DIR = os.path.join("backtesting", "results")


def simulate_trades(
    predictions_df,
    confidence_threshold=0.52,
    stop_loss_pct=0.02,
    take_profit_pct=0.04,
    max_hold_bars=24,
    initial_capital=10000,
):
    df = predictions_df.copy()
    df = df.sort_values("date").reset_index(drop=True)

    if df.empty:
        print("No predictions to simulate.")
        return pd.DataFrame(), pd.DataFrame()

    required_cols = ["date", "close", "prediction", "confidence"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    trades = []
    equity = []
    cash = initial_capital
    equity_peak = initial_capital
    in_position = False
    entry_idx = None
    entry_price = None
    stop_price = None
    target_price = None
    bars_held = 0

    for i in range(len(df)):
        current_date = df.loc[i, "date"]
        current_price = df.loc[i, "close"]
        pred = int(df.loc[i, "prediction"])
        conf = float(df.loc[i, "confidence"])

        if in_position:
            bars_held += 1
            exit_price = None
            exit_reason = None

            if current_price <= stop_price:
                exit_price = stop_price
                exit_reason = "stop_loss"
            elif current_price >= target_price:
                exit_price = target_price
                exit_reason = "take_profit"
            elif bars_held >= max_hold_bars:
                exit_price = current_price
                exit_reason = "max_hold"

            if exit_price is not None:
                pnl = exit_price - entry_price
                pnl_pct = (exit_price / entry_price - 1) * 100
                cash += pnl

                trades.append({
                    "entry_time": df.loc[entry_idx, "date"],
                    "exit_time": current_date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": round(pnl, 4),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason,
                    "bars_held": bars_held,
                    "confidence": float(df.loc[entry_idx, "confidence"]),
                    "fold_id": int(df.loc[entry_idx, "fold_id"]) if "fold_id" in df.columns else None,
                })

                in_position = False
                entry_idx = None
                entry_price = None
                stop_price = None
                target_price = None
                bars_held = 0

        if not in_position and pred == 1 and conf >= confidence_threshold:
            entry_idx = i
            entry_price = current_price
            stop_price = entry_price * (1 - stop_loss_pct)
            target_price = entry_price * (1 + take_profit_pct)
            bars_held = 0
            in_position = True

        current_equity = cash
        if current_equity > equity_peak:
            equity_peak = current_equity

        equity.append({
            "date": current_date,
            "equity": round(current_equity, 2),
            "drawdown_pct": round((equity_peak - current_equity) / equity_peak * 100, 2),
        })

    if in_position:
        exit_price = df.loc[len(df) - 1, "close"]
        pnl = exit_price - entry_price
        pnl_pct = (exit_price / entry_price - 1) * 100
        cash += pnl

        trades.append({
            "entry_time": df.loc[entry_idx, "date"],
            "exit_time": df.loc[len(df) - 1, "date"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 2),
            "exit_reason": "force_close",
            "bars_held": bars_held,
            "confidence": float(df.loc[entry_idx, "confidence"]),
            "fold_id": int(df.loc[entry_idx, "fold_id"]) if "fold_id" in df.columns else None,
        })

        equity.append({
            "date": df.loc[len(df) - 1, "date"],
            "equity": round(cash, 2),
            "drawdown_pct": round((equity_peak - cash) / equity_peak * 100, 2),
        })

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)

    if not trades_df.empty:
        trades_df["cumulative_pnl"] = trades_df["pnl"].cumsum()

    return trades_df, equity_df


def run_strategy(
    predictions_path=None,
    confidence_threshold=0.52,
    stop_loss_pct=0.02,
    take_profit_pct=0.04,
    max_hold_bars=24,
    initial_capital=10000,
):
    if predictions_path is None:
        predictions_path = os.path.join(OUTPUT_DIR, "walk_forward_predictions.parquet")

    if not os.path.exists(predictions_path):
        raise FileNotFoundError(
            f"Predictions file not found: {predictions_path}. "
            "Run walk_forward.py first."
        )

    print(f"\n=== Strategy Simulation ===")
    print(f"   Confidence threshold: {confidence_threshold}")
    print(f"   Stop loss: {stop_loss_pct*100:.0f}%")
    print(f"   Take profit: {take_profit_pct*100:.0f}%")
    print(f"   Max hold: {max_hold_bars} bars")
    print(f"   Initial capital: ${initial_capital:,.0f}\n")

    predictions = pd.read_parquet(predictions_path)
    print(f"   Loaded {len(predictions):,} predictions")

    trades_df, equity_df = simulate_trades(
        predictions,
        confidence_threshold,
        stop_loss_pct,
        take_profit_pct,
        max_hold_bars,
        initial_capital,
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trades_path = os.path.join(OUTPUT_DIR, "backtest_trades.parquet")
    trades_df.to_parquet(trades_path)
    print(f"   Trades saved: {trades_path} ({len(trades_df)} trades)")

    equity_path = os.path.join(OUTPUT_DIR, "backtest_equity.parquet")
    equity_df.to_parquet(equity_path)
    print(f"   Equity saved: {equity_path} ({len(equity_df)} rows)")

    total_pnl = trades_df["pnl"].sum() if not trades_df.empty else 0
    win_count = (trades_df["pnl"] > 0).sum() if not trades_df.empty else 0
    total_trades = len(trades_df)

    print(f"\n   Total trades: {total_trades}")
    print(f"   Winning trades: {win_count}")
    print(f"   Win rate: {win_count/total_trades*100:.1f}%" if total_trades > 0 else "   Win rate: N/A")
    print(f"   Total PnL: ${total_pnl:,.2f}")

    return trades_df, equity_df


if __name__ == "__main__":
    run_strategy()