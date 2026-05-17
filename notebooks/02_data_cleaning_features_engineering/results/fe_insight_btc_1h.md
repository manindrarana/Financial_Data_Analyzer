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

---

**Date:** 2026-05-17

### 5. V2 Feature Expansion — Open Interest & Turnover (crypto_features_02)

After the May 16 pipeline fixes successfully brought Open Interest and Turnover data into `gold_ml_features` (from Bybit API), we built a second feature engineering notebook (`crypto_features_02_after_oi_turnover.ipynb`) to integrate these new alternative data sources into the ML feature set.

#### 5.1 New Data Audit (Before Engineering)

Before adding anything to the model, we checked what actually made it through the pipeline:
- **turnover**: ~100% coverage — comes directly from Bybit kline API (quote currency volume), reliable
- **open_interest**: varies by interval — ~95-100% on 1h/1d (5min/15min OI interval mapped), ~0% on W/M (Bybit API doesn't support these intervals for OI)
- **funding_rate**: ~3% coverage — only ~2 months of data (March 2026+) merged successfully. Funding rate changes every 8 hours, so `merge_asof` with hourly klines mostly misses. **Dropped from v2 — too sparse for model training.**

#### 5.2 OI Features Engineered (4 new)

Raw `open_interest` is non-stationary (denominated in USD, trends with price). We derived:
- `oi_change_1p` — pct change over 1 period (immediate OI momentum)
- `oi_change_5p` — pct change over 5 periods (short-term positioning shift)
- `oi_change_20p` — pct change over 20 periods (medium-term positioning trend)
- `oi_zscore_50` — z-score vs 50-period rolling mean/std (extreme positioning detection)

**Rationale:** EDA showed raw OI has near-zero correlation with returns (-0.012 Spearman), but OI pct_change spikes are highly predictive — top 50 OI spike rows predicted 24× baseline next-hour returns (0.15% vs 0.006%).

#### 5.3 Turnover Features Engineered (4 new)

Raw `turnover` is also non-stationary. We derived:
- `turnover_ratio` — turnover / volume (liquidity efficiency proxy)
- `turnover_change_1p` — pct change over 1 period (sudden activity shifts)
- `turnover_change_5p` — pct change over 5 periods
- `turnover_ratio_zscore_50` — z-score of turnover ratio (unusual liquidity events)

#### 5.4 Funding Rate — Dropped

Only 3% non-null rows (~2 months). Dropped entirely. This is a known pipeline limitation — `merge_asof` tolerance in `bybit_client.py` may be too tight for 8-hour funding rate intervals merged with 1h klines. Revisit if funding rate fetch logic is fixed upstream.

#### 5.5 Final V2 Feature Set

| Category | Count | Features |
|----------|-------|----------|
| Price distance from MAs | 10 | `sma_7_dist` through `vwap_dist` |
| MACD & volatility as % | 5 | `macd_pct`, `macd_sig_pct`, `macd_hist_pct`, `atr_pct`, `volatility_pct` |
| Oscillators (already stationary) | 5 | `rsi_14`, `stoch_k`, `stoch_d`, `roc_10`, `williams_r` |
| Volume & BB ratios | 4 | `volume_ratio`, `bb_position`, `bb_squeeze`, `obv_change` |
| Returns & positional | 5 | `returns_1p`, `returns_5p`, `returns_10p`, `returns_20p`, `log_returns`, `hl_ratio`, `close_position` |
| **NEW: OI features** | **4** | `oi_change_1p`, `oi_change_5p`, `oi_change_20p`, `oi_zscore_50` |
| **NEW: Turnover features** | **4** | `turnover_ratio`, `turnover_change_1p`, `turnover_change_5p`, `turnover_ratio_zscore_50` |
| **Total** | **37** | (up from 29 in v1) |

#### 5.6 Output

Saved as `train_btc_1h_v2.parquet` and `test_btc_1h_v2.parquet` in `data/processed/`. These replace the v1 parquets for model training. The original v1 parquets are preserved — the v1 notebook (`crypto_features_01.ipynb`) remains unchanged.

#### 5.7 Next Step

Retrain XGBoost with the 37-feature v2 dataset. The key question: do OI and turnover features break the 53-54% accuracy ceiling that pure technical indicators couldn't surpass?

