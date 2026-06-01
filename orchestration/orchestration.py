import yaml
import time
import gc
import json
import sys
from pathlib import Path
from prefect import flow, task, get_run_logger
from src.utils import get_logger
from src.ingestion import YahooFinanceClient, BybitClient
from src.database import DatabaseLoader, DimensionBuilder, FactLoader
from src.processing import DataCleaner
from src.models import GoldLayerProcessor, TechnicalIndicatorProcessor

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


@task(name="extract-data", retries=2, retry_delay_seconds=30)
def extract_data(config: dict) -> dict:
    logger = get_run_logger()
    logger.info("STEP 1: DATA EXTRACTION (APIs -> Parquet)")

    yfinance_targets = config["ingestion"]["targets"].get("yfinance", [])
    bybit_targets = config["ingestion"]["targets"].get("bybit", [])
    active_providers = config["ingestion"]["active_provider"]

    stats = {"yfinance_count": 0, "bybit_count": 0}

    if "yfinance" in active_providers:
        yahoo_client = YahooFinanceClient()
        for ticker in yfinance_targets:
            yahoo_client.fetch_data(ticker)
            stats["yfinance_count"] += 1
            time.sleep(3)
        yahoo_client.close()

    if "bybit" in active_providers:
        bybit_client = BybitClient()
        for symbol in bybit_targets:
            bybit_client.fetch_data(symbol)
            stats["bybit_count"] += 1
            time.sleep(1)
        bybit_client.close()

    logger.info(f"Extraction complete: {stats['yfinance_count']} stocks, {stats['bybit_count']} crypto")
    return stats


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
        ("step1_extract",    lambda: extract_data(config)),
        ("step2_load",       lambda: load_to_duckdb()),
        ("step3_clean",      lambda: transform_clean()),
        ("step4_dimensions", lambda: build_dimensions()),
        ("step5_facts",      lambda: load_facts()),
        ("step6_gold",       lambda: build_gold_layer()),
        ("step7_indicators", lambda: build_technical_indicators()),
    ]

    for step_id, step_fn in steps:
        if _should_run(step_id, FORCE_FLAG):
            logger.info(f"[CHECKPOINT] Running {step_id}...")
            step_fn()
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
    logger.info("Docker container started. Running initial pipeline execution...")
    run_pipeline()

    while True:
        logger.info("Sleeping 3600s until next scheduled run...")
        time.sleep(3600)
        run_pipeline()