**Date:** 2026-05-07

### What We Found in the Data

- **Data Size & Missing Values:** We analyzed 53,396 rows of BTC 1h data as per todays date recent collection of data. We found some missing values (`NaN`), but we learned they are only at the very beginning of the dataset. This makes sense because indicators like Moving Averages need a few days of history to start calculating. We can safely drop these empty rows later.
- **Fat Tails & Outliers:** When we plotted the distribution, we saw a massive Kurtosis score (>50). We learned this means the crypto data has "fat tails"—extreme crashes and huge pumps happen way more often than normal. Our models will need to be ready for these outliers.
- **Correlations:** We used Spearman correlation instead of Pearson because financial data isn't perfectly linear. We discovered that `rsi_14` and `stoch_k` hold the strongest relationship with the returns. Also, we learned never to correlate against the raw `close` price to avoid fake "spurious correlations."

### Time-Series Learning (Stationarity)

- **Stationarity is Key:** We created an Autocorrelation plot and saw our returns drop to 0 instantly at lag 1. This was a huge win because it proved our data is nicely **Stationary** (the mean doesn't wander off to infinity), which Machine Learning models require.
- **Volatility Clustering:** When we plotted the _absolute_ returns, the line decayed slowly. We learned this proves "Volatility Clustering" (big price swings happen in groups).

### The Big Pipeline Catch!

- We noticed something suspicious: why was our target column named `returns_1d` if we are working with 1-hour data?
- We ran a manual math check (`df['close'].pct_change(1)`) and proved that the `returns_1d` column is actually just a **1-hour return** in disguise! The data pipeline hardcoded the column name, but the math just calculates a 1-period shift.

### Our Plan for Feature Engineering

1. **Build our own target:** Instead of trusting the pipeline's naming, we will engineer a brand new `target_1h` column so we know exactly what the model is predicting (using `shift(-1)`).
2. **Chronological Splitting:** We cannot use a random Train/Test split. We must split the data strictly by time to prevent Lookahead Bias.
3. **Scaling:** We will scale the features (like RSI and Volume) so they are on the same numerical level, but we make sure to only fit the scaler on the Training data!

---

**Date:** 2026-05-16

### What We Found in the New Data (After Pipeline Fixes)

- **Pipeline is Fixed:** After fixing the Bybit API keys and the `dropna()` bug, the gold layer now has **489,821 crypto rows** (11 symbols × 4 intervals) and **44,520 stock rows** (6 stocks × 4 intervals). The old problem where all rows got dropped is gone — only ~6,000 rows are lost for indicator warm-up.

- **Three New Columns:** The pipeline now includes `open_interest`, `funding_rate`, and `turnover` for crypto. These come from Bybit's API, not from our own calculations. Stocks don't have these columns (they only have OHLCV + indicators).

### Open Interest — The Good One

- **Coverage is solid for 1h and 1d:** OI has 95-100% coverage on 1-hour and 1-day intervals across all 11 symbols. For weekly and monthly, it's 0% — Bybit doesn't map OI to those intervals, so we drop it there.
- **BTC 1h:** OI starts from July 2020 (near the beginning of our data). After the warm-up period, only 4% of rows are missing — totally usable.
- **Raw OI is NOT correlated with returns:** Spearman correlation is -0.012 (basically zero). This makes sense — the absolute level of open interest doesn't tell you if price goes up or down.
- **But OI CHANGES matter:** When we looked at the top 50 biggest OI spikes, the average next-hour return was **0.15%** (24× the baseline of 0.006%). Big OI drops also had above-average returns at 0.09%. This means `oi_change` (pct_change of OI) is a real feature we should engineer for ML.

### Funding Rate — The Broken One

- **97% of funding rate data is missing.** For BTC 1h, the first valid funding rate date is March 11, 2026 — only 2 months out of 6 years of price data. The `merge_asof` in the pipeline is too strict and most of the historical funding rate data never gets matched to the kline timestamps.
- **Even when present, correlation is zero:** Spearman = 0.017. Funding rate changes every 8 hours on Bybit, so merging it onto 1h candles means most rows get the same value via `ffill()`. It adds almost no signal at hourly granularity.
- **Verdict:** We should either fix the merge logic to capture more history, or drop funding rate entirely for now. It's not helping ML in its current state.

### Turnover — The Reliable One

- **100% coverage across all intervals.** Turnover comes directly from Bybit's kline API (it's the quote currency volume, e.g., USDT traded). Every candle has it.
- **Correlation with returns is weak (0.014),** but like OI, the raw value isn't what matters — `turnover_change` or `turnover_ratio` (turnover / volume) might be useful features.

### What This Means for ML

| Interval | OI usable? | Funding Rate usable? | Turnover usable? |
|----------|-----------|---------------------|-----------------|
| 1h |  Yes (use `oi_change`) |  No (97% NaN) |  Yes |
| 1d |  Yes (use `oi_change`) |  No (96% NaN) |  Yes |
| W |  No (0%) |  No (only 9 rows) |  Yes |
| M |  No (0%) |  No |  Yes |

### Our Plan for Feature Engineering

1. **Engineer `oi_change`:** Instead of using raw `open_interest`, we will create `oi_change_1p` (1-period pct change) and maybe `oi_change_5p` / `oi_change_20p` for multi-period OI momentum.
2. **Engineer turnover features:** Create `turnover_ratio` (turnover / volume) and `turnover_change` to capture when dollar volume spikes relative to coin volume.
3. **Drop funding rate for now:** Until we fix the merge logic, funding rate is dead weight. We skip it in feature engineering.
4. **Focus on 1h and 1d intervals:** Weekly and monthly don't have OI, so for those we fall back to OHLCV + technical indicators only.
5. **Same chronological split and scaling rules apply:** No random splits, fit scaler only on training data, use `shift(-1)` for forward-looking targets.
