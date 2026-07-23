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
            {"asset": "BTC", "interval": "1h", "asset_class": "crypto", "test_accuracy": 0.521, "train_rows": 1680, "test_rows": 420, "status": "healthy"},
            {"asset": "ETH", "interval": "4h", "asset_class": "crypto", "test_accuracy": 0.498, "train_rows": 2100, "test_rows": 525, "status": "healthy"},
            {"asset": "SOL", "interval": "1d", "asset_class": "crypto", "test_accuracy": None, "status": "stale"},
            {"asset": "AAPL", "interval": "1h", "asset_class": "stocks", "test_accuracy": 0.535, "train_rows": 1200, "test_rows": 300, "status": "healthy"},
            {"asset": "TSLA", "interval": "1d", "asset_class": "stocks", "test_accuracy": 0.511, "train_rows": 900, "test_rows": 225, "status": "healthy"},
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
        assert "Train Rows: %{customdata[0]}" in fig.data[0].hovertemplate
        assert "Test Rows: %{customdata[1]}" in fig.data[0].hovertemplate
        assert "Accuracy: %{y:.1f}%" in fig.data[1].hovertemplate
        assert "Train Rows: %{customdata[0]}" in fig.data[1].hovertemplate
        assert "Test Rows: %{customdata[1]}" in fig.data[1].hovertemplate

    def test_customdata_has_train_and_test_rows(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "get_model_health", return_value=self._fake_models()):
            result = dashboard_app.build_accuracy_chart()

        fig = result.figure
        crypto_cd = list(fig.data[0].customdata)
        assert [1680, 420] in crypto_cd
        assert [2100, 525] in crypto_cd
        stock_cd = list(fig.data[1].customdata)
        assert [1200, 300] in stock_cd
        assert [900, 225] in stock_cd

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


