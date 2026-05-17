**Date:** 2026-05-17

## 1. What We Did — OI & Turnover Features (v2)

After the EDA showed that Bybit's [`open_interest`](src/ingestion/bybit_client.py:58) had **95.1% coverage** and [`turnover`](src/ingestion/bybit_client.py:171) had **100% coverage** in our BTC 1h data, we built 8 new features to see if market microstructure data could beat the 52.60% ceiling:

- **OI features:** `oi_change_1p`, `oi_change_5p`, `oi_change_20p`, `oi_zscore_50`
- **Turnover features:** `turnover_ratio`, `turnover_change_1p`, `turnover_change_5p`, `turnover_ratio_zscore_50`

Feature engineering notebook: [`crypto_features_02_after_oi_turnover.ipynb`](notebooks/02_data_cleaning_features_engineering/crypto_features_02_after_oi_turnover.ipynb)

We ran a **216-candidate GridSearchCV** (3-fold, CUDA-accelerated) across 37 features on ~40,536 training rows. Took **11 minutes 18 seconds**.

Model notebook: [`BTC_Xgboost_02_after_oi_turnover.ipynb`](notebooks/03_models/crypto/BTC_Xgboost_02_after_oi_turnover.ipynb)

## 2. What We Did — 4h Target Horizon (v3)

The 1h target didn't budge, so we tested whether the same OI/turnover features could predict **4-hour forward returns** instead. Reasoning: microstructure effects (OI buildup, turnover spikes) might take longer to play out.

- Same 37 features, same 216-candidate GridSearchCV
- Only change: `target_4h = close.pct_change(4).shift(-4)` instead of `target_1h = close.pct_change().shift(-1)`
- Feature engineering: [`crypto_features_03_4h_target.ipynb`](notebooks/02_data_cleaning_features_engineering/crypto_features_03_4h_target.ipynb)
- Model: [`BTC_Xgboost_03_4h_target.ipynb`](notebooks/03_models/crypto/BTC_Xgboost_03_4h_target.ipynb)

## 3. Results — All Three Experiments

| Experiment            | Features           | Target | Accuracy   | Precision | Recall | F1     | Best CV |
| --------------------- | ------------------ | ------ | ---------- | --------- | ------ | ------ | ------- |
| **v1** (baseline)     | 29 tech indicators | 1h     | **0.5260** | 0.5150    | 0.5259 | 0.5204 | —       |
| **v2** (+OI/turnover) | 37 features        | 1h     | **0.5261** | 0.5281    | 0.5137 | 0.5208 | —       |
| **v3** (+OI/turnover) | 37 features        | **4h** | **0.5243** | 0.5284    | 0.5021 | 0.5149 | 0.5394  |

**Every result is within 0.2% of each other.** That's noise, not signal.

## 4. What We Learned

### The 52.6% Ceiling is Real

Three experiments, three different feature sets, two different target horizons — all converge to the same ~52.5% accuracy. This isn't a bug or a tuning problem. It's the market being efficient.

### The Model Keeps Picking the Simplest Config

In both v2 and v3, GridSearchCV selected `learning_rate=0.01, max_depth=3` as the best parameters. That's the shallowest, most conservative setting in our grid. The algorithm is essentially saying: _"there's no robust pattern here, so don't try to fit anything complex — you'll just overfit."_

The gap between CV score (53.94%) and test score (52.43%) in v3 confirms this: even the best pattern found during cross-validation doesn't generalize to unseen data.

### OI & Turnover Added Nothing

8 new features → 0.01% accuracy change. The market microstructure data we pulled from Bybit is:

- **Noisy** at 1h granularity (OI can spike for many reasons unrelated to direction)
- **Non-directional** (OI delta doesn't tell you which way price will move)
- Possibly more useful at **daily/weekly** horizons where accumulation/distribution patterns emerge — but we can't test that with hourly candles

### 4h Target is Actually Harder

52.43% at 4h vs 52.60% at 1h. Makes intuitive sense — more randomness accumulates over 4 hours than 1 hour. The further out you predict, the more noise dominates over any signal in technical indicators.

### The Original 29 Features Are the Ceiling

The 29 stationary technical indicators (SMA distances, MACD %, RSI, Bollinger %) are doing all the work. Adding OI, turnover, or changing the horizon didn't move the needle. The model has extracted everything there is to extract from price-derived features alone.

## 5. MLflow Runs

| Run                 | Experiment    | Accuracy |
| ------------------- | ------------- | -------- |
| `BTC_1h_XGBoost_v2` | v2 GridSearch | 0.5261   |
| `BTC_1h_4h_XGBoost` | v3 Baseline   | 5126     |
| `BTC_1h_4h_XGBoost` | v3 GridSearch | 0.5243   |

## 6. What We Want to Try Next

Since classification (UP/DOWN direction) is a dead end at ~52.6%, we should pivot strategy:

1. **Regression instead of classification** — Predict the _magnitude_ of the next return (continuous `target_4h` value) rather than just UP/DOWN. The model might capture _size of moves_ even if direction is coin-flip territory. RMSE as the metric instead of accuracy.

2. **Test on stocks (AAPL)** — Crypto may be uniquely noisy at intraday horizons. AAPL's 1h data might respond better because stock markets have more structural patterns (market open/close, institutional flows, earnings cycles).

3. **External features** — Bring in non-price data: BTC ETF flows, exchange reserves, stablecoin supply changes, or the macro table. Technical indicators alone have hit their limit — the next breakthrough needs fundamentally different information.
