import duckdb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from src.models.feature_engineering import MODEL_FEATURES, NEEDED_COLS, make_stationary


PARAM_GRID = {
    "learning_rate": [0.01, 0.05, 0.1],
    "max_depth": [3, 5],
    "n_estimators": [100, 200],
}
CROSS_ASSET_COLUMNS = [
    "eth_btc_relative_return",
    "tracked_crypto_market_return",
    "tracked_crypto_market_breadth",
    "cross_asset_volatility",
    "market_asset_count",
]
EXPERIMENT_FEATURES = [
    "eth_btc_relative_return",
    "tracked_crypto_market_return",
    "tracked_crypto_market_breadth",
    "cross_asset_volatility",
]
RESULT_COLUMNS = [
    "date",
    "asset_symbol",
    "interval",
    "close",
    *CROSS_ASSET_COLUMNS,
]


def load_crypto_candles(db_path, interval):
    connection = duckdb.connect(db_path, read_only=True)
    try:
        return connection.execute(
            """
            SELECT date, asset_symbol, interval, close
            FROM gold_crypto_features
            WHERE interval = ?
            ORDER BY date, asset_symbol
            """,
            [interval],
        ).df()
    finally:
        connection.close()


def load_target_features(db_path, asset, interval):
    connection = duckdb.connect(db_path, read_only=True)
    try:
        columns = ", ".join(NEEDED_COLS)
        return connection.execute(
            f"""
            SELECT {columns}
            FROM gold_crypto_features
            WHERE asset_symbol = ? AND interval = ?
            ORDER BY date
            """,
            [asset, interval],
        ).df()
    finally:
        connection.close()


def prepare_target_features(df):
    if df.empty:
        raise ValueError("no target feature data found")

    prepared = make_stationary(df)
    prepared["date"] = pd.to_datetime(prepared["date"])
    prepared["target_direction"] = (
        prepared["close"].shift(-1) > prepared["close"]
    ).astype(int)
    prepared = prepared.iloc[:-1].copy()
    return prepared.dropna(subset=MODEL_FEATURES).copy()


def merge_cross_asset_features(target_df, cross_asset_df):
    if target_df.empty:
        return target_df.copy()

    merged = target_df.merge(
        cross_asset_df[["date", *EXPERIMENT_FEATURES]],
        on="date",
        how="inner",
        validate="one_to_one",
    )
    return merged.dropna(subset=EXPERIMENT_FEATURES).copy()


def split_experiment_data(df, features):
    if df.empty:
        raise ValueError("no complete experiment rows found")

    split_index = int(len(df) * 0.8)
    train = df.iloc[:split_index]
    test = df.iloc[split_index:]
    if len(train) < 100 or len(test) < 20:
        raise ValueError(
            f"insufficient experiment rows: train={len(train)}, test={len(test)}"
        )

    return (
        train[features],
        train["target_direction"],
        test[features],
        test["target_direction"],
        test["date"],
    )


def train_experiment_model(X_train, y_train):
    search = GridSearchCV(
        xgb.XGBClassifier(
            subsample=1.0,
            eval_metric="logloss",
            random_state=42,
        ),
        PARAM_GRID,
        cv=TimeSeriesSplit(n_splits=2),
        scoring="balanced_accuracy",
        n_jobs=1,
        verbose=0,
    )
    search.fit(X_train, y_train)
    return search


def evaluate_experiment_model(search, X_test, y_test):
    predictions = search.best_estimator_.predict(X_test)
    return {
        "accuracy": accuracy_score(y_test, predictions),
        "balanced_accuracy": balanced_accuracy_score(y_test, predictions),
        "f1": f1_score(y_test, predictions, zero_division=0),
        "best_cv_score": search.best_score_,
        "learning_rate": search.best_params_["learning_rate"],
        "max_depth": search.best_params_["max_depth"],
        "n_estimators": search.best_params_["n_estimators"],
    }


def calculate_asset_returns(candles):
    if candles.empty:
        return candles.assign(asset_return=pd.Series(dtype=float))

    prepared = candles.copy()
    prepared["date"] = pd.to_datetime(prepared["date"])
    prepared = prepared.sort_values(["asset_symbol", "date"])
    prepared["asset_return"] = prepared.groupby(
        ["asset_symbol", "interval"],
        sort=False,
    )["close"].pct_change(fill_method=None)
    return prepared


def build_cross_asset_features(candles, target_asset, interval, min_market_assets=5):
    if candles.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    returns = calculate_asset_returns(
        candles.loc[candles["interval"] == interval].copy()
    )
    target_rows = returns.loc[
        returns["asset_symbol"] == target_asset,
        ["date", "asset_symbol", "interval", "close"],
    ].copy()
    market_rows = returns.loc[returns["asset_symbol"] != target_asset].copy()

    market = market_rows.groupby("date")["asset_return"].agg(
        tracked_crypto_market_return="mean",
        tracked_crypto_market_breadth=lambda values: (values.dropna() > 0).mean(),
        cross_asset_volatility=lambda values: values.std(ddof=0),
        market_asset_count="count",
    )
    insufficient = market["market_asset_count"] < min_market_assets
    market.loc[
        insufficient,
        [
            "tracked_crypto_market_return",
            "tracked_crypto_market_breadth",
            "cross_asset_volatility",
        ],
    ] = np.nan

    relative_returns = returns.loc[
        returns["asset_symbol"].isin(["BTC", "ETH"]),
        ["date", "asset_symbol", "asset_return"],
    ].pivot(index="date", columns="asset_symbol", values="asset_return")
    if {"BTC", "ETH"}.issubset(relative_returns.columns):
        relative_returns["eth_btc_relative_return"] = (
            relative_returns["ETH"] - relative_returns["BTC"]
        )
    else:
        relative_returns["eth_btc_relative_return"] = np.nan

    result = target_rows.merge(market, on="date", how="left")
    result["market_asset_count"] = result["market_asset_count"].fillna(0).astype(int)
    result = result.merge(
        relative_returns[["eth_btc_relative_return"]],
        on="date",
        how="left",
    )
    return result[RESULT_COLUMNS].sort_values("date").reset_index(drop=True)
