import duckdb
import yaml
from src.utils import get_logger

class DataCleaner:
    def __init__(self):
        self.logger = get_logger(__name__)
        with open("configs/settings.yml", "r") as f:
            cfg = yaml.safe_load(f)
        self.db_path = cfg["paths"]["database"]
        self.conn = duckdb.connect(self.db_path)
        self.logger.info(f"Connected to DuckDB at {self.db_path}")