import yaml
import time
import gc
import json
import sys
import os
import duckdb
from pathlib import Path
from prefect import flow, task, get_run_logger
from src.utils import get_logger
from src.ingestion import YahooFinanceClient, BybitClient
from src.database import DatabaseLoader, DimensionBuilder, FactLoader
from src.processing import DataCleaner
from src.models import GoldLayerProcessor, TechnicalIndicatorProcessor, PipelineModelTrainer

CHECKPOINT_FILE = Path("data/.pipeline_checkpoint.json")


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


FORCE_FLAG = "--force" in sys.argv
def _get_db_con():
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    return duckdb.connect(config["paths"]["database"], read_only=True)

def _validate_extract():
    conn = _get_db_con()
    try:
        yahoo_count = conn.execute("SELECT COUNT(*) FROM yahoo_stocks").fetchone()[0]
        if yahoo_count == 0:
            raise RuntimeError("step1_extract failed: yahoo_stocks has 0 rows")
        bybit_count = conn.execute("SELECT COUNT(*) FROM bybit_crypto").fetchone()[0]
        if bybit_count == 0:
            raise RuntimeError("step1_extract failed: bybit_crypto has 0 rows")
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

    stats = {
        "yfinance_count": yahoo_future.result(),
        "bybit_count": bybit_future.result(),
    }

    logger.info(f"Extraction complete: {stats['yfinance_count']} stocks, {stats['bybit_count']} crypto")
    return stats


@flow(name="financial-data-pipeline", log_prints=True)
def run_pipeline():
    logger = get_run_logger()
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

    for step_id, step_fn in steps:
        if _should_run(step_id, FORCE_FLAG):
            logger.info(f"[CHECKPOINT] Running {step_id}...")
            step_fn()
            validator = STEP_VALIDATORS.get(step_id)
            if validator:
                validator()
                logger.info(f"[VALIDATE] {step_id} validation passed")
            _mark_done(step_id)
            logger.info(f"[CHECKPOINT] {step_id} complete — saved")
        else:
            logger.info(f"[CHECKPOINT] Skipping {step_id} (already done)")

    elapsed = time.time() - pipeline_start
    logger.info(f"=== Pipeline executed successfully in {elapsed:.1f}s ===")
    _clear_checkpoint()
    gc.collect()


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