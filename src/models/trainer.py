import json
import os
import shutil
import sys
import warnings
import numpy as np
import pandas as pd
import duckdb
import xgboost as xgb
import yaml
import mlflow
import mlflow.xgboost
from datetime import datetime
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from src.utils import get_logger
from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary

MIN_ROWS = 200
PARAM_GRID = {
    "learning_rate": [0.01, 0.05, 0.1],
    "max_depth": [3, 5],
    "n_estimators": [100, 200],
}

CRYPTO_INTERVAL_MAP = {"60": "1h", "240": "4h", "D": "1d", "W": "1w"}
STOCK_INTERVAL_MAP = {"1h": "1h", "1d": "1d", "1wk": "1w"}

class PipelineModelTrainer:

    def __init__(self, n_jobs=None):
        self.logger = get_logger(__name__)
        load_dotenv()

        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)

        self.db_path = os.getenv("DB_PATH", self.config["paths"]["database"])
        if not os.path.exists(self.db_path):
            self.db_path = os.path.join("database", "financial_data.duckdb")
        self.conn = duckdb.connect(self.db_path, read_only=True)

        self.models_dir = os.path.join("/app", "model_store")
        self.crypto_dir = os.path.join(self.models_dir, "crypto")
        self.stocks_dir = os.path.join(self.models_dir, "stocks")
        os.makedirs(self.crypto_dir, exist_ok=True)
        os.makedirs(self.stocks_dir, exist_ok=True)

        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(mlflow_uri)

        self.n_jobs = n_jobs or max(os.cpu_count() - 1, 1)
        self.use_gpu = self._detect_gpu()
        self._grid_n_jobs = 1 if self.use_gpu else -1
        mode = "GPU (CUDA)" if self.use_gpu else f"CPU (GridSearchCV n_jobs=-1)"
        self.logger.info(f"Trainer initialized: {mode}")

    def _detect_gpu(self):
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                test = xgb.XGBClassifier(
                    device="cuda", tree_method="hist",
                    n_estimators=1, max_depth=1, eval_metric="logloss",
                )
                test.fit(np.array([[1, 2], [3, 4]]), np.array([0, 1]))
                for warning in w:
                    msg = str(warning.message)
                    if "not compiled with CUDA" in msg or "No visible GPU" in msg:
                        self.logger.info("GPU detection: CUDA not available, falling back to CPU")
                        return False
            self.logger.info("GPU detection: CUDA available")
            return True
        except Exception:
            self.logger.info("GPU detection: CUDA not available (exception), falling back to CPU")
            return False

    def _build_combos(self):
        combos = []
        crypto_targets = self.config["ingestion"]["targets"]["bybit"]
        crypto_intervals = self.config["providers"]["bybit"]["intervals"]
        stock_targets = self.config["ingestion"]["targets"]["yfinance"]
        stock_intervals = self.config["providers"]["yfinance"]["intervals"]

        for symbol in crypto_targets:
            asset = symbol.replace("USDT", "")
            for raw_interval in crypto_intervals:
                interval = CRYPTO_INTERVAL_MAP.get(raw_interval)
                if interval is None:
                    continue
                combos.append((asset, interval, "crypto", "gold_crypto_features"))

        for symbol in stock_targets:
            for raw_interval in stock_intervals:
                interval = STOCK_INTERVAL_MAP.get(raw_interval)
                if interval is None:
                    continue
                combos.append((symbol, interval, "stocks", "gold_stock_features"))

        return combos

    def _get_metadata_path(self, asset, interval, asset_class):
        out_dir = self.crypto_dir if asset_class == "crypto" else self.stocks_dir
        meta_path = os.path.join(out_dir, f"{asset}_{interval}_xgboost_metadata.json")
        model_path = os.path.join(out_dir, f"{asset}_{interval}_xgboost_model.json")
        return meta_path, model_path

    def _read_metadata(self, asset, interval, asset_class):
        meta_path, model_path = self._get_metadata_path(asset, interval, asset_class)
        if not os.path.exists(meta_path) or not os.path.exists(model_path):
            return None
        try:
            with open(meta_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"FATAL: corrupt metadata JSON at {meta_path}: {e}")
            raise

    def _get_gold_max_date(self, asset, interval, table_name):
        try:
            result = self.conn.execute(f"""
                SELECT MAX(date)
                FROM {table_name}
                WHERE asset_symbol = '{asset}' AND interval = '{interval}'
            """).fetchone()
            if result and result[0] is not None:
                return pd.Timestamp(result[0])
        except Exception as e:
            self.logger.warning(f"  Could not query {table_name} for {asset}/{interval}: {e}")
        return None

    def _needs_training(self, asset, interval, asset_class, table_name):
        gold_max = self._get_gold_max_date(asset, interval, table_name)
        if gold_max is None:
            self.logger.info(f"  {asset}/{interval}: no gold data — skipping")
            return False, "no_gold_data"

        meta = self._read_metadata(asset, interval, asset_class)
        if meta is None:
            return True, "no_model"

        train_end = pd.Timestamp(meta["train_end_date"])
        if gold_max > train_end:
            delta = gold_max - train_end
            return True, f"stale (gold +{delta.days}d beyond train_end)"

        return False, "up_to_date"

    def _fetch_data(self, asset, interval, asset_class, table_name):
        cols = NEEDED_COLS
        if asset_class == "stocks":
            cols = [c for c in NEEDED_COLS if c != "fear_greed"]
        col_list = ", ".join(cols)
        df = self.conn.execute(f"""
            SELECT {col_list}
            FROM {table_name}
            WHERE asset_symbol = '{asset}' AND interval = '{interval}'
            ORDER BY date
        """).df()
        return df

    def _train_one(self, asset, interval, asset_class, table_name):
        self.logger.info(f"  Training {asset} {interval} ({asset_class})...")

        df = self._fetch_data(asset, interval, asset_class, table_name)
        if len(df) < MIN_ROWS:
            self.logger.warning(f"  SKIP: only {len(df)} rows (< {MIN_ROWS})")
            return None

        df["date"] = pd.to_datetime(df["date"])
        df = make_stationary(df)
        df["target_direction"] = (df["close"].shift(-1) > df["close"]).astype(int)
        df = df.dropna(subset=["target_direction"])
        df["target_direction"] = df["target_direction"].astype(int)

        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        y_train = train_df["target_direction"]
        y_test = test_df["target_direction"]

        available_features = [f for f in MODEL_FEATURES if f in train_df.columns]
        X_train = train_df[available_features].dropna()
        X_test = test_df[available_features].dropna()

        common_train = X_train.index.intersection(y_train.index)
        common_test = X_test.index.intersection(y_test.index)
        X_train = X_train.loc[common_train]
        y_train = y_train.loc[common_train]
        X_test = X_test.loc[common_test]
        y_test = y_test.loc[common_test]

        if len(X_train) < 100 or len(X_test) < 20:
            self.logger.warning(f"  SKIP: train={len(X_train)}, test={len(X_test)} after dropna")
            return None

        run_name = f"{asset_class}/{asset}/{interval}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        mlflow_run_id = None
        mlflow_enabled = False
        try:
            mlflow.set_experiment(f"pipeline_auto_retrain_{asset_class}")
            mlflow.start_run(run_name=run_name)
            mlflow_run = mlflow.active_run()
            mlflow.run_id = mlflow_run.info.run_id
            mlflow_enabled = True
            mlflow.set_tag("asset", asset)
            mlflow.set_tag("interval", interval)
            mlflow.set_tag("asset_class", asset_class)
            mlflow.log_params({
                "asset": asset, "interval": interval, "asset_class": asset_class,
                "train_rows": len(train_df), "test_rows": len(test_df),
                "n_features": len(available_features),
                "train_end_date": train_df["date"].max().isoformat(),
                "test_start_date": test_df["date"].min().isoformat(),
                "test_end_date": test_df["date"].max().isoformat(),
            })
        except Exception as e:
            self.logger.warning(f"  MLflow unavailable: {e} — training without tracking")

        model_params = {
            "subsample": 1.0, "eval_metric": "logloss", "random_state": 42,
        }
        if self.use_gpu:
            model_params["device"] = "cuda"
            model_params["tree_method"] = "hist"
        base_model = xgb.XGBClassifier(**model_params)
        tscv = TimeSeriesSplit(n_splits=2)
        grid = GridSearchCV(
            base_model, PARAM_GRID, cv=tscv, scoring="accuracy",
            n_jobs=self._grid_n_jobs, verbose=0,
        )
        grid.fit(X_train, y_train)
        model = grid.best_estimator_

        y_pred = model.predict(X_test)
        test_acc = accuracy_score(y_test, y_pred)

        if mlflow_enabled:
            try:
                mlflow.log_metrics({"test_accuracy": test_acc, "best_cv_score": grid.best_score_})
                mlflow.log_params(grid.best_params_)
                mlflow.xgboost.log_model(model, "model")
            except Exception as e:
                self.logger.warning(f"  MLflow log failed: {e}")

        meta_path, model_path = self._get_metadata_path(asset, interval, asset_class)
        model.save_model(model_path)

        best_params = dict(grid.best_params_)
        extra_params = {"subsample": 1.0, "eval_metric": "logloss", "random_state": 42}
        if self.use_gpu:
            extra_params["device"] = "cuda"
            extra_params["tree_method"] = "hist"
        best_params.update(extra_params)

        metadata = {
            "asset": asset,
            "interval": interval,
            "asset_class": asset_class,
            "train_end_date": train_df["date"].max().isoformat(),
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "test_accuracy": float(test_acc),
            "features": available_features,
            "best_params": best_params,
            "best_cv_score": float(grid.best_score_),
            "trained_at": datetime.utcnow().isoformat(),
            "mlflow_run_id": mlflow_run_id,
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        local_dir = os.path.join("/app", "src", "models", asset_class)
        os.makedirs(local_dir, exist_ok=True)
        try:
            shutil.copy2(model_path, os.path.join(local_dir, os.path.basename(model_path)))
            shutil.copy2(meta_path, os.path.join(local_dir, os.path.basename(meta_path)))
        except OSError as e:
            self.logger.warning(f"  Sync to repo failed (bind-mount): {e}")

        if mlflow_enabled:
            try:
                mlflow.end_run()
            except Exception:
                pass

        self.logger.info(f"  Saved {asset}/{interval}: acc={test_acc:.4f}, train_rows={len(train_df)}")
        return {"asset": asset, "interval": interval, "accuracy": round(test_acc, 4)}

    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("STEP 8: MODEL TRAINING (Auto-retrain on new data)")
        self.logger.info("*" * 60)

        combos = self._build_combos()
        self.logger.info(f"Checking {len(combos)} asset×interval combos...")

        to_train = []
        skipped = 0
        up_to_date = 0

        for asset, interval, asset_class, table_name in combos:
            needs, reason = self._needs_training(asset, interval, asset_class, table_name)

            if not needs:
                if reason == "up_to_date":
                    up_to_date += 1
                elif reason == "no_gold_data":
                    skipped += 1
                continue

            self.logger.info(f"[RETRAIN] {asset}/{interval}: {reason}")
            to_train.append((asset, interval, asset_class, table_name))

        total = len(to_train)
        self.logger.info(f"{total} to train, {up_to_date} up-to-date, {skipped} skipped")

        if total == 0:
            self.logger.info("Step 8 complete: nothing to train")
            self.logger.info("*" * 60)
            return

        trained = 0
        mode = "GPU (CUDA)" if self.use_gpu else "CPU (GridSearchCV n_jobs=-1)"
        self.logger.info(f"Training sequentially on {mode}...")

        for i, combo in enumerate(to_train, 1):
            result = self._train_one(*combo)
            if result:
                trained += 1
            else:
                skipped += 1
            self.logger.info(f"Progress: {i}/{total}")

        self.logger.info(f"Step 8 complete: {trained} trained, {up_to_date} up-to-date, {skipped} skipped")
        self.logger.info("*" * 60)

    def close(self):
        if self.conn:
            self.conn.close()