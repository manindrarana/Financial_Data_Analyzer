import os
import sqlite3
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import duckdb

from src.utils.pipeline_audit import (
    backfill_pipeline_runs,
    connect_audit_db,
    fetch_prefect_flow_runs,
    insert_pipeline_run,
    map_prefect_state,
    migrate_pipeline_runs,
    normalize_prefect_run,
    parse_timestamp,
    reconcile_running_runs,
    update_pipeline_run,
)


PIPELINE_RUN_SCHEMA = """
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


def test_connect_audit_db_creates_wal_database_and_table(tmp_path):
    db_path = tmp_path / "database" / "pipeline_history.sqlite3"

    conn = connect_audit_db(str(db_path))
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'pipeline_runs'"
    ).fetchone()
    conn.close()

    assert db_path.exists()
    assert journal_mode == "wal"
    assert table == ("pipeline_runs",)


def test_insert_and_update_pipeline_run_save_known_values(tmp_path):
    db_path = str(tmp_path / "pipeline_history.sqlite3")
    start_time = datetime(2026, 8, 21, 8, 20, 0)
    insert_pipeline_run(
        db_path,
        (
            "run_1",
            start_time,
            None,
            None,
            "running",
            "manual",
            None,
            None,
            None,
            None,
            0,
            1,
        ),
    )

    update_pipeline_run(
        db_path,
        "run_1",
        "success",
        None,
        {
            "models_retrained": ["BTC_1h", "ETH_4h"],
            "rows_fetched": 120,
            "rows_cleaned": 115,
            "validator_failures": 2,
        },
        datetime.now() - timedelta(seconds=5),
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT status, models_retrained, rows_fetched, rows_cleaned,
               validator_failures, checkpoint_resumed, duration_seconds
        FROM pipeline_runs
        WHERE run_id = 'run_1'
        """
    ).fetchone()
    conn.close()

    assert row[:6] == ("success", "BTC_1h,ETH_4h", 120, 115, 2, 1)
    assert 4.0 <= row[6] <= 6.0


def test_update_pipeline_run_accepts_production_float_start_time(tmp_path):
    db_path = str(tmp_path / "pipeline_history.sqlite3")
    insert_pipeline_run(
        db_path,
        (
            "run_float",
            datetime.now(),
            None,
            None,
            "running",
            "cron",
            None,
            None,
            None,
            None,
            0,
            False,
        ),
    )

    update_pipeline_run(
        db_path,
        "run_float",
        "success",
        None,
        {"rows_fetched": 10, "rows_cleaned": 9},
        time.time() - 3,
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, rows_fetched, rows_cleaned, duration_seconds FROM pipeline_runs"
    ).fetchone()
    conn.close()

    assert row[:3] == ("success", 10, 9)
    assert 2.0 <= row[3] <= 4.0


