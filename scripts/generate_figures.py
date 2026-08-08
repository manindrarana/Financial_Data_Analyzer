"""
Generate thesis figures from project data.
Outputs PNGs to obsidian_notes/latex/images/
"""
import glob
import json
import os
import sys

import duckdb
import matplotlib
import numpy as np
import pandas as pd
import xgboost as xgb
from matplotlib.patches import Patch

from backtesting.strategy import simulate_trades
from backtesting.walk_forward import run_walk_forward
from src.models.feature_engineering import MODEL_FEATURES, make_stationary

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
DB_PATH = os.path.join(PROJECT_ROOT, "database", "financial_data.duckdb")
MODELS_DIR = os.path.join(PROJECT_ROOT, "src", "models")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "obsidian_notes", "latex", "images")

os.makedirs(OUTPUT_DIR, exist_ok=True)

plt.rcParams.update({
    "figure.facecolor": "#1a1a2e",
    "axes.facecolor": "#16213e",
    "axes.edgecolor": "#0f3460",
    "axes.labelcolor": "#e0e0e0",
    "xtick.color": "#e0e0e0",
    "ytick.color": "#e0e0e0",
    "text.color": "#e0e0e0",
    "axes.grid": True,
    "grid.color": "#0f3460",
    "grid.alpha": 0.3,
    "font.size": 11,
    "font.family": "sans-serif",
})


def save_fig(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {path}")


def load_all_metadata():
    metadata_list = []
    for pattern in [os.path.join(MODELS_DIR, "crypto", "*_metadata.json"),
                    os.path.join(MODELS_DIR, "stocks", "*_metadata.json")]:
        for fpath in glob.glob(pattern):
            with open(fpath) as f:
                metadata_list.append(json.load(f))
    return metadata_list


def chart_data_volume():
    conn = duckdb.connect(DB_PATH, read_only=True)

    crypto_df = conn.execute("""
        SELECT asset_symbol, COUNT(*) as row_count
        FROM gold_crypto_features
        GROUP BY asset_symbol
        ORDER BY row_count DESC
    """).df()

    stock_df = conn.execute("""
        SELECT asset_symbol, COUNT(*) as row_count
        FROM gold_stock_features
        GROUP BY asset_symbol
        ORDER BY row_count DESC
    """).df()

    conn.close()

    fig, axes = plt.subplots(1, 2, figsize=(16, 5))

    ax1 = axes[0]
    bars1 = ax1.bar(crypto_df["asset_symbol"], crypto_df["row_count"], color="#3498db", edgecolor="#1a5276")
    ax1.set_xlabel("Crypto Asset")
    ax1.set_ylabel("Number of Rows")
    ax1.set_title("Gold Crypto Features - Row Count by Asset")
    ax1.tick_params(axis="x", rotation=45)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., height,
                 f"{int(height):,}", ha="center", va="bottom", fontsize=7)

    ax2 = axes[1]
    bars2 = ax2.bar(stock_df["asset_symbol"], stock_df["row_count"], color="#e67e22", edgecolor="#a04000")
    ax2.set_xlabel("Stock Asset")
    ax2.set_ylabel("Number of Rows")
    ax2.set_title("Gold Stock Features - Row Count by Asset")
    ax2.tick_params(axis="x", rotation=45)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2., height,
                 f"{int(height):,}", ha="center", va="bottom", fontsize=7)

    plt.tight_layout()
    save_fig(fig, "data_volume_by_asset.png")


def chart_eda_price_trend():
    conn = duckdb.connect(DB_PATH, read_only=True)

    btc_df = conn.execute("""
        SELECT date, close FROM gold_crypto_features
        WHERE asset_symbol = 'BTC' AND interval = '1h'
        ORDER BY date
    """).df()

    aapl_df = conn.execute("""
        SELECT date, close FROM gold_stock_features
        WHERE asset_symbol = 'AAPL' AND interval = '1d'
        ORDER BY date
    """).df()

    conn.close()

    fig, axes = plt.subplots(1, 2, figsize=(16, 5))

    ax1 = axes[0]
    ax1.plot(btc_df["date"], btc_df["close"], color="#3498db", linewidth=0.8)
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Close Price (USD)")
    ax1.set_title("BTC Closing Price (1h)")

    ax2 = axes[1]
    ax2.plot(aapl_df["date"], aapl_df["close"], color="#e67e22", linewidth=0.8)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Close Price (USD)")
    ax2.set_title("AAPL Closing Price (1d)")

    plt.tight_layout()
    save_fig(fig, "eda_price_trend.png")


