import json
from unittest.mock import Mock

import pandas as pd

from scripts import investigate_funding
from scripts.investigate_funding import (
    align_funding_to_candles,
    build_daily_summary,
    build_interval_alignment,
    build_symbol_report,
    fetch_funding_history,
    load_configured_symbols,
)


def funding_history():
    return pd.DataFrame({
        "funding_timestamp": [
            1585670400000,
            1585699200000,
            1585728000000,
        ],
        "funding_rate": [0.0001, -0.00024535, -0.00065103],
        "event_time": pd.to_datetime([
            "2020-03-31 16:00:00+00:00",
            "2020-04-01 00:00:00+00:00",
            "2020-04-01 08:00:00+00:00",
        ]),
    })


def test_build_interval_alignment_1h_carries_latest_known_event():
    aligned = build_interval_alignment(funding_history(), "1h")

    assert aligned.loc[aligned["candle_time"] == "2020-03-31 23:00:00+00:00", "funding_rate"].iloc[0] == 0.0001
    assert aligned.loc[aligned["candle_time"] == "2020-04-01 00:00:00+00:00", "funding_rate"].iloc[0] == -0.00024535
    assert aligned.loc[aligned["candle_time"] == "2020-04-01 07:00:00+00:00", "funding_rate"].iloc[0] == -0.00024535
    assert aligned.loc[aligned["candle_time"] == "2020-04-01 08:00:00+00:00", "funding_rate"].iloc[0] == -0.00065103


def test_build_interval_alignment_4h_carries_event_across_two_candles():
    aligned = build_interval_alignment(funding_history(), "4h")

    rates = aligned.set_index("candle_time")["funding_rate"]
    assert rates.loc["2020-03-31 16:00:00+00:00"] == 0.0001
    assert rates.loc["2020-03-31 20:00:00+00:00"] == 0.0001
    assert rates.loc["2020-04-01 00:00:00+00:00"] == -0.00024535
    assert rates.loc["2020-04-01 04:00:00+00:00"] == -0.00024535
    assert rates.loc["2020-04-01 08:00:00+00:00"] == -0.00065103


def test_build_interval_alignment_does_not_use_future_event():
    aligned = build_interval_alignment(funding_history(), "1h")

    future_rows = aligned[aligned["candle_time"] < "2020-04-01 00:00:00+00:00"]

    assert future_rows["funding_rate"].eq(0.0001).all()


def test_align_funding_to_actual_candles_counts_pre_event_rows_as_missing():
    candle_times = pd.to_datetime([
        "2020-03-31 15:00:00+00:00",
        "2020-03-31 16:00:00+00:00",
        "2020-03-31 17:00:00+00:00",
    ])

    aligned = align_funding_to_candles(funding_history(), candle_times)

    assert aligned["funding_rate"].isna().sum() == 1
    assert aligned.loc[1, "funding_rate"] == 0.0001
    assert aligned.loc[2, "funding_rate"] == 0.0001


def test_build_daily_summary_returns_known_values():
    history = funding_history()
    history = pd.concat([
        history,
        pd.DataFrame({
            "funding_timestamp": [1585756800000],
            "funding_rate": [-0.00076413],
            "event_time": pd.to_datetime(["2020-04-01 16:00:00+00:00"]),
        }),
    ], ignore_index=True)

    summary = build_daily_summary(history).set_index("date")
    row = summary.loc["2020-04-01 00:00:00+00:00"]

    assert row["funding_rate_last"] == -0.00076413
    assert row["funding_rate_mean"] == sum([-0.00024535, -0.00065103, -0.00076413]) / 3
    assert row["funding_rate_sum"] == sum([-0.00024535, -0.00065103, -0.00076413])
    assert row["event_count"] == 3


def test_build_interval_alignment_handles_empty_history():
    aligned = build_interval_alignment(pd.DataFrame(), "1h")

    assert aligned.empty
    assert list(aligned.columns) == ["candle_time", "funding_rate", "funding_timestamp"]


def test_fetch_funding_history_stops_when_oldest_timestamp_repeats():
    session = Mock()
    session.get_funding_rate_history.side_effect = [
        {
            "result": {
                "list": [
                    {"fundingRateTimestamp": "2000", "fundingRate": "0.1"},
                    {"fundingRateTimestamp": "1000", "fundingRate": "0.2"},
                ]
            }
        },
        {
            "result": {
                "list": [
                    {"fundingRateTimestamp": "1000", "fundingRate": "0.2"},
                ]
            }
        },
    ]

    history, request_count = fetch_funding_history(
        session,
        "BTCUSDT",
        start_ms=0,
        end_ms=3000,
        pause_seconds=0,
    )

    assert request_count == 2
    assert history["funding_timestamp"].tolist() == [1000, 2000]
    assert session.get_funding_rate_history.call_args_list[0].kwargs["startTime"] == 0
    assert session.get_funding_rate_history.call_args_list[0].kwargs["endTime"] == 3000
    assert session.get_funding_rate_history.call_args_list[1].kwargs["endTime"] == 999


