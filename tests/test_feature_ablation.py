from scripts.run_feature_ablation import build_feature_sets
from src.models.feature_engineering import MODEL_FEATURES


def test_baseline_uses_all_model_features():
    feature_sets = build_feature_sets()

    assert feature_sets["baseline"] == MODEL_FEATURES
