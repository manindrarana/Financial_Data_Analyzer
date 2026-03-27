import yaml
import time
import gc
import traceback
from src.utils import get_logger
from src.ingestion import YahooFinanceClient, BybitClient
from src.database import DatabaseLoader, DimensionBuilder, FactLoader
from src.processing import DataCleaner
import schedule
from src.models import GoldLayerProcessor, TechnicalIndicatorProcessor, FeatureAnalyzer

def run_pipeline():
    logger = get_logger("Orchestrator")
    logger.info("Starting Financial Data Pipeline (ELT)...")
    
    pipeline_start = time.time()

    try:
        with open("configs/settings.yml", "r") as f:
            config = yaml.safe_load(f)
            
        yfinance_targets = config["ingestion"]["targets"].get("yfinance", [])
        bybit_targets = config["ingestion"]["targets"].get("bybit", [])
        active_providers = config["ingestion"]["active_provider"]
        
        logger.info("*** STEP 1: DATA EXTRACTION (APIs ..> Parquet) ***")
        step_start = time.time()
        
        if "yfinance" in active_providers:
            yahoo_client = YahooFinanceClient()
            for ticker in yfinance_targets:
                yahoo_client.fetch_data(ticker)
                time.sleep(3)
            yahoo_client.close()
                
        if "bybit" in active_providers:
            bybit_client = BybitClient()
            for symbol in bybit_targets:
                bybit_client.fetch_data(symbol)
                time.sleep(1)
            bybit_client.close()

        logger.info(f"Step 1 completed in {time.time() - step_start:.1f}s")

        logger.info("*** STEP 2: LOADING (Parquet ..> DuckDB) ***")
        step_start = time.time()
        loader = DatabaseLoader()
        loader.load_all()
        loader.close()
        logger.info(f"Step 2 completed in {time.time() - step_start:.1f}s")
        
        logger.info("*** STEP 3: TRANSFORMATION (Cleaning and Ordering) ***")
        step_start = time.time()
        cleaner = DataCleaner()
        cleaner.run()
        cleaner.close()
        logger.info(f"Step 3 completed in {time.time() - step_start:.1f}s")
        
        logger.info("*** STEP 4: DIMENSIONAL MODELING (Building Dimensions) ***")
        step_start = time.time()
        dim_builder = DimensionBuilder()
        dim_builder.run()
        dim_builder.close()
        logger.info(f"Step 4 completed in {time.time() - step_start:.1f}s")
        
        logger.info("*** STEP 5: FACT LOADING (Silver ..> Fact Tables) ***")
        step_start = time.time()
        fact_loader = FactLoader()
        fact_loader.run()
        fact_loader.close()
        logger.info(f"Step 5 completed in {time.time() - step_start:.1f}s")
        
        logger.info("*** STEP 6: ANALYTICS (Building Gold Layer) ***")
        step_start = time.time()
        gold_processor = GoldLayerProcessor()
        gold_processor.run()
        gold_processor.close()
        logger.info(f"Step 6 completed in {time.time() - step_start:.1f}s")
        
        logger.info("*** STEP 7: TECHNICAL INDICATORS (Building Technical Indicators) ***")
        step_start = time.time()
        indicator_processor = TechnicalIndicatorProcessor()
        indicator_processor.run()
        indicator_processor.close()
        logger.info(f"Step 7 completed in {time.time() - step_start:.1f}s")
        
        logger.info("*** STEP 8: FEATURE VALIDATION (Analyzing ML Feature Quality) ***")
        step_start = time.time()
        feature_analyzer = FeatureAnalyzer()
        feature_analyzer.run()
        feature_analyzer.close()
        logger.info(f"Step 8 completed in {time.time() - step_start:.1f}s")
        
        logger.info("*** PIPELINE EXECUTED SUCCESSFULLY!!!! ***")
        logger.info(f"Total pipeline runtime: {time.time() - pipeline_start:.1f}s")
        logger.info("Pipeline completed. Next run scheduled in 1 hour.")

    except Exception as e:
        logger.error(f"PIPELINE CRASHED during execution! Error: {e}")
        logger.error(traceback.format_exc())
        
    finally:
        gc.collect()


if __name__ == "__main__":
    
    logger = get_logger("Orchestrator_Main")
    
    logger.info("Docker container started. Running initial pipeline execution...")
    run_pipeline()
    
    schedule.every(1).hours.do(run_pipeline)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
        