import os
import yaml
import requests
import pandas as pd
from dotenv import load_dotenv
from src.utils import get_logger

API_URL = "https://api.alternative.me/fng/?limit=0&format=json"


class FearGreedClient:
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()

        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)

        self.raw_path = self.config["paths"]["raw_data"]
        os.makedirs(self.raw_path, exist_ok=True)

    def fetch_data(self):
        self.logger.info("Fetching Fear & Greed Index from alternative.me...")

        try:
            response = requests.get(API_URL, timeout=30)
            response.raise_for_status()
            data = response.json().get("data", [])
        except Exception as e:
            self.logger.error(f"FATAL: Error fetching Fear & Greed Index: {e}")
            raise

        if not data:
            self.logger.warning("No Fear & Greed data returned from API")
            return False

        df = pd.DataFrame(data)
        df["value"] = df["value"].astype(int)
        df["timestamp"] = df["timestamp"].astype(int)
        df["date"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.rename(columns={"value_classification": "classification"})
        df = df[["date", "value", "classification"]]
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        df.reset_index(drop=True, inplace=True)

        self.logger.info(
            f"Fetched {len(df)} Fear & Greed data points "
            f"(from {df['date'].min().date()} to {df['date'].max().date()})"
        )

        s3_bucket = self.config["paths"].get("s3_bucket", "raw-data")
        file_path = f"s3://{s3_bucket}/fear_greed.parquet"

        s3_storage_options = {
            "client_kwargs": {"endpoint_url": os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")},
            "key": os.getenv("AWS_ACCESS_KEY_ID"),
            "secret": os.getenv("AWS_SECRET_ACCESS_KEY")
        }

        try:
            existing_df = pd.read_parquet(file_path, storage_options=s3_storage_options)
            self.logger.info(f"Found existing fear_greed.parquet ({len(existing_df)} rows). Merging...")
            df = pd.concat([existing_df, df])
            df.drop_duplicates(subset=["date"], keep="last", inplace=True)
            df.sort_values(by="date", inplace=True)
            df.reset_index(drop=True, inplace=True)
        except Exception:
            self.logger.info("No existing fear_greed.parquet, creating a new one.")

        df.to_parquet(file_path, index=False, storage_options=s3_storage_options)
        self.logger.info(f"Success! Saved total {len(df)} rows to {file_path}")

        return True

    def close(self):
        pass


if __name__ == "__main__":
    client = FearGreedClient()
    client.fetch_data()
    client.close()
