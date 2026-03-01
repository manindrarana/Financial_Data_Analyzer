import yaml
import time
from src.utils import get_logger
from src.ingestion.yahoo_finance import YahooFinanceClient
from src.ingestion.bybit_client import BybitClient
from src.database.loader import DatabaseLoader
from src.processing.transformation import DataCleaner


def run_pipeline():