import os
import yaml
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
import time 
from src.utils import get_logger

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
    
    def fetch_data(self, symbol: str):
        """
        Fetches candlestick data from Bybit.
        """
        self.logger.info(f"Fetching Bybit data for {symbol}...")
        
        provider_config = self.config["providers"]["bybit"]
        interval = provider_config["interval"]
        category = provider_config["category"]
        limit = provider_config.get("limit", 200)

        start_date_str = self.config["ingestion"]["settings"]["start_date"]
        start_ts = int(datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.now().timestamp() * 1000)
        
        self.logger.info(f"Time Range: {start_date_str} to Now ({start_ts} to {end_ts})")

        all_data = []
        cursor_end = end_ts 
        self.logger.info(f"Strategy: Fetching backwards from Now to {start_date_str}")
        
        
        while cursor_end > start_ts:
            try:
                response = self.session.get_kline(
                    category=category,
                    symbol=symbol,
                    interval=interval,
                    limit=1000,
                    end=cursor_end
                )
                
                raw_list = response.get('result', {}).get('list', [])
                
                if not raw_list:
                    self.logger.info("No more data returned.")
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
                
                self.logger.info(f"Fetched {len(batch_df)} rows. Oldest: {datetime.fromtimestamp(min_ts/1000)}")
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error in loop: {e}")
                break

        if not all_data:
             self.logger.warning(f"No data found for {symbol}")
             return None

        df = pd.concat(all_data)
        df.drop_duplicates(subset=["timestamp"], inplace=True)
            
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
            
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        
        df = df.sort_values(by="date").reset_index(drop=True)
        
        df = df[["date", "open", "high", "low", "close", "volume"]]

        timestamp_str = datetime.now().strftime("%Y-%m-%d")
        readable_interval = "1h" if interval == "60" else ("1d" if interval == "D" else interval)
        
        filename = f"{symbol}_{readable_interval}_{timestamp_str}.parquet"
        file_path = os.path.join(self.raw_path, filename)
        
        df.to_parquet(file_path, index=False)
        self.logger.info(f"Success! Saved total {len(df)} rows covering {df['date'].min()} to {df['date'].max()}")
        return file_path

if __name__ == "__main__":
    client = BybitClient()
    client.fetch_data("BTCUSDT")
