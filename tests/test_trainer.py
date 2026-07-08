import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()
sys.modules["mlflow"] = MagicMock()
sys.modules["mlflow.xgboost"] = MagicMock()

import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.models.trainer import PipelineModelTrainer

def _mock_trainer(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr(PipelineModelTrainer, "__init__", lambda self: (
        setattr(self, "logger", MagicMock()),
        setattr(self, "conn", mock_conn),
        setattr(self, "config", {
            "paths": {"database": "/tmp/test.duckdb"},
            "ingestion": {
                "targets": {"bybit": ["BTCUSDT"], "yfinance": ["AAPL"]},
            },
            "providers": {
                "bybit": {"intervals": ["60", "D"]},
                "yfinance": {"intervals": ["1h", "1d"]},
            },
        }),
        setattr(self, "models_dir", "/tmp/model_store"),
        setattr(self, "crypto_dir", "/tmp/model_store/crypto"),
        setattr(self, "stocks_dir", "/tmp/model_store/stocks"),
        None
    )[-1])


class TestBuildCombos:
    def test_builds_crypto_combos(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        combos = trainer._build_combos()
        crypto = [c for c in combos if c[2] == "crypto"]
        assert len(crypto) == 2
        assert ("BTC", "1h", "crypto", "gold_crypto_features") in crypto
        assert ("BTC", "1d", "crypto", "gold_crypto_features") in crypto

    def test_builds_stock_combos(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        combos = trainer._build_combos()
        stocks = [c for c in combos if c[2] == "stocks"]
        assert len(stocks) == 2
        assert ("AAPL", "1h", "stocks", "gold_stock_features") in stocks
        assert ("AAPL", "1d", "stocks", "gold_stock_features") in stocks


class TestReadMetadata:
    def test_returns_none_when_no_files(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        with patch("os.path.exists", return_value=False):
            result = trainer._read_metadata("BTC", "1h", "crypto")
        assert result is None

    def test_raises_on_corrupt_json(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", side_effect=json.JSONDecodeError("bad", "", 0)):
                    with pytest.raises(json.JSONDecodeError):
                        trainer._read_metadata("BTC", "1h", "crypto")


class TestGetMetadataPath:
    def test_returns_crypto_path(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        meta_path, model_path = trainer._get_metadata_path("BTC", "1h", "crypto")
        assert "crypto" in meta_path
        assert "BTC_1h_xgboost_metadata.json" in meta_path
        assert "BTC_1h_xgboost_model.json" in model_path

    def test_returns_stock_path(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        meta_path, model_path = trainer._get_metadata_path("AAPL", "1d", "stocks")
        assert "stocks" in meta_path
        assert "AAPL_1d_xgboost_metadata.json" in meta_path
        assert "AAPL_1d_xgboost_model.json" in model_path


def _mock_full_init(monkeypatch, use_gpu=False):
    monkeypatch.setattr("duckdb.connect", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("os.path.exists", lambda x: True)
    monkeypatch.setattr("os.makedirs", lambda *a, **kw: None)
    monkeypatch.setattr("mlflow.set_tracking_uri", lambda x: None)

    mock_config = {
        "paths": {"database": "/tmp/test.duckdb"},
        "ingestion": {
            "targets": {"bybit": ["BTCUSDT"], "yfinance": ["AAPL"]},
        },
        "providers": {
            "bybit": {"intervals": ["60"]},
            "yfinance": {"intervals": ["1h"]},
        },
    }
    mock_open = MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = lambda *a: None
    monkeypatch.setattr("builtins.open", mock_open)
    monkeypatch.setattr("yaml.safe_load", lambda f: mock_config)
    monkeypatch.setattr(PipelineModelTrainer, "_detect_gpu", lambda self: use_gpu)


class TestNJobs:
    def test_n_jobs_override(self, monkeypatch):
        _mock_full_init(monkeypatch, use_gpu=False)
        trainer = PipelineModelTrainer(n_jobs=4)
        assert trainer.n_jobs == 4

    def test_n_jobs_defaults_to_cpu_count_minus_one(self, monkeypatch):
        _mock_full_init(monkeypatch, use_gpu=False)
        trainer = PipelineModelTrainer()
        assert trainer.n_jobs == max(os.cpu_count() - 1, 1)

    def test_n_jobs_at_least_one_when_single_core(self, monkeypatch):
        _mock_full_init(monkeypatch, use_gpu=False)
        monkeypatch.setattr("os.cpu_count", lambda: 1)
        trainer = PipelineModelTrainer()
        assert trainer.n_jobs == 1


class TestDetectGPU:
    def test_returns_false_when_cuda_raises(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()

        mock_cls = MagicMock()
        mock_cls.return_value.fit.side_effect = RuntimeError("no CUDA")
        monkeypatch.setattr("src.models.trainer.xgb.XGBClassifier", mock_cls)

        assert trainer._detect_gpu() is False

    def test_returns_true_when_fit_succeeds_no_warnings(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()

        mock_cls = MagicMock()
        mock_cls.return_value.fit.return_value = None
        monkeypatch.setattr("src.models.trainer.xgb.XGBClassifier", mock_cls)

        assert trainer._detect_gpu() is True

    def test_returns_false_when_cuda_not_compiled_warning(self, monkeypatch):
        import warnings as w_mod
        original_simplefilter = w_mod.simplefilter
        original_catch = w_mod.catch_warnings

        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()

        cuda_warning = UserWarning("XGBoost is not compiled with CUDA support")

        class FakeCatchWarnings:
            def __init__(self, records):
                self.records = records
            def __enter__(self):
                return self.records
            def __exit__(self, *args):
                return False

        fake_records = [cuda_warning]

        def fake_catch_warnings(record=False):
            return FakeCatchWarnings(fake_records if record else [])

        def fake_simplefilter(*args, **kwargs):
            pass

        monkeypatch.setattr("src.models.trainer.warnings.catch_warnings", fake_catch_warnings)
        monkeypatch.setattr("src.models.trainer.warnings.simplefilter", fake_simplefilter)

        mock_cls = MagicMock()
        mock_cls.return_value.fit.return_value = None
        monkeypatch.setattr("src.models.trainer.xgb.XGBClassifier", mock_cls)

        assert trainer._detect_gpu() is False

    def test_returns_false_when_no_visible_gpu_warning(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()

        gpu_warning = UserWarning("No visible GPU is found, setting device to CPU")

        class FakeCatchWarnings:
            def __init__(self, records):
                self.records = records
            def __enter__(self):
                return self.records
            def __exit__(self, *args):
                return False

        def fake_catch_warnings(record=False):
            return FakeCatchWarnings([gpu_warning] if record else [])

        def fake_simplefilter(*args, **kwargs):
            pass

        monkeypatch.setattr("src.models.trainer.warnings.catch_warnings", fake_catch_warnings)
        monkeypatch.setattr("src.models.trainer.warnings.simplefilter", fake_simplefilter)

        mock_cls = MagicMock()
        mock_cls.return_value.fit.return_value = None
        monkeypatch.setattr("src.models.trainer.xgb.XGBClassifier", mock_cls)

        assert trainer._detect_gpu() is False


class TestRunMode:
    def _setup_trainer_with_combos(self, monkeypatch, use_gpu=False):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        trainer.use_gpu = use_gpu
        trainer._grid_n_jobs = 1 if use_gpu else -1

        combos = [
            ("BTC", "1h", "crypto", "gold_crypto_features"),
            ("ETH", "1h", "crypto", "gold_crypto_features"),
            ("SOL", "1h", "crypto", "gold_crypto_features"),
        ]
        monkeypatch.setattr(trainer, "_build_combos", lambda: combos)
        monkeypatch.setattr(
            trainer, "_needs_training",
            lambda asset, interval, asset_class, table: (True, "stale"),
        )
        return trainer

    def test_sequential_trains_in_order(self, monkeypatch):
        trainer = self._setup_trainer_with_combos(monkeypatch, use_gpu=False)

        call_order = []
        def mock_train(asset, interval, asset_class, table):
            call_order.append(asset)
            return {"asset": asset, "interval": interval, "accuracy": 0.8}
        monkeypatch.setattr(trainer, "_train_one", mock_train)

        trainer.run()

        assert call_order == ["BTC", "ETH", "SOL"]

    def test_gpu_sequential_trains_in_order(self, monkeypatch):
        trainer = self._setup_trainer_with_combos(monkeypatch, use_gpu=True)

        call_order = []
        def mock_train(asset, interval, asset_class, table):
            call_order.append(asset)
            return {"asset": asset, "interval": interval, "accuracy": 0.8}
        monkeypatch.setattr(trainer, "_train_one", mock_train)

        trainer.run()

        assert call_order == ["BTC", "ETH", "SOL"]

    def test_logs_progress_x_of_total(self, monkeypatch):
        trainer = self._setup_trainer_with_combos(monkeypatch, use_gpu=False)
        monkeypatch.setattr(
            trainer, "_train_one",
            lambda *a: {"asset": a[0]},
        )

        trainer.run()

        log_msgs = [str(c) for c in trainer.logger.info.call_args_list]
        progress = [m for m in log_msgs if "Progress:" in m]
        assert len(progress) == 3
        assert "1/3" in progress[0]
        assert "2/3" in progress[1]
        assert "3/3" in progress[2]

    def test_skips_up_to_date(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        trainer.use_gpu = False
        trainer._grid_n_jobs = -1

        combos = [("BTC", "1h", "crypto", "gold_crypto_features")]
        monkeypatch.setattr(trainer, "_build_combos", lambda: combos)
        monkeypatch.setattr(
            trainer, "_needs_training",
            lambda *a: (False, "up_to_date"),
        )
        trained = []
        monkeypatch.setattr(trainer, "_train_one", lambda *a: trained.append(a[0]))

        trainer.run()

        assert len(trained) == 0

    def test_nothing_to_train_returns_early(self, monkeypatch):
        _mock_trainer(monkeypatch)
        trainer = PipelineModelTrainer()
        trainer.use_gpu = False

        combos = [("BTC", "1h", "crypto", "gold_crypto_features")]
        monkeypatch.setattr(trainer, "_build_combos", lambda: combos)
        monkeypatch.setattr(
            trainer, "_needs_training",
            lambda *a: (False, "no_gold_data"),
        )
        monkeypatch.setattr(trainer, "_train_one", lambda *a: None)

        trainer.run()

        log_msgs = [str(c) for c in trainer.logger.info.call_args_list]
        assert any("nothing to train" in m for m in log_msgs)