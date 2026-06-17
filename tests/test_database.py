import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import duckdb
from src.database.dimensions import DimensionBuilder
from src.database.facts import FactLoader
from src.database.loader import DatabaseLoader


def _mock_dimension_builder_constructor(monkeypatch):
    mock_conn = duckdb.connect(":memory:")
    monkeypatch.setattr(DimensionBuilder, "__init__", lambda self: setattr(self, "conn", mock_conn) or setattr(self, "logger", MagicMock()) or setattr(self, "config", {}))


def _mock_fact_loader_constructor(monkeypatch):
    mock_conn = duckdb.connect(":memory:")
    monkeypatch.setattr(FactLoader, "__init__", lambda self: setattr(self, "conn", mock_conn) or setattr(self, "logger", MagicMock()) or setattr(self, "config", {}))


def _mock_db_loader_constructor(monkeypatch):
    mock_conn = duckdb.connect(":memory:")
    monkeypatch.setattr(DatabaseLoader, "__init__", lambda self: setattr(self, "conn", mock_conn) or setattr(self, "logger", MagicMock()) or setattr(self, "config", {"paths": {"s3_bucket": "raw-data"}, "ingestion": {"targets": {"yfinance": ["AAPL"], "bybit": ["BTCUSDT"]}}, "providers": {"yfinance": {"intervals": ["1h"]}, "bybit": {"intervals": ["60"]}}}))


class TestDimensionBuilder:
    def test_create_dimension_tables(self, monkeypatch):
        _mock_dimension_builder_constructor(monkeypatch)
        builder = DimensionBuilder()
        builder.create_dimension_tables()

        tables = builder.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'dim_%'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "dim_assets" in table_names
        assert "dim_date" in table_names
        assert "dim_interval" in table_names

    def test_dim_assets_schema(self, monkeypatch):
        _mock_dimension_builder_constructor(monkeypatch)
        builder = DimensionBuilder()
        builder.create_dimension_tables()

        cols = builder.conn.execute("DESCRIBE dim_assets").df()
        col_names = cols["column_name"].tolist()
        for c in ["asset_id", "asset_symbol", "asset_name", "asset_class", "exchange", "sector", "created_at", "updated_at"]:
            assert c in col_names

    def test_dim_interval_schema(self, monkeypatch):
        _mock_dimension_builder_constructor(monkeypatch)
        builder = DimensionBuilder()
        builder.create_dimension_tables()

        cols = builder.conn.execute("DESCRIBE dim_interval").df()
        col_names = cols["column_name"].tolist()
        for c in ["interval_id", "interval_code", "interval_minutes", "interval_description"]:
            assert c in col_names

    def test_populate_dim_interval_inserts_10_rows(self, monkeypatch):
        _mock_dimension_builder_constructor(monkeypatch)
        builder = DimensionBuilder()
        builder.create_dimension_tables()
        builder.populate_dim_interval()

        count = builder.conn.execute("SELECT COUNT(*) FROM dim_interval").fetchone()[0]
        assert count == 10

    def test_populate_dim_interval_is_idempotent(self, monkeypatch):
        _mock_dimension_builder_constructor(monkeypatch)
        builder = DimensionBuilder()
        builder.create_dimension_tables()
        builder.populate_dim_interval()
        builder.populate_dim_interval()

        count = builder.conn.execute("SELECT COUNT(*) FROM dim_interval").fetchone()[0]
        assert count == 10

    def test_populate_dim_date_skips_when_populated(self, monkeypatch):
        _mock_dimension_builder_constructor(monkeypatch)
        builder = DimensionBuilder()
        builder.create_dimension_tables()
        builder.populate_dim_date()
        first_count = builder.conn.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
        builder.populate_dim_date()
        second_count = builder.conn.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
        assert first_count == second_count
        assert first_count > 0

    def test_populate_dim_date_has_correct_columns(self, monkeypatch):
        _mock_dimension_builder_constructor(monkeypatch)
        builder = DimensionBuilder()
        builder.create_dimension_tables()
        builder.populate_dim_date()

        cols = builder.conn.execute("DESCRIBE dim_date").df()
        col_names = cols["column_name"].tolist()
        for c in ["date_id", "date", "year", "month", "is_business_day", "is_weekend"]:
            assert c in col_names


class TestFactLoader:
    def test_create_fact_table(self, monkeypatch):
        _mock_fact_loader_constructor(monkeypatch)
        loader = FactLoader()
        loader.create_fact_table()

        tables = loader.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'fact_price_history'"
        ).fetchall()
        assert len(tables) == 1

    def test_fact_table_schema(self, monkeypatch):
        _mock_fact_loader_constructor(monkeypatch)
        loader = FactLoader()
        loader.create_fact_table()

        cols = loader.conn.execute("DESCRIBE fact_price_history").df()
        col_names = cols["column_name"].tolist()
        for c in ["price_id", "asset_id", "date_id", "interval_id", "timestamp", "open", "high", "low", "close", "volume", "turnover", "open_interest", "funding_rate", "daily_volatility"]:
            assert c in col_names

    def test_fact_table_has_indexes(self, monkeypatch):
        _mock_fact_loader_constructor(monkeypatch)
        loader = FactLoader()
        loader.create_fact_table()

        indexes = loader.conn.execute(
            "SELECT index_name FROM duckdb_indexes WHERE table_name = 'fact_price_history'"
        ).fetchall()
        index_names = [i[0] for i in indexes]
        assert "idx_fact_asset" in index_names
        assert "idx_fact_date" in index_names
        assert "idx_fact_timestamp" in index_names

    def test_fact_table_is_idempotent(self, monkeypatch):
        _mock_fact_loader_constructor(monkeypatch)
        loader = FactLoader()
        loader.create_fact_table()
        loader.create_fact_table()

        count = loader.conn.execute("SELECT COUNT(*) FROM fact_price_history").fetchone()[0]
        assert count == 0


class TestDatabaseLoader:
    def test_yahoo_stocks_table_schema(self, monkeypatch):
        _mock_db_loader_constructor(monkeypatch)
        loader = DatabaseLoader()
        loader.conn.execute("DROP TABLE IF EXISTS yahoo_stocks")
        loader.conn.execute("""
            CREATE TABLE yahoo_stocks (
                ticker VARCHAR,
                interval VARCHAR,
                date TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE
            )
        """)

        cols = loader.conn.execute("DESCRIBE yahoo_stocks").df()
        col_names = cols["column_name"].tolist()
        for c in ["ticker", "interval", "date", "open", "high", "low", "close", "volume"]:
            assert c in col_names

    def test_bybit_crypto_table_schema(self, monkeypatch):
        _mock_db_loader_constructor(monkeypatch)
        loader = DatabaseLoader()
        loader.conn.execute("DROP TABLE IF EXISTS bybit_crypto")
        loader.conn.execute("""
            CREATE TABLE bybit_crypto (
                symbol VARCHAR,
                interval VARCHAR,
                date TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                turnover DOUBLE,
                open_interest DOUBLE,
                funding_rate DOUBLE
            )
        """)

        cols = loader.conn.execute("DESCRIBE bybit_crypto").df()
        col_names = cols["column_name"].tolist()
        for c in ["symbol", "interval", "date", "open", "high", "low", "close", "volume", "turnover", "open_interest", "funding_rate"]:
            assert c in col_names