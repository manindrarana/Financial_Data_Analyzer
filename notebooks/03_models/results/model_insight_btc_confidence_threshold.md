**Date:** 2026-05-20

## 1. What We Did — Confidence Thresholding on v4 Native 4h

After v4 native 4h XGBoost achieved 52.74% accuracy (the highest across all four BTC experiments), we tested whether filtering predictions by model confidence (`predict_proba`) could improve effective accuracy — even if it meant making fewer predictions.

- Model notebook: [`BTC_Xgboost_05_confidence_threshold.ipynb`](notebooks/03_models/crypto/BTC_Xgboost_05_confidence_threshold.ipynb)
- Source model: v4 native 4h (best params from GridSearchCV)
- Data: 10,579 train / 2,645 test (same as v4)
- Approach: Retrain v4 model, compute `np.max(predict_proba, axis=1)` for each test sample, sweep 11 thresholds from 0.50 to 0.70, measure accuracy on predictions above each threshold
- MLflow experiment: `BTC_4h_confidence_threshold` (ID 20)

## 2. Results

| Threshold | Accuracy | Coverage (rows) | Coverage (%) | Δ vs Baseline |
|-----------|----------|-----------------|--------------|---------------|
| 0.50 (all)| 0.5274   | 2,645           | 100.0%       | 0.0000        |
| 0.52      | 0.5447   | 1,612           | 60.9%        | **+0.0173**   |
| 0.54      | 0.5441   | 873             | 33.0%        | +0.0167       |
| 0.56      | 0.5263   | 437             | 16.5%        | -0.0011       |
| 0.58      | 0.6667   | **15**          | 0.6%         | +0.1393       |
| 0.60+     | 0.0000   | 0               | 0.0%         | —             |

**Best practical threshold: ≥0.52 → 54.47% on 60.9% coverage (1,612 rows).**
**"Best" by raw accuracy: ≥0.58 → 66.67% but only 15 predictions — statistically meaningless.**

Precision improves at ≥0.52 (0.5440) and ≥0.54 (0.5444), with recall surging to 0.9058 at ≥0.54 — the model is more confident when predicting UP correctly. But above 0.56, the model effectively stops making predictions.

## 3. What We Learned

### The Model is Not Well-Calibrated

Probability estimates cluster tightly around 0.50-0.54. Only 437 of 2,645 predictions (16.5%) exceed 0.56 confidence. This means the model itself "knows" it's uncertain — and it's right. When forced to predict everything, it's a coin flip; when allowed to be selective, it has almost nothing to select.

### Marginal Gain at 0.52 is Real but Small

Filtering at ≥0.52 gives +1.73% accuracy on 61% of trades. This is directionally useful — you'd be slightly better off only trading when the model is above-median confidence. But 54.47% is still barely above random, and you're sacrificing 39% of potential trades for a 1.7% edge.

### Confidence Thresholding Cannot Break the 52.6% Ceiling

The problem is not that we're predicting too many uncertain trades — it's that the model cannot reliably distinguish signal from noise at any confidence level. If the features contained strong predictive signal, high-confidence predictions would be abundant AND accurate. They're neither.

### The "Best" Threshold is a Trap

0.58 shows 66.67% accuracy because only 15 predictions survived — all of them correct by chance. This is a textbook example of why coverage matters more than raw accuracy in threshold analysis. A threshold with <1% coverage is not a strategy; it's survivorship bias.

### Consistent with All Four Experiments

v1 (0.5260), v2 (0.5261), v3 (0.5243), v4 (0.5274), and now confidence-thresholded v4 (0.5447 max practical) — five experiments, five different approaches, and the best we can extract is ~54.5% on a filtered subset. The ~52.6% accuracy ceiling on BTC directional prediction is now supported by **five independent experiments**.

## 4. Next Steps

1. **Multi-timeframe ensemble** — Combine 1h and 4h model predictions. Different timeframes may capture different patterns.
2. **Feature ablation** — Which of the 33 features actually contribute? Many may be noise.
3. **Regression (magnitude prediction)** — Direction may be inherently noisy; predicting the size of the next move could yield better signal-to-noise.
4. **External features** — Technical indicators alone have hit their limit across five experiments. BTC ETF flows, on-chain data, or macro variables are likely needed for a breakthrough.