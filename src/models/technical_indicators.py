import duckdb
import yaml
import os
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from src.utils import get_logger


class TechnicalIndicatorProcessor:
    """Calculates technical indicators for ML feature engineering"""
    