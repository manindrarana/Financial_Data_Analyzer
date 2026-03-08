import duckdb
import yaml
import os
from dotenv import load_dotenv
from src.utils import get_logger


class DimensionBuilder:
    """Builds and maintains dimension tables for star schema"""
    