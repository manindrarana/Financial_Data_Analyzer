# Financial Data Analyzer

Project involves both  **Data Engineering** and **Data Science** to analyze financial markets. The goal is to build a system that downloads stock/crypto data, cleans it, saves it securely, and then uses Machine Learning to predict future prices.

## How it Works

1. **Ingest**: Scripts download data from APIs and save it.
2. **Process**: The data is cleaned and formatted (removing errors, fixing dates).
3. **Store**: Clean data is saved into a local database for easy access.
4. **Analyze**: ML models (like ARIMA or LSTM) use this data to find trends.

## Project Structure

- **`configs/`**  
  Settings for the project, like API keys and database paths.

- **`data/`**  
  Where all the data is stored locally.
  - `raw/`: The original data downloaded from the internet.
  - `processed/`: Cleaned data ready for use.
  - `analytics/`: The final database used for charts and reporting.
  - `models/`: Saved AI models.

- **`notebooks/`**  
  Jupyter notebooks where I test ideas and visualize data before writing the final code.

- **`orchestration/`**  
  Contains the main scripts that run the whole pipeline automatically (e.g., download -> clean -> save).

- **`src/`**  
  The main source code for the project:
- `database/`: Code to connect to and manage the data storage layer.
  - `ingestion/`: Scripts to fetch data from APIs.
  - `processing/`: Code to clean and transform data.
  - `models/`: The Machine Learning logic for predictions.
  - `utils/`: Helper scripts (like logging).

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
    python orchestration/sample_orchestration.py
    ```

### Running with Docker
```bash
docker-compose up --build
```