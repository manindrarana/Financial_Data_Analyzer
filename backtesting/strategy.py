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
    transaction_cost_pct=0.001,
    allow_short=False,
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
    entry_cost = 0.0
    stop_price = None
    target_price = None
    direction = None
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

            if direction == "long":
                if current_price <= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop_loss"
                elif current_price >= target_price:
                    exit_price = target_price
                    exit_reason = "take_profit"
            else:
                if current_price >= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop_loss"
                elif current_price <= target_price:
                    exit_price = target_price
                    exit_reason = "take_profit"

            if exit_price is None and bars_held >= max_hold_bars:
                exit_price = current_price
                exit_reason = "max_hold"

            if exit_price is not None:
                entry_cost = entry_price * transaction_cost_pct
                exit_cost = exit_price * transaction_cost_pct
                total_cost = entry_cost + exit_cost

                if direction == "long":
                    pnl = exit_price - entry_price - total_cost
                else:
                    pnl = entry_price - exit_price - total_cost

                pnl_pct = (pnl / entry_price) * 100
                cash += pnl

                trades.append({
                    "entry_time": df.loc[entry_idx, "date"],
                    "exit_time": current_date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "direction": direction,
                    "pnl": round(pnl, 4),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason,
                    "bars_held": bars_held,
                    "confidence": float(df.loc[entry_idx, "confidence"]),
                    "fold_id": int(df.loc[entry_idx, "fold_id"]) if "fold_id" in df.columns else None,
                    "total_cost": round(total_cost, 6),
                })

                in_position = False
                entry_idx = None
                entry_price = None
                stop_price = None
                target_price = None
                direction = None
                bars_held = 0

        if not in_position and conf >= confidence_threshold:
            if pred == 1:
                entry_idx = i
                entry_price = current_price
                entry_cost = entry_price * transaction_cost_pct
                stop_price = entry_price * (1 - stop_loss_pct)
                target_price = entry_price * (1 + take_profit_pct)
                direction = "long"
                bars_held = 0
                in_position = True
            elif allow_short and pred == 0:
                entry_idx = i
                entry_price = current_price
                entry_cost = entry_price * transaction_cost_pct
                stop_price = entry_price * (1 + stop_loss_pct)
                target_price = entry_price * (1 - take_profit_pct)
                direction = "short"
                bars_held = 0
                in_position = True

        if in_position:
            if direction == "long":
                unrealized = current_price - entry_price - entry_cost
            else:
                unrealized = entry_price - current_price - entry_cost
            current_equity = cash + unrealized
        else:
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
        entry_cost = entry_price * transaction_cost_pct
        exit_cost = exit_price * transaction_cost_pct
        total_cost = entry_cost + exit_cost

        if direction == "long":
            pnl = exit_price - entry_price - total_cost
        else:
            pnl = entry_price - exit_price - total_cost

        pnl_pct = (pnl / entry_price) * 100
        cash += pnl

        trades.append({
            "entry_time": df.loc[entry_idx, "date"],
            "exit_time": df.loc[len(df) - 1, "date"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "direction": direction,
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 2),
            "exit_reason": "force_close",
            "bars_held": bars_held,
            "confidence": float(df.loc[entry_idx, "confidence"]),
            "fold_id": int(df.loc[entry_idx, "fold_id"]) if "fold_id" in df.columns else None,
            "total_cost": round(total_cost, 6),
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
    return_data=False,
    predictions_df=None,
    transaction_cost_pct=0.001,
    allow_short=False,
):
    if predictions_df is not None:
        predictions = predictions_df
        print(f"   Using provided predictions DataFrame ({len(predictions):,} rows)")
    elif predictions_path is None:
        predictions_path = os.path.join(OUTPUT_DIR, "walk_forward_predictions.parquet")

    if predictions_df is None:
        if not os.path.exists(predictions_path):
            raise FileNotFoundError(
                f"Predictions file not found: {predictions_path}. "
                "Run walk_forward.py first or pass predictions_df."
            )
        predictions = pd.read_parquet(predictions_path)
        print(f"   Loaded {len(predictions):,} predictions")

    print(f"\n=== Strategy Simulation ===")
    print(f"   Confidence threshold: {confidence_threshold}")
    print(f"   Stop loss: {stop_loss_pct*100:.0f}%")
    print(f"   Take profit: {take_profit_pct*100:.0f}%")
    print(f"   Max hold: {max_hold_bars} bars")
    print(f"   Transaction cost: {transaction_cost_pct*100:.2f}% per side")
    print(f"   Allow short: {allow_short}")
    print(f"   Initial capital: ${initial_capital:,.0f}\n")

    trades_df, equity_df = simulate_trades(
        predictions,
        confidence_threshold,
        stop_loss_pct,
        take_profit_pct,
        max_hold_bars,
        initial_capital,
        transaction_cost_pct,
        allow_short,
    )

    if return_data:
        return trades_df, equity_df

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


def compute_portfolio_buy_and_hold(
    predictions_dict,
    initial_capital=10000,
    transaction_cost_pct=0.001,
):
    if not predictions_dict:
        return {"equity": pd.Series(dtype=float), "dates": pd.Series(dtype="datetime64[ns]"), "return_pct": 0.0, "total_cost": 0.0}

    prices = []
    for asset, df in predictions_dict.items():
        if df.empty or "date" not in df.columns or "close" not in df.columns:
            continue
        asset_prices = df[["date", "close"]].copy()
        asset_prices["date"] = pd.to_datetime(asset_prices["date"])
        asset_prices = asset_prices.dropna(subset=["date", "close"])
        asset_prices = asset_prices[asset_prices["close"] > 0]
        asset_prices = asset_prices.sort_values("date").drop_duplicates("date")
        asset_prices[asset] = asset_prices["close"]
        prices.append(asset_prices[["date", asset]])

    if not prices:
        return {"equity": pd.Series(dtype=float), "dates": pd.Series(dtype="datetime64[ns]"), "return_pct": 0.0, "total_cost": 0.0}

    start_date = max(frame["date"].min() for frame in prices)
    end_date = min(frame["date"].max() for frame in prices)
    merged = prices[0]
    for frame in prices[1:]:
        merged = merged.merge(frame, on="date", how="outer")
    merged = merged[(merged["date"] >= start_date) & (merged["date"] <= end_date)]
    merged = merged.sort_values("date").ffill().dropna().reset_index(drop=True)

    if merged.empty:
        return {"equity": pd.Series(dtype=float), "dates": pd.Series(dtype="datetime64[ns]"), "return_pct": 0.0, "total_cost": 0.0}

    assets = [asset for asset in predictions_dict if asset in merged.columns]
    allocation = initial_capital / len(assets)
    first_prices = merged.iloc[0][assets]
    last_prices = merged.iloc[-1][assets]
    entry_cost = initial_capital * transaction_cost_pct
    exit_cost = sum(allocation * last_prices[asset] / first_prices[asset] for asset in assets) * transaction_cost_pct
    units = allocation / first_prices
    equity = merged[assets].mul(units, axis="columns").sum(axis=1) - entry_cost
    equity.iloc[-1] -= exit_cost
    return {
        "dates": merged["date"],
        "equity": equity.round(2),
        "return_pct": round((equity.iloc[-1] / initial_capital - 1) * 100, 2),
        "total_cost": round(entry_cost + exit_cost, 6),
    }


def simulate_portfolio_trades(
    predictions_dict,
    confidence_threshold=0.52,
    stop_loss_pct=0.02,
    take_profit_pct=0.04,
    max_hold_bars=24,
    initial_capital=10000,
    transaction_cost_pct=0.001,
    allow_short=False,
    max_positions=3,
):
    if not predictions_dict:
        return pd.DataFrame(), pd.DataFrame()

    combined_frames = []
    for asset, df in predictions_dict.items():
        df = df.copy()
        df["asset"] = asset
        combined_frames.append(df)

    merged = pd.concat(combined_frames, ignore_index=True)
    merged = merged.sort_values("date").reset_index(drop=True)

    if merged.empty:
        return pd.DataFrame(), pd.DataFrame()

    required_cols = ["date", "close", "prediction", "confidence"]
    missing = [c for c in required_cols if c not in merged.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    allocation_per_position = initial_capital / max_positions

    trades = []
    equity = []
    cash = initial_capital
    equity_peak = initial_capital
    open_positions = {}

    for i in range(len(merged)):
        current_date = merged.loc[i, "date"]
        current_price = merged.loc[i, "close"]
        current_asset = merged.loc[i, "asset"]
        pred = int(merged.loc[i, "prediction"])
        conf = float(merged.loc[i, "confidence"])

        if current_asset in open_positions:
            pos = open_positions[current_asset]
            pos["bars_held"] += 1
            exit_price = None
            exit_reason = None

            if pos["direction"] == "long":
                if current_price <= pos["stop_price"]:
                    exit_price = pos["stop_price"]
                    exit_reason = "stop_loss"
                elif current_price >= pos["target_price"]:
                    exit_price = pos["target_price"]
                    exit_reason = "take_profit"
            else:
                if current_price >= pos["stop_price"]:
                    exit_price = pos["stop_price"]
                    exit_reason = "stop_loss"
                elif current_price <= pos["target_price"]:
                    exit_price = pos["target_price"]
                    exit_reason = "take_profit"

            if exit_price is None and pos["bars_held"] >= max_hold_bars:
                exit_price = current_price
                exit_reason = "max_hold"

            if exit_price is not None:
                entry_price = pos["entry_price"]
                position_size = pos["position_size"]
                entry_cost = position_size * entry_price * transaction_cost_pct
                exit_cost = position_size * exit_price * transaction_cost_pct
                total_cost = entry_cost + exit_cost

                if pos["direction"] == "long":
                    pnl = position_size * (exit_price - entry_price) - total_cost
                else:
                    pnl = position_size * (entry_price - exit_price) - total_cost

                pnl_pct = (pnl / pos["allocation"]) * 100
                cash += pnl

                trades.append({
                    "asset": current_asset,
                    "entry_time": pos["entry_date"],
                    "exit_time": current_date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "direction": pos["direction"],
                    "pnl": round(pnl, 4),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason,
                    "bars_held": pos["bars_held"],
                    "confidence": pos["confidence"],
                    "fold_id": pos.get("fold_id"),
                    "total_cost": round(total_cost, 6),
                    "allocation": round(pos["allocation"], 2),
                })

                del open_positions[current_asset]

        if current_asset not in open_positions and len(open_positions) < max_positions and conf >= confidence_threshold:
            if pred == 1:
                allocation = allocation_per_position
                position_size = allocation / current_price
                open_positions[current_asset] = {
                    "entry_date": current_date,
                    "entry_price": current_price,
                    "stop_price": current_price * (1 - stop_loss_pct),
                    "target_price": current_price * (1 + take_profit_pct),
                    "direction": "long",
                    "bars_held": 0,
                    "confidence": conf,
                    "fold_id": int(merged.loc[i, "fold_id"]) if "fold_id" in merged.columns else None,
                    "allocation": allocation,
                    "position_size": position_size,
                }
            elif allow_short and pred == 0:
                allocation = allocation_per_position
                position_size = allocation / current_price
                open_positions[current_asset] = {
                    "entry_date": current_date,
                    "entry_price": current_price,
                    "stop_price": current_price * (1 + stop_loss_pct),
                    "target_price": current_price * (1 - take_profit_pct),
                    "direction": "short",
                    "bars_held": 0,
                    "confidence": conf,
                    "fold_id": int(merged.loc[i, "fold_id"]) if "fold_id" in merged.columns else None,
                    "allocation": allocation,
                    "position_size": position_size,
                }

        if open_positions:
            unrealized_total = 0.0
            for pos in open_positions.values():
                entry_price = pos["entry_price"]
                position_size = pos["position_size"]
                entry_cost = position_size * entry_price * transaction_cost_pct
                exit_cost_now = position_size * current_price * transaction_cost_pct
                if pos["direction"] == "long":
                    unrealized_total += position_size * (current_price - entry_price) - entry_cost - exit_cost_now
                else:
                    unrealized_total += position_size * (entry_price - current_price) - entry_cost - exit_cost_now
            current_equity = cash + unrealized_total
        else:
            current_equity = cash
        if current_equity > equity_peak:
            equity_peak = current_equity

        equity.append({
            "date": current_date,
            "equity": round(current_equity, 2),
            "drawdown_pct": round((equity_peak - current_equity) / equity_peak * 100, 2),
        })

    for asset_name, pos in list(open_positions.items()):
        asset_rows = merged[merged["asset"] == asset_name]
        if not asset_rows.empty:
            exit_price = asset_rows.iloc[-1]["close"]
            exit_date = asset_rows.iloc[-1]["date"]
        else:
            exit_price = pos["entry_price"]
            exit_date = pos["entry_date"]

        entry_price = pos["entry_price"]
        position_size = pos["position_size"]
        entry_cost = position_size * entry_price * transaction_cost_pct
        exit_cost = position_size * exit_price * transaction_cost_pct
        total_cost = entry_cost + exit_cost

        if pos["direction"] == "long":
            pnl = position_size * (exit_price - entry_price) - total_cost
        else:
            pnl = position_size * (entry_price - exit_price) - total_cost

        pnl_pct = (pnl / pos["allocation"]) * 100
        cash += pnl

        trades.append({
            "asset": asset_name,
            "entry_time": pos["entry_date"],
            "exit_time": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "direction": pos["direction"],
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 2),
            "exit_reason": "force_close",
            "bars_held": pos["bars_held"],
            "confidence": pos["confidence"],
            "fold_id": pos.get("fold_id"),
            "total_cost": round(total_cost, 6),
            "allocation": round(pos["allocation"], 2),
        })

        equity.append({
            "date": exit_date,
            "equity": round(cash, 2),
            "drawdown_pct": round((equity_peak - cash) / equity_peak * 100, 2),
        })

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)

    if not equity_df.empty:
        equity_df["date"] = pd.to_datetime(equity_df["date"])
        equity_df = equity_df.groupby("date").last().reset_index()
        equity_df = equity_df.sort_values("date").reset_index(drop=True)

    if not trades_df.empty:
        trades_df["cumulative_pnl"] = trades_df["pnl"].cumsum()

    return trades_df, equity_df


