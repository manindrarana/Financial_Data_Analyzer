import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import os
import json
import tempfile
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from dashboard.model_health import (
    _scan_models,
    _read_metadata,
    _classify_status,
    get_model_health,
    get_summary_counts,
    STALE_THRESHOLD_DAYS,
    STATUS_LABELS,
    STATUS_COLORS,
    STATUS_ORDER,
)


def _collect_text(component):
    if isinstance(component, str):
        return [component]
    children = getattr(component, "children", None)
    if children is None:
        return []
    if isinstance(children, list):
        values = []
        for child in children:
            values.extend(_collect_text(child))
        return values
    return _collect_text(children)


class TestScanModels:
    def test_scans_both_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "BTC_1d_xgboost_model.json"), "w").close()
            open(os.path.join(tmpdir, "BTC_1d_xgboost_metadata.json"), "w").close()
            open(os.path.join(tmpdir, "ETH_1h_xgboost_model.json"), "w").close()
            open(os.path.join(tmpdir, "ETH_1h_xgboost_metadata.json"), "w").close()

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                result = _scan_models("crypto")

        assert ("BTC", "1d") in result
        assert ("ETH", "1h") in result
        assert result[("BTC", "1d")]["model_path"].endswith("BTC_1d_xgboost_model.json")
        assert result[("BTC", "1d")]["metadata_path"].endswith("BTC_1d_xgboost_metadata.json")

    def test_model_only_no_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "SOL_4h_xgboost_model.json"), "w").close()

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                result = _scan_models("crypto")

        assert "model_path" in result[("SOL", "4h")]
        assert "metadata_path" not in result[("SOL", "4h")]

    def test_metadata_only_no_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "DOT_1d_xgboost_metadata.json"), "w").close()

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                result = _scan_models("crypto")

        assert "metadata_path" in result[("DOT", "1d")]
        assert "model_path" not in result[("DOT", "1d")]

    def test_nonexistent_directory(self):
        with patch("dashboard.model_health.MODEL_DIRS", {"crypto": "/nonexistent/path", "stocks": "/nonexistent2"}):
            result = _scan_models("crypto")
        assert result == {}

    def test_ignores_non_model_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "random_file.txt"), "w").close()
            open(os.path.join(tmpdir, "BTC_1d_xgboost_model.json"), "w").close()
            open(os.path.join(tmpdir, "BTC_1d_xgboost_metadata.json"), "w").close()

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                result = _scan_models("crypto")

        assert len(result) == 1
        assert ("BTC", "1d") in result


class TestReadMetadata:
    def test_reads_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"asset": "BTC", "trained_at": "2026-06-18T08:46:06"}, f)
            path = f.name
        try:
            result = _read_metadata(path)
            assert result["asset"] == "BTC"
            assert result["trained_at"] == "2026-06-18T08:46:06"
        finally:
            os.unlink(path)

    def test_returns_none_for_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            path = f.name
        try:
            result = _read_metadata(path)
            assert result is None
        finally:
            os.unlink(path)

    def test_returns_none_for_missing_file(self):
        result = _read_metadata("/nonexistent/path/metadata.json")
        assert result is None


class TestClassifyStatus:
    def test_healthy_recently_trained(self):
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).isoformat()
        metadata = {"trained_at": recent}
        result = _classify_status(metadata, True, True, 30)
        assert result == "healthy"

    def test_stale_old_training(self):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=60)).isoformat()
        metadata = {"trained_at": old}
        result = _classify_status(metadata, True, True, 30)
        assert result == "stale"

    def test_stale_no_trained_at(self):
        metadata = {"asset": "BTC"}
        result = _classify_status(metadata, True, True, 30)
        assert result == "stale"

    def test_missing_metadata_status(self):
        result = _classify_status(None, True, False, 30)
        assert result == "missing_metadata"

    def test_missing_model_status(self):
        metadata = {"trained_at": "2026-06-18T08:46:06"}
        result = _classify_status(metadata, False, True, 30)
        assert result == "missing_model"

    def test_metadata_is_none_but_has_metadata_flag(self):
        result = _classify_status(None, True, True, 30)
        assert result == "missing_metadata"

    def test_stale_at_threshold_boundary(self):
        now = datetime.now(timezone.utc)
        at_threshold = (now - timedelta(days=30)).isoformat()
        metadata = {"trained_at": at_threshold}
        result = _classify_status(metadata, True, True, 30)
        assert result == "healthy"

    def test_stale_one_second_past_threshold(self):
        now = datetime.now(timezone.utc)
        past = (now - timedelta(days=30, seconds=1)).isoformat()
        metadata = {"trained_at": past}
        result = _classify_status(metadata, True, True, 30)
        assert result == "stale"


