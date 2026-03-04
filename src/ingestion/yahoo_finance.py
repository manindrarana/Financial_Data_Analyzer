import os
import yaml
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf
from src.utils import get_logger
import duckdb


class YahooFinanceClient:
    def __init__(self):
        self.logger = get_logger(__name__)
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.raw_path = self.config["paths"]["raw_data"]
        os.makedirs(self.raw_path, exist_ok=True)

    def get_last_fetched_date(self, ticker: str, interval: str):
        """Query DuckDB for the latest date of fetched data for the given ticker and interval."""
        db_path = self.config["paths"]["database"]
        if not os.path.exists(db_path):
            return None
        
        try:
            conn = duckdb.connect(db_path, read_only=True)
            query = f"SELECT MAX(date) FROM clean_yahoo_stocks WHERE ticker='{ticker}' AND interval='{interval}'"
            res = conn.execute(query).fetchone()
            conn.close()
            return res[0] if res and res[0] else None
        except Exception:
            return None

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
            
            df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_localize(None)
            
            timestamp = datetime.now().strftime("%Y-%m-%d")
            
            filename = f"{ticker}_{interval}_{timestamp}.parquet"
            s3_bucket = self.config["paths"].get("s3_bucket", "raw-data")
            file_path = f"s3://{s3_bucket}/{filename}"
            
            s3_storage_options = {
                "client_kwargs": {"endpoint_url": os.getenv("S3_ENDPOINT_URL")},
                "key": os.getenv("AWS_ACCESS_KEY_ID"),
                "secret": os.getenv("AWS_SECRET_ACCESS_KEY")
            }
            
            df.to_parquet(file_path, index=False, storage_options=s3_storage_options)
            
            self.logger.info(f"Success! Saved {len(df)} rows to {file_path}")
            return file_path

        except Exception as e:
            self.logger.error(f"Failed to fetch {ticker}: {e}")
            return None

if __name__ == "__main__":
    client = YahooFinanceClient()
    client.fetch_data("AAPL")

