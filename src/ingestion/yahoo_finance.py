import os
import yaml
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf
from src.utils import get_logger

class YahooFinanceClient:
    def __init__(self):
        self.logger = get_logger(__name__)
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.raw_path = self.config["paths"]["raw_data"]
        os.makedirs(self.raw_path, exist_ok=True)

    def fetch_data(self, ticker: str):
        """
        Fetches historical data from Yahoo Finance and saves as Parquet.
        """
        self.logger.info(f"Fetching data for {ticker} using yfinance...")
        
        config_start_date = self.config["ingestion"]["settings"]["start_date"]
        interval = self.config["providers"]["yfinance"]["interval"] 
        
        start_date = config_start_date
        if interval == "1h":
            limit_date = (datetime.now() - timedelta(days=700)).strftime("%Y-%m-%d")
            
            if config_start_date < limit_date:
                self.logger.warning(f"Adjusting start_date for 1h data: {config_start_date} -> {limit_date}")
                start_date = limit_date
        
        try:
            df = yf.download(ticker, start=start_date, interval=interval, progress=False)
            
            if df.empty:
                self.logger.warning(f"No data found for {ticker}")
                return None

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df.reset_index(inplace=True)

            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            
            if 'datetime' in df.columns:
                df.rename(columns={'datetime': 'date'}, inplace=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d")
            
            filename = f"{ticker}_{interval}_{timestamp}.parquet"
            file_path = os.path.join(self.raw_path, filename)
            
            df.to_parquet(file_path, index=False)
            
            self.logger.info(f"Success! Saved {len(df)} rows to {file_path}")
            return file_path

        except Exception as e:
            self.logger.error(f"Failed to fetch {ticker}: {e}")
            return None

if __name__ == "__main__":
    client = YahooFinanceClient()
    client.fetch_data("AAPL")