def test_migrate_pipeline_runs_preserves_values_and_is_idempotent(tmp_path):
    duckdb_path = str(tmp_path / "financial_data.duckdb")
    audit_db_path = str(tmp_path / "pipeline_history.sqlite3")
    source = duckdb.connect(duckdb_path)
    source.execute(PIPELINE_RUN_SCHEMA)
    source.execute(
        """
        INSERT INTO pipeline_runs VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "run_success",
            datetime(2026, 8, 20, 8, 0, 0),
            datetime(2026, 8, 20, 8, 5, 0),
            300.0,
            "success",
            "cron",
            None,
            "BTC_1h",
            100,
            95,
            0,
            False,
            "run_skipped",
            datetime(2026, 8, 20, 8, 1, 0),
            datetime(2026, 8, 20, 8, 1, 0),
            0.0,
            "skipped",
            "manual",
            "Pipeline run skipped because another run is active (PID 69).",
            None,
            None,
            None,
            0,
            True,
        ],
    )
    source.close()

    first_count = migrate_pipeline_runs(duckdb_path, audit_db_path)
    second_count = migrate_pipeline_runs(duckdb_path, audit_db_path)

    conn = sqlite3.connect(audit_db_path)
    rows = conn.execute(
        """
        SELECT run_id, status, duration_seconds, error_message,
               models_retrained, rows_fetched, rows_cleaned,
               validator_failures, checkpoint_resumed
        FROM pipeline_runs
        ORDER BY run_id
        """
    ).fetchall()
    conn.close()

    assert first_count == 2
    assert second_count == 0
    assert rows == [
        (
            "run_skipped",
            "skipped",
            0.0,
            "Pipeline run skipped because another run is active (PID 69).",
            None,
            None,
            None,
            0,
            1,
        ),
        ("run_success", "success", 300.0, None, "BTC_1h", 100, 95, 0, 0),
    ]


def test_new_skipped_run_does_not_require_duckdb_access(tmp_path):
    duckdb_path = str(tmp_path / "financial_data.duckdb")
    audit_db_path = str(tmp_path / "pipeline_history.sqlite3")
    locked_source = duckdb.connect(duckdb_path)
    locked_source.execute(PIPELINE_RUN_SCHEMA)
    locked_source.execute("BEGIN TRANSACTION")
    locked_source.execute(
        """
        INSERT INTO pipeline_runs VALUES
        ('active', CURRENT_TIMESTAMP, NULL, NULL, 'running', 'manual',
         NULL, NULL, NULL, NULL, 0, FALSE)
        """
    )

    reason = "Pipeline run skipped because another run is active (PID 69)."
    insert_pipeline_run(
        audit_db_path,
        (
            "run_skipped",
            datetime(2026, 8, 21, 8, 20, 15),
            datetime(2026, 8, 21, 8, 20, 15),
            0.0,
            "skipped",
            "manual",
            reason,
            None,
            None,
            None,
            0,
            False,
        ),
    )

    conn = sqlite3.connect(audit_db_path)
    row = conn.execute(
        "SELECT status, error_message, duration_seconds FROM pipeline_runs"
    ).fetchone()
    conn.close()
    locked_source.rollback()
    locked_source.close()

    assert row == ("skipped", reason, 0.0)


def _make_prefect_run(
    run_id,
    state_type,
    start_time,
    end_time=None,
    message=None,
    deployment_id=None,
    total_run_time=None,
):
    return {
        "id": run_id,
        "state": {"type": state_type, "message": message},
        "start_time": start_time,
        "end_time": end_time,
        "total_run_time": total_run_time,
        "deployment_id": deployment_id,
    }


def _insert_audit_row(db_path, run_id, start_time, status="running"):
    insert_pipeline_run(
        db_path,
        (
            run_id,
            start_time,
            None,
            None,
            status,
            "cron",
            None,
            None,
            None,
            None,
            0,
            False,
        ),
    )


def _fetch_audit_rows(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            """
            SELECT run_id, status, end_time, duration_seconds, error_message
            FROM pipeline_runs
            ORDER BY start_time
            """
        ).fetchall()
    finally:
        conn.close()


class TestParseTimestamp:
    def test_parses_utc_iso_string_without_suffix(self):
        assert parse_timestamp("2026-08-21T07:47:07+00:00") == datetime(
            2026, 8, 21, 7, 47, 7
        )

    def test_parses_z_suffix_and_converts_to_naive_utc(self):
        assert parse_timestamp("2026-08-21T07:47:07.123456Z") == datetime(
            2026, 8, 21, 7, 47, 7, 123456
        )

    def test_converts_offset_to_utc(self):
        assert parse_timestamp("2026-08-21T08:47:07+01:00") == datetime(
            2026, 8, 21, 7, 47, 7
        )

    def test_accepts_naive_string_and_none(self):
        assert parse_timestamp("2026-08-21 07:47:07") == datetime(
            2026, 8, 21, 7, 47, 7
        )
        assert parse_timestamp(None) is None


class TestMapPrefectState:
    def test_completed_maps_to_success_without_error(self):
        assert map_prefect_state("COMPLETED") == ("success", None)

    def test_failed_and_crashed_map_to_failed_with_state_named(self):
        status, error = map_prefect_state("FAILED", "task raised RuntimeError")
        assert status == "failed"
        assert error == "Reconciled from Prefect state: Failed (task raised RuntimeError)"

        status, error = map_prefect_state("CRASHED")
        assert status == "failed"
        assert error == "Reconciled from Prefect state: Crashed"

    def test_cancelled_maps_to_failed_with_state_named(self):
        status, error = map_prefect_state("CANCELLED")
        assert status == "failed"
        assert error == "Reconciled from Prefect state: Cancelled"

    def test_running_returns_none(self):
        assert map_prefect_state("RUNNING") == (None, None)


class TestNormalizePrefectRun:
    def test_normalizes_fields_from_state_object(self):
        run = normalize_prefect_run(
            _make_prefect_run(
                "abc-123",
                "CANCELLED",
                "2026-08-21T07:47:07+00:00",
                end_time="2026-08-21T08:34:27+00:00",
            )
        )
        assert run["state_type"] == "CANCELLED"
        assert run["start_time"] == datetime(2026, 8, 21, 7, 47, 7)
        assert run["end_time"] == datetime(2026, 8, 21, 8, 34, 27)
        assert run["duration_seconds"] == 2820.0
        assert run["deployment_id"] is None

    def test_falls_back_to_state_timestamp_for_end_time(self):
        run = _make_prefect_run(
            "abc-123",
            "FAILED",
            "2026-08-20T07:20:14+00:00",
        )
        run["end_time"] = None
        run["state"]["timestamp"] = "2026-08-20T07:20:15+00:00"
        normalized = normalize_prefect_run(run)
        assert normalized["end_time"] == datetime(2026, 8, 20, 7, 20, 15)
        assert normalized["duration_seconds"] == 1.0

    def test_prefers_total_run_time_over_derived_duration(self):
        run = _make_prefect_run(
            "abc-123",
            "COMPLETED",
            "2026-08-21T07:47:07+00:00",
            end_time="2026-08-21T08:15:00+00:00",
            total_run_time=0.5,
        )
        assert normalize_prefect_run(run)["duration_seconds"] == 0.5


def _audit_db(tmp_path):
    return str(tmp_path / "pipeline_history.sqlite3")


class TestReconcileRunningRuns:
    def test_finalizes_both_stuck_running_rows_from_2026_08_21(self, tmp_path):
        db_path = _audit_db(tmp_path)
        _insert_audit_row(db_path, "run_20260821_074707_69", datetime(2026, 8, 21, 7, 47, 7))
        _insert_audit_row(db_path, "run_20260821_083637_69", datetime(2026, 8, 21, 8, 36, 37))

        prefect_runs = [
            _make_prefect_run(
                "cancel-id",
                "CANCELLED",
                "2026-08-21T07:47:05+00:00",
                end_time="2026-08-21T08:34:27+00:00",
            ),
            _make_prefect_run(
                "fail-id",
                "FAILED",
                "2026-08-21T08:36:39+00:00",
                end_time="2026-08-21T08:41:32+00:00",
            ),
        ]

        finalized = reconcile_running_runs(db_path, prefect_runs)
        rows = {row[0]: row for row in _fetch_audit_rows(db_path)}

        assert finalized == 2
        cancelled_row = rows["run_20260821_074707_69"]
        assert cancelled_row[1] == "failed"
        assert cancelled_row[2] == "2026-08-21 08:34:27"
        assert cancelled_row[3] == 2820.0
        assert "Cancelled" in cancelled_row[4]
        failed_row = rows["run_20260821_083637_69"]
        assert failed_row[1] == "failed"
        assert failed_row[2] == "2026-08-21 08:41:32"
        assert failed_row[3] == 293.0
        assert "Failed" in failed_row[4]

    def test_leaves_running_row_unmatched_when_no_prefect_run_is_close(self):
        db_path = str(tmp_path_factory_missing())
        _insert_audit_row(db_path, "run_20260821_074707_69", datetime(2026, 8, 21, 7, 47, 7))

        prefect_runs = [
            _make_prefect_run(
                "unrelated-id",
                "COMPLETED",
                "2026-08-25T10:00:00+00:00",
                end_time="2026-08-25T10:25:00+00:00",
            ),
        ]

        finalized = reconcile_running_runs(db_path, prefect_runs)
        rows = _fetch_audit_rows(db_path)

        assert finalized == 0
        assert rows[0][1] == "running"
        assert rows[0][2] is None

    def test_running_prefect_states_are_not_terminal(self):
        db_path = str(tmp_path_factory_missing())
        _insert_audit_row(db_path, "run_live", datetime(2026, 9, 7, 9, 0, 0))

        prefect_runs = [
            _make_prefect_run("live-id", "RUNNING", "2026-09-07T09:00:01+00:00"),
        ]

        finalized = reconcile_running_runs(db_path, prefect_runs)
        rows = _fetch_audit_rows(db_path)

        assert finalized == 0
        assert rows[0][1] == "running"

    def test_reconcile_is_idempotent_second_call_finalizes_nothing(self):
        db_path = str(tmp_path_factory_missing())
        _insert_audit_row(db_path, "run_20260821_074707_69", datetime(2026, 8, 21, 7, 47, 7))
        prefect_runs = [
            _make_prefect_run(
                "cancel-id",
                "CANCELLED",
                "2026-08-21T07:47:05+00:00",
                end_time="2026-08-21T08:34:27+00:00",
            ),
        ]

        first = reconcile_running_runs(db_path, prefect_runs)
        second = reconcile_running_runs(db_path, prefect_runs)

        assert first == 1
        assert second == 0


class TestBackfillPipelineRuns:
    def test_inserts_missing_instant_failure_run_from_2026_08_20(self):
        db_path = str(tmp_path_factory_missing())
        _insert_audit_row(
            db_path,
            "run_20260821_074707_69",
            datetime(2026, 8, 21, 7, 47, 7),
            status="success",
        )

        prefect_runs = [
            _make_prefect_run(
                "instant-fail-id",
                "FAILED",
                "2026-08-20T07:20:14+00:00",
                end_time="2026-08-20T07:20:15+00:00",
                message="Task run failed",
                deployment_id="deploy-1",
            ),
        ]

        inserted = backfill_pipeline_runs(db_path, prefect_runs)
        rows = _fetch_audit_rows(db_path)

        assert inserted == 1
        new_row = rows[0]
        assert new_row[1] == "failed"
        assert new_row[2] == "2026-08-20 07:20:15"
        assert new_row[3] == 1.0
        assert "Failed" in new_row[4]

    def test_backfill_is_idempotent_running_twice_inserts_no_duplicates(self):
        db_path = str(tmp_path_factory_missing())
        prefect_runs = [
            _make_prefect_run(
                "instant-fail-id",
                "FAILED",
                "2026-08-20T07:20:14+00:00",
                end_time="2026-08-20T07:20:15+00:00",
            ),
            _make_prefect_run(
                "completed-id",
                "COMPLETED",
                "2026-08-19T07:20:14+00:00",
                end_time="2026-08-19T07:45:00+00:00",
            ),
        ]

        first = backfill_pipeline_runs(db_path, prefect_runs)
        second = backfill_pipeline_runs(db_path, prefect_runs)

        assert first == 2
        assert second == 0

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        conn.close()
        assert count == 2

    def test_rebuilds_history_after_sqlite_deletion(self):
        db_path = str(tmp_path_factory_missing())
        _insert_audit_row(
            db_path,
            "run_existing",
            datetime(2026, 8, 21, 7, 47, 7),
            status="success",
        )
        prefect_runs = [
            _make_prefect_run(
                "old-1",
                "COMPLETED",
                "2026-08-21T07:47:07+00:00",
                end_time="2026-08-21T08:15:00+00:00",
                deployment_id="deploy-1",
            ),
            _make_prefect_run(
                "old-2",
                "FAILED",
                "2026-08-20T07:20:14+00:00",
                end_time="2026-08-20T07:20:15+00:00",
                deployment_id="deploy-1",
            ),
        ]

        os.remove(db_path)

        inserted = backfill_pipeline_runs(db_path, prefect_runs)
        rows = _fetch_audit_rows(db_path)

        assert inserted == 2
        statuses = {row[1] for row in rows}
        assert statuses == {"success", "failed"}

        conn = sqlite3.connect(db_path)
        triggers = conn.execute("SELECT DISTINCT trigger FROM pipeline_runs").fetchall()
        conn.close()
        assert triggers == [("cron",)]

    def test_trigger_depends_on_deployment_id(self):
        db_path = str(tmp_path_factory_missing())
        prefect_runs = [
            _make_prefect_run(
                "deployed-run",
                "COMPLETED",
                "2026-08-21T07:47:07+00:00",
                end_time="2026-08-21T08:15:00+00:00",
                deployment_id="deploy-1",
            ),
            _make_prefect_run(
                "ad-hoc-run",
                "FAILED",
                "2026-08-22T07:20:14+00:00",
                end_time="2026-08-22T07:20:15+00:00",
            ),
        ]

        backfill_pipeline_runs(db_path, prefect_runs)

        conn = sqlite3.connect(db_path)
        triggers = dict(
            conn.execute(
                """
                SELECT run_id, trigger FROM pipeline_runs
                ORDER BY start_time
                """
            ).fetchall()
        )
        conn.close()
        triggers_by_time = list(triggers.values())
        assert triggers_by_time == ["cron", "manual"]

    def test_skips_non_terminal_prefect_runs(self):
        db_path = str(tmp_path_factory_missing())
        prefect_runs = [
            _make_prefect_run("pending-id", "PENDING", "2026-08-21T07:47:07+00:00"),
            _make_prefect_run("running-id", "RUNNING", "2026-08-22T07:47:07+00:00"),
        ]

        inserted = backfill_pipeline_runs(db_path, prefect_runs)

        assert inserted == 0
        rows = _fetch_audit_rows(db_path)
        assert rows == []


class TestFetchPrefectFlowRuns:
    def test_paginates_until_short_page_and_filters_by_flow_name(self):
        pages = [
            [{"id": f"run-{i}", "state": {"type": "COMPLETED"}} for i in range(200)],
            [{"id": "run-final", "state": {"type": "COMPLETED"}}],
        ]
        with patch("src.utils.pipeline_audit.requests.post") as post:
            post.return_value = MagicMock(
                json=lambda: pages.pop(0),
                raise_for_status=lambda: None,
            )
            runs = fetch_prefect_flow_runs(api_url="http://prefect:4200/api", page_size=200)

        assert len(runs) == 201
        assert post.call_count == 2
        first_body = post.call_args_list[0].kwargs["json"]
        assert first_body["flows"] == {"name": {"any_": ["financial-data-pipeline"]}}
        assert first_body["limit"] == 200
        assert first_body["offset"] == 0
        second_body = post.call_args_list[1].kwargs["json"]
        assert second_body["offset"] == 200
