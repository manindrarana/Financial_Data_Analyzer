import os
import sys
from unittest.mock import MagicMock, patch

sys.modules["dotenv"] = MagicMock()

import pandas as pd
import pytest

from dashboard.predictor import (
    _apply_probability_calibration,
    _calibration_params,
    _discover_model,
    _INTERVAL_MINUTES,
    FEATURE_TABLES,
    get_calibration_params,
)


def _collect_text(component):
    if isinstance(component, str):
        return [component]
    if isinstance(component, list):
        values = []
        for child in component:
            values.extend(_collect_text(child))
        return values
    children = getattr(component, "children", None)
    if children is None:
        return []
    if isinstance(children, list):
        values = []
        for child in children:
            values.extend(_collect_text(child))
        return values
    return _collect_text(children)


class TestPriceChartInfoBar:
    def test_shows_candle_change_amount_and_percentage(self):
        from dashboard import app as dashboard_app

        hover_data = {
            "points": [{
                "open": 100.0,
                "high": 112.0,
                "low": 98.0,
                "close": 110.0,
                "customdata": [2500.0],
                "x": "2026-01-01T10:00:00",
            }]
        }

        result = dashboard_app.update_chart_info_bar(hover_data, {})
        text = "".join(_collect_text(result))

        assert "Change: +10.0000 (+10.00%)" in text

    def test_shows_negative_change_amount_and_percentage(self):
        from dashboard import app as dashboard_app

        hover_data = {
            "points": [{
                "open": 200.0,
                "high": 204.0,
                "low": 178.0,
                "close": 180.0,
                "customdata": [1500.0],
                "x": "2026-01-01T11:00:00",
            }]
        }

        result = dashboard_app.update_chart_info_bar(hover_data, {})
        text = "".join(_collect_text(result))

        assert "Change: -20.0000 (-10.00%)" in text

    def test_shows_candle_range_amount_and_percentage(self):
        from dashboard import app as dashboard_app

        hover_data = {
            "points": [{
                "open": 100.0,
                "high": 115.0,
                "low": 95.0,
                "close": 108.0,
                "customdata": [2000.0],
                "x": "2026-01-01T12:00:00",
            }]
        }

        result = dashboard_app.update_chart_info_bar(hover_data, {})
        text = "".join(_collect_text(result))

        assert "Range: 20.0000 (20.00%)" in text

    def test_shows_candle_volume(self):
        from dashboard import app as dashboard_app

        hover_data = {
            "points": [{
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 102.0,
                "customdata": [12345.0],
                "x": "2026-01-01T13:00:00",
            }]
        }

        result = dashboard_app.update_chart_info_bar(hover_data, {})
        text = "".join(_collect_text(result))

        assert "Volume: 12,345" in text

    def test_calculates_turnover_from_close_and_volume(self):
        from dashboard import app as dashboard_app

        hover_data = {
            "points": [{
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 102.0,
                "customdata": [12345.0],
                "x": "2026-01-01T14:00:00",
            }]
        }

        result = dashboard_app.update_chart_info_bar(hover_data, {})
        text = "".join(_collect_text(result))

        assert "Turnover: 1,259,190.00" in text

    def test_uses_green_for_positive_change(self):
        from dashboard import app as dashboard_app

        hover_data = {
            "points": [{
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 102.0,
                "customdata": [1000.0],
                "x": "2026-01-01T15:00:00",
            }]
        }

        result = dashboard_app.update_chart_info_bar(hover_data, {})
        change_span = result[8]

        assert change_span.style["color"] == "#26a69a"

    def test_uses_red_for_negative_change(self):
        from dashboard import app as dashboard_app

        hover_data = {
            "points": [{
                "open": 100.0,
                "high": 103.0,
                "low": 94.0,
                "close": 96.0,
                "customdata": [1000.0],
                "x": "2026-01-01T16:00:00",
            }]
        }

        result = dashboard_app.update_chart_info_bar(hover_data, {})
        change_span = result[8]

        assert change_span.style["color"] == "#ef5350"


