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

CLASSIFICATION_RANKING_OBJECTIVES = {
    "oos_accuracy": {"label": "OOS Accuracy", "higher_is_better": True},
    "baseline_gap": {"label": "Baseline Improvement", "higher_is_better": True},
    "balanced_accuracy": {"label": "Balanced Accuracy", "higher_is_better": True},
    "brier_score": {"label": "Brier Score", "higher_is_better": False},
}

STANDARD_TRADING_CONFIG = {
    "confidence_threshold": 0.52,
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.04,
    "max_hold_bars": 24,
    "initial_capital": 10000,
    "transaction_cost_pct": 0.001,
    "allow_short": False,
}

TRADING_METRIC_FIELDS = (
    "total_return_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "return_volatility",
)


def _unavailable_trading_metrics():
    return {field: None for field in TRADING_METRIC_FIELDS}


def evaluate_trading_performance(models: List[dict], prediction_runner=None):
    if prediction_runner is None:
        from dashboard.predictor import run_prediction
        prediction_runner = run_prediction

    from backtesting.metrics import compute_metrics
    from backtesting.strategy import simulate_trades

    evaluated = [dict(model, **_unavailable_trading_metrics()) for model in models]
    predictions_by_model = {}

    for index, model in enumerate(evaluated):
        if not model.get("has_model", True):
            continue

        try:
            predictions = prediction_runner(
                asset=model["asset"],
                interval=model["interval"],
                asset_class=model["asset_class"],
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            continue

        if predictions is None or predictions.empty:
            continue

        predictions = predictions.copy()
        predictions["date"] = pd.to_datetime(predictions["date"])
        if "is_oos" in predictions.columns:
            predictions = predictions[predictions["is_oos"] == True]
        predictions = predictions.dropna(subset=["date", "close", "prediction", "confidence"])
        if not predictions.empty:
            predictions_by_model[index] = predictions

    if not predictions_by_model:
        return evaluated

    evaluation_start = max(predictions["date"].min() for predictions in predictions_by_model.values())
    evaluation_end = min(predictions["date"].max() for predictions in predictions_by_model.values())
    if evaluation_start > evaluation_end:
        return evaluated

    for index, predictions in predictions_by_model.items():
        model = evaluated[index]
        evaluation_predictions = predictions[
            (predictions["date"] >= evaluation_start)
            & (predictions["date"] <= evaluation_end)
        ]
        if evaluation_predictions.empty:
            continue

        trades, equity = simulate_trades(evaluation_predictions, **STANDARD_TRADING_CONFIG)
        if equity.empty:
            continue

        metrics = compute_metrics(
            trades,
            equity,
            initial_capital=STANDARD_TRADING_CONFIG["initial_capital"],
            interval=model["interval"],
            asset_class=model["asset_class"],
        )
        periodic_returns = equity.sort_values("date")["equity"].pct_change().dropna()

        model["total_return_pct"] = metrics["total_return_pct"]
        model["max_drawdown_pct"] = metrics["max_drawdown_pct"]
        model["sharpe_ratio"] = metrics["sharpe_ratio"]
        model["return_volatility"] = (
            round(float(periodic_returns.std()), 6) if len(periodic_returns) > 1 else 0.0
        )
        model["trading_evaluation_start"] = evaluation_start
        model["trading_evaluation_end"] = evaluation_end

    return evaluated


def rank_models(models: List[dict], objective: str):
    if objective not in CLASSIFICATION_RANKING_OBJECTIVES:
        raise ValueError(f"Unknown ranking objective: {objective}")

    higher_is_better = CLASSIFICATION_RANKING_OBJECTIVES[objective]["higher_is_better"]
    ranked = [dict(model) for model in models]
    available = [model for model in ranked if model.get(objective) is not None and not pd.isna(model[objective])]
    unavailable = [model for model in ranked if model.get(objective) is None or pd.isna(model[objective])]

    available.sort(
        key=lambda model: (
            -model[objective] if higher_is_better else model[objective],
            model.get("asset_class", ""),
            model.get("asset", ""),
            model.get("interval", ""),
        )
    )
    unavailable.sort(key=lambda model: (
        model.get("asset_class", ""),
        model.get("asset", ""),
        model.get("interval", ""),
    ))

    previous_score = None
    previous_rank = None
    for position, model in enumerate(available, start=1):
        score = model[objective]
        if previous_score is None or score != previous_score:
            previous_rank = position
        model["rank"] = previous_rank
        model["ranking_score"] = score
        previous_score = score

    for model in unavailable:
        model["rank"] = None
        model["ranking_score"] = None

    return available + unavailable


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