def run_portfolio_strategy(
    predictions_dict=None,
    confidence_threshold=0.52,
    stop_loss_pct=0.02,
    take_profit_pct=0.04,
    max_hold_bars=24,
    initial_capital=10000,
    return_data=False,
    transaction_cost_pct=0.001,
    allow_short=False,
    max_positions=3,
):
    if not predictions_dict:
        raise ValueError("predictions_dict is required for portfolio strategy")

    print(f"\n=== Portfolio Strategy Simulation ===")
    print(f"   Assets: {list(predictions_dict.keys())}")
    print(f"   Max positions: {max_positions}")
    print(f"   Allocation: equal (${initial_capital / max_positions:,.2f} per slot)")
    print(f"   Confidence threshold: {confidence_threshold}")
    print(f"   Stop loss: {stop_loss_pct*100:.0f}%")
    print(f"   Take profit: {take_profit_pct*100:.0f}%")
    print(f"   Max hold: {max_hold_bars} bars")
    print(f"   Transaction cost: {transaction_cost_pct*100:.2f}% per side")
    print(f"   Allow short: {allow_short}")
    print(f"   Initial capital: ${initial_capital:,.0f}\n")

    trades_df, equity_df = simulate_portfolio_trades(
        predictions_dict,
        confidence_threshold,
        stop_loss_pct,
        take_profit_pct,
        max_hold_bars,
        initial_capital,
        transaction_cost_pct,
        allow_short,
        max_positions,
    )

    total_pnl = trades_df["pnl"].sum() if not trades_df.empty else 0
    win_count = (trades_df["pnl"] > 0).sum() if not trades_df.empty else 0
    total_trades = len(trades_df)

    print(f"   Total trades: {total_trades}")
    print(f"   Winning trades: {win_count}")
    print(f"   Win rate: {win_count/total_trades*100:.1f}%" if total_trades > 0 else "   Win rate: N/A")
    print(f"   Total PnL: ${total_pnl:,.2f}")

    if not trades_df.empty:
        print(f"\n   Per-asset breakdown:")
        for asset in trades_df["asset"].unique():
            asset_trades = trades_df[trades_df["asset"] == asset]
            asset_pnl = asset_trades["pnl"].sum()
            asset_wins = (asset_trades["pnl"] > 0).sum()
            print(f"     {asset}: {len(asset_trades)} trades, "
                  f"PnL ${asset_pnl:+,.2f}, "
                  f"Win {asset_wins/len(asset_trades)*100:.1f}%")

    if return_data:
        return trades_df, equity_df

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trades_path = os.path.join(OUTPUT_DIR, "portfolio_trades.parquet")
    trades_df.to_parquet(trades_path)
    print(f"\n   Trades saved: {trades_path} ({len(trades_df)} trades)")

    equity_path = os.path.join(OUTPUT_DIR, "portfolio_equity.parquet")
    equity_df.to_parquet(equity_path)
    print(f"   Equity saved: {equity_path} ({len(equity_df)} rows)")

    return trades_df, equity_df


if __name__ == "__main__":
    run_strategy()