class TestIntervalMinutes:
    def test_1h_is_60(self):
        assert _INTERVAL_MINUTES["1h"] == 60

    def test_4h_is_240(self):
        assert _INTERVAL_MINUTES["4h"] == 240

    def test_1d_is_1440(self):
        assert _INTERVAL_MINUTES["1d"] == 1440


class TestProbabilityCalibration:
    def test_applies_platt_scaling_values(self):
        raw_probabilities = pd.Series([0.2, 0.5, 0.8]).to_numpy()
        calibration = {
            "coefficient": 2.0,
            "intercept": -1.0,
        }

        calibrated = _apply_probability_calibration(raw_probabilities, calibration)

        assert calibrated == pytest.approx([0.35434369, 0.5, 0.64565631])

    def test_returns_raw_probabilities_without_calibration(self):
        raw_probabilities = pd.Series([0.2, 0.5, 0.8]).to_numpy()

        calibrated = _apply_probability_calibration(raw_probabilities, None)

        assert calibrated is raw_probabilities

    def test_loads_platt_parameters_from_metadata(self):
        _calibration_params.clear()
        metadata = {
            "calibration": {
                "method": "platt_scaling",
                "coefficient": 2.0,
                "intercept": -1.0,
                "rows": 100,
            }
        }
        with patch("dashboard.predictor._discover_meta", return_value="metadata.json"), \
             patch("builtins.open", MagicMock()) as open_mock:
            open_mock.return_value.__enter__.return_value.read.return_value = ""
            with patch("json.load", return_value=metadata):
                calibration = get_calibration_params("BTC", "1h", "crypto")

        assert calibration == metadata["calibration"]
        _calibration_params.clear()

    def test_legacy_metadata_uses_raw_probability_fallback(self):
        _calibration_params.clear()
        with patch("dashboard.predictor._discover_meta", return_value="metadata.json"), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", return_value={"train_end_date": "2026-01-01"}):
            calibration = get_calibration_params("BTC", "1h", "crypto")

        assert calibration is None
        _calibration_params.clear()


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


class TestBaselineStatisticalSignificance:
    @staticmethod
    def _prediction_rows(predictions, actual):
        total = len(actual)
        return pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=total, freq="h"),
            "close": [100.0] * total,
            "prediction": predictions,
            "confidence": [0.60] * total,
            "actual_direction": actual,
            "is_oos": [True] * total,
        })

    def test_significant_model_improvement_values(self):
        from dashboard import app as dashboard_app

        actual = [0, 1] * 50
        result = dashboard_app.build_baseline_significance(
            self._prediction_rows(actual, actual)
        )

        assert result["status"] == "ok"
        assert result["baseline_name"] == "Always Up"
        assert result["model_accuracy"] == pytest.approx(1.0)
        assert result["baseline_accuracy"] == pytest.approx(0.5)
        assert result["difference"] == pytest.approx(0.5)
        assert result["difference_interval"][0] > 0
        assert result["mcnemar_p_value"] < 0.05
        assert result["sample_size"] == 100
        assert result["start_date"] == pd.Timestamp("2026-01-01 00:00:00")
        assert result["end_date"] == pd.Timestamp("2026-01-05 03:00:00")

    def test_non_significant_equal_accuracy_values(self):
        from dashboard import app as dashboard_app

        actual = [0, 1] * 50
        result = dashboard_app.build_baseline_significance(
            self._prediction_rows([1] * 100, actual)
        )

        assert result["status"] == "ok"
        assert result["baseline_name"] == "Always Up"
        assert result["model_accuracy"] == pytest.approx(0.5)
        assert result["baseline_accuracy"] == pytest.approx(0.5)
        assert result["difference"] == pytest.approx(0.0)
        assert result["difference_interval"] == pytest.approx((0.0, 0.0))
        assert result["mcnemar_p_value"] == pytest.approx(1.0)

    def test_missing_known_oos_data_message(self):
        from dashboard import app as dashboard_app

        rows = self._prediction_rows([1, 0], [1, 0])
        rows["actual_direction"] = [float("nan"), float("nan")]
        with patch.object(dashboard_app, "run_prediction", return_value=rows):
            content = dashboard_app.build_baseline_significance_section(
                "crypto", "BTC", "1h"
            )

        assert "No known out-of-sample predictions are available." in _collect_text(content)

    def test_insufficient_paired_data_message(self):
        from dashboard import app as dashboard_app

        rows = self._prediction_rows([1], [1])
        with patch.object(dashboard_app, "run_prediction", return_value=rows):
            content = dashboard_app.build_baseline_significance_section(
                "crypto", "BTC", "1h"
            )

        assert "At least two paired out-of-sample predictions are required." in _collect_text(content)


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


