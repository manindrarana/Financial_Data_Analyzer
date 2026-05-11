**Date:** 2026-05-11

## What We Did
After spending days tuning our deep learning LSTM model, we decided to step back and try something simpler but powerful for tabular data: **XGBoost**. Since our data is made of columns and rows (technical indicators like RSI, moving averages), tree-based models like XGBoost are usually the heavy favorites in the financial world.

## Resutls
We ran the model on our newly cleaned, perfectly stationary dataset (`train_btc_1h.parquet`) and the results blew us away:
*   **Baseline Accuracy:** We hit **52.81%** on our very first try without even tuning it!
*   **Grid Search (Tuning):** We ran a massive grid search testing 108 different combinations of parameters. Thanks to utilizing our **GPU** (`device='cuda'`), it finished in just 1 minute and 18 seconds. It found that a very shallow tree (`max_depth=3`) was the most stable, giving us a final score of **52.60%**.


### . xgboost beats lstm
Our LSTM got stuck at 51.3%. XGBoost comfortably beat it out of the box. This proves the rule of thumb we learned: Neural Networks are great for images and text, but Decision Trees are best for tabular data

### . Feature Engineering worked
Unlike the LSTM, XGBoost actually tells us *how* it makes decisions. When we plotted the Feature Importances, the #1 most important feature was **`sma_7_dist`** (making up over 13% of the decision weight!). 
This `sma_7_dist` is a feature **we manually created** to make the price data stationary (calculating the percentage distance from the moving average).
