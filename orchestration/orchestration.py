import yaml
import time
import gc
from src.utils import get_logger
from src.ingestion.yahoo_finance import YahooFinanceClient
from src.ingestion.bybit_client import BybitClient
from src.database.loader import DatabaseLoader
from src.processing.transformation import DataCleaner
import schedule
from src.models.logics import GoldLayerProcessor
from src.database.dimensions import DimensionBuilder
from src.database.facts import FactLoader
from src.models.technical_indicators import TechnicalIndicatorProcessor
from src.models.feature_analyzer import FeatureAnalyzer

def run_pipeline():
    logger = get_logger("Orchestrator")
    logger.info("Starting Financial Data Pipeline (ELT)...")
    
    try:
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
        
        logger.info("*** STEP 4: DIMENSIONAL MODELING (Building Dimensions) ***")
        dim_builder = DimensionBuilder()
        dim_builder.run()
        dim_builder.close()
        
        logger.info("*** STEP 5: FACT LOADING (Silver ..> Fact Tables) ***")
        fact_loader = FactLoader()
        fact_loader.run()
        fact_loader.close()
        
        logger.info("*** STEP 6: ANALYTICS (Building Gold Layer) ***")
        gold_processor = GoldLayerProcessor()
        gold_processor.run()
        gold_processor.conn.close()
        
        logger.info("*** STEP 7: TECHNICAL INDICATORS (Building Technical Indicators) ***")
        indicator_processor = TechnicalIndicatorProcessor()
        indicator_processor.run()
        indicator_processor.conn.close()
        
        logger.info("*** STEP 8: FEATURE VALIDATION (Analyzing ML Feature Quality) ***")
        feature_analyzer = FeatureAnalyzer()
        feature_analyzer.run()
        feature_analyzer.close()
        
        logger.info("*** PIPELINE EXECUTED SUCCESSFULLY!!!! ***")
        logger.info("Pipeline going to sleep for exactly 1 hour...")
        
    except Exception as e:
        logger.error(f"PIPELINE CRASHED during execution! Error: {e}")
        
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