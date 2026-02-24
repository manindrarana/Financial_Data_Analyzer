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
    
    def fetch_data(self, symbol: str):
        """
        Fetches candlestick data from Bybit.
        """
        print(f"Fetching Bybit data for {symbol}...")
        
        provider_config = self.config["providers"]["bybit"]
        interval = provider_config["interval"]
        category = provider_config["category"]
        limit = provider_config.get("limit", 200)

        start_date_str = self.config["ingestion"]["settings"]["start_date"]
        start_ts = int(datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.now().timestamp() * 1000)
        
        print(f"Time Range: {start_date_str} to Now ({start_ts} to {end_ts})")

        all_data = []
        cursor_end = end_ts 

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
                print(f"No data found for {symbol}")
                return None
            
            columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]
            df = pd.DataFrame(raw_list, columns=columns)
            
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            
            df["date"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="ms")
            
            df = df.sort_values(by="date").reset_index(drop=True)
            
            df = df[["date", "open", "high", "low", "close", "volume"]]

            timestamp_str = datetime.now().strftime("%Y-%m-%d")
            readable_interval = "1h" if interval == "60" else ("1d" if interval == "D" else interval)
            
            filename = f"{symbol}_{readable_interval}_{timestamp_str}.parquet"
            file_path = os.path.join(self.raw_path, filename)
            
            df.to_parquet(file_path, index=False)
            print(f"Success! Saved {len(df)} rows to {file_path}")
            return file_path

        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return None

if __name__ == "__main__":
    client = BybitClient()
    client.fetch_data("BTCUSDT")