def chart_eda_return_distribution():
    conn = duckdb.connect(DB_PATH, read_only=True)

    btc_df = conn.execute("""
        SELECT date, close FROM gold_crypto_features
        WHERE asset_symbol = 'BTC' AND interval = '1h'
        ORDER BY date
    """).df()

    aapl_df = conn.execute("""
        SELECT date, close FROM gold_stock_features
        WHERE asset_symbol = 'AAPL' AND interval = '1d'
        ORDER BY date
    """).df()

    conn.close()

    btc_returns = btc_df["close"].pct_change().dropna() * 100
    aapl_returns = aapl_df["close"].pct_change().dropna() * 100

    fig, axes = plt.subplots(1, 2, figsize=(16, 5))

    ax1 = axes[0]
    ax1.hist(btc_returns, bins=100, color="#3498db", edgecolor="#1a5276", alpha=0.8)
    ax1.set_xlabel("1-Period Return (%)")
    ax1.set_ylabel("Count")
    ax1.set_title("BTC Return Distribution (1h)")
    ax1.set_xlim(-10, 10)

    ax2 = axes[1]
    ax2.hist(aapl_returns, bins=100, color="#e67e22", edgecolor="#a04000", alpha=0.8)
    ax2.set_xlabel("1-Period Return (%)")
    ax2.set_ylabel("Count")
    ax2.set_title("AAPL Return Distribution (1d)")
    ax2.set_xlim(-10, 10)

    plt.tight_layout()
    save_fig(fig, "eda_return_distribution.png")


def chart_eda_correlation_heatmap():
    conn = duckdb.connect(DB_PATH, read_only=True)

    crypto_assets = ["BTC", "ETH", "SOL", "ADA", "XRP"]
    stock_assets = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]

    all_returns = {}

    for asset in crypto_assets:
        df = conn.execute(f"""
            SELECT date, close FROM gold_crypto_features
            WHERE asset_symbol = '{asset}' AND interval = '1d'
            ORDER BY date
        """).df()
        if not df.empty:
            rets = df.set_index("date")["close"].pct_change().dropna()
            all_returns[asset] = rets

    for asset in stock_assets:
        df = conn.execute(f"""
            SELECT date, close FROM gold_stock_features
            WHERE asset_symbol = '{asset}' AND interval = '1d'
            ORDER BY date
        """).df()
        if not df.empty:
            rets = df.set_index("date")["close"].pct_change().dropna()
            all_returns[asset] = rets

    conn.close()

    returns_df = pd.DataFrame(all_returns)
    corr_matrix = returns_df.corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr_matrix.values, cmap="RdYlBu_r", vmin=-1, vmax=1, aspect="auto")

    ax.set_xticks(range(len(corr_matrix.columns)))
    ax.set_yticks(range(len(corr_matrix.columns)))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha="right", fontsize=10)
    ax.set_yticklabels(corr_matrix.columns, fontsize=10)

    for i in range(len(corr_matrix.columns)):
        for j in range(len(corr_matrix.columns)):
            val = corr_matrix.values[i, j]
            color = "white" if abs(val) > 0.5 else "#e0e0e0"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8, color=color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Correlation", color="#e0e0e0")
    cbar.ax.tick_params(colors="#e0e0e0")

    n_crypto = len(crypto_assets)
    ax.axhline(y=n_crypto - 0.5, color="#e0e0e0", linewidth=1.5, linestyle="--")
    ax.axvline(x=n_crypto - 0.5, color="#e0e0e0", linewidth=1.5, linestyle="--")

    ax.set_title("Daily Return Correlation Matrix")
    plt.tight_layout()
    save_fig(fig, "eda_correlation_heatmap.png")


