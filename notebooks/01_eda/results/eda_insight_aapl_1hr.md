**Date:** 2026-05-12

### What We Found in the Data

- **Data Size & Missing Values:** We analyzed 3,473 rows of AAPL 1h data collected from May 2024 to May 2026. Zero missing values found anywhere. The data is perfectly clean straight out of the database.
- **Low Volatility vs Crypto:** AAPL's standard deviation is only **0.66% per hour** and its max single-hour move is ±8%. This is drastically calmer than Bitcoin, which can easily move ±15-20% in an hour. Stocks are more predictable by nature.
- **Fat Tails Still Present (Kurtosis = 18.67):** Even though stocks are calmer, the kurtosis is still very high. This means rare but violent spikes still happen (e.g., earnings releases, Fed announcements). The model needs to be ready for these.
- **Negative Skew (-0.31):** When AAPL crashes, the drops tend to be bigger than the pumps. A small but important asymmetry compared to crypto.

### Time-Series Learning (Stationarity)

- **Stationarity Confirmed:** Just like BTC, the `returns_1p` autocorrelation drops to zero at lag 1, confirming the data is stationary and ML-ready.
- **Volatility Clustering Confirmed:** The absolute returns autocorrelation decays slowly, proving that big AAPL moves (earnings weeks, macro events) cluster together in time.

### Key Difference vs Bitcoin (Feature Correlations)

- For BTC, the strongest signal was `sma_7_dist` (mean reversion). For AAPL, the correlation ranking flips completely:

| Rank | Feature | Correlation |
|------|---------|-------------|
| 1 | `stoch_k` | 0.40 |
| 2 | `rsi_14` | 0.29 |
| 3 | `roc_10` | 0.25 |

- `stoch_k` being the #1 feature tells us AAPL is driven more by **momentum** than mean-reversion. This is a significant structural difference and will likely result in different optimal XGBoost hyperparameters.

### The Pipeline Verification Check

- We ran a manual check comparing `returns_1p` against `df['close'].pct_change(1)`. The values matched exactly, confirming that our **Period Standard (`1p`) fix from the ELT pipeline is correctly calculating a 1-hour return**, not the old hardcoded 24-hour return. The bug is fixed.

### Our Plan for Feature Engineering

1. **Same stationary features as BTC:** Drop raw prices, use `_dist` percentage columns for all moving averages. Make sure to use `macd_pct` instead of raw `macd`.
2. **Handle Market Hour Gaps:** Unlike BTC which is 24/7, AAPL has overnight and weekend gaps. We need to make sure our `dropna()` step handles the NaNs that appear at Monday morning opens correctly.
3. **Chronological Splitting:** Same strict time-based split. No random shuffling.
4. **Scaler fitted on Training Data only:** Same rule applies, no peeking into the future.
