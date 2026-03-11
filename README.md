# Financial Data Analyzer

Project involves both  **Data Engineering** and **Data Science** to analyze financial markets. The goal is to build a system that downloads stock/crypto data, cleans it, saves it securely, and then uses Machine Learning to predict future prices.

## How it Works (ELT pipeline)

1. **Extract (Ingestion)**: Scripts download historical data from Yahoo Finance and Bybit APIs, standardizing timezones and saving the raw data locally as `.parquet` files.
2. **Load (Storage)**: Raw Parquet files are loaded into a local **DuckDB** analytical database.
3. **Transform (Processing)**: In-database SQL transformations clean the data (removing duplicates and filtering 0/negative prices), cast all dates to a unified timezone-naive `TIMESTAMP` format, and enforce strict chronological ordering for time-series modeling.
4. **Analyze (Modeling)**: ML models (like ARIMA or LSTM) will use this clean data to find market trends.

## Architecture

The project uses a **Medallion Data Lake Architecture** with three layers stored in MinIO (S3-compatible storage):

### Data Layers

1. **Bronze Layer** (`s3://raw-data/`)  
   Raw JSON files from APIs, exactly as received then converted to the parquet and stored.

2. **Silver Layer** (`s3://processed-data/`)  
   Cleaned and validated data stored as Parquet files. Duplicates removed, schemas enforced, timestamps normalized.

3. **Gold Layer** (`s3://analytics-data/`)  
   Business-ready analytics table (`gold_financial_analytics.parquet`) with calculated metrics:
   - 7-day and 30-day moving averages (SMA)
   - Daily volatility
   - Ready for machine learning and dashboards


### Services

- **MinIO**: S3-compatible object storage (Ports: 9000 for API, 9001 for web console)
- **Python Pipeline**: Automated ELT orchestration (executes on startup + scheduled daily at 00:00 UTC)
- **Apache Superset**: Interactive BI dashboard for data visualization (Port: 8088)
- **DuckDB**: In-process analytical database for SQL transformations

## Project Structure

- **`configs/`**  
  Settings for the project, like API keys and database paths.

- **`notebooks/`**  
  Jupyter notebooks where test ideas and visualize data before writing the final code.

- **`orchestration/`**  
  Contains the main scripts that run the whole pipeline automatically (e.g., download -> clean -> save).

- **`scripts/`**
  Contains Python scripts for data analysis:
  - eda_ml.py: Checks data volume and readiness for ML.
  - top15_feat.py: Finds top 15 important features.
  - target_analysis.py: Analyzes the target variable (returns_1d).


- **`src/`**  
  The main source code for the project:
  - `ingestion/`: API configuration and Parquet extraction (`yahoo_finance.py`, `bybit_client.py`).
  - `database/`: DuckDB connection and loading logic (`loader.py`).
  - `processing/`: Data scaling, cleaning, and chronological transformation (`transformation.py`).
  - `models/`: The Machine Learning logic for predictions.
  - `utils/`: Helper scripts (like custom console logging).

- **`tests/`**  
  Simple tests to make sure the code is working correctly.

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
    python -m orchestration.orchestration
    ```

### Running with Docker
```bash
docker-compose up --build -d
```