import duckdb
import os
import yaml
from src.utils import get_logger


class DatabaseLoader:
    def __init__(self):
        """Initialize database connection and configuration"""
        self.logger = get_logger(__name__)
        
        with open("configs/settings.yml", "r") as f:
            config = yaml.safe_load(f)
        
        self.db_path = config["paths"]["database"]
        self.raw_path = config["paths"]["raw_data"]
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.conn = duckdb.connect(self.db_path)
        self.logger.info(f"Connected to DuckDB at {self.db_path}")
    
