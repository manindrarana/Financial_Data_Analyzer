import sys
from unittest.mock import MagicMock

mock_pyrate = MagicMock()
mock_pyrate.Duration = MagicMock()
mock_pyrate.RequestRate = MagicMock()
mock_pyrate.Limiter = MagicMock()
sys.modules["pyrate_limiter"] = mock_pyrate

mock_requests_cache = MagicMock()
sys.modules["requests_cache"] = mock_requests_cache

mock_requests_ratelimiter = MagicMock()
sys.modules["requests_ratelimiter"] = mock_requests_ratelimiter

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.ingestion.bybit_client import BybitClient
from src.ingestion.yahoo_finance import YahooFinanceClient


class TestBybitOIIntvMapping:
    def test_maps_60_to_1h(self):
        client = BybitClient()
        assert client._map_to_oi_interval("60") == "1h"

    def test_maps_D_to_1d(self):
        client = BybitClient()
        assert client._map_to_oi_interval("D") == "1d"

    def test_maps_240_to_4h(self):
        client = BybitClient()
        assert client._map_to_oi_interval("240") == "4h"


class TestBybitGetLastFetchedDate:
    @patch("src.ingestion.bybit_client.load_dotenv")
    @patch("os.path.exists", return_value=False)
    def test_returns_none_when_db_missing(self, mock_exists, mock_dotenv):
        client = BybitClient()
        result = client.get_last_fetched_date("BTCUSDT", "60")
        assert result is None

    @patch("src.ingestion.bybit_client.load_dotenv")
    @patch("os.path.exists", return_value=True)
    @patch("duckdb.connect")
    def test_returns_none_when_table_empty(self, mock_connect, mock_exists, mock_dotenv):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = (None,)
        mock_connect.return_value = mock_conn

        client = BybitClient()
        result = client.get_last_fetched_date("BTCUSDT", "60")
        assert result is None

    @patch("src.ingestion.bybit_client.load_dotenv")
    @patch("os.path.exists", return_value=True)
    @patch("duckdb.connect")
    def test_raises_on_db_error(self, mock_connect, mock_exists, mock_dotenv):
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("disk I/O error")
        mock_connect.return_value = mock_conn

        client = BybitClient()
        with pytest.raises(Exception):
            client.get_last_fetched_date("BTCUSDT", "60")



class TestYahooGetLastFetchedDate:
    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("os.path.exists", return_value=False)
    def test_returns_none_when_db_missing(self, mock_exists, mock_dotenv):
        client = YahooFinanceClient()
        result = client.get_last_fetched_date("AAPL", "1h")
        assert result is None

    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("os.path.exists", return_value=True)
    @patch("duckdb.connect")
    def test_returns_none_when_table_not_found(self, mock_connect, mock_exists, mock_dotenv):
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("table does not exist")
        mock_connect.return_value = mock_conn

        client = YahooFinanceClient()
        result = client.get_last_fetched_date("AAPL", "1h")
        assert result is None

    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("os.path.exists", return_value=True)
    @patch("duckdb.connect")
    def test_raises_on_other_db_error(self, mock_connect, mock_exists, mock_dotenv):
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("disk I/O error")
        mock_connect.return_value = mock_conn

        client = YahooFinanceClient()
        with pytest.raises(Exception):
            client.get_last_fetched_date("AAPL", "1h")


class TestYahooFetchData:
    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("src.ingestion.yahoo_finance.LimiterSession")
    def test_loads_configured_request_and_retry_settings(self, mock_limiter_session, mock_dotenv):
        client = YahooFinanceClient()

        assert client.requests_per_second == 1
        assert client.max_retries == 3
        assert client.retry_base_seconds == 2
        assert client.retry_jitter_seconds == 1
        assert client.error_retry_seconds == 5
        mock_limiter_session.assert_called_once_with(per_second=1)

    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("os.path.exists", return_value=False)
    @patch("time.sleep")
    @patch("src.ingestion.yahoo_finance.yf.download")
    @patch("pandas.read_parquet", side_effect=FileNotFoundError("missing parquet"))
    @patch("pandas.DataFrame.to_parquet", side_effect=Exception("S3 write failed"))
    def test_raises_on_parquet_write_error(self, mock_to_parquet, mock_read_parquet, mock_download, mock_sleep, mock_exists, mock_dotenv):
        dates = pd.date_range("2024-01-01", periods=2, freq="D", name="Date")
        mock_download.return_value = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1100],
            },
            index=dates,
        )

        client = YahooFinanceClient()
        client.config["providers"]["yfinance"]["intervals"] = ["1d"]

        with pytest.raises(Exception, match="S3 write failed"):
            client.fetch_data("AAPL")

    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("os.path.exists", return_value=False)
    @patch("time.sleep")
    @patch("src.ingestion.yahoo_finance.yf.download", return_value=pd.DataFrame())
    def test_stops_yahoo_run_after_repeated_empty_downloads(self, mock_download, mock_sleep, mock_exists, mock_dotenv):
        client = YahooFinanceClient()
        client.config["providers"]["yfinance"]["intervals"] = ["1h", "1d"]

        result = client.fetch_data("AAPL")

        assert result is False
        assert client._rate_limited is False
        assert mock_download.call_count == client.max_retries * 2

    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("os.path.exists", return_value=False)
    @patch("time.sleep")
    @patch("src.ingestion.yahoo_finance.yf.download", return_value=pd.DataFrame())
    def test_empty_download_does_not_mark_provider_rate_limited(self, mock_download, mock_sleep, mock_exists, mock_dotenv):
        client = YahooFinanceClient()
        client.config["providers"]["yfinance"]["intervals"] = ["1d"]

        result = client.fetch_data("AAPL")

        assert result is False
        assert client._rate_limited is False
        assert mock_download.call_count == client.max_retries

    @patch("src.ingestion.yahoo_finance.load_dotenv")
    @patch("os.path.exists", return_value=False)
    @patch("time.sleep")
    @patch("src.ingestion.yahoo_finance.yf.download")
    def test_stops_remaining_intervals_after_explicit_rate_limit(self, mock_download, mock_sleep, mock_exists, mock_dotenv):
        from yfinance.exceptions import YFRateLimitError

        client = YahooFinanceClient()
        client.config["providers"]["yfinance"]["intervals"] = ["1h", "1d"]
        mock_download.side_effect = YFRateLimitError()

        result = client.fetch_data("AAPL")

