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


class TestFeatureImportance:
    def test_missing_model_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch("os.path.exists", return_value=False):
            result = dashboard_app.build_feature_importance_chart("crypto", "BTC", "1h")

        text = _collect_text(result)
        assert any("No trained model" in t for t in text)

    def test_chart_shows_top_features(self):
        from dashboard import app as dashboard_app

        mock_booster = MagicMock()
        mock_booster.get_score.return_value = {
            "sma_7_dist": 15.2,
            "rsi_14": 12.1,
            "volume_ratio": 8.5,
            "returns_1p": 5.3,
            "macd": 3.1,
        }
        mock_model = MagicMock()
        mock_model.get_booster.return_value = mock_booster
        mock_model.load_model = MagicMock()

        captured_bars = []

        class FakeBar:
            def __init__(self, **kwargs):
                self.x = kwargs.get("x", [])
                self.y = kwargs.get("y", [])
                self.orientation = kwargs.get("orientation", "v")
                captured_bars.append(self)

        class FakeFig:
            def __init__(self, bar):
                self.data = (bar,)
                self.layout = MagicMock()
            def update_layout(self, **kwargs):
                self.title_text = kwargs.get("title", "")

        def mock_graph(**kwargs):
            mock_obj = MagicMock()
            mock_obj.figure = kwargs.get("figure")
            return mock_obj

        with patch("os.path.exists", return_value=True):
            with patch("xgboost.XGBClassifier", return_value=mock_model):
                with patch.object(dashboard_app.go, "Bar", FakeBar):
                    with patch.object(dashboard_app.go, "Figure", FakeFig):
                        with patch.object(dashboard_app.dcc, "Graph", side_effect=mock_graph):
                            result = dashboard_app.build_feature_importance_chart("crypto", "BTC", "1h")

        bar = captured_bars[0]
        assert bar.orientation == "h"
        assert "sma_7_dist" in list(bar.y)
        assert "rsi_14" in list(bar.y)
        assert len(bar.y) == 5

    def test_chart_limits_to_top_15(self):
        from dashboard import app as dashboard_app

        fake_importance = {f"feature_{i}": float(100 - i) for i in range(20)}
        mock_booster = MagicMock()
        mock_booster.get_score.return_value = fake_importance
        mock_model = MagicMock()
        mock_model.get_booster.return_value = mock_booster
        mock_model.load_model = MagicMock()

        captured_bars = []

        class FakeBar:
            def __init__(self, **kwargs):
                self.x = kwargs.get("x", [])
                self.y = kwargs.get("y", [])
                captured_bars.append(self)

        class FakeFig:
            def __init__(self, bar):
                self.data = (bar,)
                self.layout = MagicMock()
            def update_layout(self, **kwargs):
                pass

        def mock_graph(**kwargs):
            mock_obj = MagicMock()
            mock_obj.figure = kwargs.get("figure")
            return mock_obj

        with patch("os.path.exists", return_value=True):
            with patch("xgboost.XGBClassifier", return_value=mock_model):
                with patch.object(dashboard_app.go, "Bar", FakeBar):
                    with patch.object(dashboard_app.go, "Figure", FakeFig):
                        with patch.object(dashboard_app.dcc, "Graph", side_effect=mock_graph):
                            result = dashboard_app.build_feature_importance_chart("crypto", "BTC", "1h")

        bar = captured_bars[0]
        assert len(bar.y) == 15
        assert "feature_0" in list(bar.y)
        assert "feature_19" not in list(bar.y)

    def test_title_includes_asset_and_interval(self):
        from dashboard import app as dashboard_app

        mock_booster = MagicMock()
        mock_booster.get_score.return_value = {"rsi_14": 10.0}
        mock_model = MagicMock()
        mock_model.get_booster.return_value = mock_booster
        mock_model.load_model = MagicMock()

        captured_figs = []

        class FakeBar:
            def __init__(self, **kwargs):
                self.x = kwargs.get("x", [])
                self.y = kwargs.get("y", [])

        class FakeFig:
            def __init__(self, bar):
                self.data = (bar,)
                self.layout = MagicMock()
            def update_layout(self, **kwargs):
                captured_figs.append(kwargs.get("title", ""))

        def mock_graph(**kwargs):
            mock_obj = MagicMock()
            mock_obj.figure = kwargs.get("figure")
            return mock_obj

        with patch("os.path.exists", return_value=True):
            with patch("xgboost.XGBClassifier", return_value=mock_model):
                with patch.object(dashboard_app.go, "Bar", FakeBar):
                    with patch.object(dashboard_app.go, "Figure", FakeFig):
                        with patch.object(dashboard_app.dcc, "Graph", side_effect=mock_graph):
                            result = dashboard_app.build_feature_importance_chart("stocks", "AAPL", "1d")

        assert "AAPL" in captured_figs[0]
        assert "1d" in captured_figs[0]


