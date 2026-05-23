import duckdb
import yaml
import os
import pandas as pd
import numpy as np
import xgboost as xgb
from dotenv import load_dotenv
from src.utils import get_logger


class ModelPredictor:
    """Loads trained XGBoost model and generates predictions on Gold layer data"""

    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()

        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)

        self.db_path = self.config["paths"]["database"]
        self.models_dir = self.config["paths"].get("models", "data/models")
        self.analytics_bucket = self.config["paths"].get("analytics_bucket", "analytics-data")
        self.conn = duckdb.connect(self.db_path)

        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000").replace("http://", "")
        self.conn.execute("INSTALL httpfs; LOAD httpfs;")
        self.conn.execute(f"""
            CREATE SECRET IF NOT EXISTS (
                TYPE S3,
                KEY_ID '{os.getenv("AWS_ACCESS_KEY_ID")}',
                SECRET '{os.getenv("AWS_SECRET_ACCESS_KEY")}',
                ENDPOINT '{s3_endpoint}',
                URL_STYLE 'path',
                USE_SSL false
            );
        """)

    def load_model(self, asset: str, interval: str):
        """Load a saved XGBoost model from JSON file"""
        model_filename = f"{asset}_{interval}_xgboost_model.json"
        model_path = os.path.join(os.path.dirname(__file__), model_filename)

        if not os.path.exists(model_path):
            self.logger.error(f"Model file not found: {model_path}")
            self.logger.info("Re-run BTC_xgboost.ipynb to save the model first")
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.logger.info(f"Loading model from: {model_path}")
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        return model

    def _make_stationary(self, df):
        """
        Convert raw price-scale indicators to stationary percentages,
        matching exactly what crypto_features_01.ipynb does (lines 781-850).

        The XGBoost model was trained on stationary features like sma_50_dist
        (close/sma_50 - 1), not raw sma_50. Without this conversion, the model
        receives completely different feature names and scales.
        """
        self.logger.info("Converting raw indicators to stationary features...")

        meta_cols = [c for c in ['asset_symbol', 'asset_class', 'exchange', 'interval', 'date']
                     if c in df.columns]
        meta = df[meta_cols].copy()

        distance_pairs = [
            ('sma_7', 'sma_7_dist'),
            ('sma_30', 'sma_30_dist'),
            ('sma_50', 'sma_50_dist'),
            ('sma_100', 'sma_100_dist'),
            ('sma_200', 'sma_200_dist'),
            ('ema_12', 'ema_12_dist'),
            ('ema_26', 'ema_26_dist'),
            ('ema_50', 'ema_50_dist'),
            ('ema_200', 'ema_200_dist'),
            ('vwap', 'vwap_dist'),
        ]
        for raw_col, dist_col in distance_pairs:
            if raw_col in df.columns:
                df[dist_col] = df['close'] / df[raw_col] - 1

        ratio_pairs = [
            ('macd', 'macd_pct'),
            ('macd_signal', 'macd_sig_pct'),
            ('macd_histogram', 'macd_hist_pct'),
            ('atr_14', 'atr_pct'),
            ('daily_volatility', 'volatility_pct'),
        ]
        for raw_col, pct_col in ratio_pairs:
            if raw_col in df.columns:
                df[pct_col] = df[raw_col] / df['close']

        non_stationary_cols = [
            'open', 'high', 'low', 'close',
            'sma_7', 'sma_30', 'sma_50', 'sma_100', 'sma_200',
            'ema_12', 'ema_26', 'ema_50', 'ema_200',
            'vwap', 'prev_close', 'prev_high', 'prev_low',
            'macd', 'macd_signal', 'macd_histogram',
            'atr_14', 'daily_volatility',
            'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
            'volume', 'prev_volume', 'volume_sma_20',
            'obv',
        ]
        df = df.drop(columns=[c for c in non_stationary_cols if c in df.columns], errors='ignore')

        for col in meta_cols:
            df[col] = meta[col]

        self.logger.info(
            f"Stationarity complete: {len(df.columns)} columns "
            f"(~29 features + meta, matching model expectations)"
        )
        return df

    def predict(self, asset: str = "BTC", interval: str = "1h"):
        """Run prediction on Gold layer data for a given asset and interval"""
        self.logger.info("=" * 60)
        self.logger.info(f"Running predictions for {asset} ({interval})")
        self.logger.info("=" * 60)

        model = self.load_model(asset, interval)
        feature_names = model.get_booster().feature_names
        self.logger.info(f"Model expects {len(feature_names)} features: {feature_names[:5]}...")

        crypto_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT",
                          "LTCUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "DYDXUSDT",
                          "1000PEPEUSDT"]
        asset_class = "crypto" if asset in crypto_symbols or asset in ["BTC", "ETH", "SOL"] else "stock"
        table_name = f"gold_{asset_class}_features"

        cnt = self.conn.execute(
            f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
        ).fetchone()[0]
        if cnt == 0:
            self.logger.error(f"Table {table_name} not found. Run the pipeline first.")
            return

        self.logger.info(f"Reading data from {table_name} for {asset} ({interval})...")
        df = self.conn.execute(f"""
            SELECT * FROM {table_name}
            WHERE UPPER(asset_symbol) = UPPER('{asset}')
              AND interval = '{interval}'
            ORDER BY date
        """).df()

        if len(df) == 0:
            self.logger.error(f"No data found for {asset} ({interval}) in {table_name}")
            return

        self.logger.info(f"Loaded {len(df)} rows")

        close_prices = df['close'].copy()

        df = self._make_stationary(df)

        meta_cols = ['asset_symbol', 'asset_class', 'exchange', 'interval', 'date']

        available_features = [f for f in feature_names if f in df.columns]
        missing_features = [f for f in feature_names if f not in df.columns]

        if missing_features:
            self.logger.warning(f"Missing {len(missing_features)} features: {missing_features}")
            self.logger.warning("Predictions may be inaccurate if key features are missing")

        X = df[available_features].copy()

        valid_idx = X.dropna().index
        n_dropped = len(X) - len(valid_idx)
        if n_dropped > 0:
            self.logger.info(
                f"Dropping {n_dropped} rows with NaN features "
                f"({len(valid_idx)}/{len(X)} rows remain for prediction)"
            )
        X = X.loc[valid_idx]
        df = df.loc[valid_idx]

        self.logger.info(f"Running prediction on {len(X)} rows with {len(available_features)} features...")

        predictions = model.predict(X)
        probabilities = model.predict_proba(X)

        pred_class_indices = np.argmax(probabilities, axis=1)
        confidence = probabilities[np.arange(len(probabilities)), pred_class_indices]

        pred_labels = np.where(predictions == 1, "UP", "DOWN")

        self.logger.info(f"Predicted UP: {np.sum(predictions == 1)}, DOWN: {np.sum(predictions == 0)}")

        results = df[meta_cols].copy()
        results['model_prediction'] = pred_labels
        results['model_confidence'] = confidence.round(4)

        aligned_close = close_prices.loc[valid_idx]
        results['next_close'] = aligned_close.shift(-1).values
        results['current_close'] = aligned_close.values

        results['actual_direction'] = np.where(
            results['next_close'] > results['current_close'], "UP",
            np.where(results['next_close'] < results['current_close'], "DOWN", "SAME")
        )
        results['model_correct'] = np.where(
            results['next_close'].isna(), None,
            results['model_prediction'] == results['actual_direction']
        )

        known = results[results['model_correct'].notna()]
        if len(known) > 0:
            accuracy = known['model_correct'].mean()
            self.logger.info(f"Model accuracy on {len(known)} known outcomes: {accuracy:.4f} ({accuracy*100:.2f}%)")

        out_table = f"gold_{asset_class}_predictions"
        self.logger.info(f"Writing results to {out_table}...")
        self.conn.execute(f"DROP TABLE IF EXISTS {out_table}")
        self.conn.register("temp_results", results)
        self.conn.execute(f"CREATE TABLE {out_table} AS SELECT * FROM temp_results ORDER BY date")
        self.conn.unregister("temp_results")

        out_cnt = self.conn.execute(f"SELECT COUNT(*) FROM {out_table}").fetchone()[0]
        self.logger.info(f"Created {out_table} with {out_cnt} rows")

        out_path = f"s3://{self.analytics_bucket}/{asset_class}_predictions.parquet"
        try:
            self.conn.execute(f"COPY {out_table} TO '{out_path}' (FORMAT PARQUET)")
            self.logger.info(f"Exported to MinIO: {out_path}")
        except Exception as e:
            self.logger.error(f"Failed to export predictions to MinIO: {e}")

        self.logger.info("=" * 60)
        self.logger.info("Prediction complete!")
        self.logger.info(f"Table: {out_table} | MinIO: {out_path}")
        self.logger.info("=" * 60)

        return results

    def run(self):
        """Run predictions for all assets with available models"""
        self.logger.info("*" * 60)
        self.logger.info("Starting Model Prediction Process")
        self.logger.info("*" * 60)

        models_dir = os.path.dirname(__file__)
        model_files = [f for f in os.listdir(models_dir) if f.endswith("_xgboost_model.json")]

        if not model_files:
            self.logger.warning("No model files found. Run BTC_xgboost.ipynb to save a model first.")
            self.logger.info("Expected pattern: {ASSET}_{INTERVAL}_xgboost_model.json")
            return

        for mf in model_files:
            parts = mf.replace("_xgboost_model.json", "").split("_")
            interval = parts[-1]
            asset = "_".join(parts[:-1])
            try:
                self.predict(asset=asset, interval=interval)
            except Exception as e:
                self.logger.error(f"Failed to predict for {asset} ({interval}): {e}")

        self.logger.info("*" * 60)
        self.logger.info("Model Prediction Process Completed")
        self.logger.info("*" * 60)

    def close(self):
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    predictor = ModelPredictor()
    predictor.run()
    predictor.close()