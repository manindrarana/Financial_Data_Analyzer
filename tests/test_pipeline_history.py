import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import os
import tempfile
import duckdb
import pandas as pd
from unittest.mock import patch, MagicMock

from dashboard.pipeline_history import get_pipeline_runs, get_run_summary


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


def _walk_components(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if isinstance(children, list):
        for child in children:
            yield from _walk_components(child)
    else:
        yield from _walk_components(children)


def _make_db_with_runs(tmpdir, rows):
    db_path = os.path.join(tmpdir, "test.duckdb")
    conn = duckdb.connect(db_path)
    conn.execute(
        """
        CREATE TABLE pipeline_runs (
            run_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration_seconds DOUBLE,
            status VARCHAR,
            trigger VARCHAR,
            error_message VARCHAR,
            models_retrained VARCHAR,
            rows_fetched INTEGER,
            rows_cleaned INTEGER,
            validator_failures INTEGER,
            checkpoint_resumed BOOLEAN
        )
        """
    )
    for r in rows:
        conn.execute(
            """
            INSERT INTO pipeline_runs
                (run_id, start_time, end_time, duration_seconds, status,
                 trigger, error_message, models_retrained, rows_fetched,
                 rows_cleaned, validator_failures, checkpoint_resumed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                r["run_id"], r["start_time"], r.get("end_time"),
                r.get("duration_seconds"), r["status"], r.get("trigger"),
                r.get("error_message"), r.get("models_retrained"),
                r.get("rows_fetched"), r.get("rows_cleaned"),
                r.get("validator_failures", 0), r.get("checkpoint_resumed", False),
            ],
        )
    conn.close()
    return db_path


class TestGetPipelineRuns:
    def test_returns_empty_dataframe_when_db_missing(self):
        with patch("dashboard.pipeline_history.DB_PATH", "/nonexistent/test.duckdb"):
            df = get_pipeline_runs(limit=50)
        assert df.empty
        assert "run_id" in df.columns
        assert "status" in df.columns

    def test_returns_empty_dataframe_when_table_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.duckdb")
            duckdb.connect(db_path).close()
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                df = get_pipeline_runs(limit=50)
        assert df.empty
        assert "run_id" in df.columns

    def test_returns_rows_sorted_newest_first(self):
        rows = [
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00",
             "end_time": "2026-07-20 10:25:00", "duration_seconds": 1500.0,
             "status": "success", "trigger": "cron"},
            {"run_id": "run_2", "start_time": "2026-07-20 11:00:00",
             "end_time": "2026-07-20 11:26:00", "duration_seconds": 1560.0,
             "status": "success", "trigger": "cron"},
            {"run_id": "run_3", "start_time": "2026-07-20 12:00:00",
             "end_time": None, "duration_seconds": None,
             "status": "running", "trigger": "cron"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                df = get_pipeline_runs(limit=50)
        assert len(df) == 3
        assert df.iloc[0]["run_id"] == "run_3"
        assert df.iloc[1]["run_id"] == "run_2"
        assert df.iloc[2]["run_id"] == "run_1"

    def test_respects_limit(self):
        rows = [
            {"run_id": f"run_{i}", "start_time": f"2026-07-20 {10+i}:00:00",
             "status": "success", "trigger": "cron"}
            for i in range(5)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                df = get_pipeline_runs(limit=2)
        assert len(df) == 2
        assert df.iloc[0]["run_id"] == "run_4"
        assert df.iloc[1]["run_id"] == "run_3"

    def test_includes_all_columns(self):
        rows = [
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00",
             "status": "success", "trigger": "cron",
             "error_message": None, "models_retrained": "BTC_1h,ETH_4h",
             "rows_fetched": 5000, "rows_cleaned": 4998,
             "validator_failures": 0, "checkpoint_resumed": False},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                df = get_pipeline_runs(limit=50)
        expected_cols = {
            "run_id", "start_time", "end_time", "duration_seconds",
            "status", "trigger", "error_message", "models_retrained",
            "rows_fetched", "rows_cleaned", "validator_failures",
            "checkpoint_resumed",
        }
        assert expected_cols.issubset(set(df.columns))
        assert df.iloc[0]["models_retrained"] == "BTC_1h,ETH_4h"
        assert df.iloc[0]["rows_fetched"] == 5000


class TestGetRunSummary:
    def test_returns_zeros_when_db_missing(self):
        with patch("dashboard.pipeline_history.DB_PATH", "/nonexistent/test.duckdb"):
            summary = get_run_summary()
        assert summary["total"] == 0
        assert summary["success"] == 0
        assert summary["failed"] == 0
        assert summary["running"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["last_status"] == "none"
        assert summary["last_error"] is None

    def test_returns_zeros_when_table_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.duckdb")
            duckdb.connect(db_path).close()
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                summary = get_run_summary()
        assert summary["total"] == 0
        assert summary["last_status"] == "none"

    def test_counts_statuses_correctly(self):
        rows = [
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00", "status": "success", "trigger": "cron"},
            {"run_id": "run_2", "start_time": "2026-07-20 11:00:00", "status": "success", "trigger": "cron"},
            {"run_id": "run_3", "start_time": "2026-07-20 12:00:00", "status": "failed", "trigger": "cron",
             "error_message": "step5_facts failed: fact_price_history has 0 rows"},
            {"run_id": "run_4", "start_time": "2026-07-20 13:00:00", "status": "running", "trigger": "cron"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                summary = get_run_summary()
        assert summary["total"] == 4
        assert summary["success"] == 2
        assert summary["failed"] == 1
        assert summary["running"] == 1
        assert summary["success_rate"] == 66.7
        assert summary["last_status"] == "running"
        assert summary["last_error"] is None

    def test_skipped_runs_are_counted_but_excluded_from_success_rate(self):
        rows = [
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00", "status": "success", "trigger": "cron"},
            {"run_id": "run_2", "start_time": "2026-07-20 11:00:00", "status": "failed", "trigger": "cron"},
            {"run_id": "run_3", "start_time": "2026-07-20 12:00:00", "status": "skipped", "trigger": "cron",
             "error_message": "Pipeline run skipped because another run is active (PID 1234)."},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                summary = get_run_summary()
        assert summary["total"] == 3
        assert summary["success"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["success_rate"] == 50.0
        assert summary["last_status"] == "skipped"
        assert "PID 1234" in summary["last_error"]

    def test_last_error_captured_when_last_run_failed(self):
        rows = [
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00", "status": "success", "trigger": "cron"},
            {"run_id": "run_2", "start_time": "2026-07-20 11:00:00", "status": "failed", "trigger": "cron",
             "error_message": "step5_facts failed: fact_price_history has 0 rows"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                summary = get_run_summary()
        assert summary["last_status"] == "failed"
        assert "fact_price_history has 0 rows" in summary["last_error"]

    def test_success_rate_zero_when_all_failed(self):
        rows = [
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00", "status": "failed", "trigger": "cron"},
            {"run_id": "run_2", "start_time": "2026-07-20 11:00:00", "status": "failed", "trigger": "cron"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                summary = get_run_summary()
        assert summary["success_rate"] == 0.0
        assert summary["failed"] == 2

    def test_success_rate_excludes_running_from_denominator(self):
        rows = [
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00", "status": "success", "trigger": "cron"},
            {"run_id": "run_2", "start_time": "2026-07-20 11:00:00", "status": "running", "trigger": "cron"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _make_db_with_runs(tmpdir, rows)
            with patch("dashboard.pipeline_history.DB_PATH", db_path):
                summary = get_run_summary()
        assert summary["success_rate"] == 100.0


class TestRenderPipelineHistory:
    def test_renders_summary_cards_and_table(self):
        from dashboard import app as dashboard_app

        summary = {
            "total": 10, "success": 8, "failed": 1, "running": 1,
            "success_rate": 88.9, "last_status": "success", "last_error": None,
        }
        runs_df = pd.DataFrame([
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00",
             "end_time": "2026-07-20 10:25:00", "duration_seconds": 1500.0,
             "status": "success", "trigger": "cron", "error_message": None,
             "models_retrained": "BTC_1h", "rows_fetched": 5000,
             "rows_cleaned": 4998, "validator_failures": 0,
             "checkpoint_resumed": False},
        ])

        with patch("dashboard.app.get_run_summary", return_value=summary):
            with patch("dashboard.app.get_pipeline_runs", return_value=runs_df):
                content = dashboard_app.render_pipeline_history()

        text = _collect_text(content)
        assert "Pipeline Run History" in text
        assert "10" in text
        assert "88.9%" in text
        assert "Last Run Status" in text

    def test_renders_empty_state_when_no_runs(self):
        from dashboard import app as dashboard_app

        summary = {
            "total": 0, "success": 0, "failed": 0, "running": 0,
            "success_rate": 0.0, "last_status": "none", "last_error": None,
        }
        empty_df = pd.DataFrame(columns=[
            "run_id", "start_time", "end_time", "duration_seconds",
            "status", "trigger", "error_message", "models_retrained",
            "rows_fetched", "rows_cleaned", "validator_failures",
            "checkpoint_resumed",
        ])

        with patch("dashboard.app.get_run_summary", return_value=summary):
            with patch("dashboard.app.get_pipeline_runs", return_value=empty_df):
                content = dashboard_app.render_pipeline_history()

        text = _collect_text(content)
        assert "No pipeline runs logged yet" in " ".join(text)

    def test_renders_last_failure_alert(self):
        from dashboard import app as dashboard_app

        summary = {
            "total": 2, "success": 1, "failed": 1, "running": 0,
            "success_rate": 50.0, "last_status": "failed",
            "last_error": "step5_facts failed: fact_price_history has 0 rows",
        }
        runs_df = pd.DataFrame([
            {"run_id": "run_2", "start_time": "2026-07-20 11:00:00",
             "end_time": None, "duration_seconds": None,
             "status": "failed", "trigger": "cron",
             "error_message": "step5_facts failed",
             "models_retrained": None, "rows_fetched": None,
             "rows_cleaned": None, "validator_failures": 1,
             "checkpoint_resumed": False},
        ])

        with patch("dashboard.app.get_run_summary", return_value=summary):
            with patch("dashboard.app.get_pipeline_runs", return_value=runs_df):
                content = dashboard_app.render_pipeline_history()

        text = _collect_text(content)
        assert "Last failure" in " ".join(text)
        assert "fact_price_history has 0 rows" in " ".join(text)

    def test_renders_skipped_count_message_row_and_color(self):
        from dashboard import app as dashboard_app

        reason = "Pipeline run skipped because another run is active (PID 1234)."
        summary = {
            "total": 3, "success": 2, "failed": 0, "running": 0,
            "skipped": 1, "success_rate": 100.0, "last_status": "skipped",
            "last_error": reason,
        }
        runs_df = pd.DataFrame([
            {"run_id": "run_3", "start_time": "2026-08-05 12:00:00",
             "end_time": "2026-08-05 12:00:00", "duration_seconds": 0.0,
             "status": "skipped", "trigger": "cron", "error_message": reason,
             "models_retrained": None, "rows_fetched": None,
             "rows_cleaned": None, "validator_failures": 0,
             "checkpoint_resumed": False},
        ])

        with patch("dashboard.app.get_run_summary", return_value=summary):
            with patch("dashboard.app.get_pipeline_runs", return_value=runs_df):
                content = dashboard_app.render_pipeline_history()

        text = _collect_text(content)
        assert "Skipped" in text
        assert "1" in text
        assert "Last skipped run" in " ".join(text)
        assert "PID 1234" in " ".join(text)

        table = next(
            node for node in _walk_components(content)
            if hasattr(node, "columns") and isinstance(node.columns, list)
        )
        assert table.data[0]["status"] == "skipped"
        assert {
            "if": {"filter_query": "{status} = 'skipped'"},
            "color": "#3498db",
        } in table.style_data_conditional

    def test_table_has_correct_columns(self):
        from dashboard import app as dashboard_app

        summary = {
            "total": 1, "success": 1, "failed": 0, "running": 0,
            "success_rate": 100.0, "last_status": "success", "last_error": None,
        }
        runs_df = pd.DataFrame([
            {"run_id": "run_1", "start_time": "2026-07-20 10:00:00",
             "end_time": "2026-07-20 10:25:00", "duration_seconds": 1500.0,
             "status": "success", "trigger": "cron", "error_message": None,
             "models_retrained": "BTC_1h", "rows_fetched": 5000,
             "rows_cleaned": 4998, "validator_failures": 0,
             "checkpoint_resumed": False},
        ])

        with patch("dashboard.app.get_run_summary", return_value=summary):
            with patch("dashboard.app.get_pipeline_runs", return_value=runs_df):
                content = dashboard_app.render_pipeline_history()

        table = None
        for node in _walk_components(content):
            if hasattr(node, "columns") and isinstance(node.columns, list):
                table = node
                break
        assert table is not None, "DataTable not found in render output"
        col_names = [c["name"] for c in table.columns]
        assert "run_id" in col_names
        assert "status" in col_names
        assert "duration_seconds" in col_names
        assert "models_retrained" in col_names
        assert len(table.data) == 1
        assert table.data[0]["run_id"] == "run_1"
        assert table.data[0]["status"] == "success"
