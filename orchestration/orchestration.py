import yaml
import time
import gc
import json
import sys
import os
import duckdb
from datetime import datetime
from pathlib import Path
from prefect import flow, task, get_run_logger
from src.utils import get_logger
from src.ingestion import YahooFinanceClient, BybitClient, FearGreedClient
from src.database import DatabaseLoader, DimensionBuilder, FactLoader
from src.processing import DataCleaner
from src.models import GoldLayerProcessor, TechnicalIndicatorProcessor, PipelineModelTrainer

CHECKPOINT_FILE = Path("data/.pipeline_checkpoint.json")
LOCK_FILE = Path("data/.pipeline_running.lock")


def _load_checkpoint() -> set:
    if CHECKPOINT_FILE.exists():
        return set(json.loads(CHECKPOINT_FILE.read_text()))
    return set()


def _save_checkpoint(completed: set):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(list(completed)))


def _clear_checkpoint():
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


def _should_run(step: str, force: bool) -> bool:
    if force:
        return True
    return step not in _load_checkpoint()


def _mark_done(step: str):
    completed = _load_checkpoint()
    completed.add(step)
    _save_checkpoint(completed)


def _get_db_path() -> str:
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    return config["paths"]["database"]


def _init_pipeline_runs_table():
    db_path = _get_db_path()
    parent = os.path.dirname(db_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    conn = duckdb.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
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
    finally:
        conn.close()


def _start_pipeline_run() -> str:
    _init_pipeline_runs_table()
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    trigger = "manual"
    if "--once" in sys.argv or "--now" in sys.argv:
        trigger = "--once"
    elif not FORCE_FLAG:
        trigger = "cron"
    checkpoint_resumed = bool(_load_checkpoint())
    conn = duckdb.connect(_get_db_path())
    try:
        conn.execute(
            """
            INSERT INTO pipeline_runs
                (run_id, start_time, end_time, duration_seconds, status,
                 trigger, error_message, models_retrained, rows_fetched,
                 rows_cleaned, validator_failures, checkpoint_resumed)
            VALUES (?, NULL, NULL, NULL, 'running', ?, NULL, NULL, NULL, NULL, NULL, ?)
            """,
            [run_id, trigger, checkpoint_resumed],
        )
    finally:
        conn.close()
    return run_id


def _end_pipeline_run(run_id, status, error_message, stats, run_start):
    end_time = datetime.now()
    duration = time.time() - run_start
    models = stats.get("models_retrained") or []
    models_str = ",".join(models) if models else None
    conn = duckdb.connect(_get_db_path())
    try:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET end_time = ?, duration_seconds = ?, status = ?,
                error_message = ?, models_retrained = ?, rows_fetched = ?,
                rows_cleaned = ?, validator_failures = ?
            WHERE run_id = ?
            """,
            [
                end_time, duration, status, error_message, models_str,
                stats.get("rows_fetched"), stats.get("rows_cleaned"),
                stats.get("validator_failures", 0), run_id,
            ],
        )
    finally:
        conn.close()


def _count_rows(table_names):
    conn = _get_db_con()
    try:
        total = 0
        for t in table_names:
            try:
                total += conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                pass
        return total
    finally:
        conn.close()


FORCE_FLAG = "--force" in sys.argv
def _get_db_con():
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    return duckdb.connect(config["paths"]["database"], read_only=True)

def _validate_extract():
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    db_path = config["paths"]["database"]
    if not os.path.exists(db_path):
        logger = get_logger("Validator")
        logger.info("Skipping extract validation: DuckDB does not exist yet (first run). Data is in MinIO, DB will be created in step2_load.")
        return
    conn = _get_db_con()
    try:
        yahoo_count = conn.execute("SELECT COUNT(*) FROM yahoo_stocks").fetchone()[0]
        if yahoo_count == 0:
            raise RuntimeError("step1_extract failed: yahoo_stocks has 0 rows")
        bybit_count = conn.execute("SELECT COUNT(*) FROM bybit_crypto").fetchone()[0]
        if bybit_count == 0:
            raise RuntimeError("step1_extract failed: bybit_crypto has 0 rows")
        try:
            fg_count = conn.execute("SELECT COUNT(*) FROM fear_greed").fetchone()[0]
            if fg_count == 0:
                raise RuntimeError("step1_extract failed: fear_greed has 0 rows")
        except Exception as e:
            if "does not exist" in str(e).lower():
                pass
            else:
                raise
        return yahoo_count, bybit_count
    finally:
        conn.close()

def _validate_clean():
    conn = _get_db_con()
    try:
        for table in ["clean_yahoo_stocks", "clean_bybit_crypto"]:
            null_count = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE close IS NULL"
            ).fetchone()[0]
            if null_count > 0:
                raise RuntimeError(f"step3_clean failed: {table} has {null_count} nulls in close")
        fg_null_count = conn.execute("SELECT COUNT(*) FROM clean_fear_greed WHERE value IS NULL").fetchone()[0]
        if fg_null_count > 0:
            raise RuntimeError(f"step3_clean failed: clean_fear_greed has {fg_null_count} nulls in value")
    finally:
        conn.close()

def _validate_dimensions():
    conn = _get_db_con()
    try:
        dim_count = conn.execute("SELECT COUNT(*) FROM dim_assets").fetchone()[0]
        if dim_count == 0:
            raise RuntimeError("step4_dimensions failed: dim_assets has 0 rows")
    finally:
        conn.close()


def _validate_facts():
    conn = _get_db_con()
    try:
        fact_count = conn.execute("SELECT COUNT(*) FROM fact_price_history").fetchone()[0]
        if fact_count == 0:
            raise RuntimeError("step5_facts failed: fact_price_history has 0 rows")
    finally:
        conn.close()
        

_GOLD_ANALYTICS_COLS = [
    "asset_symbol", "asset_class", "exchange", "interval", "date",
    "open", "high", "low", "close", "volume",
    "daily_volatility", "sma_7", "sma_30",
]

_FEATURE_INDICATOR_COLS = [
    "close", "rsi_14", "macd", "macd_signal", "macd_histogram",
    "roc_10", "roc_20", "stoch_k", "stoch_d",
    "ema_12", "ema_26", "ema_50", "ema_200",
    "sma_50", "sma_100", "sma_200",
    "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_percentage",
    "atr_14", "obv", "vwap", "volume_sma_20", "volume_ratio",
    "returns_1p", "returns_5p", "returns_10p", "returns_20p",
    "log_returns", "hl_ratio", "close_position",
]


def _validate_gold():
    conn = _get_db_con()
    try:
        for table in ["gold_crypto_analytics", "gold_stock_analytics"]:
            try:
                existing = [
                    r[0] for r in conn.execute(
                        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
                    ).fetchall()
                ]
            except Exception:
                raise RuntimeError(f"step6_gold failed: {table} does not exist")
            missing = [c for c in _GOLD_ANALYTICS_COLS if c not in existing]
            if missing:
                raise RuntimeError(f"step6_gold failed: {table} missing columns: {missing}")
    finally:
        conn.close()


def _validate_features():
    conn = _get_db_con()
    try:
        for table in ["gold_crypto_features", "gold_stock_features"]:
            try:
                existing = [
                    r[0] for r in conn.execute(
                        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
                    ).fetchall()
                ]
            except Exception:
                raise RuntimeError(f"step7_indicators failed: {table} does not exist")
            missing = [c for c in _FEATURE_INDICATOR_COLS if c not in existing]
            if missing:
                raise RuntimeError(f"step7_indicators failed: {table} missing columns: {missing}")
            null_count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE close IS NULL").fetchone()[0]
            if null_count > 0:
                raise RuntimeError(f"step7_indicators failed: {table} has {null_count} nulls in close")
    finally:
        conn.close()
        
        
def _validate_train():
    models_dir = os.path.join("/app", "model_store")
    if not os.path.exists(models_dir):
        raise RuntimeError("step8_models failed: model_store/ directory does not exist")
    json_files = []
    for _root, _dirs, files in os.walk(models_dir):
        json_files = [f for f in files if f.endswith(".json")]
        if json_files:
            break
    if not json_files:
        raise RuntimeError("step8_models failed: no model JSON files found in model_store/")


STEP_VALIDATORS = {
    "step1_extract": _validate_extract,
    "step2_load": None,
    "step3_clean": _validate_clean,
    "step4_dimensions": _validate_dimensions,
    "step5_facts": _validate_facts,
    "step6_gold": _validate_gold,
    "step7_indicators": _validate_features,
    "step8_models": _validate_train,
}

@task(name="extract-yahoo", retries=2, retry_delay_seconds=30)
def extract_yahoo(config: dict) -> int:
    logger = get_run_logger()
    logger.info("EXTRACT: Yahoo Finance (stocks)")

    yfinance_targets = config["ingestion"]["targets"].get("yfinance", [])

    if "yfinance" not in config["ingestion"]["active_provider"]:
        logger.info("Yahoo Finance provider not active, skipping")
        return 0

    client = YahooFinanceClient()
    count = 0
    for ticker in yfinance_targets:
        client.fetch_data(ticker)
        count += 1
        time.sleep(3)
    client.close()

    logger.info(f"Yahoo extraction complete: {count} stocks")
    return count


@task(name="extract-bybit", retries=2, retry_delay_seconds=30)
def extract_bybit(config: dict) -> int:
    logger = get_run_logger()
    logger.info("EXTRACT: Bybit (crypto)")

    bybit_targets = config["ingestion"]["targets"].get("bybit", [])

    if "bybit" not in config["ingestion"]["active_provider"]:
        logger.info("Bybit provider not active, skipping")
        return 0

    client = BybitClient()
    count = 0
    for symbol in bybit_targets:
        client.fetch_data(symbol)
        count += 1
        time.sleep(1)
    client.close()

    logger.info(f"Bybit extraction complete: {count} crypto")
    return count


@task(name="extract-fear-greed", retries=2, retry_delay_seconds=30)
def extract_fear_greed(config: dict) -> int:
    logger = get_run_logger()
    logger.info("EXTRACT: Fear & Greed Index (crypto sentiment)")

    if "bybit" not in config["ingestion"]["active_provider"]:
        logger.info("Crypto not active, skipping Fear & Greed extraction")
        return 0

    client = FearGreedClient()
    client.fetch_data()
    client.close()

    logger.info("Fear & Greed extraction complete")
    return 1


@task(name="load-to-duckdb", retries=1, retry_delay_seconds=15)
def load_to_duckdb():
    logger = get_run_logger()
    logger.info("STEP 2: LOADING (Parquet -> DuckDB)")
    loader = DatabaseLoader()
    loader.load_all()
    loader.close()


@task(name="transform-clean")
def transform_clean():
    logger = get_run_logger()
    logger.info("STEP 3: TRANSFORMATION (Cleaning and Ordering)")
    cleaner = DataCleaner()
    cleaner.run()
    cleaner.close()


@task(name="build-dimensions")
def build_dimensions():
    logger = get_run_logger()
    logger.info("STEP 4: DIMENSIONAL MODELING (Building Star Schema)")
    dim_builder = DimensionBuilder()
    dim_builder.run()
    dim_builder.close()


@task(name="load-facts")
def load_facts():
    logger = get_run_logger()
    logger.info("STEP 5: FACT LOADING (Silver -> Fact Tables)")
    fact_loader = FactLoader()
    fact_loader.run()
    fact_loader.close()


@task(name="build-gold-layer")
def build_gold_layer():
    logger = get_run_logger()
    logger.info("STEP 6: ANALYTICS (Building Gold Layer)")
    gold_processor = GoldLayerProcessor()
    gold_processor.run()
    gold_processor.close()


@task(name="build-technical-indicators")
def build_technical_indicators():
    logger = get_run_logger()
    logger.info("STEP 7: TECHNICAL INDICATORS")
    indicator_processor = TechnicalIndicatorProcessor()
    indicator_processor.run()
    indicator_processor.close()


@task(name="train-models", retries=1, retry_delay_seconds=30)
def train_models():
    logger = get_run_logger()
    logger.info("STEP 8: MODEL TRAINING (Auto-retrain on new data)")
    trainer = PipelineModelTrainer()
    trainer.run()
    trainer.close()


def _run_concurrent_extract(config: dict) -> dict:
    logger = get_logger("Extract")
    logger.info("STEP 1: DATA EXTRACTION (APIs -> Parquet) — running Yahoo + Bybit concurrently")

    yahoo_future = extract_yahoo.submit(config)
    bybit_future = extract_bybit.submit(config)
    fg_future = extract_fear_greed.submit(config)

    stats = {
        "yfinance_count": yahoo_future.result(),
        "bybit_count": bybit_future.result(),
        "fear_greed_count": fg_future.result(),
    }

    logger.info(f"Extraction complete: {stats['yfinance_count']} stocks, {stats['bybit_count']} crypto, {stats['fear_greed_count']} sentiment")
    return stats


@flow(name="financial-data-pipeline", log_prints=True)
def run_pipeline():
    logger = get_run_logger()

    if LOCK_FILE.exists():
        try:
            existing_pid = int(LOCK_FILE.read_text().strip())
            os.kill(existing_pid, 0)
            logger.warning(f"Another pipeline run is active (PID {existing_pid}). Exiting.")
            return
        except (ValueError, ProcessLookupError, OSError):
            logger.info("Stale lock file found — removing and acquiring lock")

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))

    run_id = _start_pipeline_run()
    run_start = time.time()
    try:
        stats = _run_pipeline_impl(logger, run_id)
        _end_pipeline_run(run_id, "success", None, stats, run_start)
    except Exception as e:
        logger.exception("Pipeline failed — marking run as failed in pipeline_runs")
        _end_pipeline_run(
            run_id, "failed", str(e)[:500],
            {"models_retrained": [], "rows_fetched": None, "rows_cleaned": None,
             "validator_failures": 0},
            run_start,
        )
        raise
    finally:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()


def _run_pipeline_impl(logger, run_id):
    logger.info("=== Financial Data Pipeline (ELT) Starting ===")
    pipeline_start = time.time()

    if FORCE_FLAG:
        _clear_checkpoint()
        logger.info("--force detected: cleared checkpoint, running all steps")

    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)

    steps = [
        ("step1_extract",    lambda: _run_concurrent_extract(config)),
        ("step2_load",       lambda: load_to_duckdb()),
        ("step3_clean",      lambda: transform_clean()),
        ("step4_dimensions", lambda: build_dimensions()),
        ("step5_facts",      lambda: load_facts()),
        ("step6_gold",       lambda: build_gold_layer()),
        ("step7_indicators", lambda: build_technical_indicators()),
        ("step8_models",     lambda: train_models()),
    ]

    validator_failures = 0
    for step_id, step_fn in steps:
        if _should_run(step_id, FORCE_FLAG):
            logger.info(f"[CHECKPOINT] Running {step_id}...")
            step_fn()
            validator = STEP_VALIDATORS.get(step_id)
            if validator:
                try:
                    validator()
                    logger.info(f"[VALIDATE] {step_id} validation passed")
                except Exception as e:
                    validator_failures += 1
                    logger.error(f"[VALIDATE] {step_id} validation FAILED: {e}")
                    raise
            _mark_done(step_id)
            logger.info(f"[CHECKPOINT] {step_id} complete — saved")
        else:
            logger.info(f"[CHECKPOINT] Skipping {step_id} (already done)")

    rows_fetched = _count_rows(["yahoo_stocks", "bybit_crypto", "fear_greed"])
    rows_cleaned = _count_rows(["clean_yahoo_stocks", "clean_bybit_crypto", "clean_fear_greed"])
    models_retrained = _collect_retrained_models(config)

    elapsed = time.time() - pipeline_start
    logger.info(f"=== Pipeline executed successfully in {elapsed:.1f}s ===")
    _clear_checkpoint()
    gc.collect()

    return {
        "models_retrained": models_retrained,
        "rows_fetched": rows_fetched,
        "rows_cleaned": rows_cleaned,
        "validator_failures": validator_failures,
    }


def _collect_retrained_models(config) -> list:
    try:
        from src.models.trainer import PipelineModelTrainer
        trainer = PipelineModelTrainer()
        retrained = trainer.last_retrained_models if hasattr(trainer, "last_retrained_models") else []
        return list(retrained)
    except Exception:
        return []


if __name__ == "__main__":
    logger = get_logger("Orchestrator_Main")

    if "--once" in sys.argv or "--now" in sys.argv:
        logger.info("Running single pipeline execution (--once)...")
        run_pipeline()
    else:
        logger.info("Starting Prefect deployment — hourly schedule via Prefect server")
        run_pipeline.serve(
            name="financial-data-pipeline",
            cron="0 * * * *",
            description="Hourly ELT pipeline ingesting stock & crypto data, building gold layer, and retraining models",
        )