# Financial Data Analyzer

Project involves both  **Data Engineering** and **Data Science** to analyze financial markets. The goal is to build a system that downloads stock/crypto data, cleans it, saves it securely, and then uses Machine Learning to predict future prices.

## How it Works (ELT pipeline)

1. **Extract (Ingestion)**: Scripts download historical data from Yahoo Finance and Bybit APIs, standardizing timezones and saving the raw data locally as `.parquet` files.
2. **Load (Storage)**: Raw Parquet files are loaded into a local **DuckDB** analytical database.
3. **Transform (Processing)**: In-database SQL transformations clean the data (removing duplicates and filtering 0/negative prices), cast all dates to a unified timezone-naive `TIMESTAMP` format, and enforce strict chronological ordering for time-series modeling.
4. **Analyze (Modeling)**: ML models (like ARIMA or LSTM) will use this clean data to find market trends.

## Project Structure

- **`configs/`**  
  Settings for the project, like API keys and database paths.

- **`data/`**  
  Where all data is stored locally (ignored by Git):
  - `raw/`: The original extracted `.parquet` data.
  - `processed/`: Saved flat files of cleaned data.
  - `analytics/`: The DuckDB database `financial_data.duckdb`.
  - `models/`: Saved AI/ML models.

- **`notebooks/`**  
  Jupyter notebooks where test ideas and visualize data before writing the final code.

- **`orchestration/`**  
  Contains the main scripts that run the whole pipeline automatically (e.g., download -> clean -> save).

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