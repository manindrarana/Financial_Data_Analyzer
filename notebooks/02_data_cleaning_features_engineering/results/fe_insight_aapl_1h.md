**Date:** 2026-05-12

### 1. Data Cleaning

- **Dropped Metadata Columns:** We dropped `asset_symbol`, `asset_class`, `exchange`, and `interval` as they are identifiers, not features. The model would learn nothing useful from them.
- **Zero NaN Rows at Start:** Unlike Bitcoin which had NaN warmup rows from the SMA_200 lookback, AAPL's data in our database already has pre-calculated indicators from historical data going back years. This means we lost zero rows during initial cleaning, which is a bonus given our smaller dataset size (only 3,472 rows vs BTC's ~50k).

### 2. Target Engineering

- **Forward-Looking Target:** We engineered `target_1h` using `df['close'].pct_change().shift(-1)`. The `pct_change()` always calculates a 1-period return regardless of overnight or weekend gaps, which is exactly what we want for stock data.
- **Classification Setup:** We converted `target_1h` into a binary `target_direction`. `1` = Price went up next hour, `0` = Price went down next hour.
- **Outstanding Class Balance:** The natural balance came out at **50.29% Up / 49.71% Down**. This is almost perfectly 50/50, meaning the market is genuinely a coin flip at the 1-hour level. No synthetic oversampling needed.

### 3. Chronological Train/Test Split

- We performed a strict **80/20 Chronological Split** instead of a random split.
- **Training Data:** 2024-05-13 to 2025-12-15 (2,777 Rows)
- **Testing Data:** 2025-12-16 to 2026-05-11 (695 Rows)
- This means our model is trained on ~1.5 years of AAPL trading and tested on the most recent ~5 months of real unseen data. This is the gold standard for time series validation.

### 4. Stationarity Conversion

- **Moving Average Distance (`_dist`):** All raw moving averages (`sma_7`, `ema_12`, `vwap`, etc.) were converted to percentage distances from the current close price. This makes them stationary and scale-invariant.
- **MACD to Percentage (`_pct`):** Raw `macd`, `macd_signal`, and `macd_histogram` were divided by the close price to normalize them. This is critical because raw MACD values for a $230 stock are very different numerically from MACD values for a $50 stock.
- **Dropped 30 Non-Stationary Columns:** All raw prices (`open`, `high`, `low`, `close`) and raw indicators were removed. The model now trains on purely stationary, relative features.

### 5. Scaling & Storage

- **Avoiding Data Leakage:** We `fit()` the `StandardScaler` **only on the training data** and then used `transform()` on both sets. Fitting on the test set would have leaked future knowledge of what the "average" AAPL price would be.
- **Dynamic Parquet Naming:** We saved outputs as `train_aapl_1h.parquet` and `test_aapl_1h.parquet` dynamic.
