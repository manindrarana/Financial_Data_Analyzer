from unittest.mock import Mock

import pandas as pd

from scripts.investigate_funding import (
    build_daily_summary,
    build_interval_alignment,
    fetch_funding_history,
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
