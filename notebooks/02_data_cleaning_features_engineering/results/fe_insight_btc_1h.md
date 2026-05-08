**Date:** 2026-05-08

### 1. Data Cleaning

- **Dropped Confusing Data:** We explicitly dropped the `returns_1d` column (and other historical return columns like `returns_5d` and `log_returns`) that were generated during the ELT duckdb pipeline. Since we proved in EDA that they were named misleadingly, removing them gave us a perfectly clean slate.
- **Dropped Lookback NaNs:** We dropped the starting `NaN` rows caused by moving average lookbacks. Machine learning models will crash if they encounter missing values.

### 2. Target Engineering

- **Forward-Looking Target:** We engineered a brand new target column called `target_1h` using `df['close'].pct_change().shift(-1)`. This forces the AI to look at _current_ indicators to predict the _future_ 1-hour return.
- **Classification Setup:** We converted `target_1h` into a binary classification variable (`target_direction`). `1` = Price went up, `0` = Price went down.
- **Natural Class Balance:** We checked the balance of classes and found it naturally sits at exactly **50.6% Up / 49.3% Down**. Because it is naturally balanced, we did not have to use any synthetic data techniques (which would have ruined our time-series timeline).

### 3. Chronological Train/Test Split

- We performed a strict **80/20 Chronological Split** instead of a random split.
- **Training Data:** 2020-04-02 to 2025-02-15 (42,716 Rows)
- **Testing Data:** 2025-02-15 to 2026-05-06 (10,679 Rows)
- Splitting chronologically completely removes "Lookahead Bias," ensuring our AI learns the past and is tested only on the unseen future.

### 4. Scaling & Storage

- **Avoiding Data Leakage:** We initialized a `StandardScaler` to compress all features (Volume, RSI, etc.) down to standard deviation values. Crucially, we only `fit()` the scaler on the **Training Data** before transforming both sets. Fitting on test data would have leaked future knowledge to the model.
- **Parquet Export:** We saved our completed `train_df` and `test_df` as `.parquet` files in `data/processed/`. We chose Parquet instead of DuckDB for this specific step because Parquet perfectly preserves the datetime index and offers incredibly fast memory loading for the upcoming Machine Learning phase.
