# Financial Data Analyzer

Project involves both  **Data Engineering** and **Data Science** to analyze financial markets. The goal is to build a system that downloads stock/crypto data, cleans it, saves it securely, and then uses Machine Learning to predict future prices.

## How it Works (ELT pipeline)

1. **Extract (Ingestion)**: Scripts download historical data from Yahoo Finance and Bybit APIs, standardizing timezones and saving the raw data locally as `.parquet` files.
2. **Load (Storage)**: Raw Parquet files are loaded into a local **DuckDB** analytical database.
3. **Transform (Processing)**: In-database SQL transformations clean the data (removing duplicates and filtering 0/negative prices), cast all dates to a unified timezone-naive `TIMESTAMP` format, and enforce strict chronological ordering for time-series modeling.
4. **Analyze (Modeling)**: ML models (XGBoost) use this clean data to predict market direction.

## Architecture

The project uses a **Medallion Data Lake Architecture** with three layers stored in MinIO (S3-compatible storage):

### Data Layers

1. **Bronze Layer** (`s3://raw-data/`)  
   Raw JSON files from APIs, exactly as received then converted to the parquet and stored.

2. **Silver Layer** (`s3://processed-data/`)  
   Cleaned and validated data stored as Parquet files. Duplicates removed, schemas enforced, timestamps normalized.

3. **Gold Layer** (`s3://analytics-data/`)  
   Separate analytics tables for crypto and stocks (`gold_crypto_analytics`, `gold_stock_analytics`) with calculated features including moving averages, RSI, MACD, Bollinger Bands, VWAP, and technical indicators. Also includes feature tables and prediction tables. Ready for dashboards and ML.

### Services

- **MinIO**: S3-compatible object storage (Ports: 9000 for API, 9001 for web console)
- **Prefect**: Flow orchestration with task-level retries and checkpoint/resume recovery (Port: 4200)
- **Python Pipeline**: Automated ELT orchestration using Prefect (executes on startup + scheduled hourly)
- **Plotly Dash**: Interactive dashboard with 5 tabs — Price, Predictions, Backtest, Indicators, Data Explorer (Port: 8050)
- **Apache Superset**: Interactive BI dashboard for data visualization (Port: 8088)
- **MLflow**: ML experiment tracking (Port: 5000)
- **DuckDB**: In-process analytical database for SQL transformations

## Project Structure

- **`backtesting/`**  
  Walk-forward validation with trade simulation and performance metrics.

- **`configs/`**  
  Settings for the project, like API keys and database paths.

- **`dashboard/`**  
  Plotly Dash web application (`app.py`) with XGBoost predictor (`predictor.py`).

- **`notebooks/`**  
  Jupyter notebooks where test ideas and visualize data before writing the final code.

- **`orchestration/`**  
  Contains the main Prefect flow and checkpoint/resume logic that runs the whole pipeline automatically.

- **`scripts/`**
  Contains Python scripts for data analysis and model training:
  - `train_btc_model.py`: Trains XGBoost model for BTC.
  - `train_aapl_model.py`: Trains XGBoost model for AAPL.
  - `eda_ml.py`: Checks data volume and readiness for ML.
  - `top15_feat.py`: Finds top 15 important features.
  - `target_analysis.py`: Analyzes the target variable (returns_1d).

- **`src/`**  
  The main source code for the project:
  - `ingestion/`: API clients for Yahoo Finance (`yahoo_finance.py`) and Bybit (`bybit_client.py`).
  - `database/`: DuckDB loading (`loader.py`), dimensional modeling (`dimensions.py`), and fact tables (`facts.py`).
  - `processing/`: Data scaling, cleaning, and chronological transformation (`transformation.py`).
  - `models/`: Gold layer processor, technical indicators processor, and feature analyzer.
  - `utils/`: Helper scripts (like custom console logging).

- **`tests/`**  
  Simple tests to make sure the code is working correctly.

- **`reports/`**  
  Generated market and ML profile reports.

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
    python -m orchestration.orchestration --force     # Force full re-run (clears checkpoint)
    ```

### Running with Docker
```bash
docker-compose up --build -d
```