def test_load_configured_symbols_returns_bybit_targets(tmp_path):
    config_path = tmp_path / "settings.yml"
    config_path.write_text(
        "ingestion:\n  targets:\n    bybit:\n      - BTCUSDT\n      - ETHUSDT\n      - SOLUSDT\n",
        encoding="utf-8",
    )

    assert load_configured_symbols(config_path) == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def test_build_symbol_report_uses_actual_candle_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(
        investigate_funding,
        "fetch_funding_history",
        lambda session, symbol, start_ms, end_ms: (funding_history(), 2),
    )
    monkeypatch.setattr(
        investigate_funding,
        "load_actual_candle_times",
        lambda symbol, interval, config: pd.to_datetime([
            "2020-03-31 15:00:00+00:00",
            "2020-03-31 16:00:00+00:00",
            "2020-03-31 17:00:00+00:00",
        ]),
    )

    coverage = build_symbol_report(Mock(), "ETHUSDT", 0, 1585728000000, tmp_path)
    symbol_dir = tmp_path / "ethusdt"
    saved_alignment = pd.read_csv(symbol_dir / "funding_alignment_1h.csv")

    assert coverage["symbol"] == "ETHUSDT"
    assert coverage["intervals"]["1h"]["candle_rows"] == 3
    assert coverage["intervals"]["1h"]["aligned_rows"] == 2
    assert coverage["intervals"]["1h"]["missing_rows"] == 1
    assert coverage["intervals"]["1h"]["coverage_percent"] == 2 / 3 * 100
    assert saved_alignment["funding_rate"].isna().sum() == 1
    assert (symbol_dir / "funding_history.csv").exists()
    assert (symbol_dir / "funding_alignment_4h.csv").exists()
    assert (symbol_dir / "funding_alignment_1d.csv").exists()
    assert (symbol_dir / "funding_daily_summary.csv").exists()
    assert json.loads((symbol_dir / "funding_coverage.json").read_text(encoding="utf-8"))["symbol"] == "ETHUSDT"


def test_backfill_production_parquet_fills_only_null_values(monkeypatch):
    data = pd.DataFrame({
        "date": pd.to_datetime([
            "2020-03-31 15:00:00+00:00",
            "2020-03-31 16:00:00+00:00",
            "2020-03-31 17:00:00+00:00",
        ]),
        "close": [100.0, 101.0, 102.0],
        "funding_rate": [None, 0.9, None],
    })
    saved = []

    monkeypatch.setattr(investigate_funding.pd, "read_parquet", lambda *args, **kwargs: data.copy())
    monkeypatch.setattr(
        investigate_funding.pd.DataFrame,
        "to_parquet",
        lambda frame, *args, **kwargs: saved.append(frame.copy()),
    )

    aligned = align_funding_to_candles(funding_history(), data["date"])
    filled_rows = investigate_funding.backfill_production_parquet(
        "ETHUSDT",
        "1h",
        aligned,
        {"paths": {"s3_bucket": "raw-data"}},
    )

    assert filled_rows == 1
    assert pd.isna(saved[0]["funding_rate"].iloc[0])
    assert saved[0]["funding_rate"].iloc[1] == 0.9
    assert saved[0]["funding_rate"].iloc[2] == 0.0001
    assert saved[0]["close"].tolist() == [100.0, 101.0, 102.0]


def test_main_excludes_btc_by_default_and_combines_remaining_reports(tmp_path, monkeypatch):
    processed = []

    monkeypatch.setattr(
        investigate_funding,
        "load_configured_symbols",
        lambda config_path: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    )
    monkeypatch.setattr(investigate_funding, "load_dotenv", lambda: None)
    monkeypatch.setattr(investigate_funding, "HTTP", lambda **kwargs: Mock())

    def build_report(session, symbol, start_ms, end_ms, output_dir, config_path, backfill):
        processed.append(symbol)
        return {"symbol": symbol}

    monkeypatch.setattr(investigate_funding, "build_symbol_report", build_report)
    monkeypatch.setattr(
        "sys.argv",
        ["investigate_funding.py", "--output-dir", str(tmp_path)],
    )

    investigate_funding.main()

    assert processed == ["ETHUSDT", "SOLUSDT"]
    assert json.loads((tmp_path / "funding_coverage.json").read_text(encoding="utf-8")) == {
        "ETHUSDT": {"symbol": "ETHUSDT"},
        "SOLUSDT": {"symbol": "SOLUSDT"},
    }
