from scripts.run_feature_ablation import build_feature_sets
from src.models.feature_engineering import MODEL_FEATURES


TREND_FEATURES = [
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct",
]


def test_baseline_uses_all_model_features():
    feature_sets = build_feature_sets()

    assert feature_sets["baseline"] == MODEL_FEATURES


def test_trend_ablation_removes_only_trend_features():
    feature_sets = build_feature_sets()
    expected = [feature for feature in MODEL_FEATURES if feature not in TREND_FEATURES]

    assert feature_sets["without_trend"] == expected
