import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb


def _prefect_decorator(*args, **kwargs):
    def decorate(function):
        function.fn = function
        return function

    if args and callable(args[0]):
        return decorate(args[0])
    return decorate


mock_prefect = MagicMock()
mock_prefect.task = _prefect_decorator
mock_prefect.flow = _prefect_decorator
mock_prefect.get_run_logger = MagicMock(return_value=MagicMock())
sys.modules["dotenv"] = MagicMock()
sys.modules["prefect"] = mock_prefect
sys.modules["prefect.task"] = MagicMock()
sys.modules["prefect.flow"] = MagicMock()

mock_pyrate = MagicMock()
mock_pyrate.Duration = MagicMock()
mock_pyrate.RequestRate = MagicMock()
mock_pyrate.Limiter = MagicMock()
sys.modules["pyrate_limiter"] = mock_pyrate
sys.modules["requests_cache"] = MagicMock()
sys.modules["requests_ratelimiter"] = MagicMock()

mock_src_ingestion = MagicMock()
mock_src_ingestion.YahooFinanceClient = MagicMock()
mock_src_ingestion.BybitClient = MagicMock()
sys.modules["src.ingestion"] = mock_src_ingestion
sys.modules["src.database"] = MagicMock()

from orchestration.orchestration import (
    CHECKPOINT_FILE,
    LOCK_FILE,
    STEP_VALIDATORS,
    _clear_checkpoint,
    _load_checkpoint,
    _mark_done,
    _save_checkpoint,
    _should_run,
    _start_pipeline_run,
)


class TestCheckpoint:
    def test_load_empty_checkpoint(self):
        with patch.object(Path, "exists", return_value=False):
            result = _load_checkpoint()
            assert result == set()

    def test_save_and_load_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = CHECKPOINT_FILE
            try:
                monkey = CHECKPOINT_FILE.__class__
                checkpoint_file = Path(os.path.join(tmpdir, "checkpoint.json"))
                import orchestration.orchestration as orch
                orch.CHECKPOINT_FILE = checkpoint_file

                _save_checkpoint({"step1", "step2"})
                result = _load_checkpoint()
                assert result == {"step1", "step2"}
            finally:
                orch.CHECKPOINT_FILE = orig

    def test_clear_checkpoint_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import orchestration.orchestration as orch
            checkpoint_file = Path(os.path.join(tmpdir, "checkpoint.json"))
            orch.CHECKPOINT_FILE = checkpoint_file
            _save_checkpoint({"step1"})
            _clear_checkpoint()
            assert not checkpoint_file.exists()

    def test_should_run_when_not_in_checkpoint(self):
        with patch("orchestration.orchestration._load_checkpoint", return_value=set()):
            assert _should_run("step1", force=False) is True

    def test_should_skip_when_in_checkpoint(self):
        with patch("orchestration.orchestration._load_checkpoint", return_value={"step1"}):
            assert _should_run("step1", force=False) is False

    def test_should_run_when_force(self):
        with patch("orchestration.orchestration._load_checkpoint", return_value={"step1"}):
            assert _should_run("step1", force=True) is True

    def test_mark_done_adds_to_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import orchestration.orchestration as orch
            checkpoint_file = Path(os.path.join(tmpdir, "checkpoint.json"))
            orch.CHECKPOINT_FILE = checkpoint_file
            _mark_done("step3")
            completed = _load_checkpoint()
            assert "step3" in completed


class TestStepValidators:
    def test_all_steps_have_validators(self):
        expected_steps = [
            "step1_extract", "step2_load", "step3_clean",
            "step4_dimensions", "step5_facts", "step6_gold",
            "step7_indicators", "step8_models",
        ]
        for step in expected_steps:
            assert step in STEP_VALIDATORS

    def test_step2_load_has_no_validator(self):
        assert STEP_VALIDATORS["step2_load"] is None

    def test_step1_has_validator(self):
        assert STEP_VALIDATORS["step1_extract"] is not None
        assert callable(STEP_VALIDATORS["step1_extract"])


class TestPipelineRunHistory:
    def test_start_pipeline_run_saves_skipped_status_and_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.duckdb")
            reason = "Pipeline run skipped because another run is active (PID 1234)."
            with patch("orchestration.orchestration._get_db_path", return_value=db_path):
                with patch("orchestration.orchestration._load_checkpoint", return_value=set()):
                    run_id = _start_pipeline_run(status="skipped", error_message=reason)

            conn = duckdb.connect(db_path, read_only=True)
            row = conn.execute(
                """
                SELECT status, error_message, end_time, duration_seconds
                FROM pipeline_runs
                WHERE run_id = ?
                """,
                [run_id],
            ).fetchone()
            conn.close()

        assert row[0] == "skipped"
        assert row[1] == reason
        assert row[2] is not None
        assert row[3] == 0.0


class TestLockFile:
    def test_lock_file_path(self):
        assert LOCK_FILE.name == ".pipeline_running.lock"

    def test_checkpoint_file_path(self):
        assert CHECKPOINT_FILE.name == ".pipeline_checkpoint.json"


class TestModelFamilyRefresh:
    def test_refreshes_after_btc_1h_retraining(self):
        import orchestration.orchestration as orch

        trainer = MagicMock()
        trainer.last_retrained_models = ["BTC_1h", "ETH_1h"]
        with patch.object(orch, "PipelineModelTrainer", return_value=trainer):
            with patch(
                "scripts.compare_model_families.refresh_comparison"
            ) as refresh:
                result = orch.train_models.fn()

        assert result == ["BTC_1h", "ETH_1h"]
        refresh.assert_called_once_with()

    def test_does_not_refresh_for_unrelated_retraining(self):
        import orchestration.orchestration as orch

        trainer = MagicMock()
        trainer.last_retrained_models = ["ETH_1h"]
        with patch.object(orch, "PipelineModelTrainer", return_value=trainer):
            with patch(
                "scripts.compare_model_families.refresh_comparison"
            ) as refresh:
                result = orch.train_models.fn()

        assert result == ["ETH_1h"]
        refresh.assert_not_called()

    def test_comparison_failure_does_not_fail_retraining(self):
        import orchestration.orchestration as orch

        trainer = MagicMock()
        trainer.last_retrained_models = ["BTC_1h"]
        logger = MagicMock()
        with patch.object(orch, "PipelineModelTrainer", return_value=trainer):
            with patch.object(orch, "get_run_logger", return_value=logger):
                with patch(
                    "scripts.compare_model_families.refresh_comparison",
                    side_effect=RuntimeError("comparison failed"),
                ):
                    result = orch.train_models.fn()

        assert result == ["BTC_1h"]
        logger.warning.assert_called_once_with(
            "BTC 1h model family comparison failed: comparison failed"
        )