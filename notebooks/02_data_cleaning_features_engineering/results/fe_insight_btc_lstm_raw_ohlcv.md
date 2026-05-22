**Date:** 2026-05-22

## Experiment -- LSTM Raw OHLCV Feature Engineering

### 1. Data Source

- **Source table:** `gold_crypto_features` in DuckDB -- queried only the 6 raw OHLCV columns (`date, open, high, low, close, volume`), deliberately excluding all 45 engineered indicators
- **Asset/Interval:** BTC 4h
- **Rows loaded:** 13,296 candles
- **Date range:** 2020-04-27 12:00 -> 2026-05-22 08:00 (~6.1 years of 4h data)

### 2. Log Return Transformation

**Why log returns instead of raw prices:**
- Raw prices are non-stationary (BTC went from $7k to $77k+) -- LSTM training on raw prices would fail due to non-zero mean and trend
- Log returns `log(price_t / price_{t-1})` are stationary (mean ~ 0), scale-invariant, and safe for neural networks
- Applied to all 5 columns: `open_logret`, `high_logret`, `low_logret`, `close_logret`, `volume_logret`

**Log return statistics (13,295 rows after dropping first NaN):**

| Column | Mean | Std | Min | Max |
|--------|------|-----|-----|-----|
| open_logret | 0.00017 | 0.0124 | -0.1107 | 0.1368 |
| high_logret | 0.00017 | 0.0116 | -0.0988 | 0.1563 |
| low_logret | 0.00017 | 0.0137 | -0.2423 | 0.2276 |
| close_logret | 0.00017 | 0.0124 | -0.1107 | 0.1368 |
| volume_logret | 0.00009 | 0.6828 | -5.0786 | 4.9074 |

All price log returns: mean ~ 0, no trend -- confirmed stationary and safe for LSTM.

### 3. Target Engineering

- **Target:** `target_4h = close_logret.shift(-1)` -- predict next 4h candle's log return
- **Binary classification:** `target_direction = (target_4h > 0).astype(int)` -- same target definition as XGBoost v4 for direct comparability
- **After dropping last row (no future close):** 13,294 rows
- **Class balance:** 51.28% UP / 48.72% DOWN -- naturally balanced, no synthetic balancing needed

### 4. 3D Sequence Building

LSTM requires 3D input: `(samples, timesteps, features)`

- **Sequence length:** 20 candles (each sequence spans 80 hours / ~3.3 days of 4h data)
- **Features:** 5 log-return columns
- **Sliding window:** Non-overlapping target -- each sequence predicts the candle immediately after the window
- **Result:** X shape `(13274, 20, 5)`, y shape `(13274,)`
- **Lost rows:** 20 (first incomplete sequence) -- from 13,294 rows -> 13,274 sequences

### 5. Chronological Train/Test Split (80/20)

Same split methodology as all previous experiments -- no shuffling, strict temporal order:

| Split | Samples | Shape | Date Range | UP% |
|-------|---------|-------|------------|-----|
| **Train** | 10,619 (80.0%) | (10619, 20, 5) | 2020-05-01 -> 2025-03-05 | 51.5% |
| **Test** | 2,655 (20.0%) | (2655, 20, 5) | 2025-03-05 -> 2026-05-22 | 50.1% |

Test set covers ~14 months of unseen future data. Class balance near 50/50 in both splits.

### 6. Output Format -- Dual Format Decision

**X (features) saved as `.npy`:**
- `X_train_btc_4h_lstm_raw.npy` -> (10619, 20, 5)
- `X_test_btc_4h_lstm_raw.npy` -> (2655, 20, 5)
- **Why .npy:** Only NumPy binary format preserves 3D tensor shape `(samples, timesteps, features)`. Parquet/CSV cannot store 3D arrays -- they would flatten to 2D and lose the temporal dimension. LSTM's `input_shape` requires exactly 3D, so `.npy` is the only viable format.

**y (targets) saved as `.parquet`:**
- `y_train_btc_4h_lstm_raw.parquet` -> columns: `target_direction`, `date`
- `y_test_btc_4h_lstm_raw.parquet` -> columns: `target_direction`, `date`
- **Why .parquet:** Targets are 2D tabular data -- Parquet is consistent with all prior experiments, preserves the date column for time-series alignment, and loads instantly via `pd.read_parquet()`.

### 7. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| 5 features only (no indicators) | Test whether raw price patterns alone can beat engineered features (51.30% old LSTM) |
| 20-candle sequences | Matches XGBoost v4's 20-period lookback; 80 hours of context for 4h candles |
| Log returns (not raw prices) | Non-negotiable for LSTM -- neural networks require stationary inputs |
| Same target as XGBoost v4 | Direct comparability -- isolates effect of model architecture vs feature set |
| No scaling applied | Log returns are already standardized (~0 mean, ~0.01 std) -- additional StandardScaler unnecessary and would add complexity |
| 80/20 chronological split | Eliminates lookahead bias, consistent with all prior experiments |

### 8. Comparison: Old LSTM vs New LSTM (Input Data)

| Aspect | Old LSTM (`BTC_lstm.ipynb`) | New LSTM (this FE notebook) |
|--------|---------------------------|----------------------------|
| **Features** | 29 engineered indicators (RSI, MACD, etc.) | 5 log-return columns (raw OHLCV only) |
| **Interval** | 1h candles | 4h candles |
| **Timesteps** | 6 candles | 20 candles |
| **Sequencing** | Built inside model notebook from DataFrame | Pre-built as 3D `.npy` arrays |
| **Scaling** | StandardScaler fit on train only | None needed (log returns already stationary) |
| **Data source** | `gold_crypto_features` (29 cols + OHLCV) | `gold_crypto_features` (6 cols: OHLCV only) |

### 9. Next Step

Train a 2-layer LSTM with identical architecture to the old LSTM (LSTM(64)->Dropout(0.4)->LSTM(32)->Dropout(0.2)->Dense(16)->Dropout(0.2)->Dense(1,sigmoid)) on these raw OHLCV sequences. The only variable being tested: **raw prices vs. engineered indicators** as input features. Benchmark: 51.30% accuracy (old LSTM). If raw OHLCV beats this, proceed to LSTM+XGBoost hybrid.