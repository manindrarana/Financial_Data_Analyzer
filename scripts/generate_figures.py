"""
Generate thesis figures from project data.
Outputs PNGs to obsidian_notes/latex/images/
"""
import os
import sys
import json
import glob
import numpy as np
import pandas as pd
import duckdb
import matplotlib
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
    bars = ax.bar(range(len(labels)), accuracies, color=colors, edgecolor="#1a1a2e")
    ax.axhline(y=50, color="#ffc107", linestyle="--", linewidth=1, label="Random (50%)")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_ylabel("Test Accuracy (%)")
    ax.set_title("Test Accuracy for All 45 Models")
    ax.set_ylim(40, 60)
    ax.legend(loc="upper right")

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#3498db", label="Crypto"),
        Patch(facecolor="#e67e22", label="Stocks"),
    ]
    ax.legend(handles=legend_elements + [plt.Line2D([0], [0], color="#ffc107", linestyle="--", label="Random (50%)")],
              loc="upper right")
    plt.tight_layout()
    save_fig(fig, "per_asset_accuracy.png")


def chart_feature_importance():
    import xgboost as xgb

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
    bars = ax.barh(range(len(feat_names)), feat_values, color="#3498db", edgecolor="#1a5276")
    ax.set_yticks(range(len(feat_names)))
    ax.set_yticklabels(feat_names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Feature Importance (Gain)")
    ax.set_title("Top 15 Feature Importance - BTC 1h XGBoost")
    plt.tight_layout()
    save_fig(fig, "feature_importance_btc_1h.png")


def chart_confidence_distribution():
    import xgboost as xgb
    from src.models.feature_engineering import make_stationary, MODEL_FEATURES

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


if __name__ == "__main__":
    print("Generating thesis figures...")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    charts = [
        ("Data volume by asset", chart_data_volume),
        ("XGBoost vs LSTM comparison", chart_model_comparison),
        ("Ceiling experiments", chart_ceiling_experiments),
        ("Per-asset accuracy (all 45 models)", chart_per_asset_accuracy),
        ("Feature importance (BTC 1h)", chart_feature_importance),
        ("Confidence distribution (BTC 1h)", chart_confidence_distribution),
    ]

    for name, func in charts:
        try:
            print(f"Generating: {name}")
            func()
        except Exception as e:
            print(f"  SKIPPED: {e}")

    print()
    print("Done. Figures saved to obsidian_notes/latex/images/")
    print()
