import argparse
import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from pybit.unified_trading import HTTP


MAX_RECORDS = 200
INTERVALS = {
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
}


def parse_timestamp(value):
    return pd.Timestamp(value, tz="UTC")


def to_milliseconds(value):
    return int(parse_timestamp(value).timestamp() * 1000)


def fetch_funding_history(session, symbol, start_ms, end_ms, pause_seconds=0.1):
    records = []
    request_end = end_ms
    seen_oldest = set()
    request_count = 0

    while request_end >= start_ms:
        response = session.get_funding_rate_history(
            category="linear",
            symbol=symbol,
            startTime=start_ms,
            endTime=request_end,
            limit=MAX_RECORDS,
        )
        request_count += 1
        raw_records = response.get("result", {}).get("list", [])
        if not raw_records:
            break

        page = pd.DataFrame([
            {
                "funding_timestamp": int(item["fundingRateTimestamp"]),
                "funding_rate": float(item["fundingRate"]),
            }
            for item in raw_records
        ])
        page = page.drop_duplicates("funding_timestamp")
        records.extend(page.to_dict("records"))

        oldest = int(page["funding_timestamp"].min())
        if oldest in seen_oldest:
            break
        seen_oldest.add(oldest)
        if oldest <= start_ms:
            break

        request_end = oldest - 1
        time.sleep(pause_seconds)

    history = pd.DataFrame(records, columns=["funding_timestamp", "funding_rate"])
    if history.empty:
        return history, request_count

    history = history.drop_duplicates("funding_timestamp").sort_values("funding_timestamp")
    history["event_time"] = pd.to_datetime(history["funding_timestamp"], unit="ms", utc=True)
    return history.reset_index(drop=True), request_count


def build_interval_alignment(history, interval):
    if history.empty:
        return pd.DataFrame(columns=["candle_time", "funding_rate", "funding_timestamp"])

    start = history["event_time"].min().floor(interval)
    end = history["event_time"].max().ceil(interval)
    candles = pd.DataFrame({"candle_time": pd.date_range(start, end, freq=INTERVALS[interval], tz="UTC")})
    events = history[["event_time", "funding_timestamp", "funding_rate"]].sort_values("event_time")
    return pd.merge_asof(
        candles.sort_values("candle_time"),
        events,
        left_on="candle_time",
        right_on="event_time",
        direction="backward",
    )


def build_daily_summary(history):
    if history.empty:
        return pd.DataFrame(columns=["date", "funding_rate_last", "funding_rate_mean", "funding_rate_sum", "event_count"])

    events = history.copy()
    events["date"] = events["event_time"].dt.floor("D")
    daily = events.groupby("date", as_index=False).agg(
        funding_rate_last=("funding_rate", "last"),
        funding_rate_mean=("funding_rate", "mean"),
        funding_rate_sum=("funding_rate", "sum"),
        event_count=("funding_rate", "size"),
    )
    return daily


def build_coverage(history, aligned, interval):
    total = len(aligned)
    available = int(aligned["funding_rate"].notna().sum()) if total else 0
    return {
        "interval": interval,
        "candle_rows": total,
        "aligned_rows": available,
        "missing_rows": total - available,
        "coverage_percent": (available / total * 100) if total else 0.0,
        "funding_events": int(len(history)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start-date", default="2012-01-01T00:00:00Z")
    parser.add_argument("--end-date", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    load_dotenv()
    session = HTTP(
        testnet=False,
        api_key=os.getenv("BYBIT_API_KEY"),
        api_secret=os.getenv("BYBIT_API_SECRET"),
    )
    start_ms = to_milliseconds(args.start_date)
    end_ms = to_milliseconds(args.end_date)
    history, request_count = fetch_funding_history(session, args.symbol, start_ms, end_ms)

    os.makedirs(args.output_dir, exist_ok=True)
    history_path = os.path.join(args.output_dir, "btc_funding_history_investigation.csv")
    history.to_csv(history_path, index=False)

    coverage = {
        "symbol": args.symbol,
        "requested_start": pd.to_datetime(start_ms, unit="ms", utc=True).isoformat(),
        "requested_end": pd.to_datetime(end_ms, unit="ms", utc=True).isoformat(),
        "api_requests": request_count,
        "funding_events": int(len(history)),
        "oldest_available": history["event_time"].min().isoformat() if not history.empty else None,
        "latest_available": history["event_time"].max().isoformat() if not history.empty else None,
        "intervals": {},
    }

    for interval in ("1h", "4h"):
        aligned = build_interval_alignment(history, interval)
        aligned.to_csv(
            os.path.join(args.output_dir, f"btc_funding_alignment_{interval}.csv"),
            index=False,
        )
        coverage["intervals"][interval] = build_coverage(history, aligned, interval)

    daily_alignment = build_interval_alignment(history, "1d")
    daily_summary = build_daily_summary(history)
    daily_alignment.to_csv(
        os.path.join(args.output_dir, "btc_funding_alignment_1d.csv"),
        index=False,
    )
    daily_summary.to_csv(
        os.path.join(args.output_dir, "btc_funding_daily_summary.csv"),
        index=False,
    )
    coverage["intervals"]["1d"] = build_coverage(history, daily_alignment, "1d")
    coverage["daily_summary_rows"] = int(len(daily_summary))

    with open(os.path.join(args.output_dir, "btc_funding_coverage.json"), "w", encoding="utf-8") as output:
        json.dump(coverage, output, indent=2)

    print(json.dumps(coverage, indent=2))


if __name__ == "__main__":
    main()