def chart_model_comparison():
    models = ["XGBoost\n(29 features)", "LSTM\n(engineered)", "LSTM\n(raw OHLCV)"]
    accuracies = [52.81, 51.30, 50.09]
    colors = ["#26a69a", "#ef5350", "#ef5350"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(models, accuracies, color=colors, edgecolor="#1a1a2e", width=0.5)
    ax.axhline(y=50, color="#ffc107", linestyle="--", linewidth=1.5, label="Random (50%)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Model Comparison on BTC 1h")
    ax.set_ylim(48, 55)
    for bar, acc in zip(bars, accuracies):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.15,
                f"{acc}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.legend(loc="upper right")
    plt.tight_layout()
    save_fig(fig, "model_comparison_xgboost_lstm.png")


def chart_ceiling_experiments():
    experiments = [
        ("v1\nBaseline", 52.81, "#3498db"),
        ("v2\n+OI/Turnover", 52.61, "#3498db"),
        ("v3\nDerived 4h", 52.43, "#e67e22"),
        ("v4\nNative 4h", 52.74, "#3498db"),
        ("v5\nConf>=0.52", 54.47, "#9b59b6"),
        ("v6\n+F&G", 52.80, "#1abc9c"),
        ("#97\nLSTM raw", 50.09, "#ef5350"),
    ]
    labels = [e[0] for e in experiments]
    values = [e[1] for e in experiments]
    colors = [e[2] for e in experiments]

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="#1a1a2e", width=0.6)
    ax.axhline(y=50, color="#ffc107", linestyle="--", linewidth=1.5, label="Random (50%)")
    ax.axhline(y=52.6, color="#ef5350", linestyle=":", linewidth=1.5, label="Ceiling (~52.6%)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Seven Experiments Testing the Accuracy Ceiling (BTC)")
    ax.set_ylim(48, 56)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.15,
                f"{val}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.legend(loc="upper right")
    plt.tight_layout()
    save_fig(fig, "ceiling_experiments.png")


def chart_per_asset_accuracy():
    metadata_list = load_all_metadata()
    metadata_list.sort(key=lambda m: (m.get("asset_class", ""), m["asset"], m["interval"]))

    labels = []
    accuracies = []
    colors = []
    for m in metadata_list:
        acc = m.get("test_accuracy")
        if acc is None:
            continue
        labels.append(f"{m['asset']}_{m['interval']}")
        accuracies.append(acc * 100)
        colors.append("#3498db" if m.get("asset_class") == "crypto" else "#e67e22")

    fig, ax = plt.subplots(figsize=(16, 6))
    ax.bar(range(len(labels)), accuracies, color=colors, edgecolor="#1a1a2e")
    ax.axhline(y=50, color="#ffc107", linestyle="--", linewidth=1, label="Random (50%)")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_ylabel("Test Accuracy (%)")
    ax.set_title("Test Accuracy for All 45 Models")
    ax.set_ylim(40, 60)

    legend_elements = [
        Patch(facecolor="#3498db", label="Crypto"),
        Patch(facecolor="#e67e22", label="Stocks"),
    ]
    ax.legend(handles=legend_elements + [plt.Line2D([0], [0], color="#ffc107", linestyle="--", label="Random (50%)")],
              loc="upper right")
    plt.tight_layout()
    save_fig(fig, "per_asset_accuracy.png")