class TestGetModelHealth:
    def test_returns_healthy_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "BTC_1d_xgboost_model.json")
            metadata_path = os.path.join(tmpdir, "BTC_1d_xgboost_metadata.json")
            now = datetime.now(timezone.utc)
            metadata = {
                "asset": "BTC",
                "interval": "1d",
                "asset_class": "crypto",
                "train_end_date": "2025-04-28T00:00:00",
                "train_rows": 1662,
                "test_rows": 416,
                "test_accuracy": 0.55,
                "best_cv_score": 0.52,
                "trained_at": (now - timedelta(days=2)).isoformat(),
            }
            with open(model_path, "w") as f:
                f.write("{}")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                results = get_model_health(threshold_days=30)

        assert len(results) == 1
        r = results[0]
        assert r["asset"] == "BTC"
        assert r["interval"] == "1d"
        assert r["asset_class"] == "crypto"
        assert r["status"] == "healthy"
        assert r["train_rows"] == 1662
        assert r["test_rows"] == 416
        assert r["test_accuracy"] == 0.55
        assert r["best_cv_score"] == 0.52
        assert r["has_model"] is True
        assert r["has_metadata"] is True

    def test_returns_stale_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "ETH_1h_xgboost_model.json")
            metadata_path = os.path.join(tmpdir, "ETH_1h_xgboost_metadata.json")
            old = datetime.now(timezone.utc) - timedelta(days=60)
            metadata = {
                "asset": "ETH",
                "interval": "1h",
                "asset_class": "crypto",
                "trained_at": old.isoformat(),
            }
            with open(model_path, "w") as f:
                f.write("{}")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                results = get_model_health(threshold_days=30)

        assert len(results) == 1
        assert results[0]["status"] == "stale"

    def test_missing_model_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_path = os.path.join(tmpdir, "SOL_4h_xgboost_metadata.json")
            now = datetime.now(timezone.utc)
            metadata = {
                "asset": "SOL",
                "interval": "4h",
                "asset_class": "crypto",
                "trained_at": (now - timedelta(days=1)).isoformat(),
            }
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                results = get_model_health(threshold_days=30)

        assert len(results) == 1
        assert results[0]["status"] == "missing_model"
        assert results[0]["has_model"] is False

    def test_missing_metadata_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "DOT_1d_xgboost_model.json")
            with open(model_path, "w") as f:
                f.write("{}")

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                results = get_model_health(threshold_days=30)

        assert len(results) == 1
        assert results[0]["status"] == "missing_metadata"
        assert results[0]["has_metadata"] is False

    def test_results_sorted_worst_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            now = datetime.now(timezone.utc)
            models = [
                ("AAA", "1d", "missing_model", False, True),
                ("BBB", "1d", "healthy", True, True),
                ("CCC", "1d", "stale", True, True),
            ]
            for asset, interval, status, has_model, has_meta in models:
                if has_meta:
                    meta = {"asset": asset, "interval": interval, "asset_class": "crypto"}
                    if status == "stale":
                        meta["trained_at"] = (now - timedelta(days=60)).isoformat()
                    else:
                        meta["trained_at"] = (now - timedelta(days=2)).isoformat()
                    with open(os.path.join(tmpdir, f"{asset}_{interval}_xgboost_metadata.json"), "w") as f:
                        json.dump(meta, f)
                if has_model:
                    with open(os.path.join(tmpdir, f"{asset}_{interval}_xgboost_model.json"), "w") as f:
                        f.write("{}")

            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                results = get_model_health(threshold_days=30)

        statuses = [r["status"] for r in results]
        assert statuses[0] == "missing_model"
        assert statuses[1] == "stale"
        assert statuses[2] == "healthy"

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("dashboard.model_health.MODEL_DIRS", {"crypto": tmpdir, "stocks": "/nonexistent"}):
                results = get_model_health()
        assert results == []


