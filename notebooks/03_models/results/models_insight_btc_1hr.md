**Date:** 2026-05-08

## 1. What we Did
 Built first set of machine learning models to predict if the Bitcoin 1-hour candle will close Up (1) or Down (0). To make sure track my experiments properly,  hooked everything up to  local MLflow container (running on port 5000 via Docker).

## 2. Results
- **Logistic Regression (Baseline):** `52.26% Accuracy`
- **Random Forest:** `51.97% Accuracy`
- **XGBoost:** `53.12% Accuracy`

## 3. What we Learned
- **Traditional ML vs. Finance ML:** At first, getting ~53% felt like a failing grade. But we learned that in Quantitative Finance, predicting efficient markets is incredibly hard. A mechanical 53.12% win rate on out-of-sample test data is actually a huge success (an "edge"). It proves my feature engineering (RSI, MACD, Bollinger Bands, etc.) actually works!
- **Why XGBoost Won:** Logistic Regression just draws straight lines. Random Forest tried to find complex patterns but got "scared" and over-predicted the Down trends (bad recall balance). XGBoost handled the noisy crypto data much better by learning from its mistakes sequentially.
- **Jupyter & Terminal Environments:**  fell into the "dual-environment trap"!  learned that just because I `pip install` something in my powershell terminal doesn't mean my Jupyter Notebook kernel automatically has it. The notebook runs on its own kernel.

## 4. What we Want to Try Next
Now that we have a working MLflow pipeline and a 53% baseline, in my next branch I want to:
1. **Hyperparameter Tuning:** Try Optuna to find the absolute best settings for XGBoost instead of just guessing the tree depth and learning rate.
2. **Look inside the Black Box:** Use SHAP values to figure out *which* of my custom features are actually helping XGBoost make its decisions so I can drop the useless ones.
3. **Set a Confidence Threshold:** See what happens if I force the model to only trade when it is >60% sure instead of 50.1% sure.