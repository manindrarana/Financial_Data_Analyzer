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

    def test_returns_none_for_unknown(self):
        client = BybitClient()
        assert client._map_to_oi_interval("W") is None
        assert client._map_to_oi_interval("M") is None
        assert client._map_to_oi_interval("240") is None


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


class TestYahooFetchData:
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
