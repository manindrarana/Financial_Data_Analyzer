import os
import requests
import yaml
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class AlphaVantageClient:
    def __init__(self):
        with open("configs/settings.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY not found in environment variables")
        self.base_url = self.config["providers"]["alpha_vantage"]["base_url"]
        self.raw_data_path = self.config["paths"]["raw_data"]
        os.makedirs(self.raw_data_path, exist_ok=True)
  