class TestBybitFundingRate:
    @patch("src.ingestion.bybit_client.load_dotenv")
    @patch("time.sleep")
    def test_fetches_bounded_pages_and_moves_end_time_backward(self, mock_sleep, mock_dotenv):
        client = BybitClient()
        client.session.get_funding_rate_history = MagicMock(side_effect=[
            {
                "result": {
                    "list": [
                        {"fundingRateTimestamp": "3000", "fundingRate": "0.3"},
                        {"fundingRateTimestamp": "2000", "fundingRate": "0.2"},
                    ]
                }
            },
            {
                "result": {
                    "list": [
                        {"fundingRateTimestamp": "1000", "fundingRate": "0.1"},
                    ]
                }
            },
        ])

        result = client.fetch_funding_rate("BTCUSDT", 1000, 4000)

        assert result["timestamp"].tolist() == [1000, 2000, 3000]
        first_call = client.session.get_funding_rate_history.call_args_list[0].kwargs
        second_call = client.session.get_funding_rate_history.call_args_list[1].kwargs
        assert first_call["startTime"] == 1000
        assert first_call["endTime"] == 4000
        assert first_call["limit"] == 200
        assert second_call["endTime"] == 1999
        assert mock_sleep.call_count == 1

    @patch("src.ingestion.bybit_client.load_dotenv")
    @patch("time.sleep")
    def test_deduplicates_events_and_stops_on_repeated_oldest_timestamp(self, mock_sleep, mock_dotenv):
        client = BybitClient()
        client.session.get_funding_rate_history = MagicMock(side_effect=[
            {
                "result": {
                    "list": [
                        {"fundingRateTimestamp": "2000", "fundingRate": "0.2"},
                        {"fundingRateTimestamp": "1000", "fundingRate": "0.1"},
                    ]
                }
            },
            {
                "result": {
                    "list": [
                        {"fundingRateTimestamp": "1000", "fundingRate": "0.1"},
                    ]
                }
            },
        ])

        result = client.fetch_funding_rate("BTCUSDT", 0, 3000)

        assert result["timestamp"].tolist() == [1000, 2000]
    @patch("src.ingestion.bybit_client.load_dotenv")
    @patch("src.ingestion.bybit_client.pd.read_parquet")
    @patch("src.ingestion.bybit_client.pd.DataFrame.to_parquet")
    @patch("time.sleep")
    def test_full_refresh_does_not_seed_previous_funding_rate(self, mock_sleep, mock_to_parquet, mock_read_parquet, mock_dotenv):
        client = BybitClient()
        client.config["providers"]["bybit"]["intervals"] = ["60"]
        client.config["ingestion"]["settings"]["start_date"] = "2023-01-01"
        client.get_last_fetched_date = MagicMock(return_value=None)
        client.session.get_kline = MagicMock(side_effect=[
            {"result": {"list": [["1704067200000", "1", "2", "0.5", "1.5", "10", "20"]]}},
            {"result": {"list": []}},
        ])
        client.fetch_open_interest = MagicMock(return_value=None)
        client.fetch_funding_rate = MagicMock(return_value=pd.DataFrame([{
            "timestamp": 1704070800000,
            "funding_rate": 0.2,
        }]))
        existing = pd.DataFrame([{
            "date": pd.Timestamp("2023-01-01"),
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 10.0,
            "turnover": 20.0,
            "open_interest": None,
            "funding_rate": 0.9,
        }])
        mock_read_parquet.return_value = existing

        client.fetch_data("BTCUSDT")

        saved = mock_to_parquet.call_args.args[0]
        refreshed_row = saved[saved["date"] == pd.Timestamp("2024-01-01")]
        assert refreshed_row["funding_rate"].isna().all()
