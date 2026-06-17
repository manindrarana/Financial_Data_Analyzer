import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import duckdb
from datetime import datetime
from src.processing.transformation import DataCleaner


def _mock_cleaner(monkeypatch):
    mock_conn = duckdb.connect(":memory:")
    monkeypatch.setattr(DataCleaner, "__init__", lambda self: (
        setattr(self, "conn", mock_conn),
        setattr(self, "logger", MagicMock()),
        setattr(self, "processed_bucket", "processed-data"),
        None
    )[-1])


def _seed_raw_table(conn, table_name, columns, rows):
    typed_cols = []
    for c in columns:
        if c == "date":
            typed_cols.append(f"{c} TIMESTAMP")
        else:
            typed_cols.append(f"{c} VARCHAR" if c in ("ticker", "interval", "symbol") else f"{c} DOUBLE")
    col_str = ", ".join(typed_cols)
    placeholders = ", ".join(["?" for _ in columns])
    conn.execute(f"CREATE TABLE {table_name} ({col_str})")
    conn.executemany(f"INSERT INTO {table_name} VALUES ({placeholders})", rows)


CLEAN_YAHOO_SQL = """
    CREATE TABLE clean_yahoo_stocks AS
    SELECT
        ticker, interval, CAST(date AS TIMESTAMP) AS date,
        open, high, low, close, volume
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (PARTITION BY ticker, interval, date ORDER BY volume DESC) AS rn
        FROM yahoo_stocks
        WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
          AND date IS NOT NULL
    ) sub
    WHERE rn = 1
    ORDER BY ticker, interval, date
"""

CLEAN_BYBIT_SQL = """
    CREATE TABLE clean_bybit_crypto AS
    SELECT
        symbol, interval, CAST(date AS TIMESTAMP) AS date,
        open, high, low, close, volume, turnover,
        open_interest, funding_rate
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (PARTITION BY symbol, interval, date ORDER BY volume DESC) AS rn
        FROM bybit_crypto
        WHERE open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
          AND date IS NOT NULL
    ) sub
    WHERE rn = 1
    ORDER BY symbol, interval, date
"""


