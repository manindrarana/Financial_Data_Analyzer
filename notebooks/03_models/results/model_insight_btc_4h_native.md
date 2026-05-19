**Date:** 2026-05-19

## 1. What We Did — Native 4h Candles (v4)

After v3's derived 4h target (1h candles shifted by 4 periods) produced 0.5243 — slightly below the 52.6% ceiling — we tested whether **true 4h candles** from the exchange could capture signal better than mathematically derived ones.

- FE notebook: [`crypto_features_04_4hnative_target.ipynb`](notebooks/02_data_cleaning_features_engineering/crypto_features_04_4hnative_target.ipynb)
- Model notebook: [`BTC_Xgboost_native4h.ipynb`](notebooks/03_models/crypto/BTC_Xgboost_native4h.ipynb)
- Target: `target_4h = close.pct_change(1).shift(-1)` on true 4h candles (native), not `pct_change(4).shift(-4)` on 1h candles (derived)
- **open_interest is 100% NULL at 4h granularity** — Bybit's OI endpoint doesn't align with 4h klines. We skipped OI features and used 33 features (29 core + 4 turnover, no OI)
- 13,224 total rows → 10,579 train / 2,645 test (4x fewer than 1h experiments due to 4h candle spacing)
- 216-candidate GridSearchCV, 3-fold CV, CUDA-accelerated

## 2. Results — All Four Experiments

| Experiment                 | Data Source     | Features       | Target       | Accuracy   | Precision | Recall | F1     | Best CV |
| -------------------------- | --------------- | -------------- | ------------ | ---------- | --------- | ------ | ------ | ------- |
| **v1** (baseline)          | 1h candles      | 29 indicators  | 1h           | **0.5260** | 0.5150    | 0.5259 | 0.5204 | —       |
| **v2** (+OI/turnover)      | 1h candles      | 37 features    | 1h           | **0.5261** | 0.5281    | 0.5137 | 0.5208 | —       |
| **v3** (derived 4h)        | 1h candles      | 37 features    | derived 4h   | **0.5243** | 0.5284    | 0.5021 | 0.5149 | 0.5394  |
| **v4** (native 4h, tuned)  | **4h candles**  | 33 features    | **native 4h**| **0.5274** | 0.5245    | 0.5982 | 0.5589 | 0.5486  |

**v4 native 4h baseline (untuned): 0.5183** — weakest untuned model yet due to fewer rows and no OI features. GridSearch recovered it to 0.5274 (+0.0091).

**0.5274 is the highest accuracy across all four experiments.** It beats v2 (0.5261) by +0.0013 and v3 (0.5243) by +0.0031.

## 3. What We Learned

### Native 4h → Slightly Better Than Derived 4h

True 4h candles (0.5274) outperform derived 4h from 1h candles (0.5243) by +0.31%. The native candles eliminate the synthetic 4-period compounding from 1h → 4h derivation. Small but directionally consistent.

### The 52.6% Ceiling Still Holds

Four experiments, four different data configurations — all converge within 0.31% of each other. The gain from native 4h is real but tiny. The signal-to-noise ratio of BTC intraday price data hasn't fundamentally changed.

### GridSearch Compensates for Smaller Data

v4 baseline (0.5183) was the worst untuned model — 10,579 rows and no OI features hurt out of the box. But GridSearch recovered it to the best-tuned model. With fewer samples, parameter selection matters more, not less.

### Same Config Again

GridSearch picked `learning_rate=0.01, max_depth=3` — the shallowest configuration in the grid. This is the **third experiment in a row** where the algorithm says: "don't fit complex patterns, you'll overfit." The CV-Test gap (-2.12%, from 0.5486 → 0.5274) confirms the pattern doesn't generalize.

### OI is Useless at 4h Anyway

open_interest being 100% NULL at 4h didn't matter — v3 had OI and got 0.5243, v4 skipped it and got 0.5274. OI features never contributed to BTC directional prediction at any timeframe.

## 4. Next Steps

1. **Confidence thresholding** — Filter predictions by `predict_proba()` confidence. None of v1-v4 used thresholding, so it's a free experiment.
2. **Regression** — Predict magnitude (continuous `target_4h`) instead of direction. RMSE as metric.
3. **External features** — Technical indicators alone have hit their ceiling. BTC ETF flows, exchange reserves, macro data.