def chart_feature_importance():
    model_path = os.path.join(MODELS_DIR, "crypto", "BTC_1h_xgboost_model.json")
    meta_path = os.path.join(MODELS_DIR, "crypto", "BTC_1h_xgboost_metadata.json")

    with open(meta_path) as f:
        meta = json.load(f)
    features = meta["features"]

    model = xgb.XGBClassifier()
    model.load_model(model_path)
    booster = model.get_booster()
    importance = booster.get_score(importance_type="gain")

    if not importance:
        importance = booster.get_score(fmap="", importance_type="gain")

    if not importance:
        scores = model.feature_importances_
        importance = {f: s for f, s in zip(features, scores)}

    sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:15]
    feat_names = [x[0] for x in sorted_items]
    feat_values = [x[1] for x in sorted_items]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(range(len(feat_names)), feat_values, color="#3498db", edgecolor="#1a5276")
    ax.set_yticks(range(len(feat_names)))
    ax.set_yticklabels(feat_names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Feature Importance (Gain)")
    ax.set_title("Top 15 Feature Importance - BTC 1h XGBoost")
    plt.tight_layout()
    save_fig(fig, "feature_importance_btc_1h.png")


def chart_confidence_distribution():
    conn = duckdb.connect(DB_PATH, read_only=True)
    df = conn.execute("""
        SELECT * FROM gold_crypto_features
        WHERE asset_symbol = 'BTC' AND interval = '1h'
        ORDER BY date
    """).df()
    conn.close()

    df = make_stationary(df)
    available = [f for f in MODEL_FEATURES if f in df.columns]
    X = df[available].fillna(0).values

    model_path = os.path.join(MODELS_DIR, "crypto", "BTC_1h_xgboost_model.json")
    model = xgb.XGBClassifier()
    model.load_model(model_path)
    probas = model.predict_proba(X)[:, 1]
    confidences = np.maximum(probas, 1 - probas)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(confidences, bins=40, color="#3498db", edgecolor="#1a5276", alpha=0.8)
    ax.axvline(x=0.5, color="#ef5350", linestyle="--", linewidth=2, label="Random (0.50)")
    ax.set_xlabel("Prediction Confidence")
    ax.set_ylabel("Count")
    ax.set_title("Confidence Distribution - BTC 1h XGBoost")
    ax.legend(loc="upper right")
    plt.tight_layout()
    save_fig(fig, "confidence_distribution_btc_1h.png")


def chart_backtest_equity_curve():
    predictions_df, _ = run_walk_forward(
        asset="BTC",
        interval="1h",
        train_months=6,
        test_months=1,
        step_months=1,
        return_data=True,
        asset_class="crypto",
    )

    _, equity_df = simulate_trades(
        predictions_df,
        confidence_threshold=0.52,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_hold_bars=24,
        initial_capital=10000,
    )

    if equity_df.empty:
        raise RuntimeError("Equity curve is empty - no trades were simulated")

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]})

    ax1 = axes[0]
    ax1.plot(equity_df["date"], equity_df["equity"], color="#26a69a", linewidth=1.2)
    ax1.axhline(y=10000, color="#ffc107", linestyle="--", linewidth=1, label="Initial Capital ($10,000)")
    ax1.set_ylabel("Equity (USD)")
    ax1.set_title("Walk-Forward Backtest Equity Curve - BTC 1h")
    ax1.legend(loc="upper left")

    ax2 = axes[1]
    ax2.fill_between(equity_df["date"], equity_df["drawdown_pct"], 0, color="#ef5350", alpha=0.5)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.set_title("Drawdown")

    plt.tight_layout()
    save_fig(fig, "backtest_equity_curve.png")


if __name__ == "__main__":
    print("Generating thesis figures...")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    charts = [
        ("Data volume by asset", chart_data_volume),
        ("EDA: Price trends (BTC + AAPL)", chart_eda_price_trend),
        ("EDA: Return distributions (BTC + AAPL)", chart_eda_return_distribution),
        ("EDA: Correlation heatmap", chart_eda_correlation_heatmap),
        ("XGBoost vs LSTM comparison", chart_model_comparison),
        ("Ceiling experiments", chart_ceiling_experiments),
        ("Per-asset accuracy (all 45 models)", chart_per_asset_accuracy),
        ("Feature importance (BTC 1h)", chart_feature_importance),
        ("Confidence distribution (BTC 1h)", chart_confidence_distribution),
        ("Backtest equity curve (BTC 1h)", chart_backtest_equity_curve),
    ]

    for name, func in charts:
        try:
            print(f"Generating: {name}")
            func()
        except Exception as e:
            print(f"  SKIPPED: {e}")

    print()
    print("Done. Figures saved to obsidian_notes/latex/images/")
