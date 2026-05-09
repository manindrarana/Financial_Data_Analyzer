**Date:** 2026-05-09

## 1. (Optuna)
Instead of manually typing in different settings for XGBoost and hitting "run" over and over, used Optuna. 

Optuna automatically ran 50 tests to find the absolute best mathematical settings.

## 2. (SHAP)
In algorithmic trading, you can't blindly trust an AI. Used a tool called SHAP to look inside the model.

SHAP showed me exactly *which* custom indicators the model was actually using to make its buy and sell decisions. This proves the model is trading based on logic, not just random noise.

## 3. (Thresholding)
Normally, a model makes a move if it is just 51% sure. But in crypto, exchange fees and slight price changes will destroy you if you trade on a coin-flip.

So forced the model to hold back and ONLY act when it was **58% sure**. It made way fewer trades, but win rate shot up to **54.99%**.

## 4. Model(MLflow)

Finally understand what MLOps is. Moodel isnt' stuck inside this Jupyter Notebook anymore. 

"registered" the final winning model into MLflow as `BTC_1h_Production_Model`.