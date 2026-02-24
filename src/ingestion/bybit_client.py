import os
import yaml
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

class BybitClient:
    def __init__(self):
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.raw_path = self.config["paths"]["raw_data"]
        os.makedirs(self.raw_path, exist_ok=True)
        
        load_dotenv()
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
        
        self.session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret
        )