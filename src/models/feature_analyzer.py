import duckdb
import yaml
import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from src.utils import get_logger
from sklearn.ensemble import RandomForestRegressor


class FeatureAnalyzer:
    """Analyzes gold_ml_features quality and selects best indicators for ML"""
    