# Financial Data Analyzer

Project involves both  **Data Engineering** and **Data Science** to analyze financial markets. The goal is to build a system that downloads stock/crypto data, cleans it, saves it securely, and then uses Machine Learning to predict future prices.

## How it Works (8-step ELT pipeline)

1. **Extract**: Yahoo Finance and Bybit APIs run concurrently, fetching historical OHLCV data plus Open Interest and Funding Rate for crypto, saving to MinIO (S3) as Parquet files.
2. **Load**: DuckDB reads raw Parquet files from MinIO into staging tables (`yahoo_stocks`, `bybit_crypto`).
3. **Clean**: Removes duplicates, filters invalid prices, normalizes timestamps, enforces chronological ordering → `clean_*` tables.
4. **Dimensions**: Builds a star schema (`dim_assets`, `dim_dates`) for analytical querying.
5. **Facts**: Loads cleaned data into `fact_price_history` from the silver layer.
6. **Gold Analytics**: Aggregates analytics (daily volatility, moving averages) → `gold_crypto_analytics`, `gold_stock_analytics`.
7. **Technical Indicators**: Computes 30+ indicators (RSI, MACD, ATR, Bollinger Bands, VWAP, OBV, etc.) → `gold_crypto_features`, `gold_stock_features`.
8. **Model Training**: `PipelineModelTrainer` auto-discovers all asset×interval combos from `settings.yml`, applies stationarity transformations (SMA/EMA distances, MACD/ATR as % of close) via `src/models/feature_engineering.py`, and trains one XGBoost model per combo. Saves to `src/models/crypto/` and `src/models/stocks/`.

The pipeline uses **checkpoint/resume** — if it crashes mid-run, restarting skips completed steps. Use `--force` to clear checkpoints and run all steps fresh. Use `--once` for a single run (vs. the default hourly schedule).

## Architecture

The project uses a **Medallion Data Lake Architecture** with three layers stored in MinIO (S3-compatible storage):

### Data Layers

1. **Bronze Layer** (`s3://raw-data/`)  
   Raw JSON files from APIs, exactly as received then converted to the parquet and stored.

2. **Silver Layer** (`s3://processed-data/`)  
   Cleaned and validated data stored as Parquet files. Duplicates removed, schemas enforced, timestamps normalized.

3. **Gold Layer** (`s3://analytics-data/`)  
   Separate analytics tables for crypto and stocks (`gold_crypto_analytics`, `gold_stock_analytics`) with calculated features including moving averages, RSI, MACD, Bollinger Bands, VWAP, and technical indicators. Also includes feature tables used for ML training. Ready for dashboards and ML.

### Services

- **MinIO**: S3-compatible object storage (Ports: 9000 for API, 9001 for web console)
- **Prefect**: Flow orchestration with task-level retries and checkpoint/resume recovery (Port: 4200)
- **Python Pipeline**: Automated ELT orchestration using Prefect (executes on startup + scheduled hourly)
- **Plotly Dash**: Interactive dashboard with 9 tabs — Overview, Price Dashboard, Predictions, Backtest, Technical Indicators, Data Explorer, Model Health, Model Insights, Pipeline History (Port: 8050)
- **MLflow**: ML experiment tracking (Port: 5000)
- **DuckDB**: In-process analytical database for SQL transformations

### Model Training

- **Per-asset, per-interval models**: Separate XGBoost models for each combination (e.g., BTC 1h, BTC 4h, AAPL 1h, AAPL 1d). `PipelineModelTrainer` reads `settings.yml` and auto-discovers all combos.
- **Stationarity transforms**: Raw indicators (SMA, EMA, MACD) are non-stationary. `make_stationary()` in `src/models/feature_engineering.py` converts them to distance-from-close ratios, making features comparable across price levels.
- **Walk-forward backtesting**: `backtesting/walk_forward.py` validates models by walking a 6-month training window forward month-by-month, retraining on each fold to mirror real-world periodic retraining.

## Project Structure

- **`backtesting/`**  
  Walk-forward validation with trade simulation and performance metrics.

- **`configs/`**  
  Settings for the project, like API keys and database paths.

- **`dashboard/`**
  Plotly Dash web application (`app.py`) with XGBoost predictor (`predictor.py`) and model health monitoring (`model_health.py`).

- **`notebooks/`**  
  Jupyter notebooks where test ideas and visualize data before writing the final code.

- **`orchestration/`**  
  Contains the main Prefect flow and checkpoint/resume logic that runs the whole pipeline automatically.

- **`scripts/`**
  Manual and research scripts (not used by the main pipeline):
  - `investigate_funding.py`: Investigates and backfills historical funding-rate coverage for all configured Bybit assets.
  - `run_funding_rate_experiment.py`: Leakage-safe funding feature experiment with accuracy significance tests and cost-aware backtest variant comparison.
  - `run_cross_asset_experiment.py`: Leakage-safe cross-asset feature experiment comparing baseline and cross-asset variants.
  - `run_feature_ablation.py`: Controlled BTC 1h feature-ablation experiment (auto-refreshed after BTC 1h retraining by orchestration).
  - `compare_model_families.py`: BTC 1h model-family comparison across XGBoost, Logistic Regression, and Random Forest (auto-refreshed after BTC 1h retraining by orchestration).
  - `compare_multitimeframe_models.py`: BTC 1h/4h multi-timeframe comparison with ensemble metrics (auto-refreshed after BTC 1h/4h retraining by orchestration).
  - `build_macro_table.py`: Builds the macroeconomic table from FRED data.
  - `data_health_check.py`: Checks data quality and coverage per asset and interval.
  - `data_profiler.py`: Profiles raw market data for volume and readiness.
  - `ml_profiler.py`: Profiles ML training data and feature distributions.
  - `generate_figures.py`: Generates report figures from backtest and model results.
  - `inspect_bybit_api.py`: Inspects raw Bybit API responses for debugging ingestion.
  - Legacy training scripts (superseded by `PipelineModelTrainer`):
    `train_all_models.py`, `train_btc_model.py`, `train_aapl_model.py`, `eda_ml.py`, `top15_feat.py`, `target_analysis.py`.

- **`src/`**  
  The main source code for the project:
  - `ingestion/`: API clients for Yahoo Finance (`yahoo_finance.py`) and Bybit (`bybit_client.py`).
  - `database/`: DuckDB loading (`loader.py`), dimensional modeling (`dimensions.py`), and fact tables (`facts.py`).
  - `processing/`: Data scaling, cleaning, and chronological transformation (`transformation.py`).
  - `models/`: Gold layer processor, technical indicators processor, feature analyzer, and shared feature engineering (`feature_engineering.py`).
  - `utils/`: Helper scripts (like custom console logging).

- **`tests/`**  
  Simple tests to make sure the code is working correctly.

- **`reports/`**
  Generated reports: market and ML profiles, funding coverage and experiment results, feature ablation, model-family and multi-timeframe comparisons.

## how to Run

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Set up virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Configure Environment:**
    Rename `.env.example` to `.env` and add API keys.

4. **Run the pipeline:**
    ```bash
    python -m orchestration.orchestration             # Normal run (resumes from checkpoint)
    python -m orchestration.orchestration --once       # Single run (no hourly schedule)
    python -m orchestration.orchestration --force      # Force full re-run (clears checkpoint)
    ```

### Running with Docker
```bash
docker-compose up --build -d                           # Start all services (pipeline runs hourly)
docker exec financial_data_pipeline python -m orchestration.orchestration --once   # Single manual run
docker exec financial_data_pipeline python -m orchestration.orchestration --force  # Force full re-run
```