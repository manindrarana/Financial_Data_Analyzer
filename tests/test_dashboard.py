import sys
from unittest.mock import MagicMock

sys.modules["dotenv"] = MagicMock()

import pytest
import os
import pandas as pd
from unittest.mock import patch, MagicMock
from dashboard.predictor import _discover_model, _INTERVAL_MINUTES, FEATURE_TABLES


def _collect_text(component):
    if isinstance(component, str):
        return [component]
    children = getattr(component, "children", None)
    if children is None:
        return []
    if isinstance(children, list):
        values = []
        for child in children:
            values.extend(_collect_text(child))
        return values
    return _collect_text(children)


class TestIntervalMinutes:
    def test_1h_is_60(self):
        assert _INTERVAL_MINUTES["1h"] == 60

    def test_4h_is_240(self):
        assert _INTERVAL_MINUTES["4h"] == 240

    def test_1d_is_1440(self):
        assert _INTERVAL_MINUTES["1d"] == 1440


class TestDiscoverModel:
    def test_exact_match_found(self):
        with patch("os.path.exists", return_value=True):
            path, interval = _discover_model("BTC", "1h", "crypto")
            assert "BTC_1h_xgboost_model.json" in path
            assert interval == "1h"

    def test_no_model_found(self):
        with patch("os.path.exists", return_value=False):
            with patch("os.path.isdir", return_value=True):
                with patch("os.listdir", return_value=[]):
                    path, interval = _discover_model("BTC", "1h", "crypto")
                    assert path is None
                    assert interval is None

    def test_fallback_to_nearest_interval(self):
        with patch("os.path.exists", side_effect=lambda p: "BTC_1h" not in p):
            with patch("os.path.isdir", return_value=True):
                with patch("os.listdir", return_value=[
                    "BTC_1d_xgboost_model.json",
                    "BTC_4h_xgboost_model.json",
                ]):
                    path, interval = _discover_model("BTC", "1h", "crypto")
                    assert path is not None
                    assert interval == "4h"


class TestFeatureTables:
    def test_crypto_table(self):
        assert FEATURE_TABLES["crypto"] == "gold_crypto_features"

    def test_stocks_table(self):
        assert FEATURE_TABLES["stocks"] == "gold_stock_features"


class TestPredictionCards:
    def test_next_prediction_card_uses_latest_prediction(self):
        from dashboard import app as dashboard_app

        prediction_rows = pd.DataFrame({
            "date": pd.to_datetime(["2026-06-18 10:00", "2026-06-18 11:00"]),
            "close": [100.0, 101.0],
            "prediction": [0, 1],
            "confidence": [0.62, 0.873],
            "actual_direction": [0, 1],
            "is_oos": [True, True],
        })

        with patch.object(dashboard_app, "run_prediction", return_value=prediction_rows):
            content = dashboard_app.build_prediction_charts("crypto", "BTC", "1h", "all")

        text = _collect_text(content)
        assert "Next Prediction" in text
        assert "BTC 1 Hour" in text
        assert "UP" in text
        assert "Confidence: 87.3%" in text

    def test_model_comparison_table_shows_baselines(self):
        from dashboard import app as dashboard_app

        prediction_rows = pd.DataFrame({
            "date": pd.to_datetime([
                "2026-06-18 10:00", "2026-06-18 11:00", "2026-06-18 12:00",
                "2026-06-18 13:00", "2026-06-18 14:00", "2026-06-18 15:00",
                "2026-06-18 16:00", "2026-06-18 17:00", "2026-06-18 18:00",
                "2026-06-18 19:00", "2026-06-18 20:00", "2026-06-18 21:00",
                "2026-06-18 22:00", "2026-06-18 23:00", "2026-06-19 00:00",
                "2026-06-19 01:00", "2026-06-19 02:00", "2026-06-19 03:00",
                "2026-06-19 04:00", "2026-06-19 05:00", "2026-06-19 06:00",
                "2026-06-19 07:00", "2026-06-19 08:00", "2026-06-19 09:00",
                "2026-06-19 10:00", "2026-06-19 11:00", "2026-06-19 12:00",
                "2026-06-19 13:00", "2026-06-19 14:00", "2026-06-19 15:00",
                "2026-06-19 16:00", "2026-06-19 17:00", "2026-06-19 18:00",
                "2026-06-19 19:00", "2026-06-19 20:00", "2026-06-19 21:00",
                "2026-06-19 22:00", "2026-06-19 23:00", "2026-06-20 00:00",
                "2026-06-20 01:00", "2026-06-20 02:00", "2026-06-20 03:00",
                "2026-06-20 04:00", "2026-06-20 05:00", "2026-06-20 06:00",
                "2026-06-20 07:00", "2026-06-20 08:00", "2026-06-20 09:00",
                "2026-06-20 10:00", "2026-06-20 11:00", "2026-06-20 12:00",
            ]),
            "close": list(range(100, 151)),
            "prediction": [1, 0, 1] * 17,
            "confidence": [0.60] * 51,
            "actual_direction": [1, 0, 1] * 17,
            "is_oos": [True] * 51,
        })

        with patch.object(dashboard_app, "run_prediction", return_value=prediction_rows):
            content = dashboard_app.build_prediction_charts("crypto", "BTC", "1h", "all")

        text = _collect_text(content)
        assert "Model Comparison" in text
        assert "XGBoost beats best baseline (Last Candle Direction) by 32.0%" in text
        assert "Model beats baselines" in text
        assert "XGBoost" in text
        assert "Always Up" in text
        assert "Always Down" in text
        assert "Last Candle Direction" in text
        assert "SMA 20 > SMA 50 Rule" in text

    def test_model_comparison_table_uses_only_oos_rows(self):
        from dashboard import app as dashboard_app

        prediction_rows = pd.DataFrame({
            "date": pd.to_datetime([
                "2026-06-18 10:00", "2026-06-18 11:00", "2026-06-18 12:00",
                "2026-06-18 13:00", "2026-06-18 14:00",
            ]),
            "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "prediction": [1, 1, 1, 1, 1],
            "confidence": [0.60] * 5,
            "actual_direction": [1, 1, 1, 0, 1],
            "is_oos": [False, False, False, True, True],
        })
        comparison_tables = []

        def capture_comparison_table(df, *args, **kwargs):
            comparison_tables.append(df)
            return dashboard_app.html.Div("comparison table")

        with patch.object(dashboard_app, "run_prediction", return_value=prediction_rows):
            with patch.object(dashboard_app.dbc.Table, "from_dataframe", side_effect=capture_comparison_table):
                dashboard_app.build_prediction_charts("crypto", "BTC", "1h", "all")

        xgboost_row = comparison_tables[0].loc[comparison_tables[0]["Model / Rule"] == "XGBoost"].iloc[0]
        assert xgboost_row["Correct"] == 1
        assert xgboost_row["Rows Tested"] == 2