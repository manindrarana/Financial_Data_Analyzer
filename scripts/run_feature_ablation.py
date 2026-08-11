from src.models.feature_engineering import MODEL_FEATURES


TREND_FEATURES = [
    "sma_7_dist", "sma_30_dist", "sma_50_dist", "sma_100_dist", "sma_200_dist",
    "ema_12_dist", "ema_26_dist", "ema_50_dist", "ema_200_dist", "vwap_dist",
    "macd_pct", "macd_sig_pct", "macd_hist_pct",
]


def build_feature_sets():
    return {
        "baseline": MODEL_FEATURES.copy(),
        "without_trend": [
            feature for feature in MODEL_FEATURES if feature not in TREND_FEATURES
        ],
    }
