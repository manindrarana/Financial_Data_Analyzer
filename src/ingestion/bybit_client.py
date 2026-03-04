import os
import yaml
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
import time 
from src.utils import get_logger
import duckdb

class BybitClient:
    def __init__(self):
        self.logger = get_logger(__name__)
        
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
        
    def get_last_fetched_date(self, symbol: str, interval: str):
        """Query DuckDB for the latest date of fetched data for the given symbol and interval."""
        db_path = self.config["paths"]["database"]
        if not os.path.exists(db_path):
            return None
            
        try:
            import duckdb
            conn = duckdb.connect(db_path, read_only=True)
            readable_interval = "1h" if interval == "60" else ("1d" if interval == "D" else interval)
            query = f"SELECT MAX(date) FROM clean_bybit_crypto WHERE symbol='{symbol}' AND interval='{readable_interval}'"
            res = conn.execute(query).fetchone()
            conn.close()
            return res[0] if res and res[0] else None
        except Exception:
            return None
    
    def fetch_data(self, symbol: str):
        """
        Fetches candlestick data from Bybit.
        """
        self.logger.info(f"Fetching Bybit data for {symbol}...")
        
        provider_config = self.config["providers"]["bybit"]
        interval = provider_config["interval"]
        category = provider_config["category"]
        limit = provider_config.get("limit", 1000)

        start_date_str = self.config["ingestion"]["settings"]["start_date"]
        start_ts = int(datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.now().timestamp() * 1000)
        
        last_date = self.get_last_fetched_date(symbol, interval)
        if last_date:
            start_ts = int(last_date.timestamp() * 1000)
            self.logger.info(f"Incremental load: Found existing data. Resuming fetches from {last_date} to Now.")
        else:
            self.logger.info(f"Full Refresh: No existing data. Strategy: Fetching backwards from Now to {start_date_str}")

        self.logger.info(f"Time Range: {datetime.fromtimestamp(start_ts/1000)} to Now ({start_ts} to {end_ts})")

        all_data = []
        cursor_end = end_ts 
        
        while cursor_end > start_ts:
            try:
                response = self.session.get_kline(
                    category=category,
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    end=cursor_end
                )
                
                raw_list = response.get('result', {}).get('list', [])
                
                if not raw_list:
                    self.logger.info("No more data returned from API.")
                    break
                
                columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]
                batch_df = pd.DataFrame(raw_list, columns=columns)
                batch_df["timestamp"] = batch_df["timestamp"].astype(int)
                
                batch_df = batch_df[batch_df["timestamp"] >= start_ts]
                
                if batch_df.empty:
                    self.logger.info("Reached start date boundary.")
                    break
                
                all_data.append(batch_df)
                
                min_ts = batch_df["timestamp"].min()
                cursor_end = min_ts - 1
                
                self.logger.info(f"Fetched {len(batch_df)} rows. Oldest in batch: {datetime.fromtimestamp(min_ts/1000)}")
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error in loop: {e}")
                break

        if not all_data:
             self.logger.warning(f"No new data found for {symbol}")
             return None

        df = pd.concat(all_data)
        df.drop_duplicates(subset=["timestamp"], inplace=True)
            
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
            
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        
        df = df.sort_values(by="date").reset_index(drop=True)
        
        df = df[["date", "open", "high", "low", "close", "volume"]]

        readable_interval = "1h" if interval == "60" else ("1d" if interval == "D" else interval)
        
        filename = f"{symbol}_{readable_interval}.parquet"
        s3_bucket = self.config["paths"].get("s3_bucket", "raw-data")
        file_path = f"s3://{s3_bucket}/{filename}"
        
        s3_storage_options = {
            "client_kwargs": {"endpoint_url": os.getenv("S3_ENDPOINT_URL")},
            "key": os.getenv("AWS_ACCESS_KEY_ID"),
            "secret": os.getenv("AWS_SECRET_ACCESS_KEY")
        }
        
        try:
            existing_df = pd.read_parquet(file_path, storage_options=s3_storage_options)
            self.logger.info(f"Found existing {filename} ({len(existing_df)} rows). Merging...")
            df = pd.concat([existing_df, df])
            df.drop_duplicates(subset=['date'], keep='last', inplace=True)
            df.sort_values(by='date', inplace=True)
            df.reset_index(drop=True, inplace=True)
        except Exception:
            self.logger.info(f"No existing file for {filename}, creating a new one.")
        
        df.to_parquet(file_path, index=False, storage_options=s3_storage_options)
        self.logger.info(f"Success! Saved total {len(df)} rows to {file_path}")
        return file_path

if __name__ == "__main__":
    client = BybitClient()
    client.fetch_data("BTCUSDT")
