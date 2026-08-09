import os
import yaml
import time
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
import requests
from src.utils import get_logger
import duckdb
from pyrate_limiter import Duration, RequestRate, Limiter
from requests_cache import CacheMixin, SQLiteCache
from requests_ratelimiter import LimiterSession
import random


class YahooFinanceClient:
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.raw_path = self.config["paths"]["raw_data"]
        os.makedirs(self.raw_path, exist_ok=True)
        yahoo_config = self.config["providers"]["yfinance"]
        self.requests_per_second = yahoo_config.get("requests_per_second", 2)
        self.max_retries = yahoo_config.get("max_retries", 2)
        self.retry_base_seconds = yahoo_config.get("retry_base_seconds", 2)
        self.retry_jitter_seconds = yahoo_config.get("retry_jitter_seconds", 1)
        self.error_retry_seconds = yahoo_config.get("error_retry_seconds", 5)
        self.session = LimiterSession(per_second=self.requests_per_second)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self._rate_limited = False

    def get_last_fetched_date(self, ticker: str, interval: str):
        """Query DuckDB for the latest date of fetched data for the given ticker and interval."""
        db_path = self.config["paths"]["database"]
        if not os.path.exists(db_path):
            return None
        
        conn = None
        try:
            conn = duckdb.connect(db_path, read_only=True)
            query = f"SELECT MAX(date) FROM clean_yahoo_stocks WHERE ticker='{ticker}' AND interval='{interval}'"
            res = conn.execute(query).fetchone()
            return res[0] if res and res[0] else None
        except Exception as e:
            if "does not exist" in str(e).lower() or "not found" in str(e).lower():
                return None
            self.logger.error(f"FATAL: DB error querying last fetched date for {ticker}/{interval}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def fetch_data(self, ticker: str):
        """
        Fetches historical data from Yahoo Finance and saves as Parquet.
        """
        self.logger.info(f"Fetching data for {ticker} using yfinance...")
        
        config_start_date = self.config["ingestion"]["settings"]["start_date"]
        intervals = self.config["providers"]["yfinance"]["intervals"]
        fetched_any = False
        for interval in intervals:
            if self._rate_limited:
                self.logger.warning(f"Yahoo Finance rate limit detected earlier — skipping {ticker} [{interval}] (existing data will be used)")
                return False

            self.logger.info(f"Fetching data for {ticker} using yfinance... [{interval}]")
            
            last_date = self.get_last_fetched_date(ticker, interval)
            if last_date:
                start_date = last_date.strftime("%Y-%m-%d")
                self.logger.info(f"Incremental load: Found existing data up to {last_date}. Resuming from {start_date}")
            else:
                self.logger.info(f"Full Refresh: No existing data. Starting from {config_start_date}")
                start_date = config_start_date
                if interval == "1h":
                    limit_date = (datetime.now() - timedelta(days=700)).strftime("%Y-%m-%d")
                    if config_start_date < limit_date:
                        self.logger.warning(f"Adjusting start_date for 1h data: {config_start_date} -> {limit_date}")
                        start_date = limit_date
            
            try:
                retry_count = 0
                df = pd.DataFrame()

                USER_AGENTS = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ]

                while retry_count < self.max_retries:
                    try:
                        base_wait = self.retry_base_seconds ** retry_count
                        jitter = random.uniform(0, self.retry_jitter_seconds)
                        time.sleep(base_wait + jitter)

                        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

                        df = yf.download(ticker, start=start_date, interval=interval, progress=False, session=self.session)

                        if not df.empty:
                            break

                        self.logger.warning(f"Empty data for {ticker} at {interval} (Attempt {retry_count + 1}/{self.max_retries})")

                        if last_date and (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d") <= start_date:
                            self.logger.info(f"Assuming market is closed (weekend/holiday) and no new data for {ticker} [{interval}]. Moving on.")
                            break

                        retry_count += 1

                    except YFRateLimitError:
                        self._rate_limited = True
                        self.logger.warning(
                            f"Yahoo Finance rate limited for {ticker} [{interval}]. "
                            f"IP-level block detected — skipping all remaining Yahoo fetches. "
                            f"Existing data in S3 will be used by the loader."
                        )
                        return False

                    except Exception as e:
                        error_text = str(e).lower()
                        if "429" in error_text or "rate limit" in error_text or "too many requests" in error_text:
                            self._rate_limited = True
                            self.logger.warning(
                                f"HTTP 429 block for {ticker} [{interval}]. "
                                f"IP-level block detected — skipping all remaining Yahoo fetches."
                            )
                            return False

                        retry_count += 1
                        self.logger.error(f"Error fetching {ticker} [{interval}] (Attempt {retry_count}): {e}")
                        if retry_count < self.max_retries:
                            time.sleep(self.error_retry_seconds)

                if df.empty:
                    self.logger.warning(
                        f"No data returned for {ticker} [{interval}] after {self.max_retries} attempts. "
                        f"Continuing without marking the Yahoo provider as rate limited."
                    )
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df.reset_index(inplace=True)
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]
                
                if 'datetime' in df.columns:
                    df.rename(columns={'datetime': 'date'}, inplace=True)
                
                if df['date'].dt.tz is not None:
                    df['date'] = df['date'].dt.tz_convert('UTC').dt.tz_localize(None)
                
                filename = f"{ticker}_{interval}.parquet"
                s3_bucket = self.config["paths"].get("s3_bucket", "raw-data")
                file_path = f"s3://{s3_bucket}/{filename}"
                
                s3_storage_options = {
                    "client_kwargs": {"endpoint_url": os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")},
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
                fetched_any = True
                self.logger.info(f"Success! Saved total {len(df)} rows to {file_path}")

            except Exception as e:
                self.logger.error(f"Critical error processing {ticker}: {e}")
                raise

        return fetched_any

    def close(self):
        """Close session and cleanup"""
        if hasattr(self, 'session'):
            self.session.close()

if __name__ == "__main__":
    client = YahooFinanceClient()
    client.fetch_data("AAPL")
    client.close()