class TestModelFamilyComparison:
    def test_displays_known_model_metrics(self, tmp_path):
        from dashboard import app as dashboard_app

        result_data = {
            "test_rows": 11102,
            "test_start_date": "2025-04-27T21:00:00",
            "test_end_date": "2026-08-03T10:00:00",
            "models": {
                "xgboost": {
                    "accuracy": 0.5251306071,
                    "balanced_accuracy": 0.5251528181,
                    "precision": 0.5233327677,
                    "recall": 0.5559762034,
                    "f1_score": 0.5391608392,
                },
                "logistic_regression": {
                    "accuracy": 0.5284633399,
                    "balanced_accuracy": 0.5284657563,
                    "precision": 0.5279169649,
                    "recall": 0.5318190013,
                    "f1_score": 0.5298607993,
                },
                "random_forest": {
                    "accuracy": 0.5227886867,
                    "balanced_accuracy": 0.5228141419,
                    "precision": 0.5209490156,
                    "recall": 0.5581395349,
                    "f1_score": 0.5389033943,
                },
            },
            "conclusion": "The models perform similarly.",
        }
        result_file = tmp_path / "scripts" / "results" / "btc_1h_model_family_comparison.json"
        result_file.parent.mkdir(parents=True)
        result_file.write_text(__import__("json").dumps(result_data), encoding="utf-8")

        with patch.object(dashboard_app, "_project_root", str(tmp_path)):
            result = dashboard_app.build_model_family_comparison()

        text = " ".join(_collect_text(result))
        assert "52.51%" in text
        assert "52.85%" in text
        assert "52.28%" in text
        assert "11,102 identical unseen rows" in text

    def test_missing_result_file_shows_clear_alert(self, tmp_path):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "_project_root", str(tmp_path)):
            result = dashboard_app.build_model_family_comparison()

        text = " ".join(_collect_text(result))
        assert "No model family comparison results are available" in text
        assert "Run the BTC 1h comparison experiment first" in text

    def test_displays_saved_conclusion(self, tmp_path):
        from dashboard import app as dashboard_app

        result_file = tmp_path / "scripts" / "results" / "btc_1h_model_family_comparison.json"
        result_file.parent.mkdir(parents=True)
        result_file.write_text(
            __import__("json").dumps({
                "test_rows": 100,
                "test_start_date": "2025-01-01T00:00:00",
                "test_end_date": "2025-01-05T03:00:00",
                "models": {
                    "xgboost": {"accuracy": 0.52, "balanced_accuracy": 0.52, "precision": 0.52, "recall": 0.52, "f1_score": 0.52},
                },
                "conclusion": "The available data is the main limitation.",
            }),
            encoding="utf-8",
        )

        with patch.object(dashboard_app, "_project_root", str(tmp_path)):
            result = dashboard_app.build_model_family_comparison()

        text = " ".join(_collect_text(result))
        assert "The available data is the main limitation." in text

    def test_displays_result_freshness(self, tmp_path):
        from dashboard import app as dashboard_app

        result_file = tmp_path / "scripts" / "results" / "btc_1h_model_family_comparison.json"
        result_file.parent.mkdir(parents=True)
        result_file.write_text(
            __import__("json").dumps({
                "generated_at": "2026-08-07T14:30:00+00:00",
                "source_data_end_date": "2026-08-07T13:00:00",
                "test_rows": 100,
                "test_start_date": "2026-08-01T00:00:00",
                "test_end_date": "2026-08-07T13:00:00",
                "models": {
                    "xgboost": {"accuracy": 0.52, "balanced_accuracy": 0.52, "precision": 0.52, "recall": 0.52, "f1_score": 0.52},
                },
                "conclusion": "The models perform similarly.",
            }),
            encoding="utf-8",
        )

        with patch.object(dashboard_app, "_project_root", str(tmp_path)):
            result = dashboard_app.build_model_family_comparison()

        text = " ".join(_collect_text(result))
        assert "Generated: 2026-08-07 14:30 UTC" in text
        assert "Source data through: 2026-08-07 13:00 UTC" in text


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


