import os
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, matthews_corrcoef, brier_score_loss

MODEL_DIRS = {
    "crypto": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "models", "crypto"),
    "stocks": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "models", "stocks"),
}

STALE_THRESHOLD_DAYS = 30

_MODEL_PATTERN = re.compile(r"^(.+)_(\d+[hmd])_xgboost_model\.json$")
_METADATA_PATTERN = re.compile(r"^(.+)_(\d+[hmd])_xgboost_metadata\.json$")


def _scan_models(asset_class: str):
    directory = MODEL_DIRS.get(asset_class)
    if not directory or not os.path.isdir(directory):
        return {}

    models = {}
    try:
        for fname in os.listdir(directory):
            match = _MODEL_PATTERN.match(fname)
            if match:
                key = (match.group(1), match.group(2))
                models.setdefault(key, {})["model_path"] = os.path.join(directory, fname)
            match = _METADATA_PATTERN.match(fname)
            if match:
                key = (match.group(1), match.group(2))
                models.setdefault(key, {})["metadata_path"] = os.path.join(directory, fname)
    except OSError:
        return {}
    return models


def _read_metadata(path: str):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _classify_status(metadata: Optional[dict], has_model: bool, has_metadata: bool, threshold_days: int = STALE_THRESHOLD_DAYS):
    if not has_metadata:
        return "missing_metadata"
    if not has_model:
        return "missing_model"
    if metadata is None:
        return "missing_metadata"

    trained_at_str = metadata.get("trained_at")
    if not trained_at_str:
        return "stale"

    try:
        trained_at = datetime.fromisoformat(trained_at_str)
    except (ValueError, TypeError):
        return "stale"

    if trained_at.tzinfo is None:
        trained_at = trained_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if now - trained_at > timedelta(days=threshold_days):
        return "stale"

    return "healthy"


STATUS_LABELS = {
    "healthy": "Healthy",
    "stale": "Stale",
    "missing_model": "Missing Model",
    "missing_metadata": "Missing Metadata",
}

STATUS_COLORS = {
    "healthy": "#27ae60",
    "stale": "#f39c12",
    "missing_model": "#e74c3c",
    "missing_metadata": "#e67e22",
}

STATUS_ORDER = {"missing_model": 0, "missing_metadata": 1, "stale": 2, "healthy": 3}


def get_model_health(threshold_days: int = STALE_THRESHOLD_DAYS):
    results = []

    for asset_class in ("crypto", "stocks"):
        models = _scan_models(asset_class)
        for (asset, interval), paths in models.items():
            model_path = paths.get("model_path")
            metadata_path = paths.get("metadata_path")
            has_model = model_path is not None
            has_metadata = metadata_path is not None

            metadata = None
            if has_metadata:
                metadata = _read_metadata(metadata_path)

            status = _classify_status(metadata, has_model, has_metadata, threshold_days)

            results.append({
                "asset": asset,
                "interval": interval,
                "asset_class": asset_class,
                "trained_at": metadata.get("trained_at") if metadata else None,
                "train_end_date": metadata.get("train_end_date") if metadata else None,
                "train_rows": metadata.get("train_rows") if metadata else None,
                "test_rows": metadata.get("test_rows") if metadata else None,
                "test_accuracy": metadata.get("test_accuracy") if metadata else None,
                "best_cv_score": metadata.get("best_cv_score") if metadata else None,
                "status": status,
                "has_model": has_model,
                "has_metadata": has_metadata,
            })

    results.sort(key=lambda r: (STATUS_ORDER.get(r["status"], 99), r["asset"], r["interval"]))
    return results


def get_summary_counts(results: List[dict]):
    counts = {"total": len(results), "healthy": 0, "stale": 0, "missing_model": 0, "missing_metadata": 0}
    for r in results:
        status = r.get("status", "healthy")
        if status in counts:
            counts[status] += 1
    return counts