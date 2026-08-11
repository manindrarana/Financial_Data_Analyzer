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
VOLATILITY_FEATURES = [
    "bb_percentage", "atr_pct", "volatility_pct", "hl_ratio", "close_position",
]


def build_feature_sets():
    return {
        "baseline": MODEL_FEATURES.copy(),
        "without_trend": [
            feature for feature in MODEL_FEATURES if feature not in TREND_FEATURES
        ],
        "without_momentum": [
            feature for feature in MODEL_FEATURES if feature not in MOMENTUM_FEATURES
        ],
        "without_volatility": [
            feature for feature in MODEL_FEATURES if feature not in VOLATILITY_FEATURES
        ],
    }
