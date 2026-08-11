from scripts.run_feature_ablation import build_feature_sets
from src.models.feature_engineering import MODEL_FEATURES


TREND_FEATURES = [
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct",
]
MOMENTUM_FEATURES = [
    "rsi_14", "roc_10", "roc_20", "stoch_k", "stoch_d",
    "returns_1p", "returns_5p", "returns_10p", "returns_20p", "log_returns",
]


def test_baseline_uses_all_model_features():
    feature_sets = build_feature_sets()

    assert feature_sets["baseline"] == MODEL_FEATURES


def test_trend_ablation_removes_only_trend_features():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature not in TREND_FEATURES]

    assert feature_sets["without_trend"] == expected


def test_momentum_ablation_removes_only_momentum_features():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature not in MOMENTUM_FEATURES]

    assert feature_sets["without_momentum"] == expected
