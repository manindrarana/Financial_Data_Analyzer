# LSTM Raw OHLCV -- Experiment Results (FAILED)
**Date:** 2026-05-22

## 1. What We Did

Tested whether an LSTM trained on **raw OHLCV log-return sequences** (5 features, 20x4h candles) could outperform the old LSTM trained on 29 engineered technical indicators (51.30%).

- **Model notebook:** [`BTC_lstm_02_raw_ohlcv.ipynb`](../notebooks/03_models/deep_learning/BTC_lstm_02_raw_ohlcv.ipynb)
- **FE notebook:** [`crypto_features_05_lstm_raw_ohlcv.ipynb`](../notebooks/02_data_cleaning_features_engineering/crypto_features_05_lstm_raw_ohlcv.ipynb)
- **FE Insight:** [`fe_insight_btc_lstm_raw_ohlcv.md`](../notebooks/02_data_cleaning_features_engineering/results/fe_insight_btc_lstm_raw_ohlcv.md)
- **MLflow experiment:** `BTC_4h_deep_learning` (ID 21), run `LSTM_raw_OHLCV_BTC_4h_seq20`
- **Data:** 10,619 train / 2,655 test, 51.28%/48.72% class balance, 5 log-return features

## 2. Configuration (Identical to Old LSTM for Fair Comparison)

| Parameter | Value |
|-----------|-------|
| Architecture | LSTM(64)->Drop(0.4)->LSTM(32)->Drop(0.2)->Dense(16,relu)->Drop(0.2)->Dense(1,sigmoid) |
| Trainable params | 30,881 |
| Optimizer | Adam(lr=0.0001) |
| Loss | binary_crossentropy |
| Epochs | 50 |
| Batch size | 64 |
| EarlyStopping | patience=15, monitor=val_loss, restore_best_weights |
| Validation split | 20% |

## 3. Training Behavior -- Complete Failure to Learn

| Metric | Value |
|--------|-------|
| Best epoch | 4 |
| Stopped at | Epoch 19 |
| Val accuracy (all epochs) | **51.93% -- flatlined** |
| Val loss | 0.6928 -> 0.6925 (negligible change) |

The validation accuracy locked at **51.93% from epoch 1 through epoch 19** -- zero learning occurred. The loss barely moved (0.0003 decrease over 19 epochs). This is textbook "model cannot find any signal."

## 4. Test Results

| Metric | Value |
|--------|-------|
| **Accuracy** | **50.09%** |
| Precision | 50.09% |
| Recall | **100.00%** |
| F1 Score | 66.75% |
| Loss | 0.6934 |

### Classification Report

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| DOWN (0) | **0.00** | **0.00** | **0.00** | 1,325 |
| UP (1) | 0.50 | 1.00 | 0.67 | 1,330 |

### Confusion Matrix

| | Predicted DOWN | Predicted UP |
|---|:-:|:-:|
| **Actual DOWN** | **0** (TN) | 1,325 (FP) |
| **Actual UP** | 0 (FN) | **1,330** (TP) |

- TPR (Recall): 1.0000 -- caught every UP correctly
- TNR (Specificity): **0.0000** -- caught ZERO DOWN correctly

### Complete Degenerate Collapse

The model predicted **every single test sample as UP**. Not a single DOWN prediction across 2,655 test samples. This is the worst possible failure mode:

- The model learned nothing about what distinguishes UP from DOWN
- It converged to the trivial solution: predict the majority class always
- Binary cross-entropy loss (0.6934) is essentially at the random baseline of -ln(0.5) = 0.6931
- The LSTM weights effectively encode "output ~0.51 sigmoid on any input"

This is not "bad performance" -- it's **total failure**. The model is functionally equivalent to `np.ones(2655)`.

## 5. Comparison

| Model | Features | Accuracy | Notes |
|-------|----------|----------|-------|
| Old LSTM | 29 engineered indicators | **51.30%** | 1h candles, 6 timesteps |
| **Experiment #97** | **5 raw log-returns** | **50.09%** | 4h candles, 20 timesteps |
| -- | -- | ** -1.21pp** | Worse than old LSTM |

**Raw OHLCV log-returns performed WORSE than engineered indicators for LSTM.** This refutes the hypothesis that raw price sequences would better leverage LSTM's temporal pattern recognition.

## 6. Why It Failed

### Zero Information in Raw Log-Returns
Log returns of OHLCV data are essentially white noise at the 4h timeframe. The mean is ~0.00017 with std ~0.012 -- the signal-to-noise ratio is near zero. The LSTM had nothing to latch onto.

### Indicators Encode Useful Structure
The old LSTM's 29 engineered features (RSI, MACD, Bollinger Bands, etc.) encode non-linear transformations that capture overbought/oversold states, momentum, and volatility regimes. Even though these are "tabular," they contain processed signal that raw prices don't surface.

### Degenerate Collapse
The model converged to the trivial solution: predict the majority class (UP) on every sample. This is a well-known failure mode of neural networks on noisy binary classification -- the path of least resistance is to output ~0.51 on every prediction, which minimizes binary cross-entropy given no real signal.

### Validation Loss Never Moved
0.6928 -> 0.6925 over 19 epochs is essentially zero improvement. A healthy model on this problem would drop below 0.69 within a few epochs. The flat validation curve is the clearest evidence of complete signal absence.

## 7. What We Learned

### LSTM Needs Structure, Not Raw Data
The LSTM architecture is powerful, but it needs *informative* sequential input. Raw OHLCV log-returns are too noisy -- the model can't extract temporal patterns from 20 candles of near-random walk data. Engineered features (even tabular ones) provide more usable signal because they encode domain knowledge about what matters.

### 5 Features vs 29: Dimensionality Matters
The old LSTM had 29 features feeding into 64 LSTM units -- a rich input space. This experiment had only 5 features, making it harder for the LSTM to find any combination that distinguishes UP from DOWN.

### Log-Returns Alone Are Insufficient
Log-returns successfully solved stationarity (mean~0, std~0.012), but stationarity alone doesn't create predictive signal. The price series after log-differencing is essentially a martingale difference sequence -- by definition, it should be unpredictable.

### This Experiment Was Still Valuable
Negative results are results. We now have **conclusive evidence** that:
1. Raw price sequences -> LSTM = 50.09% (worse than coin flip baseline)
2. Engineered indicators -> LSTM = 51.30% (slightly above coin flip but below XGBoost)
3. Engineered indicators -> XGBoost = 52.81% (best we've achieved)

The hierarchy is now firmly established: **XGBoost + indicators > LSTM + indicators > LSTM + raw prices**.

## 8. Conclusion

**Experiment is a FAILURE.** Raw OHLCV log-return sequences cannot train a useful LSTM for BTC directional prediction at the 4h timeframe. The hypothesis was sound (LSTM's strength is sequential data -> give it raw sequences), but the data contained no learnable signal.

The LSTM chapter of this project is now closed with two data points:
- Engineered features: 51.30% (marginal)
- Raw log-returns: 50.09% (failure)

## 9. Next Steps

1. ~~LSTM + raw OHLCV~~  Tested -- failed at 50.09%
2. ~~LSTM + XGBoost hybrid~~  Cancelled -- Step 1 failed, Step 2 not justified
3. Multi-timeframe XGBoost ensemble (1h + 4h combined predictions)
4. External features: BTC ETF flows, on-chain data, macro variables
5. Regression approach: predict magnitude instead of direction
6. Walk-forward validation to test model stability over time