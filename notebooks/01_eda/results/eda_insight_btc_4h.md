**Date:** 2026-05-18

### Why We Did This

We added native 4-hour candle support to the pipeline. Previously, the 4h data existed in the silver layer (`clean_bybit_crypto`) but was silently dropped when building gold tables. The root cause was a missing `dim_interval` mapping — Bybit stores 4h as `"240"` but `dim_interval` only had entries for `'1h'`, `'60'`, `'1d'`, `'D'`, `'1wk'`, `'W'`, `'1mo'`, `'M'`. The JOIN at `facts.py:159` (`c.interval = di.interval_code`) found no match for `"240"` and dropped all 4h rows.

### What We Fixed

- **`dimensions.py` — `populate_dim_interval()`:** Added two new rows: `(9, '4h', 240, '4-Hour')` and `(10, '240', 240, '4-Hour (Bybit)')`. Changed from a skip-guard (`if existing > 0: return`) to `INSERT OR IGNORE` so the seed data is safe to run on existing databases without errors.

### 4h Data — Verified

| Metric | BTC 4h | BTC 1h |
|--------|--------|--------|
| Rows | 13,274 | 53,688 |
| Date range | 2020-04-27 → 2026-05-18 | 2020-04-02 → 2026-05-18 |
| Close range | $7,669.50 – $125,329.40 | (same underlying) |
| Avg close | $51,049.62 | (same underlying) |
| Total 4h rows (all 11 symbols) | 116,404 | — |

### Key Observations

- **4h starts ~25 days later than 1h:** First 4h candle is April 27, 2020 vs April 2 for 1h. This is a Bybit API limitation — 4h klines simply don't go back as far as 1h for the earliest trading periods.
- **1:4 ratio holds:** 13,274 4h candles vs 53,688 1h candles ≈ 1:4 ratio, exactly as expected (4 × 1h = 1 × 4h).
- **Same price range:** The close prices cover the identical range ($7.6K–$125K), confirming both intervals draw from the same underlying price history.
- **11 symbols with 4h data:** All crypto assets in the pipeline now have 4h gold-layer data, not just BTC.

### Symbol Naming in Gold Tables

> **Important:** In `gold_crypto_features`, the column is `asset_symbol` and values are `BTC`, `ETH`, `SOL` (no `USDT` suffix). This is because `dim_assets` strips the suffix via `REPLACE(symbol, 'USDT', '')`. When querying gold tables, use `WHERE asset_symbol = 'BTC'` — not `'BTCUSDT'`.

### What This Enables

- **True 4h feature engineering:** We can now build features directly from 4h candles (e.g., 4h RSI, 4h MACD) instead of downsampling 1h data.
- **4h native model training:** A model trained on native 4h candles may capture different patterns than the previous `target_4h` experiment, which used 1h features with a 4-period lookahead.
- **Cross-interval validation:** We can compare 1h-native vs 4h-native models to see if the 4h timeframe carries different signal.