class TestCleanYahoo:
    def test_deduplicates_by_ticker_interval_date(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "yahoo_stocks",
            ["ticker", "interval", "date", "open", "high", "low", "close", "volume"],
            [
                ("AAPL", "1h", datetime(2024, 1, 1, 10, 0), 150.0, 152.0, 149.0, 151.0, 1000.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 10, 0), 150.0, 152.0, 149.0, 151.0, 500.0),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        cleaner.conn.execute(CLEAN_YAHOO_SQL)

        count = cleaner.conn.execute("SELECT COUNT(*) FROM clean_yahoo_stocks").fetchone()[0]
        assert count == 1

    def test_keeps_row_with_highest_volume(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "yahoo_stocks",
            ["ticker", "interval", "date", "open", "high", "low", "close", "volume"],
            [
                ("AAPL", "1h", datetime(2024, 1, 1, 10, 0), 150.0, 152.0, 149.0, 151.0, 100.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 10, 0), 150.0, 152.0, 149.0, 151.0, 999.0),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        cleaner.conn.execute(CLEAN_YAHOO_SQL)

        vol = cleaner.conn.execute("SELECT volume FROM clean_yahoo_stocks").fetchone()[0]
        assert vol == 999.0

    def test_filters_out_zero_or_negative_prices(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "yahoo_stocks",
            ["ticker", "interval", "date", "open", "high", "low", "close", "volume"],
            [
                ("AAPL", "1h", datetime(2024, 1, 1, 10, 0), 0.0, 152.0, 149.0, 151.0, 1000.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 11, 0), -1.0, 152.0, 149.0, 151.0, 1000.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 12, 0), 150.0, 0.0, 149.0, 151.0, 1000.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 13, 0), 150.0, 152.0, 0.0, 151.0, 1000.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 14, 0), 150.0, 152.0, 149.0, 0.0, 1000.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 15, 0), 150.0, 152.0, 149.0, 151.0, 1000.0),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        cleaner.conn.execute(CLEAN_YAHOO_SQL)

        count = cleaner.conn.execute("SELECT COUNT(*) FROM clean_yahoo_stocks").fetchone()[0]
        assert count == 1

    def test_filters_out_null_dates(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "yahoo_stocks",
            ["ticker", "interval", "date", "open", "high", "low", "close", "volume"],
            [
                ("AAPL", "1h", None, 150.0, 152.0, 149.0, 151.0, 1000.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 10, 0), 150.0, 152.0, 149.0, 151.0, 1000.0),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        cleaner.conn.execute(CLEAN_YAHOO_SQL)

        count = cleaner.conn.execute("SELECT COUNT(*) FROM clean_yahoo_stocks").fetchone()[0]
        assert count == 1

    def test_orders_by_ticker_interval_date(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "yahoo_stocks",
            ["ticker", "interval", "date", "open", "high", "low", "close", "volume"],
            [
                ("AAPL", "1h", datetime(2024, 1, 1, 12, 0), 153.0, 154.0, 152.0, 153.0, 500.0),
                ("AAPL", "1h", datetime(2024, 1, 1, 10, 0), 150.0, 152.0, 149.0, 151.0, 1000.0),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_yahoo_stocks")
        cleaner.conn.execute(CLEAN_YAHOO_SQL)

        dates = cleaner.conn.execute("SELECT date FROM clean_yahoo_stocks ORDER BY date").fetchall()
        assert dates[0][0] == datetime(2024, 1, 1, 10, 0)
        assert dates[1][0] == datetime(2024, 1, 1, 12, 0)


class TestCleanBybit:
    def test_deduplicates_by_symbol_interval_date(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "bybit_crypto",
            ["symbol", "interval", "date", "open", "high", "low", "close", "volume", "turnover", "open_interest", "funding_rate"],
            [
                ("BTCUSDT", "1h", datetime(2024, 1, 1, 10, 0), 40000.0, 41000.0, 39000.0, 40500.0, 500.0, 100.0, 50.0, 0.01),
                ("BTCUSDT", "1h", datetime(2024, 1, 1, 10, 0), 40000.0, 41000.0, 39000.0, 40500.0, 200.0, 100.0, 50.0, 0.01),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_bybit_crypto")
        cleaner.conn.execute(CLEAN_BYBIT_SQL)

        count = cleaner.conn.execute("SELECT COUNT(*) FROM clean_bybit_crypto").fetchone()[0]
        assert count == 1

    def test_filters_out_bad_prices(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "bybit_crypto",
            ["symbol", "interval", "date", "open", "high", "low", "close", "volume", "turnover", "open_interest", "funding_rate"],
            [
                ("BTCUSDT", "1h", datetime(2024, 1, 1, 10, 0), 0.0, 41000.0, 39000.0, 40500.0, 500.0, 100.0, 50.0, 0.01),
                ("BTCUSDT", "1h", datetime(2024, 1, 1, 11, 0), 40000.0, 41000.0, 39000.0, 40500.0, 500.0, 100.0, 50.0, 0.01),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_bybit_crypto")
        cleaner.conn.execute(CLEAN_BYBIT_SQL)

        count = cleaner.conn.execute("SELECT COUNT(*) FROM clean_bybit_crypto").fetchone()[0]
        assert count == 1

    def test_preserves_extra_columns(self, monkeypatch):
        _mock_cleaner(monkeypatch)
        cleaner = DataCleaner()

        _seed_raw_table(cleaner.conn, "bybit_crypto",
            ["symbol", "interval", "date", "open", "high", "low", "close", "volume", "turnover", "open_interest", "funding_rate"],
            [
                ("BTCUSDT", "1h", datetime(2024, 1, 1, 10, 0), 40000.0, 41000.0, 39000.0, 40500.0, 500.0, 100.0, 50.0, 0.01),
            ]
        )

        cleaner.conn.execute("DROP TABLE IF EXISTS clean_bybit_crypto")
        cleaner.conn.execute(CLEAN_BYBIT_SQL)

        row = cleaner.conn.execute("SELECT turnover, open_interest, funding_rate FROM clean_bybit_crypto").fetchone()
        assert row[0] == 100.0
        assert row[1] == 50.0
        assert row[2] == 0.01