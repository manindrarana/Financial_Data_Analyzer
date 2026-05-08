**Date:** 2026-05-07

### What We Found in the Data

- **Data Size & Missing Values:** We analyzed 53,396 rows of BTC 1h data. We found some missing values (`NaN`), but we learned they are only at the very beginning of the dataset. This makes sense because indicators like Moving Averages need a few days of history to start calculating. We can safely drop these empty rows later.
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