class TestConfusionMatrix:
    def _fake_predictions(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="1h"),
            "close": [100, 101, 102, 101, 103, 104, 103, 105, 106, 105],
            "prediction": [1, 1, 1, 0, 1, 1, 0, 1, 0, 1],
            "confidence": [0.6, 0.7, 0.55, 0.65, 0.6, 0.7, 0.55, 0.65, 0.6, 0.7],
            "actual_direction": [1, 1, 0, 0, 1, 1, 0, 1, 1, 0],
            "is_oos": [True] * 10,
        })

    def test_correct_counts_tp_fp_tn_fn(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confusion_matrix("crypto", "BTC", "1h")

        fig = result.figure
        text = fig.data[0].text
        assert "TN" in text[0][0] and "2 (20.0%)" in text[0][0]
        assert "FP" in text[0][1] and "2 (20.0%)" in text[0][1]
        assert "FN" in text[1][0] and "1 (10.0%)" in text[1][0]
        assert "TP" in text[1][1] and "5 (50.0%)" in text[1][1]

    def test_correct_cells_green_wrong_cells_red(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confusion_matrix("crypto", "BTC", "1h")

        fig = result.figure
        z = fig.data[0].z
        assert z[0][0] == 1
        assert z[0][1] == 0
        assert z[1][0] == 0
        assert z[1][1] == 1

    def test_no_model_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", side_effect=FileNotFoundError):
            result = dashboard_app.build_confusion_matrix("crypto", "BTC", "1h")

        text = _collect_text(result)
        assert any("No trained model" in t for t in text)

    def test_no_data_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=None):
            result = dashboard_app.build_confusion_matrix("crypto", "BTC", "1h")

        text = _collect_text(result)
        assert any("No prediction data" in t for t in text)

    def test_title_includes_asset_interval_and_accuracy(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confusion_matrix("crypto", "BTC", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "BTC" in title
        assert "1h" in title
        assert "70.0%" in title

    def test_total_count_in_title(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confusion_matrix("crypto", "BTC", "1h")

        fig = result.figure
        assert "n=10" in fig.layout.title.text

    def test_only_oos_data_used(self):
        from dashboard import app as dashboard_app

        df = self._fake_predictions()
        df["is_oos"] = [True] * 5 + [False] * 5
        with patch.object(dashboard_app, "run_prediction", return_value=df):
            result = dashboard_app.build_confusion_matrix("crypto", "BTC", "1h")

        fig = result.figure
        text = fig.data[0].text
        assert "1 (20.0%)" in text[0][0]
        assert "1 (20.0%)" in text[0][1]
        assert "0 (0.0%)" in text[1][0]
        assert "3 (60.0%)" in text[1][1]
        assert "n=5" in fig.layout.title.text

    def test_works_for_stocks(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confusion_matrix("stocks", "AAPL", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "AAPL" in title
        assert "1h" in title


class TestExplorerFilterOptions:
    def _mock_result(self, rows):
        mock = MagicMock()
        mock.fetchall.return_value = rows
        return mock

    def test_returns_distinct_assets_sorted(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = [
            self._mock_result([("ETH",), ("BTC",), ("SOL",)]),
            self._mock_result([("1d",), ("1h",), ("4h",)]),
        ]
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            assets, intervals, asset_val, interval_val = (
                dashboard_app.update_explorer_filter_options("gold_crypto_analytics")
            )

        asset_labels = [a["label"] for a in assets]
        assert asset_labels == ["ETH", "BTC", "SOL"]
        assert asset_val is None
        assert interval_val is None

    def test_returns_distinct_intervals(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = [
            self._mock_result([("BTC",)]),
            self._mock_result([("1d",), ("1h",), ("4h",)]),
        ]
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            _, intervals, _, _ = (
                dashboard_app.update_explorer_filter_options("gold_crypto_analytics")
            )

        interval_labels = [i["label"] for i in intervals]
        assert interval_labels == ["1d", "1h", "4h"]

    def test_returns_empty_options_on_db_error(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("table not found")
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            assets, intervals, asset_val, interval_val = (
                dashboard_app.update_explorer_filter_options("bad_table")
            )

        assert assets == []
        assert intervals == []
        assert asset_val is None
        assert interval_val is None


class TestExplorerTableQuery:
    def _fake_df(self):
        return pd.DataFrame({
            "asset_symbol": ["BTC", "ETH"],
            "interval": ["1h", "1h"],
            "date": pd.to_datetime(["2026-01-01 10:00", "2026-01-01 11:00"]),
            "close": [100.0, 200.0],
        })

    def test_no_filters_returns_all_rows(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = self._fake_df()
        captured = []

        def capture_query(query, *args, **kwargs):
            captured.append(query)
            return mock_conn.execute.return_value

        mock_conn.execute.side_effect = capture_query
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            table, row_text = dashboard_app.update_explorer_table(
                "gold_crypto_analytics", None, None
            )

        assert "WHERE" not in captured[0]
        assert "Showing 2 rows" in row_text

    def test_asset_filter_adds_where_clause(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = self._fake_df()
        captured = []

        def capture_query(query, *args, **kwargs):
            captured.append(query)
            return mock_conn.execute.return_value

        mock_conn.execute.side_effect = capture_query
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            dashboard_app.update_explorer_table(
                "gold_crypto_analytics", "BTC", None
            )

        assert "WHERE asset_symbol = 'BTC'" in captured[0]
        assert "interval" not in captured[0].split("ORDER BY")[0]

    def test_interval_filter_adds_where_clause(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = self._fake_df()
        captured = []

        def capture_query(query, *args, **kwargs):
            captured.append(query)
            return mock_conn.execute.return_value

        mock_conn.execute.side_effect = capture_query
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            dashboard_app.update_explorer_table(
                "gold_crypto_analytics", None, "1h"
            )

        assert "WHERE interval = '1h'" in captured[0]

    def test_both_filters_combined_with_and(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = self._fake_df()
        captured = []

        def capture_query(query, *args, **kwargs):
            captured.append(query)
            return mock_conn.execute.return_value

        mock_conn.execute.side_effect = capture_query
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            dashboard_app.update_explorer_table(
                "gold_crypto_analytics", "BTC", "1h"
            )

        assert "WHERE asset_symbol = 'BTC' AND interval = '1h'" in captured[0]

    def test_empty_table_shows_warning(self):
        from dashboard import app as dashboard_app

        mock_conn = MagicMock()
        mock_conn.execute.return_value.df.return_value = pd.DataFrame()
        with patch("dashboard.app.duckdb.connect", return_value=mock_conn):
            table, row_text = dashboard_app.update_explorer_table(
                "gold_crypto_analytics", None, None
            )

        text = _collect_text(table)
        assert any("is empty" in t for t in text)


class TestConfidenceHistogram:
    def _fake_predictions(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="1h"),
            "close": [100, 101, 102, 101, 103, 104, 103, 105, 106, 105],
            "prediction": [1, 1, 1, 0, 1, 1, 0, 1, 0, 1],
            "confidence": [0.6, 0.7, 0.55, 0.65, 0.6, 0.7, 0.55, 0.65, 0.6, 0.7],
            "actual_direction": [1, 1, 0, 0, 1, 1, 0, 1, 1, 0],
            "is_oos": [True] * 10,
        })

    def test_split_by_correctness(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        fig = result.figure
        names = [t.name for t in fig.data]
        assert any("Correct" in n for n in names)
        assert any("Wrong" in n for n in names)

    def test_correct_trace_green_wrong_trace_red(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        fig = result.figure
        for trace in fig.data:
            if "Correct" in trace.name:
                assert trace.marker.color == "#27ae60"
            elif "Wrong" in trace.name:
                assert trace.marker.color == "#c0392b"

    def test_correct_counts_match_data(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        fig = result.figure
        df = self._fake_predictions()
        expected_correct = int((df["prediction"] == df["actual_direction"]).sum())
        expected_wrong = int((df["prediction"] != df["actual_direction"]).sum())
        correct_trace = [t for t in fig.data if "Correct" in t.name][0]
        wrong_trace = [t for t in fig.data if "Wrong" in t.name][0]
        assert f"Correct ({expected_correct})" == correct_trace.name
        assert f"Wrong ({expected_wrong})" == wrong_trace.name

    def test_title_includes_asset_interval_and_accuracy(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "BTC" in title
        assert "1h" in title
        assert "n=10" in title

    def test_no_model_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", side_effect=FileNotFoundError):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        text = _collect_text(result)
        assert any("No trained model" in t for t in text)

    def test_no_data_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=None):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        text = _collect_text(result)
        assert any("No prediction data" in t for t in text)

    def test_only_oos_data_used(self):
        from dashboard import app as dashboard_app

        df = self._fake_predictions()
        df["is_oos"] = [True] * 5 + [False] * 5
        with patch.object(dashboard_app, "run_prediction", return_value=df):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "n=5" in title

    def test_works_for_stocks(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_histogram("stocks", "AAPL", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "AAPL" in title
        assert "1h" in title

    def test_barmode_overlay(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_histogram("crypto", "BTC", "1h")

        fig = result.figure
        assert fig.layout.barmode == "overlay"