import yaml
import time
from src.utils import get_logger
from src.ingestion.yahoo_finance import YahooFinanceClient
from src.ingestion.bybit_client import BybitClient
from src.database.loader import DatabaseLoader
from src.processing.transformation import DataCleaner
import schedule



def run_pipeline():
    logger = get_logger("Orchestrator")
    logger.info("Starting Financial Data Pipeline (ELT)...")
    
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
        
    yfinance_targets = config["ingestion"]["targets"].get("yfinance", [])
    bybit_targets = config["ingestion"]["targets"].get("bybit", [])
    active_providers = config["ingestion"]["active_provider"]
    
    logger.info("*** STEP 1: DATA EXTRACTION (APIs ..> Parquet) ***")
    
    if "yfinance" in active_providers:
        yahoo_client = YahooFinanceClient()
        for ticker in yfinance_targets:
            yahoo_client.fetch_data(ticker)
            time.sleep(15)
            
    if "bybit" in active_providers:
        bybit_client = BybitClient()
        for symbol in bybit_targets:
            bybit_client.fetch_data(symbol)
            time.sleep(1)

    logger.info("*** STEP 2: LOADING (Parquet ..> DuckDB) ***")
    loader = DatabaseLoader()
    loader.load_all()
    loader.close()
    
    logger.info("*** STEP 3: TRANSFORMATION (Cleaning and Ordering) ***")
    cleaner = DataCleaner()
    cleaner.run()
    cleaner.conn.close()
    
    logger.info("*** PIPELINE EXECUTED SUCCESSFULLY!!!! ***")

if __name__ == "__main__":
    
    logger = get_logger("Orchestrator_Main")
    
    run_pipeline()
    schedule.every().day.at("00:00").do(run_pipeline)
    
    logger.info("Pipeline scheduled container will now stay alive and wait for the next run...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)