class TestAccuracyChart:
    def _fake_models(self):
        return [
            {"asset": "BTC", "interval": "1h", "asset_class": "crypto", "test_accuracy": 0.521, "status": "healthy"},
            {"asset": "ETH", "interval": "4h", "asset_class": "crypto", "test_accuracy": 0.498, "status": "healthy"},
            {"asset": "SOL", "interval": "1d", "asset_class": "crypto", "test_accuracy": None, "status": "stale"},
            {"asset": "AAPL", "interval": "1h", "asset_class": "stocks", "test_accuracy": 0.535, "status": "healthy"},
            {"asset": "TSLA", "interval": "1d", "asset_class": "stocks", "test_accuracy": 0.511, "status": "healthy"},
        ]

    def test_all_models_with_accuracy_appear_as_bars(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        crypto_bars = len(fig.data[0].x)
        stock_bars = len(fig.data[1].x)
        assert crypto_bars == 2
        assert stock_bars == 2
        assert crypto_bars + stock_bars == 4

    def test_bars_colored_by_asset_class(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        assert fig.data[0].marker.color == "#f7931a"
        assert fig.data[1].marker.color == "#3498db"

    def test_crypto_and_stock_traces_separate(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        assert fig.data[0].name == "Crypto"
        assert fig.data[1].name == "Stocks"
        assert "BTC 1h" in list(fig.data[0].x)
        assert "AAPL 1h" in list(fig.data[1].x)

    def test_baseline_and_ceiling_lines_visible(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        y_values = [shape.y0 for shape in fig.layout.shapes]
        assert 50 in y_values
        assert 52.6 in y_values

    def test_hover_template_shows_values(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        assert "Accuracy: %{y:.1f}%" in fig.data[0].hovertemplate
        assert "Accuracy: %{y:.1f}%" in fig.data[1].hovertemplate

    def test_no_accuracy_data_shows_alert(self):
        from dashboard import app as dashboard_app

        fake_models = [
            {"asset": "BTC", "interval": "1h", "asset_class": "crypto", "test_accuracy": None, "status": "stale"},
            {"asset": "AAPL", "interval": "1h", "asset_class": "stocks", "test_accuracy": None, "status": "stale"},
        ]
        with patch.object(dashboard_app, "get_model_health", return_value=fake_models):
            result = dashboard_app.build_accuracy_chart()

        text = _collect_text(result)
        assert any("No accuracy data" in t for t in text)

    def test_bars_sorted_by_accuracy_ascending(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        crypto_y = list(fig.data[0].y)
        assert crypto_y == sorted(crypto_y)
        stock_y = list(fig.data[1].y)
        assert stock_y == sorted(stock_y)

    def test_avg_lines_present(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        y_values = [shape.y0 for shape in fig.layout.shapes]
        crypto_avg = round((52.1 + 49.8) / 2, 1)
        stock_avg = round((53.5 + 51.1) / 2, 1)
        assert crypto_avg in y_values
        assert stock_avg in y_values