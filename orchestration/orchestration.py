import yaml
import time
from src.utils import get_logger
from src.ingestion.yahoo_finance import YahooFinanceClient
from src.ingestion.bybit_client import BybitClient
from src.database.loader import DatabaseLoader
from src.processing.transformation import DataCleaner


def run_pipeline():
    logger = get_logger("Orchestrator")
    logger.info("Starting Financial Data Pipeline (ELT)...")
    
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
        
    yfinance_targets = config["ingestion"]["targets"].get("yfinance", [])
    bybit_targets = config["ingestion"]["targets"].get("bybit", [])
    active_providers = config["ingestion"]["active_provider"]
    