class TestConfidenceTimeline:
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
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        fig = result.figure
        names = [t.name for t in fig.data]
        assert any("Correct" in n for n in names)
        assert any("Wrong" in n for n in names)

    def test_correct_green_wrong_red(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        fig = result.figure
        for trace in fig.data:
            if "Correct" in trace.name:
                assert trace.marker.color == "#27ae60"
            elif "Wrong" in trace.name:
                assert trace.marker.color == "#c0392b"

    def test_x_axis_is_date(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        fig = result.figure
        assert fig.layout.xaxis.title.text == "Date"
        correct_trace = [t for t in fig.data if "Correct" in t.name][0]
        assert len(correct_trace.x) == 7

    def test_y_axis_is_confidence(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        fig = result.figure
        assert fig.layout.yaxis.title.text == "Confidence"

    def test_coin_flip_line_at_0_5(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        fig = result.figure
        shapes = fig.layout.shapes
        assert any(s.y0 == 0.5 and s.y1 == 0.5 for s in shapes)

    def test_title_includes_asset_interval_and_n(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "BTC" in title
        assert "1h" in title
        assert "n=10" in title

    def test_no_model_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", side_effect=FileNotFoundError):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        text = _collect_text(result)
        assert any("No trained model" in t for t in text)

    def test_no_data_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=None):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        text = _collect_text(result)
        assert any("No prediction data" in t for t in text)

    def test_only_oos_data_used(self):
        from dashboard import app as dashboard_app

        df = self._fake_predictions()
        df["is_oos"] = [True] * 5 + [False] * 5
        with patch.object(dashboard_app, "run_prediction", return_value=df):
            result = dashboard_app.build_confidence_timeline("crypto", "BTC", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "n=5" in title

    def test_works_for_stocks(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_confidence_timeline("stocks", "AAPL", "1h")

        fig = result.figure
        title = fig.layout.title.text
        assert "AAPL" in title
        assert "1h" in title


class TestCalibrationMetrics:
    def test_calculates_ece_and_confidence_bins_from_oos_predictions(self):
        from dashboard import app as dashboard_app

        predictions = pd.DataFrame({
            "prediction": [1, 0, 1, 0, 1],
            "confidence": [0.52, 0.54, 0.62, 0.68, 0.95],
            "actual_direction": [1, 1, 1, 0, 0],
            "is_oos": [True, True, True, True, False],
        })

        metrics = dashboard_app._calculate_calibration_metrics(predictions, n_bins=5)
        bins = metrics["calibration_bins"]

        assert metrics["expected_calibration_error"] == pytest.approx(0.19)
        assert bins.to_dict("records") == [
            {"confidence": pytest.approx(0.53), "accuracy": pytest.approx(0.5), "count": 2},
            {"confidence": pytest.approx(0.65), "accuracy": pytest.approx(1.0), "count": 2},
        ]

    def test_returns_unavailable_metrics_without_known_outcomes(self):
        from dashboard import app as dashboard_app

        predictions = pd.DataFrame({
            "prediction": [1, 0],
            "confidence": [0.6, 0.7],
            "actual_direction": [float("nan"), float("nan")],
            "is_oos": [True, True],
        })

        metrics = dashboard_app._calculate_calibration_metrics(predictions)

        assert metrics["expected_calibration_error"] is None
        assert metrics["calibration_bins"].empty


class TestCalibrationReliability:
    def _fake_predictions(self):
        return pd.DataFrame({
            "prediction": [1, 0, 1, 0, 1],
            "confidence": [0.52, 0.54, 0.62, 0.68, 0.95],
            "actual_direction": [1, 1, 1, 0, 0],
            "is_oos": [True, True, True, True, False],
        })

    def test_displays_curve_scores_and_reliability_values(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()):
            result = dashboard_app.build_calibration_reliability("crypto", "BTC", "1h")

        graph = next(child for child in result.children if hasattr(child, "figure"))
        fig = graph.figure
        perfect, reliability = fig.data
        text = _collect_text(result)

        assert list(perfect.x) == [0.5, 1.0]
        assert list(perfect.y) == [0.5, 1.0]
        assert list(reliability.x) == pytest.approx([0.53, 0.62, 0.68])
        assert list(reliability.y) == pytest.approx([0.5, 1.0, 1.0])
        assert list(reliability.customdata) == [2, 1, 1]
        for value in ["0.192", "19.0%", "53.0%", "50.0%", "62.0%", "68.0%", "100.0%", "2", "1"]:
            assert value in text
        assert "n=4" in fig.layout.title.text

    def test_no_model_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", side_effect=FileNotFoundError):
            result = dashboard_app.build_calibration_reliability("crypto", "BTC", "1h")

        assert any("No trained model" in value for value in _collect_text(result))

    def test_no_known_outcomes_shows_warning(self):
        from dashboard import app as dashboard_app

        predictions = self._fake_predictions()
        predictions["actual_direction"] = float("nan")
        with patch.object(dashboard_app, "run_prediction", return_value=predictions):
            result = dashboard_app.build_calibration_reliability("crypto", "BTC", "1h")

        assert any("No valid predictions" in value for value in _collect_text(result))


class TestConfidenceThresholdEvaluation:
    def _fake_predictions(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="1h"),
            "close": [100, 101, 102, 103, 104],
            "prediction": [1, 0, 1, 0, 1],
            "confidence": [0.50, 0.51, 0.52, 0.54, 0.58],
            "actual_direction": [1, 1, 1, 0, 0],
            "is_oos": [True] * 5,
        })

    def test_threshold_accuracy_coverage_and_counts(self):
        from dashboard import app as dashboard_app

        empty = pd.DataFrame()
        metrics = {
            "total_trades": 2,
            "total_return_pct": 1.25,
            "max_drawdown_pct": 0.75,
        }
        with patch("backtesting.strategy.run_strategy", return_value=(empty, empty)), \
             patch("backtesting.metrics.compute_metrics", return_value=metrics):
            rows = dashboard_app.build_confidence_threshold_rows(
                self._fake_predictions(), "1h", "crypto"
            )

        assert rows[0] == {
            "threshold": 0.50,
            "accuracy": 60.0,
            "coverage": 100.0,
            "correct": 3,
            "wrong": 2,
            "trades": 2,
            "return": 1.25,
            "drawdown": 0.75,
        }
        assert rows[1]["threshold"] == 0.52
        assert rows[1]["accuracy"] == pytest.approx(66.67, abs=0.01)
        assert rows[1]["coverage"] == 60.0
        assert rows[1]["correct"] == 2
        assert rows[1]["wrong"] == 1
        assert rows[-1]["threshold"] == 0.58
        assert rows[-1]["accuracy"] == 0.0
        assert rows[-1]["coverage"] == 20.0

    def test_only_oos_predictions_are_evaluated(self):
        from dashboard import app as dashboard_app

        df = self._fake_predictions()
        df.loc[4, "is_oos"] = False
        empty = pd.DataFrame()
        metrics = {
            "total_trades": 0,
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }
        with patch("backtesting.strategy.run_strategy", return_value=(empty, empty)), \
             patch("backtesting.metrics.compute_metrics", return_value=metrics):
            rows = dashboard_app.build_confidence_threshold_rows(df, "1h", "crypto")

        assert rows[0]["coverage"] == 100.0
        assert rows[0]["correct"] == 3
        assert rows[0]["wrong"] == 1
        assert rows[-1]["coverage"] == 0.0

    def test_table_displays_headers_and_formatted_values(self):
        from dashboard import app as dashboard_app

        rows = [{
            "threshold": 0.52,
            "accuracy": 54.4,
            "coverage": 61.0,
            "correct": 33,
            "wrong": 28,
            "trades": 12,
            "return": 2.5,
            "drawdown": 1.75,
        }]
        with patch.object(dashboard_app, "run_prediction", return_value=self._fake_predictions()), \
             patch.object(dashboard_app, "build_confidence_threshold_rows", return_value=rows):
            result = dashboard_app.build_confidence_threshold_table("crypto", "BTC", "1h")

        text = _collect_text(result)
        for heading in ["Threshold", "Accuracy", "Coverage", "Correct", "Wrong", "Trades", "Return", "Drawdown"]:
            assert heading in text
        for value in ["0.52", "54.4%", "61.0%", "33", "28", "12", "+2.50%", "1.75%"]:
            assert value in text

    def test_no_model_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", side_effect=FileNotFoundError):
            result = dashboard_app.build_confidence_threshold_table("crypto", "BTC", "1h")

        assert any("No trained model" in value for value in _collect_text(result))

    def test_no_data_shows_warning(self):
        from dashboard import app as dashboard_app

        with patch.object(dashboard_app, "run_prediction", return_value=None):
            result = dashboard_app.build_confidence_threshold_table("crypto", "BTC", "1h")

        assert any("No prediction data" in value for value in _collect_text(result))


class TestPerformanceStability:
    def test_monthly_and_quarterly_accuracy_use_known_oos_outcomes(self):
        from dashboard import app as dashboard_app

        predictions = pd.DataFrame({
            "date": pd.to_datetime([
                "2024-01-05", "2024-01-15", "2024-01-25",
                "2024-02-05", "2024-02-15", "2024-02-20", "2024-02-25",
            ]),
            "close": [100, 101, 102, 103, 104, 105, 106],
            "prediction": [1, 0, 1, 0, 1, 1, 0],
            "confidence": [0.60] * 7,
            "actual_direction": [1, 1, 1, 0, 0, 0, float("nan")],
            "is_oos": [True, True, True, True, True, False, True],
        })

        with patch("backtesting.strategy.simulate_trades", return_value=(pd.DataFrame(), pd.DataFrame())):
            result = dashboard_app.calculate_performance_stability(predictions, 30)

        monthly = result["monthly_accuracy"]
        quarterly = result["quarterly_accuracy"]
        assert monthly["accuracy"].tolist() == pytest.approx([2 / 3, 1 / 2])
        assert monthly["count"].tolist() == [3, 2]
        assert quarterly["accuracy"].tolist() == pytest.approx([3 / 5])
        assert quarterly["count"].tolist() == [5]

    def test_rolling_accuracy_uses_30_and_90_day_windows(self):
        from dashboard import app as dashboard_app

        dates = pd.date_range("2024-01-01", periods=91, freq="1D")
        predictions = pd.DataFrame({
            "date": dates,
            "close": range(100, 191),
            "prediction": [1] * 89 + [0, 0],
            "confidence": [0.60] * 91,
            "actual_direction": [1] * 89 + [0, 1],
            "is_oos": [True] * 91,
        })

        with patch("backtesting.strategy.simulate_trades", return_value=(pd.DataFrame(), pd.DataFrame())):
            result = dashboard_app.calculate_performance_stability(predictions, 30)

        rolling = result["rolling_accuracy"].dropna(subset=["accuracy_30d", "accuracy_90d"])
        assert rolling.iloc[-1]["accuracy_30d"] == pytest.approx(29 / 30)
        assert rolling.iloc[-1]["accuracy_90d"] == pytest.approx(89 / 90)

    def test_rolling_trading_return_and_drawdown_use_selected_window(self):
        from dashboard import app as dashboard_app

        dates = pd.date_range("2024-01-01", periods=31, freq="1D")
        predictions = pd.DataFrame({
            "date": dates,
            "close": [100] * 31,
            "prediction": [1] * 31,
            "confidence": [0.60] * 31,
            "actual_direction": [1] * 31,
            "is_oos": [True] * 31,
        })
        equity = pd.DataFrame({
            "date": dates,
            "equity": [10000, 100, 120] + [120] * 27 + [90],
            "drawdown_pct": [0.0] * 31,
        })

        with patch("backtesting.strategy.simulate_trades", return_value=(pd.DataFrame(), equity)):
            result = dashboard_app.calculate_performance_stability(predictions, 30)

        rolling = result["rolling_trading"].dropna()
        assert rolling.iloc[-1]["rolling_return"] == pytest.approx(-0.1)
        assert rolling.iloc[-1]["rolling_drawdown"] == pytest.approx(0.3)

    def test_callback_uses_selected_window_and_displays_exact_values(self):
        from dashboard import app as dashboard_app

        stability = {
            "monthly_accuracy": pd.DataFrame({
                "date": pd.to_datetime(["2024-01-31"]),
                "accuracy": [0.60],
                "count": [10],
            }),
            "quarterly_accuracy": pd.DataFrame({
                "date": pd.to_datetime(["2024-03-31"]),
                "accuracy": [0.55],
                "count": [20],
            }),
            "rolling_accuracy": pd.DataFrame({
                "date": pd.to_datetime(["2024-03-31"]),
                "accuracy_30d": [0.58],
                "accuracy_90d": [0.53],
            }),
            "rolling_trading": pd.DataFrame({
                "date": pd.to_datetime(["2024-03-31"]),
                "rolling_return": [4.25],
                "rolling_drawdown": [1.75],
            }),
        }

        with patch.object(dashboard_app, "run_prediction", return_value=pd.DataFrame({"date": ["2024-01-01"]})), \
             patch.object(dashboard_app, "calculate_performance_stability", return_value=stability) as calculate:
            result = dashboard_app.build_performance_stability("crypto", "BTC", "1h", 90)

        calculate.assert_called_once()
        assert calculate.call_args.args[1] == 90
        accuracy_fig = result.children[0].children.figure
        trading_fig = result.children[1].children.figure
        assert [trace.name for trace in accuracy_fig.data] == [
            "Monthly accuracy",
            "Quarterly accuracy",
            "Rolling 30-day accuracy",
            "Rolling 90-day accuracy",
        ]
        assert [trace.y[0] for trace in accuracy_fig.data] == pytest.approx([0.60, 0.55, 0.58, 0.53])
        assert [trace.name for trace in trading_fig.data] == [
            "Rolling 90-day return",
            "Rolling 90-day drawdown",
        ]
        assert [trace.y[0] for trace in trading_fig.data] == pytest.approx([4.25, 1.75])

    def test_missing_oos_data_shows_warning(self):
        from dashboard import app as dashboard_app

        predictions = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "close": [100, 101],
            "prediction": [1, 0],
            "confidence": [0.60, 0.60],
            "actual_direction": [1, 0],
            "is_oos": [False, False],
        })

        with patch.object(dashboard_app, "run_prediction", return_value=predictions):
            result = dashboard_app.build_performance_stability("crypto", "BTC", "1h", 30)

        assert any(
            "No valid out-of-sample data" in value
            for value in _collect_text(result)
        )