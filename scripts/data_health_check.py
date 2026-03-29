import pandas as pd
import duckdb
import yaml
import os
from src.utils import get_logger

logger = get_logger("HealthCheck")


def get_db_connection():
    """Loads config and returns the DuckDB connection."""
    with open("configs/settings.yml", "r") as f:
        config = yaml.safe_load(f)
    
    db_path = config["paths"]["database"]
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}!")
        return None
        
    return duckdb.connect(db_path, read_only=True)
