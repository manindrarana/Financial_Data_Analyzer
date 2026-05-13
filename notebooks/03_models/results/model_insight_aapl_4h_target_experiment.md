**Date:** 2026-05-13
**Branch:** `80-experiment4-hour-time-horizon-target-shifting-for-improving-accuracy`

## What We Tried

Our 1-hour direction models hit a ceiling of ~53-54%. We hypothesized that predicting the **4-hour direction** (using 1-hour features) might reduce market "noise" and improve accuracy. The idea was:
- 1-hour moves are random and noisy
- 4-hour moves are driven by bigger institutional trends
- Same data, same features — just change the target from `shift(-1)` to `shift(-4)`

**Key change in feature engineering:**
```python
# Before (1h)
df['target_1h'] = df['close'].pct_change(1).shift(-1)

# After (4h experiment)
df['target_4h'] = df['close'].pct_change(4).shift(-4)
```

## The Results

| Run | Accuracy | vs 1h Baseline |
|-----|----------|----------------|
| 1h Baseline (original champion) | 53.38% | — |
| **4h Baseline (this experiment)** | **48.41%** | -4.97% WORSE |
| 4h Tuned (GPU Grid Search) | 50.72% | -2.66% WORSE |

**The 4-hour target made the model worse than a coin flip (48.4%).**

## Why It Got Worse — The Feature-Target Mismatch

This result teaches us a very important lesson: **the features and the target must be "compatible" in time.**

All 29 of our features (RSI, MACD, SMA distances, etc.) describe what is happening **right now** at this exact hour. They were designed and validated to predict what happens in the **next 1 hour**.

When we asked the model to predict 4 hours into the future using only current-hour features, we created a mismatch. The model is like someone looking at the current weather and trying to predict the weather 4 hours later. Too many things can change in between — earnings news, macro announcements, whale orders — that have nothing to do with the current RSI value.

## The Grid Search Collapse

The tuned model report revealed a complete collapse:
```
Class 0 (Down): precision 0.20, recall 0.00  ← Model gave up on predicting DOWN entirely
Class 1 (Up):   precision 0.51, recall 0.99  ← Just predicted UP for everything
```
When a model predicts only one class, it means the signal is too weak. There is no learnable pattern connecting 1-hour indicators to 4-hour outcomes with our dataset size (only 3,472 rows).

## What Would Actually Work for a 4h Model

To properly predict 4-hour moves, we would need:
1. **4-hour candle data** — features calculated on 4h bars, not 1h bars
2. **More rows** — AAPL only has 3,473 hourly rows (≈ 868 four-hour bars), which is far too little
3. **Multi-timeframe stacking** — combine 1h features AND 4h features simultaneously

## Conclusion

The experiment is officially closed. The **1-hour direction model remains the optimal approach** for our current dataset. The 4-hour target shift is a scientifically proven dead-end for AAPL hourly data.

**Updated Model Leaderboard:**

| Asset | Model | Best Accuracy | Status |
|-------|-------|--------------|--------|
| AAPL 1h | XGBoost + Confidence Filter | **54.06%** | best so far |
| BTC 1h | XGBoost Baseline | 52.81% | |
| BTC 1h | LSTM | 51.30% | |
| AAPL 4h target | XGBoost | 48.41% |  Failed experiment |