class TestGetSummaryCounts:
    def test_all_healthy(self):
        results = [
            {"status": "healthy"},
            {"status": "healthy"},
            {"status": "healthy"},
        ]
        counts = get_summary_counts(results)
        assert counts["total"] == 3
        assert counts["healthy"] == 3
        assert counts["stale"] == 0
        assert counts["missing_model"] == 0
        assert counts["missing_metadata"] == 0

    def test_mixed_statuses(self):
        results = [
            {"status": "healthy"},
            {"status": "healthy"},
            {"status": "stale"},
            {"status": "missing_model"},
            {"status": "missing_metadata"},
        ]
        counts = get_summary_counts(results)
        assert counts["total"] == 5
        assert counts["healthy"] == 2
        assert counts["stale"] == 1
        assert counts["missing_model"] == 1
        assert counts["missing_metadata"] == 1

    def test_empty_list(self):
        counts = get_summary_counts([])
        assert counts["total"] == 0
        assert sum(v for k, v in counts.items() if k != "total") == 0


class TestStatusConstants:
    def test_status_labels_have_all_keys(self):
        for key in ["healthy", "stale", "missing_model", "missing_metadata"]:
            assert key in STATUS_LABELS

    def test_status_colors_have_all_keys(self):
        for key in ["healthy", "stale", "missing_model", "missing_metadata"]:
            assert key in STATUS_COLORS

    def test_status_order_ascending(self):
        assert STATUS_ORDER["missing_model"] < STATUS_ORDER["missing_metadata"]
        assert STATUS_ORDER["missing_metadata"] < STATUS_ORDER["stale"]
        assert STATUS_ORDER["stale"] < STATUS_ORDER["healthy"]


class TestModelQualityMetrics:
    def test_calculates_known_oos_metric_values(self):
        from dashboard.app import _calculate_model_quality

        predictions = pd.DataFrame({
            "close": [100, 101, 100, 102, 103, 104],
            "prediction": [0, 1, 0, 1, 1, 0],
            "confidence": [0.9, 0.9, 0.8, 0.7, 0.6, 0.9],
            "actual_direction": [0, 0, 1, 1, 0, float("nan")],
            "is_oos": [False, False, True, True, True, True],
        })

        metrics = _calculate_model_quality(predictions)

        assert metrics["oos_rows"] == 3
        assert metrics["oos_accuracy"] == pytest.approx(1 / 3)
        assert metrics["balanced_accuracy"] == pytest.approx(0.25)
        assert metrics["f1_score"] == pytest.approx(0.5)
        assert metrics["mcc"] == pytest.approx(-0.5)
        assert metrics["best_baseline_accuracy"] == pytest.approx(2 / 3)
        assert metrics["baseline_gap"] == pytest.approx(-1 / 3)
        assert metrics["actual_up_pct"] == pytest.approx(2 / 3)
        assert metrics["actual_down_pct"] == pytest.approx(1 / 3)
        assert metrics["predicted_up_pct"] == pytest.approx(2 / 3)
        assert metrics["predicted_down_pct"] == pytest.approx(1 / 3)
        assert metrics["brier_score"] == pytest.approx((0.64 + 0.09 + 0.36) / 3)

    def test_returns_unavailable_metrics_without_known_actuals(self):
        from dashboard.app import _calculate_model_quality

        predictions = pd.DataFrame({
            "close": [100, 101],
            "prediction": [1, 0],
            "confidence": [0.6, 0.7],
            "actual_direction": [float("nan"), float("nan")],
            "is_oos": [True, True],
        })

        metrics = _calculate_model_quality(predictions)

        assert metrics["oos_rows"] == 0
        assert metrics["oos_accuracy"] is None
        assert metrics["balanced_accuracy"] is None
        assert metrics["f1_score"] is None
        assert metrics["mcc"] is None
        assert metrics["best_baseline_accuracy"] is None
        assert metrics["baseline_gap"] is None
        assert metrics["brier_score"] is None


