## Asset: BTC | Interval: 1h
**Date:** 2026-05-07
* **Data Quality:** is clean. 53,396 rows. Missing values are only at the very beginning (due to technical indicator lookback periods). safe to drop.
* **Target Distribution:** `returns_1d` has extreme Kurtosis (>50). we have "fat tails" meaning extreme outliers happen often. 
* **Correlations:** `rsi_14` and `stoch_k` are our strongest positive predictors. `volume_ratio` also shows some signal.
* **Time-Series Memory:** the data is perfectly Stationary (raw returns drop to 0 autocorrelation instantly). autocorrelation of absolute returns shows Volatility Clustering. 
* **Conclusion for Feature Engineering:** data must be chronologically split, not shuffled. we must use `returns_1d` as the target, not `close` price.