class TestDashboardRenderModelHealth:
    def test_renders_tab_label(self):
        from dashboard import app as dashboard_app

        tabs = dashboard_app.app.layout.children
        tab_labels = []
        for child in tabs:
            if hasattr(child, "children") and child.children is not None:
                for c in child.children:
                    if hasattr(c, "label"):
                        tab_labels.append(c.label)
                    if hasattr(c, "children") and c.children is not None:
                        for cc in c.children:
                            if hasattr(cc, "label"):
                                tab_labels.append(cc.label)

        assert any("Model Health" in label for label in tab_labels)

    def test_renders_summary_cards_with_data(self):
        from dashboard import app as dashboard_app

        now = datetime.now(timezone.utc)
        models = [
            {"asset": "BTC", "interval": "1d", "asset_class": "crypto",
             "trained_at": (now - timedelta(days=2)).isoformat(),
             "train_end_date": "2025-04-28", "train_rows": 1662, "test_rows": 416,
             "test_accuracy": 0.55, "best_cv_score": 0.52,
             "status": "healthy", "has_model": True, "has_metadata": True},
            {"asset": "ETH", "interval": "1h", "asset_class": "crypto",
             "trained_at": (now - timedelta(days=60)).isoformat(),
             "train_end_date": "2025-04-01", "train_rows": 5000, "test_rows": 1000,
             "test_accuracy": 0.48, "best_cv_score": 0.50,
             "status": "stale", "has_model": True, "has_metadata": True},
            {"asset": "SOL", "interval": "4h", "asset_class": "crypto",
             "trained_at": (now - timedelta(days=1)).isoformat(),
             "train_end_date": "2025-04-20", "train_rows": 3000, "test_rows": 750,
             "test_accuracy": 0.52, "best_cv_score": 0.51,
             "status": "missing_model", "has_model": False, "has_metadata": True},
        ]

        with patch("dashboard.app.get_model_health", return_value=models):
            with patch("dashboard.app.get_summary_counts", return_value={
                "total": 3, "healthy": 1, "stale": 1, "missing_model": 1, "missing_metadata": 0,
            }):
                content = dashboard_app.render_model_health()

        text = _collect_text(content)
        assert "Model Health" in text
        assert "Total Models" in text

    def test_renders_table_with_asset_data(self):
        from dashboard import app as dashboard_app

        now = datetime.now(timezone.utc)
        models = [
            {"asset": "BTC", "interval": "1d", "asset_class": "crypto",
             "trained_at": (now - timedelta(days=2)).isoformat(),
             "train_end_date": "2025-04-28", "train_rows": 1662, "test_rows": 416,
             "test_accuracy": 0.55, "best_cv_score": 0.52,
             "status": "healthy", "has_model": True, "has_metadata": True},
        ]

        with patch("dashboard.app.get_model_health", return_value=models):
            with patch("dashboard.app.get_summary_counts", return_value={
                "total": 1, "healthy": 1, "stale": 0, "missing_model": 0, "missing_metadata": 0,
            }):
                content = dashboard_app.render_model_health()

        table = content.children[2]
        table_data = table.data
        assert len(table_data) == 1
        assert table_data[0]["Asset"] == "BTC"
        assert table_data[0]["Interval"] == "1d"
        assert table_data[0]["Class"] == "Crypto"
        assert table_data[0]["Status"] == "healthy"

    def test_renders_no_models_message(self):
        from dashboard import app as dashboard_app

        with patch("dashboard.app.get_model_health", return_value=[]):
            with patch("dashboard.app.get_summary_counts", return_value={
                "total": 0, "healthy": 0, "stale": 0, "missing_model": 0, "missing_metadata": 0,
            }):
                content = dashboard_app.render_model_health()

        assert len(content.children) == 3
        alert = content.children[2]
        alert_text = _collect_text(alert)
        assert "No models found" in " ".join(alert_text)