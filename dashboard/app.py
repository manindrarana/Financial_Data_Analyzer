"""
Financial Data Analyzer — Plotly Dash Dashboard
Multi-tab web UI reading directly from DuckDB gold tables.
"""

import math
import os
import sys
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
import dash
from dash import dcc, html, dash_table, DiskcacheManager
import dash_bootstrap_components as dbc
import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, f1_score, matthews_corrcoef
from dashboard.predictor import run_prediction
from dashboard.model_health import (
    CLASSIFICATION_RANKING_OBJECTIVES,
    RANKING_OBJECTIVES,
    STATUS_COLORS,
    STATUS_LABELS,
    get_model_health,
    get_summary_counts,
    evaluate_trading_performance,
    rank_models,
)
from dashboard.pipeline_history import get_pipeline_runs, get_run_summary
import diskcache

load_dotenv()
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "financial_data.duckdb")

_cache_dir = os.environ.get("DASH_CACHE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".dash_cache")))
_cache = diskcache.Cache(_cache_dir, sqlite_journal_mode="wal", sqlite_synchronous=1)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="Financial Data Analyzer",
    background_callback_manager=DiskcacheManager(_cache),
)

app._favicon = None

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .dash-datepicker,
            .dash-datepicker-input-wrapper,
            .dash-datepicker-content,
            .dash-datepicker-portal,
            .dash-datepicker-portal .dash-datepicker-calendar-wrapper,
            .dash-datepicker-portal .dash-datepicker-fullscreen,
            .dash-datepicker-controls,
            .dash-datepicker-controls .dash-dropdown,
            .dash-datepicker-controls .dash-input {
                --Dash-Fill-Inverse-Strong: #1a1a1a;
                --Dash-Stroke-Strong: #444;
                --Dash-Text-Strong: #ccc;
                --Dash-Text-Disabled: #666;
                --Dash-Text-Weak: #999;
                --Dash-Fill-Interactive-Strong: #3498db;
                --Dash-Fill-Interactive-Weak: rgba(52,152,219,0.15);
                --Dash-Shading-Strong: rgba(0,0,0,0.7);
                --Dash-Shading-Weak: rgba(0,0,0,0.3);
                --Dash-Fill-Disabled: #333;
            }
            .dash-dropdown-content {
                background: #1a1a1a !important;
            }
            .dash-dropdown-content .dash-dropdown-option {
                color: #ccc !important;
            }
            .dash-dropdown-content .dash-dropdown-search {
                color: #ccc !important;
            }
            .dash-datepicker-input {
                color: #fff !important;
            }
            .dash-datepicker-input::placeholder {
                color: #888 !important;
            }
            .dash-datepicker-content,
            .dash-datepicker-portal,
            .dash-datepicker-controls {
                color: #ccc !important;
            }
            .dash-datepicker-controls *,
            .dash-datepicker-calendar-wrapper *,
            .dash-datepicker-content * {
                color: #ccc !important;
            }
            .dash-datepicker-calendar-wrapper [role="gridcell"] button:hover {
                background: rgba(52,152,219,0.2) !important;
            }
            .dash-datepicker-calendar-wrapper [role="gridcell"][aria-selected="true"] button {
                background: #3498db !important;
                color: #fff !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

PRICE_RANGE_OPTIONS = [
    {"label": "1 Day", "value": "1d"},
    {"label": "3 Days", "value": "3d"},
    {"label": "1 Week", "value": "7d"},
    {"label": "1 Month", "value": "30d"},
    {"label": "3 Months", "value": "90d"},
    {"label": "6 Months", "value": "180d"},
    {"label": "1 Year", "value": "365d"},
    {"label": "All Data", "value": "all"},
]

app.layout = dbc.Container(
    fluid=True,
    className="p-3",
    children=[
        dbc.Row(
            dbc.Col(
                html.H1(" Financial Data Analyzer", className="text-center text-info my-3"),
                width=12,
            )
        ),
        dbc.Row(
            [
                dbc.Col(
                    html.Div(id="freshness-crypto-badge", className="text-center mb-2"),
                    width=6,
                ),
                dbc.Col(
                    html.Div(id="freshness-stock-badge", className="text-center mb-2"),
                    width=6,
                ),
            ]
        ),
        dcc.Interval(id="freshness-interval", interval=60_000),
        dbc.Tabs(
            id="main-tabs",
            active_tab="tab-overview",
            children=[
                dbc.Tab(label=" Overview", tab_id="tab-overview"),
                dbc.Tab(label=" Price Dashboard", tab_id="tab-price"),
                dbc.Tab(label=" Predictions", tab_id="tab-predictions"),
                dbc.Tab(label=" Backtest", tab_id="tab-backtest"),
                dbc.Tab(label=" Technical Indicators", tab_id="tab-indicators"),
                dbc.Tab(label=" Data Explorer", tab_id="tab-explorer"),
                dbc.Tab(label=" Model Health", tab_id="tab-model-health"),
                dbc.Tab(label=" Model Insights", tab_id="tab-model-insights"),
                dbc.Tab(label=" Pipeline History", tab_id="tab-pipeline-history"),
            ],
        ),
        html.Hr(),
        html.Div(
            id="indicator-toggles-container",
            children=dbc.Checklist(
                id="indicator-toggles",
                options=[
                    {"label": "EMA 9", "value": "ema9"},
                    {"label": "EMA 21", "value": "ema21"},
                    {"label": "EMA 50", "value": "ema50"},
                    {"label": "SMA 50", "value": "sma50"},
                    {"label": "SMA 200", "value": "sma200"},
                    {"label": "Bollinger Bands", "value": "bb"},
                    {"label": "VWAP", "value": "vwap"},
                    {"label": "SMA Crossover", "value": "sma_crossover"},
                    {"label": "MACD", "value": "macd"},
                    {"label": "RSI", "value": "rsi"},
                    {"label": "ATR", "value": "atr"},
                    {"label": "OBV", "value": "obv"},
                    {"label": "Volume", "value": "volume"},
                ],
                value=[],
                inline=True,
                className="mb-2",
            ),
        ),
        html.Div(
            id="price-chart-area",
            children=[
                html.H3("Price Dashboard", className="text-light mb-2"),
                html.P(
                    "Interactive candlestick charts with volume and moving averages for any asset and timeframe. Use the dropdowns to switch between assets, intervals, and date ranges.",
                    className="text-muted small mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Asset Class", className="text-muted small mb-1"),
                                dcc.Dropdown(
                                    id="price-class-dropdown",
                                    options=[
                                        {"label": "Crypto", "value": "crypto"},
                                        {"label": "Stocks", "value": "stocks"},
                                    ],
                                    value="crypto",
                                    clearable=False,
                                    searchable=False,
                                    style={"color": "#000"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Asset", className="text-muted small mb-1"),
                                dcc.Dropdown(
                                    id="price-asset-dropdown",
                                    clearable=False,
                                    searchable=True,
                                    style={"color": "#000"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Interval", className="text-muted small mb-1"),
                                dcc.Dropdown(
                                    id="price-interval-dropdown",
                                    clearable=False,
                                    searchable=False,
                                    style={"color": "#000"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Time Range", className="text-muted small mb-1"),
                                dcc.Dropdown(
                                    id="price-range-dropdown",
                                    options=PRICE_RANGE_OPTIONS,
                                    value="7d",
                                    clearable=False,
                                    searchable=False,
                                    style={"color": "#000"},
                                ),
                            ],
                            width=2,
                        ),
                    ],
                    className="mb-3",
                ),
                html.Div(
                    id="chart-info-bar",
                    style={
                        "color": "#adb5bd", "fontSize": "12px", "fontFamily": "monospace",
                        "padding": "2px 8px", "backgroundColor": "rgba(33,37,41,0.6)",
                        "borderRadius": "4px", "minHeight": "22px",
                        "display": "flex", "flexWrap": "wrap", "gap": "8px 16px",
                    },
                ),
                dcc.Store(id="indicator-data-store"),
                dcc.Loading(
                    id="loading-price",
                    type="circle",
                    children=dcc.Graph(
                        id="price-chart",
                        config={"displayModeBar": True, "responsive": True, "scrollZoom": True, "displaylogo": False},
                    ),
                ),
            ],
        ),
        html.Div(id="tab-content"),
    ],
)

@app.callback(
    dash.Output("tab-content", "children"),
    dash.Input("main-tabs", "active_tab"),
)

def render_tab(active_tab: str):
    """Route to the correct tab layout based on the active tab ID."""
    if active_tab == "tab-overview":
        return render_overview()
    elif active_tab == "tab-price":
        return render_price_dashboard()
    elif active_tab == "tab-predictions":
        return render_predictions()
    elif active_tab == "tab-backtest":
        return render_backtest()
    elif active_tab == "tab-indicators":
        return render_indicators()
    elif active_tab == "tab-explorer":
        return render_explorer()
    elif active_tab == "tab-model-health":
        return render_model_health()
    elif active_tab == "tab-model-insights":
        return render_model_insights()
    elif active_tab == "tab-pipeline-history":
        return render_pipeline_history()
    return html.P("Select a tab.", className="text-muted")


@app.callback(
    dash.Output("price-chart-area", "style"),
    dash.Input("main-tabs", "active_tab"),
)
def toggle_price_chart_area(active_tab):
    if active_tab == "tab-price":
        return {"display": "block"}
    return {"display": "none"}


@app.callback(
    dash.Output("indicator-toggles-container", "style"),
    dash.Input("main-tabs", "active_tab"),
)
def toggle_indicator_toggles(active_tab):
    if active_tab == "tab-price":
        return {"display": "block"}
    return {"display": "none"}


def render_price_dashboard():
    return None

def render_predictions():
    """XGBoost model predictions with asset class, asset, and interval selectors."""
    try:
        return dbc.Row(
            dbc.Col(
                [
                    html.H3("XGBoost Direction Predictions", className="text-light mb-2"),
                    html.P(
                        "Machine learning predictions for next-day price direction (up or down) using XGBoost models. Shows out-of-sample accuracy and compares against simple baselines like always predicting up.",
                        className="text-muted small mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Asset Class", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="pred-class-dropdown",
                                        options=[
                                            {"label": "Crypto", "value": "crypto"},
                                            {"label": "Stocks", "value": "stocks"},
                                        ],
                                        value="crypto",
                                        clearable=False,
                                        searchable=False,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Asset", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="pred-asset-dropdown",
                                        clearable=False,
                                        searchable=True,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Interval", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="pred-interval-dropdown",
                                        clearable=False,
                                        searchable=False,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Time Range", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="pred-range-dropdown",
                                        options=[
                                            {"label": "1 Day", "value": "1d"},
                                            {"label": "3 Days", "value": "3d"},
                                            {"label": "1 Week", "value": "7d"},
                                            {"label": "1 Month", "value": "30d"},
                                            {"label": "3 Months", "value": "90d"},
                                            {"label": "6 Months", "value": "180d"},
                                            {"label": "1 Year", "value": "365d"},
                                            {"label": "All Time", "value": "all"},
                                        ],
                                        value="90d",
                                        clearable=False,
                                        searchable=False,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dcc.Loading(
                        id="loading-pred",
                        type="circle",
                        children=html.Div(id="pred-content"),
                    ),
                ],
                width=12,
            )
        )
    except Exception as e:
        return dbc.Alert(f"Error: {e}", color="danger")

def render_backtest():
    """Interactive walk-forward backtest with configurable asset, date range, and strategy params."""
    return dbc.Row(
        dbc.Col(
            [
                html.H3("Walk-Forward Backtest", className="text-light mb-2"),
                html.P(
                    "Simulates trading strategies on historical data using walk-forward validation, which retrains the model on each fold to mimic real-world conditions. Shows the equity curve, trade metrics, and per-fold breakdown.",
                    className="text-muted small mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Backtest Mode", className="text-muted small mb-1", title="Walk-Forward retrains the model on each fold to simulate real conditions. Pre-trained uses an existing saved model. Portfolio tests multiple assets together."),
                                dcc.RadioItems(
                                    id="bt-mode-radio",
                                    options=[
                                        {"label": "Walk-Forward (retrain/fold)", "value": "walk_forward"},
                                        {"label": "Pre-trained Model", "value": "pretrained"},
                                        {"label": "Portfolio (multi-asset)", "value": "portfolio"},
                                    ],
                                    value="walk_forward",
                                    labelStyle={"display": "block", "color": "#adb5bd", "fontSize": "12px"},
                                    inputStyle={"marginRight": "6px"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Asset Class", className="text-muted small mb-1"),
                                dcc.Dropdown(
                                    id="bt-class-dropdown",
                                    options=[
                                        {"label": "Crypto", "value": "crypto"},
                                        {"label": "Stocks", "value": "stocks"},
                                    ],
                                    value="crypto",
                                    clearable=False,
                                    searchable=False,
                                    style={"color": "#000"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Asset", className="text-muted small mb-1"),
                                dcc.Dropdown(
                                    id="bt-asset-dropdown",
                                    clearable=False,
                                    searchable=True,
                                    style={"color": "#000"},
                                ),
                                html.Div(
                                    dcc.Dropdown(
                                        id="bt-portfolio-assets",
                                        multi=True,
                                        placeholder="Select 2+ assets",
                                        searchable=True,
                                        style={"color": "#000"},
                                    ),
                                    id="bt-portfolio-assets-container",
                                    style={"display": "none"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Interval", className="text-muted small mb-1"),
                                dcc.Dropdown(
                                    id="bt-interval-dropdown",
                                    clearable=False,
                                    searchable=False,
                                    style={"color": "#000"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Date Range", className="text-muted small mb-1"),
                                dcc.DatePickerRange(
                                    id="bt-date-range",
                                    start_date_placeholder_text="Start",
                                    end_date_placeholder_text="End",
                                    calendar_orientation="horizontal",
                                    display_format="YYYY-MM-DD",
                                    style={"fontSize": "12px"},
                                ),
                            ],
                            width=3,
                        ),
                        dbc.Col(
                            [
                                html.Label("\u00A0", className="mb-1", style={"display": "block"}),
                                dbc.Button(
                                    "Run Backtest",
                                    id="bt-run-btn",
                                    color="info",
                                    className="w-100",
                                ),
                            ],
                            width=3,
                        ),
                    ],
                    className="mb-3 align-items-end",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Confidence", className="text-muted small mb-1", title="Minimum model prediction probability to enter a trade. Higher means fewer but safer trades."),
                                dbc.Input(id="bt-confidence", type="number", min=0.5, max=0.95, step=0.01, value=0.52, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Stop Loss %", className="text-muted small mb-1", title="If price drops this percentage from entry, the position is automatically closed to limit losses."),
                                dbc.Input(id="bt-stop-loss", type="number", min=0.5, max=10, step=0.5, value=2.0, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Take Profit %", className="text-muted small mb-1", title="If price rises this percentage from entry, the position is automatically closed to lock in gains."),
                                dbc.Input(id="bt-take-profit", type="number", min=1, max=20, step=0.5, value=4.0, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Max Hold Bars", className="text-muted small mb-1", title="Maximum number of candles to hold a position before closing it, regardless of profit or loss."),
                                dbc.Input(id="bt-max-hold", type="number", min=4, max=200, step=1, value=24, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Initial Capital", className="text-muted small mb-1", title="Starting balance for the simulated portfolio."),
                                dbc.Input(id="bt-capital", type="number", min=1000, max=1000000, step=1000, value=10000, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Train Months", className="text-muted small mb-1", title="Number of months of historical data used to train the model in each walk-forward fold."),
                                dbc.Input(id="bt-train-months", type="number", min=3, max=24, step=1, value=6, style={"color": "#000"}),
                            ],
                            width=1,
                        ),
                        dbc.Col(
                            [
                                html.Label("Test Months", className="text-muted small mb-1", title="Number of months of data the trained model predicts on before the next fold retrains."),
                                dbc.Input(id="bt-test-months", type="number", min=1, max=6, step=1, value=1, style={"color": "#000"}),
                            ],
                            width=1,
                        ),
                        dbc.Col(
                            [
                                html.Label("Step Months", className="text-muted small mb-1", title="How far forward the window shifts after each fold. Smaller means more folds and more retraining."),
                                dbc.Input(id="bt-step-months", type="number", min=1, max=6, step=1, value=1, style={"color": "#000"}),
                            ],
                            width=1,
                        ),
                        dbc.Col(
                            [
                                html.Label("Txn Cost %", className="text-muted small mb-1", title="Simulated fee percentage charged per trade. Models real exchange or broker fees."),
                                dbc.Input(id="bt-txn-cost", type="number", min=0, max=1, step=0.01, value=0.10, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Allow Short", className="text-muted small mb-1", title="When enabled, the strategy can sell assets it does not own, profiting from price drops."),
                                dbc.Checklist(
                                    id="bt-allow-short",
                                    options=[{"label": " Enable short selling", "value": True}],
                                    value=[],
                                    inline=True,
                                    style={"color": "#adb5bd", "fontSize": "12px", "paddingTop": "10px"},
                                ),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Max Positions", className="text-muted small mb-1", title="Maximum number of open positions at the same time in portfolio mode."),
                                dbc.Input(id="bt-max-positions", type="number", min=1, max=10, step=1, value=3, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                    ],
                    className="mb-3 align-items-end",
                ),
                html.Div(id="bt-progress-bar", className="mb-2"),
                html.Div(id="bt-results"),
            ],
            width=12,
        )
    )


def _build_backtest_results(metrics, equity_df, trades_df, buy_hold_df=None):
    """Build Dash UI components from backtest results."""
    if trades_df.empty:
        return dbc.Alert("No trades executed — try relaxing the confidence threshold or date range.", color="warning")

    buy_hold_return_pct = 0.0
    buy_hold_equity = None
    buy_hold_dates = None
    if isinstance(buy_hold_df, dict):
        buy_hold_return_pct = buy_hold_df.get("return_pct", 0.0)
        buy_hold_equity = buy_hold_df.get("equity")
        buy_hold_dates = buy_hold_df.get("dates")
    elif buy_hold_df is not None and not buy_hold_df.empty:
        bh = buy_hold_df[["date", "close"]].copy()
        bh["date"] = pd.to_datetime(bh["date"])
        bh = bh.sort_values("date")
        bh = bh[bh["date"] >= pd.to_datetime(equity_df["date"].min())]
        if not bh.empty and bh["close"].iloc[0] > 0:
            buy_hold_return_pct = (bh["close"].iloc[-1] / bh["close"].iloc[0] - 1) * 100
            buy_hold_dates = bh["date"]
            buy_hold_equity = equity_df["equity"].iloc[0] * bh["close"] / bh["close"].iloc[0]

    benchmark_metrics = buy_hold_df if isinstance(buy_hold_df, dict) else {}
    benchmark_cards = None
    if benchmark_metrics:
        benchmark_cards = dbc.Row(
            [
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5(f"{benchmark_metrics.get('max_drawdown_pct', 0):.2f}%", className="card-title text-warning"),
                    html.P("Buy & Hold Max Drawdown", className="card-text text-muted small"),
                ]), color="dark", outline=True), width=3),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5(f"{benchmark_metrics.get('sharpe_ratio', 0):.2f}", className="card-title text-warning"),
                    html.P("Buy & Hold Sharpe", className="card-text text-muted small"),
                ]), color="dark", outline=True), width=3),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5(f"{benchmark_metrics.get('volatility_pct', 0):.2f}%", className="card-title text-warning"),
                    html.P("Buy & Hold Volatility", className="card-text text-muted small"),
                ]), color="dark", outline=True), width=3),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H5(f"${benchmark_metrics.get('total_cost', 0):,.2f}", className="card-title text-warning"),
                    html.P("Buy & Hold Total Cost", className="card-text text-muted small"),
                ]), color="dark", outline=True), width=3),
            ],
            className="mb-3",
        )
    metric_cards = dbc.Row(
        [
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('total_return_pct', 0):+.2f}%", className="card-title text-info"),
                html.P("Total Return", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{buy_hold_return_pct:+.2f}%", className="card-title text-warning"),
                html.P("Buy & Hold Return", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('sharpe_ratio', 0):.2f}", className="card-title text-info"),
                html.P("Sharpe Ratio", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('volatility_pct', 0):.2f}%", className="card-title text-info"),
                html.P("Volatility", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('max_drawdown_pct', 0):.1f}%", className="card-title text-danger"),
                html.P("Max Drawdown", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('win_rate', 0):.1f}%", className="card-title text-info"),
                html.P("Win Rate", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('profit_factor', 0):.2f}", className="card-title text-info"),
                html.P("Profit Factor", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(metrics.get("total_trades", 0)), className="card-title text-info"),
                html.P("Total Trades", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"${metrics.get('total_cost', 0):,.2f}", className="card-title text-warning"),
                html.P("Total Cost", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
        ],
        className="mb-3",
    )

    exit_reasons = metrics.get("exit_reasons", {})
    exit_html = None
    if exit_reasons:
        exit_items = [html.Span(f"{k}: {v}", className="me-3 text-muted small") for k, v in exit_reasons.items()]
        exit_html = html.Div(
            [html.Span("Exit reasons: ", className="text-muted small")] + exit_items,
            className="mb-2",
        )

    equity_df = equity_df.copy()
    equity_df["date"] = pd.to_datetime(equity_df["date"])
    equity_df = equity_df.sort_values("date")

    fig_equity = go.Figure()
    fig_equity.add_trace(go.Scatter(
        x=equity_df["date"], y=equity_df["equity"],
        mode="lines", name="Equity",
        line=dict(color="#17a2b8", width=1.5),
        fill="tozeroy", fillcolor="rgba(23,162,184,0.1)",
    ))
    if buy_hold_equity is not None and buy_hold_dates is not None:
        fig_equity.add_trace(go.Scatter(
            x=pd.to_datetime(buy_hold_dates), y=buy_hold_equity,
            mode="lines", name="Buy & Hold",
            line=dict(color="#f7931a", width=1.5, dash="dash"),
        ))
    fig_equity.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=400, title="Equity Curve", hovermode="x unified",
        margin=dict(l=10, r=10, t=40, b=10),
        dragmode="pan",
        hoverlabel=dict(bgcolor="#212529", font_size=13),
    )
    fig_equity.update_yaxes(title_text="Equity ($)")
    fig_equity.update_xaxes(hoverformat="%Y-%m-%d %H:%M")
    fig_equity.update_traces(hovertemplate="Date: %{x}<br>Value: $%{y:,.2f}<extra></extra>")

    trades_df = trades_df.copy()
    trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])
    trades_df = trades_df.sort_values("entry_time")

    trades_df["color"] = np.where(trades_df["pnl"] > 0, "#26a69a", "#ef5350")
    trades_df["symbol"] = np.where(trades_df["pnl"] > 0, "triangle-up", "triangle-down")

    fig_trades = go.Figure()
    fig_trades.add_trace(go.Scatter(
        x=trades_df["entry_time"], y=trades_df["pnl_pct"],
        mode="markers", name="Trade PnL",
        marker=dict(color=trades_df["color"], size=12, symbol=trades_df["symbol"], line=dict(width=1, color="#fff")),
        customdata=np.column_stack([
            trades_df["entry_time"].dt.strftime("%Y-%m-%d %H:%M"),
            trades_df["exit_time"].dt.strftime("%Y-%m-%d %H:%M"),
            trades_df["pnl"].round(2),
            trades_df["pnl_pct"].round(2),
            trades_df["exit_reason"],
        ]),
        hovertemplate=(
            "Entry: %{customdata[0]}<br>Exit: %{customdata[1]}<br>"
            "PnL: $%{customdata[2]} (%{customdata[3]}%)<br>Exit: %{customdata[4]}<extra></extra>"
        ),
    ))
    fig_trades.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
    fig_trades.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=400, title="Trade PnL (% per trade)", hovermode="closest",
        margin=dict(l=10, r=10, t=40, b=10),
        dragmode="pan",
    )
    fig_trades.update_yaxes(title_text="PnL (%)")

    fold_breakdown = metrics.get("fold_breakdown", [])
    fold_table = None
    if fold_breakdown:
        fold_rows = []
        for fm in fold_breakdown:
            pnl_color = "#26a69a" if fm["pnl"] >= 0 else "#ef5350"
            fold_rows.append(html.Tr([
                html.Td(fm["fold_id"], className="text-center"),
                html.Td(str(fm["trades"]), className="text-center"),
                html.Td(f"${fm['pnl']:+,.2f}", style={"color": pnl_color}),
                html.Td(f"{fm['win_rate']:.1f}%", className="text-center"),
            ]))
        fold_table = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("Fold"), html.Th("Trades"), html.Th("PnL"), html.Th("Win %"),
            ]))] + [html.Tbody(fold_rows)],
            bordered=True, hover=True, size="sm", striped=True,
            className="mt-2",
        )

    direction_breakdown = metrics.get("direction_breakdown", [])
    direction_table = None
    if direction_breakdown:
        dir_rows = []
        for dm in direction_breakdown:
            pnl_color = "#26a69a" if dm["pnl"] >= 0 else "#ef5350"
            dir_label = "Long" if dm["direction"] == "long" else "Short"
            dir_rows.append(html.Tr([
                html.Td(dir_label, className="text-center"),
                html.Td(str(dm["trades"]), className="text-center"),
                html.Td(f"${dm['pnl']:+,.2f}", style={"color": pnl_color}),
                html.Td(f"{dm['win_rate']:.1f}%", className="text-center"),
            ]))
        direction_table = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("Direction"), html.Th("Trades"), html.Th("PnL"), html.Th("Win %"),
            ]))] + [html.Tbody(dir_rows)],
            bordered=True, hover=True, size="sm", striped=True,
            className="mt-2",
        )

    asset_breakdown = metrics.get("asset_breakdown", [])
    asset_table = None
    if asset_breakdown:
        asset_rows = []
        for am in asset_breakdown:
            pnl_color = "#26a69a" if am["pnl"] >= 0 else "#ef5350"
            asset_rows.append(html.Tr([
                html.Td(am["asset"], className="text-center"),
                html.Td(str(am["trades"]), className="text-center"),
                html.Td(f"${am['pnl']:+,.2f}", style={"color": pnl_color}),
                html.Td(f"{am['win_rate']:.1f}%", className="text-center"),
                html.Td(f"${am['total_cost']:.2f}", className="text-center"),
            ]))
        asset_table = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("Asset"), html.Th("Trades"), html.Th("PnL"), html.Th("Win %"), html.Th("Cost"),
            ]))] + [html.Tbody(asset_rows)],
            bordered=True, hover=True, size="sm", striped=True,
            className="mt-2",
        )

    return html.Div([
        metric_cards,
        benchmark_cards,
        exit_html,
        dbc.Row(dbc.Col(dcc.Graph(figure=fig_equity, config={"displayModeBar": True, "responsive": True}), width=12)),
        dbc.Row(dbc.Col(dcc.Graph(figure=fig_trades, config={"displayModeBar": True, "responsive": True}), width=12)),
        html.H6("Per-Fold Breakdown", className="text-light mt-3") if fold_table else None,
        fold_table,
        html.H6("Direction Breakdown", className="text-light mt-3") if direction_table else None,
        direction_table,
        html.H6("Per-Asset Breakdown", className="text-light mt-3") if asset_table else None,
        asset_table,
    ])


@app.callback(
    dash.Output("bt-results", "children"),
    dash.Input("bt-run-btn", "n_clicks"),
    dash.State("bt-mode-radio", "value"),
    dash.State("bt-class-dropdown", "value"),
    dash.State("bt-asset-dropdown", "value"),
    dash.State("bt-portfolio-assets", "value"),
    dash.State("bt-interval-dropdown", "value"),
    dash.State("bt-date-range", "start_date"),
    dash.State("bt-date-range", "end_date"),
    dash.State("bt-confidence", "value"),
    dash.State("bt-stop-loss", "value"),
    dash.State("bt-take-profit", "value"),
    dash.State("bt-max-hold", "value"),
    dash.State("bt-capital", "value"),
    dash.State("bt-train-months", "value"),
    dash.State("bt-test-months", "value"),
    dash.State("bt-step-months", "value"),
    dash.State("bt-txn-cost", "value"),
    dash.State("bt-allow-short", "value"),
    dash.State("bt-max-positions", "value"),
    background=True,
    running=[(dash.Output("bt-run-btn", "disabled"), True, False)],
    progress=[dash.Output("bt-progress-bar", "children")],
    prevent_initial_call=True,
)
def run_backtest_pipeline(set_progress, n_clicks, bt_mode, asset_class, asset, portfolio_assets,
                           interval, date_start, date_end, confidence, stop_loss, take_profit,
                           max_hold, capital, train_months, test_months, step_months,
                           txn_cost, allow_short, max_positions):
    """Background callback: runs the full walk-forward → strategy → metrics pipeline."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if bt_mode == "portfolio":
        if not portfolio_assets or len(portfolio_assets) < 2:
            return dbc.Alert("Portfolio mode requires at least 2 assets selected.", color="warning")
    else:
        if not asset:
            raise dash.exceptions.PreventUpdate

    try:
        if bt_mode == "portfolio":
            set_progress(dbc.Alert(f"Running portfolio backtest for {len(portfolio_assets)} assets...", color="info"))
        elif bt_mode == "pretrained":
            set_progress(dbc.Alert("Loading pre-trained model...", color="info"))
        else:
            set_progress(dbc.Alert("Loading data & training walk-forward model...", color="info"))

        from backtesting.walk_forward import run_walk_forward, run_walk_forward_pretrained, run_portfolio_backtest
        from backtesting.strategy import run_strategy, run_portfolio_strategy, compute_portfolio_buy_and_hold
        from backtesting.metrics import run_metrics

        if bt_mode == "portfolio":
            predictions_dict, _summaries = run_portfolio_backtest(
                assets=portfolio_assets,
                interval=interval,
                train_months=int(train_months),
                test_months=int(test_months),
                step_months=int(step_months),
                date_start=date_start if date_start else None,
                date_end=date_end if date_end else None,
                mode="walk_forward",
                asset_class=asset_class,
            )

            set_progress(dbc.Alert("Simulating portfolio trades...", color="info"))
            trades_df, equity_df = run_portfolio_strategy(
                predictions_dict=predictions_dict,
                confidence_threshold=float(confidence),
                stop_loss_pct=float(stop_loss) / 100,
                take_profit_pct=float(take_profit) / 100,
                max_hold_bars=int(max_hold),
                initial_capital=float(capital),
                return_data=True,
                transaction_cost_pct=float(txn_cost) / 100 if txn_cost else 0.0,
                allow_short=bool(allow_short),
                max_positions=int(max_positions),
            )
            buy_hold_data = compute_portfolio_buy_and_hold(
                predictions_dict=predictions_dict,
                initial_capital=float(capital),
                transaction_cost_pct=float(txn_cost) / 100 if txn_cost else 0.0,
                interval=interval,
                asset_class=asset_class,
            )
        else:
            if bt_mode == "pretrained":
                predictions_df, _summary = run_walk_forward_pretrained(
                    asset=asset,
                    interval=interval,
                    train_months=int(train_months),
                    test_months=int(test_months),
                    step_months=int(step_months),
                    date_start=date_start if date_start else None,
                    date_end=date_end if date_end else None,
                    return_data=True,
                    asset_class=asset_class,
                )
            else:
                predictions_df, _summary = run_walk_forward(
                    asset=asset,
                    interval=interval,
                    train_months=int(train_months),
                    test_months=int(test_months),
                    step_months=int(step_months),
                    date_start=date_start if date_start else None,
                    date_end=date_end if date_end else None,
                    return_data=True,
                    asset_class=asset_class,
                )

            if predictions_df.empty:
                return dbc.Alert("No predictions generated. Check date range and asset.", color="warning")

            set_progress(dbc.Alert("Simulating trades...", color="info"))
            trades_df, equity_df = run_strategy(
                predictions_df=predictions_df,
                confidence_threshold=float(confidence),
                stop_loss_pct=float(stop_loss) / 100,
                take_profit_pct=float(take_profit) / 100,
                max_hold_bars=int(max_hold),
                initial_capital=float(capital),
                return_data=True,
                transaction_cost_pct=float(txn_cost) / 100 if txn_cost else 0.0,
                allow_short=bool(allow_short),
            )

        if trades_df.empty:
            return dbc.Alert("No trades executed — try relaxing the confidence threshold or date range.", color="warning")

        set_progress(dbc.Alert("Computing metrics...", color="info"))
        metrics = run_metrics(
            trades_df=trades_df,
            equity_df=equity_df,
            initial_capital=float(capital),
            return_data=True,
            interval=interval,
            asset_class=asset_class,
        )

        set_progress(dbc.Alert("Rendering results...", color="success"))
        if bt_mode != "portfolio":
            buy_hold_data = compute_portfolio_buy_and_hold(
                predictions_dict={asset: predictions_df},
                initial_capital=float(capital),
                transaction_cost_pct=float(txn_cost) / 100 if txn_cost else 0.0,
                interval=interval,
                asset_class=asset_class,
            )
        return _build_backtest_results(metrics, equity_df, trades_df, buy_hold_df=buy_hold_data)

    except Exception as e:
        return dbc.Alert(f"Backtest failed: {e}", color="danger")


@app.callback(
    dash.Output("bt-asset-dropdown", "options"),
    dash.Output("bt-asset-dropdown", "value"),
    dash.Input("bt-class-dropdown", "value"),
)
def _update_bt_asset_dropdown(asset_class):
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = "BTC" if "BTC" in assets else (assets[0] if assets else None)
    else:
        assets = STOCK_ASSETS
        default = assets[0] if assets else None
    return [{"label": a, "value": a} for a in assets], default


@app.callback(
    dash.Output("bt-interval-dropdown", "options"),
    dash.Output("bt-interval-dropdown", "value"),
    dash.Input("bt-class-dropdown", "value"),
    dash.Input("bt-mode-radio", "value"),
)
def _update_bt_interval_dropdown(asset_class, bt_mode):
    if asset_class == "crypto":
        intervals = PRED_CRYPTO_INTERVALS if bt_mode in ("pretrained", "portfolio") else CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = PRED_STOCK_INTERVALS if bt_mode in ("pretrained", "portfolio") else STOCK_INTERVALS
        default = "1h"
    return [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals], default


@app.callback(
    dash.Output("bt-asset-dropdown", "style"),
    dash.Output("bt-portfolio-assets-container", "style"),
    dash.Input("bt-mode-radio", "value"),
)
def _toggle_portfolio_asset_dropdown(bt_mode):
    if bt_mode == "portfolio":
        return {"display": "none"}, {"display": "block"}
    return {"color": "#000"}, {"display": "none"}


@app.callback(
    dash.Output("bt-portfolio-assets", "options"),
    dash.Output("bt-portfolio-assets", "value"),
    dash.Input("bt-class-dropdown", "value"),
)
def _update_bt_portfolio_assets(asset_class):
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = ["BTC", "ETH"] if "BTC" in assets and "ETH" in assets else assets[:2]
    else:
        assets = STOCK_ASSETS
        default = assets[:2]
    return [{"label": a, "value": a} for a in assets], default


def render_indicators():
    """RSI, MACD, Bollinger Bands, and SMA crossover charts with multi-asset dropdowns."""
    try:
        range_options = [{"label": "1 Day", "value": "1d"}, {"label": "3 Days", "value": "3d"},
                         {"label": "1 Week", "value": "7d"}, {"label": "1 Month", "value": "30d"},
                         {"label": "3 Months", "value": "90d"}, {"label": "6 Months", "value": "180d"},
                         {"label": "1 Year", "value": "365d"}, {"label": "All Time", "value": "all"}]
        return dbc.Row(
            dbc.Col(
                [
                    html.H3("Technical Indicators", className="text-light mb-2"),
                    html.P(
                        "Plots RSI, MACD, Bollinger Bands, and SMA crossovers to help analyze price trends and momentum. These are the same indicators used as features by the ML models.",
                        className="text-muted small mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Asset Class", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="ind-class-dropdown",
                                        options=[
                                            {"label": "Crypto", "value": "crypto"},
                                            {"label": "Stocks", "value": "stocks"},
                                        ],
                                        value="crypto",
                                        clearable=False,
                                        searchable=False,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Asset", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="ind-asset-dropdown",
                                        clearable=False,
                                        searchable=True,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Interval", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="ind-interval-dropdown",
                                        clearable=False,
                                        searchable=False,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Time Range", className="text-muted small mb-1"),
                                    dcc.Dropdown(
                                        id="ind-range-dropdown",
                                        options=range_options,
                                        value="90d",
                                        clearable=False,
                                        searchable=False,
                                        style={"color": "#000"},
                                    ),
                                ],
                                width=2,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dcc.Loading(
                        id="loading-ind",
                        type="circle",
                        children=html.Div(id="ind-content"),
                    ),
                ],
                width=12,
            )
        )
    except Exception as e:
        return dbc.Alert(f"Error: {e}", color="danger")

def render_explorer():
    """Dropdown-driven sortable data table explorer for all gold layer tables."""
    TABLE_OPTIONS = [
        {"label": "Crypto Analytics (gold_crypto_analytics)", "value": "gold_crypto_analytics"},
        {"label": "Crypto Features (gold_crypto_features)", "value": "gold_crypto_features"},
        {"label": "Stock Analytics (gold_stock_analytics)", "value": "gold_stock_analytics"},
        {"label": "Stock Features (gold_stock_features)", "value": "gold_stock_features"},
    ]
    return html.Div([
        html.H3("Data Explorer", className="text-light mb-2"),
        html.P(
            "Browse the gold-layer analytics and feature tables used for model training and analysis. Pick a table from the dropdown to inspect the raw data.",
            className="text-muted small mb-3",
        ),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    id="explorer-table-selector",
                    options=TABLE_OPTIONS,
                    value="gold_crypto_analytics",
                    clearable=False,
                    className="mb-3",
                    style={"color": "#000"},
                ),
                width=3,
            ),
            dbc.Col(
                dcc.Dropdown(
                    id="explorer-asset-selector",
                    placeholder="All Assets",
                    clearable=True,
                    className="mb-3",
                    style={"color": "#000"},
                ),
                width=3,
            ),
            dbc.Col(
                dcc.Dropdown(
                    id="explorer-interval-selector",
                    placeholder="All Intervals",
                    clearable=True,
                    className="mb-3",
                    style={"color": "#000"},
                ),
                width=3,
            ),
            dbc.Col(html.Div(id="explorer-row-count", className="text-muted mt-2"), width=3),
        ]),
        dbc.Row(dbc.Col(html.Div(id="explorer-table-container"), width=12)),
    ])

@app.callback(
    dash.Output("explorer-asset-selector", "options"),
    dash.Output("explorer-interval-selector", "options"),
    dash.Output("explorer-asset-selector", "value"),
    dash.Output("explorer-interval-selector", "value"),
    dash.Input("explorer-table-selector", "value"),
)
def update_explorer_filter_options(table_name):
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        assets = conn.execute(
            f"SELECT DISTINCT asset_symbol FROM {table_name} ORDER BY asset_symbol"
        ).fetchall()
    except Exception:
        assets = []
    try:
        intervals = conn.execute(
            f"SELECT DISTINCT interval FROM {table_name} ORDER BY interval"
        ).fetchall()
    except Exception:
        intervals = []
    conn.close()
    asset_options = [{"label": a[0], "value": a[0]} for a in assets]
    interval_options = [{"label": i[0], "value": i[0]} for i in intervals]
    return asset_options, interval_options, None, None

@app.callback(
    dash.Output("explorer-table-container", "children"),
    dash.Output("explorer-row-count", "children"),
    dash.Input("explorer-table-selector", "value"),
    dash.Input("explorer-asset-selector", "value"),
    dash.Input("explorer-interval-selector", "value"),
)
def update_explorer_table(table_name, selected_asset, selected_interval):
    """Query the selected gold table and render a sortable DataTable."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        query = f"SELECT * FROM {table_name}"
        conditions = []
        if selected_asset:
            conditions.append(f"asset_symbol = '{selected_asset}'")
        if selected_interval:
            conditions.append(f"interval = '{selected_interval}'")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY date DESC LIMIT 5000"
        df = conn.execute(query).df()
        conn.close()
        if df.empty:
            return dbc.Alert(f"Table '{table_name}' is empty. Run the pipeline first.", color="warning"), ""
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d %H:%M")
        total = len(df)
        row_text = f"Showing {total} row{'s' if total != 1 else ''} (latest 5,000)"
        columns = [{"name": col, "id": col} for col in df.columns]
        table = dash_table.DataTable(
            data=df.to_dict("records"),
            columns=columns,
            page_size=25,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_cell={
                "backgroundColor": "#222222",
                "color": "#e0e0e0",
                "borderColor": "#404040",
                "fontSize": "12px",
                "padding": "4px 8px",
                "minWidth": "80px",
            },
            style_header={
                "backgroundColor": "#333333",
                "fontWeight": "bold",
                "borderColor": "#555555",
            },
            style_filter={
                "backgroundColor": "#2a2a2a",
                "borderColor": "#555555",
            },
            style_data_conditional=[
                {
                    "if": {"row_index": "odd"},
                    "backgroundColor": "#262626",
                },
            ],
        )
        return table, row_text
    except Exception as e:
        return dbc.Alert(f"Error loading table '{table_name}': {e}", color="danger"), ""

def render_overview():
    conn = duckdb.connect(DB_PATH, read_only=True)

    crypto_count = conn.execute(
        "SELECT COUNT(DISTINCT asset_symbol) FROM gold_crypto_analytics"
    ).fetchone()[0]

    stock_count = conn.execute(
        "SELECT COUNT(DISTINCT asset_symbol) FROM gold_stock_analytics"
    ).fetchone()[0]

    crypto_latest = conn.execute(
        "SELECT MAX(date) FROM gold_crypto_analytics"
    ).fetchone()[0]

    stock_latest = conn.execute(
        "SELECT MAX(date) FROM gold_stock_analytics"
    ).fetchone()[0]

    top5_crypto = conn.execute("""
        WITH latest AS (
            SELECT asset_symbol, close, date,
                   ROW_NUMBER() OVER (PARTITION BY asset_symbol ORDER BY date DESC) AS rn
            FROM gold_crypto_analytics
        )
        SELECT asset_symbol, close, date
        FROM latest WHERE rn = 1
        ORDER BY close DESC
        LIMIT 5
    """).df()

    top5_stocks = conn.execute("""
        WITH latest AS (
            SELECT asset_symbol, close, date,
                   ROW_NUMBER() OVER (PARTITION BY asset_symbol ORDER BY date DESC) AS rn
            FROM gold_stock_analytics
        )
        SELECT asset_symbol, close, date
        FROM latest WHERE rn = 1
        ORDER BY close DESC
        LIMIT 5
    """).df()

    conn.close()

    models = get_model_health()
    counts = get_summary_counts(models)

    model_cards = dbc.Row(
        [
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["total"]), className="card-title text-info text-center"),
                html.P("Total Models", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["healthy"]), className="card-title text-success text-center"),
                html.P("Healthy", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["stale"]), className="card-title text-warning text-center"),
                html.P("Stale", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["missing_model"]), className="card-title text-danger text-center"),
                html.P("Missing Model", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["missing_metadata"]), className="card-text text-warning-emphasis text-center"),
                html.P("Missing Metadata", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
        ],
        className="mb-3",
    )

    def _fmt_price(p):
        if p >= 1:
            return f"${p:,.2f}"
        if p >= 0.01:
            return f"${p:,.4f}"
        if p >= 0.0001:
            return f"${p:,.6f}"
        return f"${p:.8f}"

    def _build_top5_table(df, label, color):
        if df.empty:
            return dbc.Col([
                html.H5(label, className="text-light mb-2"),
                dbc.Alert("No data available", color="secondary"),
            ], width=6)

        rows = []
        for _, row in df.iterrows():
            price = row["close"]
            date_str = pd.Timestamp(row["date"]).strftime("%Y-%m-%d %H:%M")
            rows.append(html.Tr([
                html.Td(row["asset_symbol"], className="text-light"),
                html.Td(_fmt_price(price), className="text-light"),
                html.Td(date_str, className="text-muted small"),
            ]))

        table_header = html.Thead(html.Tr([
            html.Th("Asset", className="text-muted"),
            html.Th("Latest Price", className="text-muted"),
            html.Th("Date", className="text-muted"),
        ]))

        return dbc.Col([
            html.H5(label, className="text-light mb-2"),
            dbc.Table(
                [table_header, html.Tbody(rows)],
                color="dark",
                hover=True,
                striped=True,
                size="sm",
                className="mb-0",
            ),
        ], width=6)

    def _fmt_date(d):
        if d is None:
            return "No data"
        if isinstance(d, str):
            d = datetime.fromisoformat(d)
        return d.strftime("%Y-%m-%d %H:%M UTC")

    freshness_row = dbc.Row(
        [
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(crypto_count), className="card-title text-info text-center"),
                html.P("Crypto Assets", className="card-text text-muted small text-center"),
                html.Small(f"Latest: {_fmt_date(crypto_latest)}", className="text-muted"),
            ]), color="dark", outline=True), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(stock_count), className="card-title text-success text-center"),
                html.P("Stock Assets", className="card-text text-muted small text-center"),
                html.Small(f"Latest: {_fmt_date(stock_latest)}", className="text-muted"),
            ]), color="dark", outline=True), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(crypto_count + stock_count), className="card-title text-warning text-center"),
                html.P("Total Tracked", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=3),
        ],
        className="mb-4",
    )

    top5_row = dbc.Row(
        [
            _build_top5_table(top5_crypto, "Top 5 Crypto", "info"),
            _build_top5_table(top5_stocks, "Top 5 Stocks", "success"),
        ],
        className="mb-4",
    )

    return html.Div([
        html.H3("Dashboard Overview", className="text-light mb-2"),
        html.P(
            "Summary of all tracked assets, data freshness, and model health across the system. A starting point to see what data is available and how the models are doing.",
            className="text-muted small mb-3",
        ),
        freshness_row,
        html.H5("Most Recently Updated", className="text-light mb-2"),
        top5_row,
        html.Hr(),
        html.H5("Model Health Summary", className="text-light mb-2"),
        model_cards,
        dbc.Row(
            dbc.Col(
                html.Small(
                    "Switch to the Model Health tab for detailed per-model status.",
                    className="text-muted",
                ),
            )
        ),
    ])

def _calculate_model_quality(predictions):

    empty_metrics = {
        "oos_accuracy": None,
        "balanced_accuracy": None,
        "f1_score": None,
        "mcc": None,
        "best_baseline_accuracy": None,
        "baseline_gap": None,
        "oos_rows": 0,
        "actual_up_pct": None,
        "actual_down_pct": None,
        "predicted_up_pct": None,
        "predicted_down_pct": None,
        "brier_score": None,
    }
    if predictions is None or predictions.empty:
        return empty_metrics

    known = predictions[predictions["actual_direction"].notna()]
    if "is_oos" in known.columns:
        oos = known[known["is_oos"]]
        scored = oos if not oos.empty else known
    else:
        scored = known
    if scored.empty:
        return empty_metrics

    y_true = scored["actual_direction"].astype(int)
    y_pred = scored["prediction"].astype(int)
    accuracy = float((y_true == y_pred).mean())

    sma20 = predictions["close"].rolling(window=20).mean()
    sma50 = predictions["close"].rolling(window=50).mean()
    baseline_rules = [
        pd.Series(1, index=predictions.index),
        pd.Series(0, index=predictions.index),
        (predictions["close"].diff() > 0).astype(int).shift(1),
        (sma20 > sma50).astype(float).where(sma20.notna() & sma50.notna()),
    ]
    baseline_accuracies = []
    for rule in baseline_rules:
        rule = rule.reindex(scored.index)
        valid = rule.notna()
        if valid.any():
            baseline_accuracies.append(float((rule[valid].astype(int) == y_true[valid]).mean()))

    best_baseline = max(baseline_accuracies) if baseline_accuracies else None
    actual_up_pct = float((y_true == 1).mean())
    predicted_up_pct = float((y_pred == 1).mean())

    brier = None
    if "confidence" in scored.columns:
        confidence = pd.to_numeric(scored["confidence"], errors="coerce")
        up_probability = confidence.where(y_pred == 1, 1 - confidence)
        valid_probability = up_probability.between(0, 1) & up_probability.notna()
        if valid_probability.any():
            brier = float(brier_score_loss(y_true[valid_probability], up_probability[valid_probability]))

    return {
        "oos_accuracy": accuracy,
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "best_baseline_accuracy": best_baseline,
        "baseline_gap": accuracy - best_baseline if best_baseline is not None else None,
        "oos_rows": len(scored),
        "actual_up_pct": actual_up_pct,
        "actual_down_pct": 1 - actual_up_pct,
        "predicted_up_pct": predicted_up_pct,
        "predicted_down_pct": 1 - predicted_up_pct,
        "brier_score": brier,
    }


def _calculate_calibration_metrics(predictions, n_bins=10):
    empty_metrics = {
        "expected_calibration_error": None,
        "calibration_bins": pd.DataFrame(columns=["confidence", "accuracy", "count"]),
    }
    if predictions is None or predictions.empty:
        return empty_metrics

    known = predictions[predictions["actual_direction"].notna()]
    if "is_oos" in known.columns:
        oos = known[known["is_oos"]]
        scored = oos if not oos.empty else known
    else:
        scored = known
    if scored.empty or "confidence" not in scored.columns:
        return empty_metrics

    confidence = pd.to_numeric(scored["confidence"], errors="coerce")
    correctness = (
        scored["prediction"].astype(int) == scored["actual_direction"].astype(int)
    ).astype(float)
    valid = confidence.between(0.5, 1.0) & confidence.notna()
    if not valid.any():
        return empty_metrics

    confidence = confidence[valid]
    correctness = correctness[valid]
    bins = np.linspace(0.5, 1.0, n_bins + 1)
    bin_ids = pd.cut(confidence, bins=bins, labels=False, include_lowest=True)
    grouped = pd.DataFrame({
        "confidence": confidence,
        "correctness": correctness,
        "bin": bin_ids,
    }).dropna(subset=["bin"])
    if grouped.empty:
        return empty_metrics

    calibration_bins = (
        grouped.groupby("bin", observed=True)
        .agg(confidence=("confidence", "mean"), accuracy=("correctness", "mean"), count=("correctness", "size"))
        .reset_index(drop=True)
    )
    weights = calibration_bins["count"] / calibration_bins["count"].sum()
    ece = float((weights * (calibration_bins["confidence"] - calibration_bins["accuracy"]).abs()).sum())

    return {
        "expected_calibration_error": ece,
        "calibration_bins": calibration_bins,
    }


def build_model_ranking_table(models, objective="oos_accuracy"):
    ranked_models = []
    for model in models:
        try:
            predictions = run_prediction(model["asset"], model["interval"], model["asset_class"])
            quality = _calculate_model_quality(predictions)
        except (FileNotFoundError, OSError, ValueError, KeyError):
            quality = _calculate_model_quality(None)
        ranked_models.append({**model, **quality})

    if objective not in CLASSIFICATION_RANKING_OBJECTIVES:
        ranked_models = evaluate_trading_performance(ranked_models)

    ranked_models = rank_models(ranked_models, objective)
    objective_label = RANKING_OBJECTIVES[objective]["label"]

    def format_percent(value):
        return f"{value:.1%}" if value is not None else "N/A"

    def format_percentage_points(value):
        return f"{value:.2f}%" if value is not None else "N/A"

    def format_score(value):
        return f"{value:.3f}" if value is not None else "N/A"

    def format_ranking_score(value):
        if objective in ("total_return_pct", "max_drawdown_pct"):
            return format_percentage_points(value)
        if objective == "return_volatility":
            return format_percent(value)
        if objective in ("brier_score", "sharpe_ratio"):
            return format_score(value)
        return format_percent(value)

    table_data = []
    for model in ranked_models:
        selected_score = model["ranking_score"]
        table_data.append({
            "Rank": model["rank"] if model["rank"] is not None else "N/A",
            "Class": model["asset_class"].capitalize(),
            "Asset": model["asset"],
            "Interval": model["interval"],
            objective_label: format_ranking_score(selected_score),
            "OOS Accuracy": format_percent(model.get("oos_accuracy")),
            "Baseline Gap": format_percent(model.get("baseline_gap")),
            "Balanced Accuracy": format_percent(model.get("balanced_accuracy")),
            "Brier Score": format_score(model.get("brier_score")),
            "OOS Rows": model.get("oos_rows") or "N/A",
        })

    columns = [
        {"name": "Rank", "id": "Rank"},
        {"name": "Class", "id": "Class"},
        {"name": "Asset", "id": "Asset"},
        {"name": "Interval", "id": "Interval"},
        {"name": objective_label, "id": objective_label},
        {"name": "OOS Accuracy", "id": "OOS Accuracy"},
        {"name": "Baseline Gap", "id": "Baseline Gap"},
        {"name": "Balanced Accuracy", "id": "Balanced Accuracy"},
        {"name": "Brier Score", "id": "Brier Score"},
        {"name": "OOS Rows", "id": "OOS Rows"},
    ]

    return dash_table.DataTable(
        id="model-ranking-table",
        data=table_data,
        columns=columns,
        page_size=50,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "backgroundColor": "#222222",
            "color": "#e0e0e0",
            "borderColor": "#404040",
            "fontSize": "12px",
            "padding": "6px 10px",
            "minWidth": "90px",
        },
        style_header={
            "backgroundColor": "#333333",
            "fontWeight": "bold",
            "borderColor": "#555555",
        },
        style_filter={
            "backgroundColor": "#2a2a2a",
            "borderColor": "#555555",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#262626"},
            {"if": {"column_id": "Rank"}, "fontWeight": "bold", "color": "#5dade2"},
        ],
    )


def render_model_health():
    models = get_model_health()
    counts = get_summary_counts(models)

    summary_cards = dbc.Row(
        [
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["total"]), className="card-title text-info text-center"),
                html.P("Total Models", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["healthy"]), className="card-title text-success text-center"),
                html.P("Healthy", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["stale"]), className="card-title text-warning text-center"),
                html.P("Stale", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["missing_model"]), className="card-title text-danger text-center"),
                html.P("Missing Model", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(counts["missing_metadata"]), className="card-text text-warning-emphasis text-center"),
                html.P("Missing Metadata", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=2),
        ],
        className="mb-3",
    )

    if not models:
        return html.Div([
            html.H3("Model Health", className="text-light mb-2"),
            html.P(
                "Tracks the status of every trained model — accuracy, training date, and whether the model file and metadata exist.",
                className="text-muted small mb-3",
            ),
            summary_cards,
            dbc.Alert("No models found. Run the training pipeline first.", color="info"),
        ])

    table_data = []
    for m in models:
        try:
            predictions = run_prediction(m["asset"], m["interval"], m["asset_class"])
            quality = _calculate_model_quality(predictions)
        except (FileNotFoundError, OSError, ValueError, KeyError):
            quality = _calculate_model_quality(None)

        trained_at = m.get("trained_at")
        if trained_at:
            try:
                dt = datetime.fromisoformat(str(trained_at))
                trained_at_display = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                trained_at_display = str(trained_at)
        else:
            trained_at_display = "N/A"

        train_end = m.get("train_end_date") or "N/A"
        if train_end != "N/A":
            try:
                train_end = str(train_end)[:10]
            except Exception:
                pass

        accuracy = m.get("test_accuracy")
        accuracy_display = f"{accuracy:.1%}" if accuracy is not None else "N/A"

        cv_score = m.get("best_cv_score")
        cv_display = f"{cv_score:.1%}" if cv_score is not None else "N/A"

        status = m["status"]
        badge_color = STATUS_COLORS.get(status, "#888")

        def format_percent(value):
            return f"{value:.1%}" if value is not None else "N/A"

        def format_score(value):
            return f"{value:.3f}" if value is not None else "N/A"

        table_data.append({
            "Asset": m["asset"],
            "Interval": m["interval"],
            "Class": m["asset_class"].capitalize(),
            "Last Trained": trained_at_display,
            "Train End": train_end,
            "Train Rows": m.get("train_rows") or "N/A",
            "Test Rows": m.get("test_rows") or "N/A",
            "Accuracy": accuracy_display,
            "CV Score": cv_display,
            "OOS Accuracy": format_percent(quality["oos_accuracy"]),
            "Balanced Accuracy": format_percent(quality["balanced_accuracy"]),
            "F1 Score": format_score(quality["f1_score"]),
            "MCC": format_score(quality["mcc"]),
            "Best Baseline": format_percent(quality["best_baseline_accuracy"]),
            "Baseline Gap": format_percent(quality["baseline_gap"]),
            "OOS Rows": quality["oos_rows"] or "N/A",
            "Actual UP / DOWN": (
                f"{quality['actual_up_pct']:.1%} / {quality['actual_down_pct']:.1%}"
                if quality["actual_up_pct"] is not None else "N/A"
            ),
            "Predicted UP / DOWN": (
                f"{quality['predicted_up_pct']:.1%} / {quality['predicted_down_pct']:.1%}"
                if quality["predicted_up_pct"] is not None else "N/A"
            ),
            "Brier Score": format_score(quality["brier_score"]),
            "Status": status,
        })

    columns = [
        {"name": "Asset", "id": "Asset"},
        {"name": "Interval", "id": "Interval"},
        {"name": "Class", "id": "Class"},
        {"name": "Last Trained", "id": "Last Trained"},
        {"name": "Train End", "id": "Train End"},
        {"name": "Train Rows", "id": "Train Rows"},
        {"name": "Test Rows", "id": "Test Rows"},
        {"name": "Accuracy", "id": "Accuracy"},
        {"name": "CV Score", "id": "CV Score"},
        {"name": "OOS Accuracy", "id": "OOS Accuracy"},
        {"name": "Balanced Accuracy", "id": "Balanced Accuracy"},
        {"name": "F1 Score", "id": "F1 Score"},
        {"name": "MCC", "id": "MCC"},
        {"name": "Best Baseline", "id": "Best Baseline"},
        {"name": "Baseline Gap", "id": "Baseline Gap"},
        {"name": "OOS Rows", "id": "OOS Rows"},
        {"name": "Actual UP / DOWN", "id": "Actual UP / DOWN"},
        {"name": "Predicted UP / DOWN", "id": "Predicted UP / DOWN"},
        {"name": "Brier Score", "id": "Brier Score"},
        {"name": "Status", "id": "Status"},
    ]

    status_style = []
    for status_key, color in STATUS_COLORS.items():
        status_style.append({
            "if": {"filter_query": "{Status} = '" + status_key + "'", "column_id": "Status"},
            "backgroundColor": color,
            "color": "#fff",
            "fontWeight": "bold",
        })

    table = dash_table.DataTable(
        data=table_data,
        columns=columns,
        page_size=50,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "backgroundColor": "#222222",
            "color": "#e0e0e0",
            "borderColor": "#404040",
            "fontSize": "12px",
            "padding": "4px 8px",
            "minWidth": "80px",
        },
        style_header={
            "backgroundColor": "#333333",
            "fontWeight": "bold",
            "borderColor": "#555555",
        },
        style_filter={
            "backgroundColor": "#2a2a2a",
            "borderColor": "#555555",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#262626",
            },
        ] + status_style,
    )

    return html.Div([
        html.H3("Model Health", className="text-light mb-2"),
        html.P(
            "Tracks the status of every trained model — accuracy, training date, and whether the model file and metadata exist.",
            className="text-muted small mb-3",
        ),
        summary_cards,
        html.H4("Model Rankings", className="text-light mt-4 mb-2"),
        html.P(
            "Ranks models by out-of-sample classification quality or standardized trading performance. Trading metrics use the same evaluation period and strategy settings for every model.",
            className="text-muted small mb-2",
        ),
        dbc.Row([
            dbc.Col([
                html.Label("Rank By", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="model-ranking-objective",
                    options=[
                        {"label": details["label"], "value": objective}
                        for objective, details in RANKING_OBJECTIVES.items()
                    ],
                    value="oos_accuracy",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=4),
        ], className="mb-3"),
        html.Div(
            id="model-ranking-container",
            children=build_model_ranking_table(models),
        ),
        html.H4("Model Status", className="text-light mt-4 mb-2"),
        table,
    ])


@app.callback(
    dash.Output("model-ranking-container", "children"),
    dash.Input("model-ranking-objective", "value"),
)
def update_model_ranking(objective):
    return build_model_ranking_table(get_model_health(), objective or "oos_accuracy")


def _wilson_accuracy_interval(correct, total):
    if total <= 0:
        return None
    z = 1.959963984540054
    proportion = correct / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = z * np.sqrt((proportion * (1 - proportion) + z**2 / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _paired_bootstrap_interval(model_correct, baseline_correct, block_size=10, iterations=2000, seed=42):
    values = np.asarray(model_correct, dtype=float) - np.asarray(baseline_correct, dtype=float)
    total = len(values)
    if total < 2:
        return None
    block_size = min(block_size, total)
    starts = np.arange(total)
    rng = np.random.default_rng(seed)
    bootstrap = np.empty(iterations)
    blocks_needed = int(np.ceil(total / block_size))
    for index in range(iterations):
        sampled_starts = rng.choice(starts, size=blocks_needed, replace=True)
        sampled = np.concatenate([
            values[(start + np.arange(block_size)) % total]
            for start in sampled_starts
        ])[:total]
        bootstrap[index] = sampled.mean()
    return tuple(np.quantile(bootstrap, [0.025, 0.975]))


def _exact_mcnemar_p_value(model_only, baseline_only):
    discordant = model_only + baseline_only
    if discordant == 0:
        return 1.0
    smaller = min(model_only, baseline_only)
    probability = sum(
        math.comb(discordant, successes)
        for successes in range(smaller + 1)
    ) / (2**discordant)
    return min(1.0, 2 * probability)


def calculate_performance_stability(predictions, trading_window_days):
    from backtesting.strategy import simulate_trades
    from dashboard.model_health import STANDARD_TRADING_CONFIG

    empty_accuracy = pd.DataFrame(columns=["date", "accuracy", "count"])
    empty_rolling = pd.DataFrame(columns=["date", "accuracy_30d", "accuracy_90d"])
    empty_trading = pd.DataFrame(columns=["date", "rolling_return", "rolling_drawdown"])
    empty_result = {
        "monthly_accuracy": empty_accuracy,
        "quarterly_accuracy": empty_accuracy.copy(),
        "rolling_accuracy": empty_rolling,
        "rolling_trading": empty_trading,
    }
    required = {"date", "prediction", "actual_direction", "close", "confidence"}
    if predictions is None or predictions.empty or not required.issubset(predictions.columns):
        return empty_result
    if trading_window_days not in (30, 90):
        raise ValueError("Trading window must be 30 or 90 days.")

    scored = predictions[predictions["actual_direction"].notna()].copy()
    if "is_oos" in scored.columns:
        scored = scored[scored["is_oos"]].copy()
    scored["date"] = pd.to_datetime(scored["date"], errors="coerce", utc=True)
    scored["prediction"] = pd.to_numeric(scored["prediction"], errors="coerce")
    scored["actual_direction"] = pd.to_numeric(scored["actual_direction"], errors="coerce")
    scored["close"] = pd.to_numeric(scored["close"], errors="coerce")
    scored["confidence"] = pd.to_numeric(scored["confidence"], errors="coerce")
    scored = scored.dropna(subset=["date", "prediction", "actual_direction", "close", "confidence"])
    scored = scored.sort_values("date").drop_duplicates(subset="date", keep="last")
    if scored.empty:
        return empty_result

    scored["correct"] = (scored["prediction"].astype(int) == scored["actual_direction"].astype(int)).astype(float)

    def aggregate_accuracy(period):
        period_groups = scored["date"].dt.tz_localize(None).dt.to_period(period)
        grouped = scored.groupby(period_groups)["correct"].agg(["mean", "count"])
        grouped = grouped.rename(columns={"mean": "accuracy"}).reset_index(drop=True)
        grouped["date"] = scored.groupby(period_groups)["date"].max().to_numpy()
        return grouped[["date", "accuracy", "count"]]

    indexed_correct = scored.set_index("date")["correct"]
    rolling_accuracy = pd.DataFrame(index=scored["date"])
    for days in (30, 90):
        values = indexed_correct.rolling(f"{days}D", min_periods=2).mean()
        values.loc[values.index < values.index.min() + pd.Timedelta(days=days)] = np.nan
        rolling_accuracy[f"accuracy_{days}d"] = values.to_numpy()
    rolling_accuracy = rolling_accuracy.reset_index()

    _, equity = simulate_trades(scored, **STANDARD_TRADING_CONFIG)
    rolling_trading = empty_trading
    if not equity.empty:
        equity = equity.copy()
        equity["date"] = pd.to_datetime(equity["date"], errors="coerce", utc=True)
        equity["equity"] = pd.to_numeric(equity["equity"], errors="coerce")
        equity = equity.dropna(subset=["date", "equity"]).sort_values("date")
        equity = equity.drop_duplicates(subset="date", keep="last").set_index("date")
        window = f"{trading_window_days}D"
        initial_capital = STANDARD_TRADING_CONFIG["initial_capital"]
        rolling_return = equity["equity"].rolling(window, min_periods=2).apply(
            lambda values: (values[-1] - values[0]) / initial_capital * 100,
            raw=True,
        )
        rolling_drawdown = equity["equity"].rolling(window, min_periods=2).apply(
            lambda values: float(np.max((np.maximum.accumulate(values) - values) / np.maximum.accumulate(values)) * 100),
            raw=True,
        )
        full_window_start = equity.index.min() + pd.Timedelta(days=trading_window_days)
        rolling_return.loc[rolling_return.index < full_window_start] = np.nan
        rolling_drawdown.loc[rolling_drawdown.index < full_window_start] = np.nan
        rolling_trading = pd.DataFrame({
            "date": equity.index,
            "rolling_return": rolling_return.to_numpy(),
            "rolling_drawdown": rolling_drawdown.to_numpy(),
        })

    return {
        "monthly_accuracy": aggregate_accuracy("M"),
        "quarterly_accuracy": aggregate_accuracy("Q"),
        "rolling_accuracy": rolling_accuracy,
        "rolling_trading": rolling_trading,
    }


def build_baseline_significance(results):
    """Compare a selected model with its strongest paired baseline."""
    required = {"prediction", "actual_direction", "close", "date"}
    if results is None or results.empty or not required.issubset(results.columns):
        return {"status": "missing"}

    scored = results[results["actual_direction"].notna()].copy()
    if "is_oos" in scored.columns:
        scored = scored[scored["is_oos"]].copy()
    if scored.empty:
        return {"status": "missing"}

    sma20 = scored["close"].rolling(window=20).mean()
    sma50 = scored["close"].rolling(window=50).mean()
    rules = {
        "Always Up": pd.Series(1, index=scored.index),
        "Always Down": pd.Series(0, index=scored.index),
        "Last Candle Direction": (scored["close"].diff() > 0).astype(int).shift(1),
        "SMA 20 > SMA 50 Rule": (sma20 > sma50).where(sma20.notna() & sma50.notna()),
    }
    model_prediction = scored["prediction"]
    paired_scores = {}
    paired_values = {}
    for name, baseline_prediction in rules.items():
        valid = model_prediction.notna() & baseline_prediction.notna()
        if valid.any():
            actual = scored.loc[valid, "actual_direction"].astype(int)
            model_correct = (model_prediction[valid].astype(int) == actual).to_numpy()
            baseline_correct = (baseline_prediction[valid].astype(int) == actual).to_numpy()
            paired_scores[name] = float(baseline_correct.mean())
            paired_values[name] = (
                model_correct,
                baseline_correct,
                pd.to_datetime(scored.loc[valid, "date"]),
            )

    if not paired_scores:
        return {"status": "insufficient"}
    best_name = max(paired_scores, key=paired_scores.get)
    model_correct, baseline_correct, dates = paired_values[best_name]
    total = len(model_correct)
    if total < 2:
        return {"status": "insufficient", "baseline_name": best_name, "sample_size": total}

    model_accuracy = float(model_correct.mean())
    baseline_accuracy = float(baseline_correct.mean())
    model_only = int(np.sum(model_correct & ~baseline_correct))
    baseline_only = int(np.sum(~model_correct & baseline_correct))
    return {
        "status": "ok",
        "baseline_name": best_name,
        "model_accuracy": model_accuracy,
        "baseline_accuracy": baseline_accuracy,
        "model_interval": _wilson_accuracy_interval(int(model_correct.sum()), total),
        "baseline_interval": _wilson_accuracy_interval(int(baseline_correct.sum()), total),
        "difference": model_accuracy - baseline_accuracy,
        "difference_interval": _paired_bootstrap_interval(model_correct, baseline_correct),
        "mcnemar_p_value": _exact_mcnemar_p_value(model_only, baseline_only),
        "sample_size": total,
        "start_date": dates.min(),
        "end_date": dates.max(),
    }


def render_model_insights():
    return html.Div([
        html.H3("Feature Importance", className="text-light mb-2"),
        html.P(
            "Shows which features the selected model uses most for its predictions.",
            className="text-muted small mb-3",
        ),
        dbc.Row([
            dbc.Col([
                html.Label("Asset Class", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="fi-class-dropdown",
                    options=[
                        {"label": "Crypto", "value": "crypto"},
                        {"label": "Stocks", "value": "stocks"},
                    ],
                    value="crypto",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Asset", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="fi-asset-dropdown",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Interval", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="fi-interval-dropdown",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
        ], className="mb-3"),
        dcc.Loading(
            id="fi-loading",
            type="circle",
            children=html.Div(id="fi-chart-container"),
        ),
        html.Hr(className="my-4"),
        html.H3("Confusion Matrix", className="text-light mb-2"),
        html.P(
            "Shows where the selected model predicts Up or Down correctly and where it makes mistakes.",
            className="text-muted small mb-3",
        ),
        dbc.Row([
            dbc.Col([
                html.Label("Asset Class", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="cm-class-dropdown",
                    options=[
                        {"label": "Crypto", "value": "crypto"},
                        {"label": "Stocks", "value": "stocks"},
                    ],
                    value="crypto",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Asset", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="cm-asset-dropdown",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Interval", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="cm-interval-dropdown",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
        ], className="mb-3"),
        dcc.Loading(
            id="cm-loading",
            type="circle",
            children=html.Div(id="cm-chart-container"),
        ),
        html.Hr(className="my-4"),
        html.H3("Per-Asset Accuracy", className="text-light mb-2"),
        html.P(
            "Compares test accuracy across all trained asset and interval models.",
            className="text-muted small mb-3",
        ),
        build_accuracy_chart(),
        html.Hr(className="my-4"),
        html.H3("Model Family Comparison", className="text-light mb-2"),
        html.P(
            "Compares XGBoost, logistic regression, and random forest using the same BTC 1h training and unseen test data.",
            className="text-muted small mb-3",
        ),
        build_model_family_comparison(),
        html.Hr(className="my-4"),
        html.H3("Prediction Confidence", className="text-light mb-2"),
        html.P(
            "Shows how confident the model was for each prediction and whether that confidence was justified.",
            className="text-muted small mb-3",
        ),
        dbc.Row([
            dbc.Col([
                html.Label("Asset Class", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="ch-class-dropdown",
                    options=[
                        {"label": "Crypto", "value": "crypto"},
                        {"label": "Stocks", "value": "stocks"},
                    ],
                    value="crypto",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Asset", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="ch-asset-dropdown",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Interval", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="ch-interval-dropdown",
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
        ], className="mb-3"),
        dcc.Loading(
            id="ch-loading",
            type="circle",
            children=html.Div(id="ch-chart-container"),
        ),
        html.Hr(className="my-4"),
        html.H3("Baseline Statistical Significance", className="text-light mb-2"),
        html.P(
            "Tests whether the selected model's accuracy difference from its strongest simple baseline is statistically meaningful.",
            className="text-muted small mb-3",
        ),
        dcc.Loading(
            id="baseline-significance-loading",
            type="circle",
            children=html.Div(id="baseline-significance-container"),
        ),
        html.Hr(className="my-4"),
        html.H3("Probability Calibration", className="text-light mb-2"),
        html.P(
            "Compares predicted confidence with actual correctness to show whether the confidence can be treated as a probability.",
            className="text-muted small mb-3",
        ),
        dcc.Loading(
            id="calibration-loading",
            type="circle",
            children=html.Div(id="calibration-container"),
        ),
        html.Hr(className="my-4"),
        html.H3("Confidence Threshold Evaluation", className="text-light mb-2"),
        html.P(
            "Compares accuracy and trading results at different confidence levels, including how many predictions are kept or discarded.",
            className="text-muted small mb-3",
        ),
        dcc.Loading(
            id="cte-loading",
            type="circle",
            children=html.Div(id="cte-table-container"),
        ),
        html.Hr(className="my-4"),
        html.H3("Performance Stability Over Time", className="text-light mb-2"),
        html.P(
            "Tracks classification accuracy and trading performance across time to reveal model deterioration.",
            className="text-muted small mb-3",
        ),
        dbc.Row([
            dbc.Col([
                html.Label("Trading Window", className="text-muted small mb-1"),
                dcc.Dropdown(
                    id="stability-window-dropdown",
                    options=[
                        {"label": "30 days", "value": 30},
                        {"label": "90 days", "value": 90},
                    ],
                    value=30,
                    clearable=False,
                    style={"color": "#000"},
                ),
            ], width=3),
        ], className="mb-3"),
        dcc.Loading(
            id="stability-loading",
            type="circle",
            children=html.Div(id="stability-chart-container"),
        ),
        html.Hr(className="my-4"),
        html.H3("Confidence Timeline", className="text-light mb-2"),
        html.P(
            "Plots each prediction over time so you can see when the model was confident and whether it was right.",
            className="text-muted small mb-3",
        ),
        dcc.Loading(
            id="ct-loading",
            type="circle",
            children=html.Div(id="ct-chart-container"),
        ),
    ])


def build_accuracy_chart():
    """Bar chart of test accuracy for all models, grouped by asset class."""
    models = get_model_health()

    crypto_labels, crypto_acc, crypto_train, crypto_test = [], [], [], []
    stock_labels, stock_acc, stock_train, stock_test = [], [], [], []

    for m in models:
        acc = m.get("test_accuracy")
        if acc is None:
            continue
        label = f"{m['asset']} {m['interval']}"
        pct = round(acc * 100, 1)
        train_rows = m.get("train_rows")
        test_rows = m.get("test_rows")
        if m["asset_class"] == "crypto":
            crypto_labels.append(label)
            crypto_acc.append(pct)
            crypto_train.append(train_rows if train_rows is not None else "N/A")
            crypto_test.append(test_rows if test_rows is not None else "N/A")
        else:
            stock_labels.append(label)
            stock_acc.append(pct)
            stock_train.append(train_rows if train_rows is not None else "N/A")
            stock_test.append(test_rows if test_rows is not None else "N/A")

    crypto_data = sorted(zip(crypto_labels, crypto_acc, crypto_train, crypto_test), key=lambda p: p[1])
    crypto_labels = [p[0] for p in crypto_data]
    crypto_acc = [p[1] for p in crypto_data]
    crypto_train = [p[2] for p in crypto_data]
    crypto_test = [p[3] for p in crypto_data]

    stock_data = sorted(zip(stock_labels, stock_acc, stock_train, stock_test), key=lambda p: p[1])
    stock_labels = [p[0] for p in stock_data]
    stock_acc = [p[1] for p in stock_data]
    stock_train = [p[2] for p in stock_data]
    stock_test = [p[3] for p in stock_data]

    if not crypto_labels and not stock_labels:
        return dbc.Alert("No accuracy data available. Train models first.", color="info")

    fig = go.Figure()

    crypto_hover = "<b>%{x}</b><br>Accuracy: %{y:.1f}%<br>Train Rows: %{customdata[0]}<br>Test Rows: %{customdata[1]}<extra>Crypto</extra>"
    stock_hover = "<b>%{x}</b><br>Accuracy: %{y:.1f}%<br>Train Rows: %{customdata[0]}<br>Test Rows: %{customdata[1]}<extra>Stocks</extra>"

    fig.add_trace(go.Bar(
        x=crypto_labels,
        y=crypto_acc,
        name="Crypto",
        marker_color="#f7931a",
        customdata=list(zip(crypto_train, crypto_test)),
        hovertemplate=crypto_hover,
    ))

    fig.add_trace(go.Bar(
        x=stock_labels,
        y=stock_acc,
        name="Stocks",
        marker_color="#3498db",
        customdata=list(zip(stock_train, stock_test)),
        hovertemplate=stock_hover,
    ))

    fig.add_hline(
        y=50,
        line_dash="dash",
        line_color="white",
        annotation_text="Random Baseline (50%)",
        annotation_position="top left",
        annotation_font_color="white",
    )
    fig.add_hline(
        y=52.6,
        line_dash="dash",
        line_color="#e74c3c",
        annotation_text="Ceiling (52.6%)",
        annotation_position="top left",
        annotation_font_color="#e74c3c",
    )

    fig.update_layout(
        template="plotly_dark",
        title=f"Per-Asset Model Accuracy (All {len(crypto_labels) + len(stock_labels)} Models)",
        xaxis_title="Asset + Interval",
        yaxis_title="Accuracy (%)",
        yaxis=dict(range=[40, 65]),
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=600,
        margin=dict(l=40, r=40, t=60, b=120),
        xaxis_tickangle=-45,
        legend=dict(x=0.01, y=0.99),
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def build_model_family_comparison():
    result_path = os.path.join(
        _project_root,
        "scripts",
        "results",
        "btc_1h_model_family_comparison.json",
    )
    if not os.path.exists(result_path):
        return dbc.Alert(
            "No model family comparison results are available. Run the BTC 1h comparison experiment first.",
            color="info",
        )

    try:
        with open(result_path, encoding="utf-8") as result_file:
            result = json.load(result_file)
    except (OSError, json.JSONDecodeError) as error:
        return dbc.Alert(f"Could not load model family comparison: {error}", color="danger")

    model_labels = {
        "xgboost": "XGBoost",
        "logistic_regression": "Logistic Regression",
        "random_forest": "Random Forest",
    }
    rows = []
    for model_name, label in model_labels.items():
        metrics = result.get("models", {}).get(model_name)
        if not metrics:
            continue
        rows.append({
            "Model": label,
            "Accuracy": f"{metrics['accuracy'] * 100:.2f}%",
            "Balanced Accuracy": f"{metrics['balanced_accuracy'] * 100:.2f}%",
            "Precision": f"{metrics['precision'] * 100:.2f}%",
            "Recall": f"{metrics['recall'] * 100:.2f}%",
            "F1 Score": f"{metrics['f1_score'] * 100:.2f}%",
        })

    if not rows:
        return dbc.Alert("The model family comparison result has no model metrics.", color="warning")

    comparison_table = dbc.Table.from_dataframe(
        pd.DataFrame(rows),
        striped=True,
        bordered=True,
        hover=True,
        responsive=True,
        color="dark",
        className="mb-3",
    )
    period = (
        f"{result.get('test_rows', 0):,} identical unseen rows from "
        f"{str(result.get('test_start_date', ''))[:10]} to "
        f"{str(result.get('test_end_date', ''))[:10]}."
    )
    return html.Div([
        html.P(period, className="text-muted small mb-2"),
        comparison_table,
        dbc.Alert(result.get("conclusion", ""), color="info", className="mb-0"),
    ])


PRICE_RANGE_MAP = {
    "1d": 1, "3d": 3, "7d": 7, "30d": 30,
    "90d": 90, "180d": 180, "365d": 365,
}

MAX_CANDLES_DISPLAY = 2000

CRYPTO_INTERVALS = ["1h", "4h", "1d", "W", "M"]
STOCK_INTERVALS  = ["1h", "1d", "1wk", "1mo"]

PRED_CRYPTO_INTERVALS = ["1h", "4h", "1d"]
PRED_STOCK_INTERVALS  = ["1h", "1d"]

INTERVAL_LABELS = {
    "1h": "1 Hour",
    "4h": "4 Hours",
    "1d": "1 Day",
    "W":  "1 Week",
    "M":  "1 Month",
    "1wk": "1 Week",
    "1mo": "1 Month",
}

def _load_asset_list():
    """Read all distinct crypto symbols from DuckDB (gold_crypto_analytics)."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        crypto = conn.execute(
            "SELECT DISTINCT asset_symbol FROM gold_crypto_analytics ORDER BY asset_symbol"
        ).df()["asset_symbol"].tolist()
        conn.close()
        return crypto
    except Exception:
        return ["BTC"]

CRYPTO_ASSETS = _load_asset_list()
STOCK_ASSETS  = ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "TSLA"]


def render_pipeline_history():
    summary = get_run_summary()
    runs_df = get_pipeline_runs(limit=50)

    status_color_map = {
        "success": "success",
        "failed": "danger",
        "running": "warning",
        "skipped": "info",
    }

    summary_cards = dbc.Row(
        [
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(summary["total"]), className="card-title text-info text-center"),
                html.P("Total Runs", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=True),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{summary['success_rate']}%", className="card-title text-success text-center"),
                html.P("Success Rate", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=True),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(summary["success"]), className="card-title text-success text-center"),
                html.P("Successful", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=True),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(summary["failed"]), className="card-title text-danger text-center"),
                html.P("Failed", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=True),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(summary["running"]), className="card-title text-warning text-center"),
                html.P("Running", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=True),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(summary.get("skipped", 0)), className="card-title text-info text-center"),
                html.P("Skipped", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=True),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(summary["last_status"], className=f"card-title text-{status_color_map.get(summary['last_status'], 'muted')} text-center"),
                html.P("Last Run Status", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=True),
        ],
        className="mb-3",
    )

    last_message_block = None
    if summary["last_status"] == "failed" and summary["last_error"]:
        last_message_block = dbc.Alert(
            f"Last failure: {summary['last_error']}",
            color="danger",
            className="mb-3",
        )
    elif summary["last_status"] == "skipped" and summary["last_error"]:
        last_message_block = dbc.Alert(
            f"Last skipped run: {summary['last_error']}",
            color="info",
            className="mb-3",
        )

    if runs_df.empty:
        table_block = dbc.Alert(
            "No pipeline runs logged yet. The table is created on the first pipeline run.",
            color="info",
        )
    else:
        display_df = runs_df.copy()
        if "start_time" in display_df.columns:
            display_df["start_time"] = display_df["start_time"].astype(str)
        if "end_time" in display_df.columns:
            display_df["end_time"] = display_df["end_time"].astype(str)
        if "duration_seconds" in display_df.columns:
            display_df["duration_seconds"] = (pd.to_numeric(display_df["duration_seconds"], errors="coerce") / 60).round(1)
            display_df = display_df.rename(columns={"duration_seconds": "duration_mins"})
        if "models_retrained" in display_df.columns:
            display_df["models_retrained"] = display_df["models_retrained"].fillna("").astype(str)

        table_block = dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in display_df.columns],
            data=display_df.to_dict("records"),
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "#1a1a1a",
                "color": "#ccc",
                "fontWeight": "bold",
                "border": "1px solid #333",
            },
            style_cell={
                "backgroundColor": "#111",
                "color": "#ddd",
                "textAlign": "left",
                "padding": "6px",
                "border": "1px solid #333",
                "fontFamily": "monospace",
                "fontSize": "12px",
            },
            style_data_conditional=[
                {
                    "if": {"filter_query": "{status} = 'success'"},
                    "color": "#2ecc71",
                },
                {
                    "if": {"filter_query": "{status} = 'failed'"},
                    "color": "#e74c3c",
                },
                {
                    "if": {"filter_query": "{status} = 'running'"},
                    "color": "#f1c40f",
                },
                {
                    "if": {"filter_query": "{status} = 'skipped'"},
                    "color": "#3498db",
                },
            ],
            page_size=15,
            sort_action="native",
        )

    return dbc.Row(
        dbc.Col(
            [
                html.H3("Pipeline Run History", className="text-light mb-2"),
                html.P(
                    "Every pipeline run is logged in a DuckDB table so we can see the hourly cadence and success rate without opening the Prefect UI. Shows the last 50 runs.",
                    className="text-muted small mb-3",
                ),
                summary_cards,
                last_message_block,
                table_block,
            ]
        )
    )


def _downsample_ohlcv(df, max_points):
    """Downsample OHLCV data by merging candles so total points <= max_points."""
    n = len(df)
    if n <= max_points:
        return df

    group_size = (n + max_points - 1) // max_points
    df = df.copy()
    df["_group"] = df.index // group_size

    resampled = df.groupby("_group").agg(
        date=("date", "first"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index(drop=True)

    return resampled

@app.callback(
    dash.Output("price-asset-dropdown", "options"),
    dash.Output("price-asset-dropdown", "value"),
    dash.Input("price-class-dropdown", "value"),
)
def update_asset_dropdown(asset_class):
    """When asset class changes, update the asset dropdown with the correct list."""
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = "BTC" if "BTC" in assets else (assets[0] if assets else None)
    else:
        assets = STOCK_ASSETS
        default = assets[0] if assets else None

    options = [{"label": a, "value": a} for a in assets]
    return options, default


@app.callback(
    dash.Output("price-interval-dropdown", "options"),
    dash.Output("price-interval-dropdown", "value"),
    dash.Input("price-class-dropdown", "value"),
)
def update_interval_dropdown(asset_class):
    """When asset class changes, update the interval dropdown with the correct intervals."""
    if asset_class == "crypto":
        intervals = CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = STOCK_INTERVALS
        default = "1h"

    options = [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals]
    return options, default

@app.callback(
    dash.Output("price-chart", "figure"),
    dash.Output("indicator-data-store", "data"),
    dash.Input("price-class-dropdown", "value"),
    dash.Input("price-asset-dropdown", "value"),
    dash.Input("price-interval-dropdown", "value"),
    dash.Input("price-range-dropdown", "value"),
    dash.Input("indicator-toggles", "value"),
)
def build_price_chart(asset_class, asset_symbol, interval, range_value, indicators):
    """Query the database, downsample if needed, and build the OHLCV figure."""

    if not asset_symbol or not interval or not asset_class:
        return go.Figure().update_layout(
            template="plotly_dark",
            title="Select an asset and interval",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

    table = "gold_crypto_analytics" if asset_class == "crypto" else "gold_stock_analytics"

    conn = duckdb.connect(DB_PATH, read_only=True)

    if range_value == "all":
        df = conn.execute(f"""
            SELECT date, open, high, low, close, volume
            FROM {table}
            WHERE asset_symbol = ? AND interval = ?
            ORDER BY date
        """, [asset_symbol, interval]).df()
    else:
        days = PRICE_RANGE_MAP[range_value]
        df = conn.execute(f"""
            SELECT date, open, high, low, close, volume
            FROM {table}
            WHERE asset_symbol = ? AND interval = ?
              AND date >= (SELECT MAX(date) FROM {table}
                           WHERE asset_symbol = ? AND interval = ?)
                           - INTERVAL '{days} days'
            ORDER BY date
        """, [asset_symbol, interval, asset_symbol, interval]).df()

    conn.close()

    if df.empty:
        return go.Figure().update_layout(
            template="plotly_dark",
            title=f"No data for {asset_symbol} @ {INTERVAL_LABELS.get(interval, interval)}",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

    df["date"] = pd.to_datetime(df["date"])

    original_count = len(df)
    df = _downsample_ohlcv(df, MAX_CANDLES_DISPLAY)

    price_fmt = ".4f"

    symbol_label = f"{asset_symbol}/USDT" if asset_class == "crypto" else asset_symbol
    interval_label = INTERVAL_LABELS.get(interval, interval)

    show_volume = "volume" in (indicators or [])
    show_rsi = "rsi" in (indicators or [])
    show_macd = "macd" in (indicators or [])
    show_atr = "atr" in (indicators or [])
    show_obv = "obv" in (indicators or [])
    show_sma_crossover = "sma_crossover" in (indicators or [])

    SUBPLOT_ORDER = [
        ("volume", show_volume, "Volume"),
        ("rsi", show_rsi, "RSI (14)"),
        ("macd", show_macd, "MACD (12,26,9)"),
        ("atr", show_atr, "ATR (14)"),
        ("obv", show_obv, "OBV"),
    ]
    subplot_row = {}
    current_row = 1
    subplot_titles = [f"{symbol_label} · {interval_label}"]
    for key, active, title in SUBPLOT_ORDER:
        if active:
            current_row += 1
            subplot_row[key] = current_row
            subplot_titles.append(title)
    total_rows = current_row

    if total_rows > 1:
        row_heights = [0.55] + [0.45 / (total_rows - 1)] * (total_rows - 1)
        fig = make_subplots(
            rows=total_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=subplot_titles,
        )
    else:
        fig = make_subplots(
            rows=1, cols=1,
            shared_xaxes=True,
            subplot_titles=subplot_titles,
        )

    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol_label,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            customdata=df[["volume"]].values,
            hovertext=df["volume"] if show_volume else None,
            hovertemplate="<extra></extra>",
        ),
        row=1, col=1,
    )

    ema9 = df["close"].ewm(span=9, adjust=False).mean()
    ema21 = df["close"].ewm(span=21, adjust=False).mean()
    ema50 = df["close"].ewm(span=50, adjust=False).mean()
    sma50 = df["close"].rolling(window=50).mean()
    sma200 = df["close"].rolling(window=200).mean()

    if indicators:
        INDICATOR_CONFIG = {
            "ema9":  {"name": "EMA 9",  "color": "#2196f3", "series": ema9},
            "ema21": {"name": "EMA 21", "color": "#ff9800", "series": ema21},
            "ema50": {"name": "EMA 50", "color": "#9c27b0", "series": ema50},
            "sma50": {"name": "SMA 50", "color": "#f39c12", "series": sma50},
            "sma200":{"name": "SMA 200","color": "#e83e8c", "series": sma200},
        }

        for key in indicators:
            cfg = INDICATOR_CONFIG.get(key)
            if not cfg:
                continue
            if show_sma_crossover and key in ("sma50", "sma200"):
                continue
            fig.add_trace(
                go.Scatter(
                    x=df["date"], y=cfg["series"],
                    mode="lines", name=cfg["name"],
                    line=dict(color=cfg["color"], width=1.2),
                    hoverinfo="none",
                ),
                row=1, col=1,
            )

        if show_sma_crossover:
            fig.add_trace(go.Scatter(
                x=df["date"], y=sma50, mode="lines", name="SMA 50",
                line=dict(color="#f39c12", width=1.5), hoverinfo="none",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=sma200, mode="lines", name="SMA 200",
                line=dict(color="#e83e8c", width=1.5), hoverinfo="none",
            ), row=1, col=1)

        if "bb" in indicators:
            sma20 = df["close"].rolling(window=20).mean()
            std20 = df["close"].rolling(window=20).std()
            bb_upper = sma20 + 2 * std20
            bb_lower = sma20 - 2 * std20
            fig.add_trace(go.Scatter(x=df["date"], y=bb_upper, mode="lines", name="BB Upper", line=dict(color="rgba(255,255,255,0.25)", width=0.8), hoverinfo="none"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df["date"], y=sma20,   mode="lines", name="BB Mid",   line=dict(color="rgba(255,255,255,0.45)", width=0.8, dash="dash"), hoverinfo="none"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df["date"], y=bb_lower, mode="lines", name="BB Lower", line=dict(color="rgba(255,255,255,0.25)", width=0.8), fill="tonexty", fillcolor="rgba(255,255,255,0.04)", hoverinfo="none"), row=1, col=1)

        if "vwap" in indicators:
            typical = (df["high"] + df["low"] + df["close"]) / 3
            cvp = (typical * df["volume"]).cumsum()
            cv = df["volume"].cumsum()
            vwap = cvp / cv.replace(0, 1)
            fig.add_trace(
                go.Scatter(x=df["date"], y=vwap, mode="lines", name="VWAP",
                           line=dict(color="#ffeb3b", width=1, dash="dot"),
                           hoverinfo="none"),
                row=1, col=1,
            )

        if show_volume:
            vol_colors = ["#26a69a" if c >= o else "#ef5350" for o, c in zip(df["open"], df["close"])]
            fig.add_trace(
                go.Bar(
                    x=df["date"], y=df["volume"], name="Volume",
                    marker_color=vol_colors, opacity=0.6,
                    hovertemplate="Volume: %{y:,}<extra></extra>",
                ),
                row=subplot_row["volume"], col=1,
            )

        rsi_series = None
        if show_rsi:
            delta = df["close"].diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-10)
            rsi_series = 100.0 - (100.0 / (1.0 + rs))
            rsi_row = subplot_row["rsi"]
            fig.add_trace(go.Scatter(
                x=df["date"], y=rsi_series, mode="lines", name="RSI",
                line=dict(color="#f39c12", width=1.5), hoverinfo="none",
            ), row=rsi_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="rgba(255,255,255,0.15)", row=rsi_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="rgba(255,255,255,0.15)", row=rsi_row, col=1)
            fig.add_hline(y=50, line_dash="dot", line_color="rgba(255,255,255,0.08)", row=rsi_row, col=1)

        macd_line = signal_line = macd_hist = None
        if show_macd:
            ema12 = df["close"].ewm(span=12, adjust=False).mean()
            ema26 = df["close"].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line
            macd_row = subplot_row["macd"]
            hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in macd_hist]
            fig.add_trace(go.Bar(
                x=df["date"], y=macd_hist, name="MACD Hist",
                marker_color=hist_colors, opacity=0.7,
                hovertemplate="%{y:.6f}<extra></extra>",
            ), row=macd_row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=macd_line, mode="lines", name="MACD",
                line=dict(color="#17a2b8", width=1.2), hoverinfo="none",
            ), row=macd_row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=signal_line, mode="lines", name="MACD Signal",
                line=dict(color="#e83e8c", width=1.2), hoverinfo="none",
            ), row=macd_row, col=1)

        atr_series = None
        if show_atr:
            high, low, close = df["high"], df["low"], df["close"]
            prev_close = close.shift(1)
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_series = true_range.rolling(window=14).mean()
            atr_row = subplot_row["atr"]
            fig.add_trace(go.Scatter(
                x=df["date"], y=atr_series, mode="lines", name="ATR",
                fill="tozeroy", fillcolor="rgba(108,92,231,0.1)",
                line=dict(color="#6c5ce7", width=1.5), hoverinfo="none",
            ), row=atr_row, col=1)

        obv_series = None
        if show_obv:
            close_diff = df["close"].diff()
            direction = close_diff.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
            obv_series = (df["volume"] * direction).cumsum()
            obv_row = subplot_row["obv"]
            fig.add_trace(go.Scatter(
                x=df["date"], y=obv_series, mode="lines", name="OBV",
                fill="tozeroy", fillcolor="rgba(0,184,148,0.1)",
                line=dict(color="#00b894", width=1.5), hoverinfo="none",
            ), row=obv_row, col=1)

    chart_height = max(500, 280 * total_rows)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=chart_height,
        dragmode="pan",
        hovermode="x",
        hoverdistance=20,
        hoverlabel=dict(bgcolor="rgba(33,37,41,0.85)", font_size=11),
        showlegend=bool(indicators),
        margin=dict(l=15, r=15, t=45, b=10),
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikecolor="rgba(255,255,255,0.5)",
            spikedash="dashdot",
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=3, label="3D", step="day", stepmode="backward"),
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all", label="All"),
                ]),
                bgcolor="#1e1e1e",
                activecolor="#375a7f",
                font=dict(color="#aaa", size=11),
            ),
        ),
        annotations=[
            dict(
                x=1.0, y=0.0,
                xref="paper", yref="paper",
                text=f"{len(df):,} candles",
                showarrow=False,
                font=dict(size=10, color="#666"),
                xanchor="right", yanchor="bottom",
                xshift=0, yshift=16,
            ),
        ],
    )

    fig.update_yaxes(
        title_text="Price (USD)", row=1, col=1,
        showgrid=True, gridcolor="rgba(255,255,255,0.06)",
        showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
        spikecolor="rgba(255,255,255,0.5)", spikedash="dashdot",
        tickformat=price_fmt,
    )
    if show_volume:
        fig.update_yaxes(
            title_text="Volume", row=subplot_row["volume"], col=1,
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
            spikecolor="rgba(255,255,255,0.5)", spikedash="dashdot",
        )
    if show_rsi:
        fig.update_yaxes(
            title_text="RSI", row=subplot_row["rsi"], col=1,
            range=[0, 100], tickvals=[0, 30, 50, 70, 100],
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
            spikecolor="rgba(255,255,255,0.5)", spikedash="dashdot",
        )
    if show_macd:
        fig.update_yaxes(
            title_text="MACD", row=subplot_row["macd"], col=1,
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
            spikecolor="rgba(255,255,255,0.5)", spikedash="dashdot",
        )
    if show_atr:
        fig.update_yaxes(
            title_text="ATR", row=subplot_row["atr"], col=1,
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
            spikecolor="rgba(255,255,255,0.5)", spikedash="dashdot",
        )
    if show_obv:
        fig.update_yaxes(
            title_text="OBV", row=subplot_row["obv"], col=1,
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
            spikecolor="rgba(255,255,255,0.5)", spikedash="dashdot",
        )

    indicator_data = {}
    indicators_for_data = indicators or []
    if indicators_for_data:
        dates_iso = df["date"].dt.strftime("%Y-%m-%dT%H:%M:%S").tolist()

        def _store_series(arr, label):
            values = arr.tolist() if hasattr(arr, "tolist") else arr
            for i, d in enumerate(dates_iso):
                v = values[i] if pd.notna(values[i]) else None
                indicator_data.setdefault(d, {})[label] = v

        INDICATOR_LABELS = {
            "ema9": "EMA 9", "ema21": "EMA 21", "ema50": "EMA 50",
            "sma50": "SMA 50", "sma200": "SMA 200",
        }
        for key in indicators_for_data:
            cfg = INDICATOR_CONFIG.get(key)
            if cfg:
                label = INDICATOR_LABELS.get(key, cfg["name"])
                if show_sma_crossover and key in ("sma50", "sma200"):
                    continue
                _store_series(cfg["series"], label)

        if show_sma_crossover:
            _store_series(sma50, "SMA 50")
            _store_series(sma200, "SMA 200")

        if "bb" in indicators_for_data:
            sma20 = df["close"].rolling(window=20).mean()
            std20 = df["close"].rolling(window=20).std()
            _store_series(sma20 + 2 * std20, "BB Upper")
            _store_series(sma20, "BB Mid")
            _store_series(sma20 - 2 * std20, "BB Lower")

        if "vwap" in indicators_for_data:
            typical = (df["high"] + df["low"] + df["close"]) / 3
            cvp = (typical * df["volume"]).cumsum()
            cv = df["volume"].cumsum()
            _store_series(cvp / cv.replace(0, 1), "VWAP")

        if show_rsi and rsi_series is not None:
            _store_series(rsi_series, "RSI")

        if show_macd and macd_line is not None:
            _store_series(macd_line, "MACD")
            _store_series(signal_line, "MACD Signal")
            _store_series(macd_hist, "MACD Hist")

        if show_atr and atr_series is not None:
            _store_series(atr_series, "ATR")

        if show_obv and obv_series is not None:
            _store_series(obv_series, "OBV")

    return fig, indicator_data


@app.callback(
    dash.Output("chart-info-bar", "children"),
    dash.Input("price-chart", "hoverData"),
    dash.State("indicator-data-store", "data"),
)
def update_chart_info_bar(hover_data, indicator_data):
    """TradingView-style info bar: OHLCV + indicator values pinned above chart."""
    if not hover_data or not hover_data.get("points"):
        return dash.no_update
    o = h = l = c = v = None
    hovered_x = None
    for pt in hover_data["points"]:
        if "open" in pt:
            o, h, l, c = pt["open"], pt["high"], pt["low"], pt["close"]
            customdata = pt.get("customdata")
            if isinstance(customdata, (list, tuple)) and customdata:
                v = customdata[0]
            elif customdata is not None:
                v = customdata
            else:
                v = pt.get("hovertext") or None
        if hovered_x is None and pt.get("x"):
            hovered_x = pt["x"]
    parts = []
    if o is not None:
        change = c - o
        change_pct = (change / o * 100) if o else 0
        candle_range = h - l
        range_pct = (candle_range / o * 100) if o else 0
        movement_color = "#26a69a" if change >= 0 else "#ef5350"
        turnover = c * v if v is not None else None
        parts.extend([
            html.Span(f"O: {o:.4f}"),
            html.Span(f"H: {h:.4f}"),
            html.Span(f"L: {l:.4f}"),
            html.Span(f"C: {c:.4f}"),
            html.Span(
                f"Change: {change:+.4f} ({change_pct:+.2f}%)",
                style={"color": movement_color},
            ),
            html.Span(f"Range: {candle_range:.4f} ({range_pct:.2f}%)"),
        ])
        if v is not None:
            parts.append(html.Span(f"Volume: {v:,.0f}"))
            parts.append(html.Span(f"Turnover: {turnover:,.2f}"))
    if hovered_x and indicator_data:
        dt_str = pd.to_datetime(hovered_x).strftime("%Y-%m-%dT%H:%M:%S")
        ind_vals = indicator_data.get(dt_str, {})
        ORDERED_NAMES = [
            "EMA 9", "EMA 21", "EMA 50", "SMA 50", "SMA 200",
            "BB Upper", "BB Mid", "BB Lower", "VWAP",
            "RSI", "MACD", "MACD Signal", "MACD Hist", "ATR", "OBV",
        ]
        for name in ORDERED_NAMES:
            val = ind_vals.get(name)
            if val is not None:
                parts.append(html.Span(f"{name}: {val:.4f}"))
    children = []
    for index, part in enumerate(parts):
        if index:
            children.append(html.Span("  |  "))
        children.append(part)
    return children if children else ""


@app.callback(
    dash.Output("pred-asset-dropdown", "options"),
    dash.Output("pred-asset-dropdown", "value"),
    dash.Input("pred-class-dropdown", "value"),
)
def update_pred_asset_dropdown(asset_class):
    """When asset class changes, update the predictions asset dropdown."""
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = "BTC" if "BTC" in assets else (assets[0] if assets else None)
    else:
        assets = STOCK_ASSETS
        default = assets[0] if assets else None
    options = [{"label": a, "value": a} for a in assets]
    return options, default


@app.callback(
    dash.Output("pred-interval-dropdown", "options"),
    dash.Output("pred-interval-dropdown", "value"),
    dash.Input("pred-class-dropdown", "value"),
)
def update_pred_interval_dropdown(asset_class):
    """When asset class changes, update the predictions interval dropdown."""
    if asset_class == "crypto":
        intervals = PRED_CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = PRED_STOCK_INTERVALS
        default = "1h"
    options = [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals]
    return options, default


@app.callback(
    dash.Output("pred-content", "children"),
    dash.Input("pred-class-dropdown", "value"),
    dash.Input("pred-asset-dropdown", "value"),
    dash.Input("pred-interval-dropdown", "value"),
    dash.Input("pred-range-dropdown", "value"),
)
def build_prediction_charts(asset_class, asset_symbol, interval, range_value):
    """Run XGBoost prediction and render charts for the selected asset/interval."""
    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        results = run_prediction(asset=asset_symbol, interval=interval, asset_class=asset_class)
    except Exception as e:
        return dbc.Alert(
            f"Prediction failed for {asset_symbol}/{interval}: {e}", color="warning"
        )

    if results is None or results.empty:
        return dbc.Alert(
            f"No prediction data for {asset_symbol}/{interval}. "
            "Run the pipeline first or try BTC/1h.",
            color="warning",
        )

    latest_prediction = results.iloc[-1]

    if range_value and range_value != "all":
        days = PRICE_RANGE_MAP.get(range_value, 90)
        cutoff = results["date"].max() - pd.Timedelta(days=days)
        results = results[results["date"] >= cutoff]

    if results.empty:
        return dbc.Alert(
            f"No prediction data in selected time range for {asset_symbol}/{interval}.",
            color="warning",
        )

    if "is_oos" in results.columns:
        oos = results[results["is_oos"] & results["actual_direction"].notna()]
        oos_total = len(oos)
    else:
        oos = results[results["actual_direction"].notna()]
        oos_total = len(oos)

    scored = results[results["actual_direction"].notna()]
    total = len(scored)
    correct = (scored["prediction"] == scored["actual_direction"]).sum()
    accuracy = correct / total if total > 0 else 0

    oos_correct = (oos["prediction"] == oos["actual_direction"]).sum()
    oos_accuracy = oos_correct / oos_total if oos_total > 0 else 0

    comparison_data = oos if oos_total > 0 else results
    comparison_rows = []
    comparison_scores = []
    sma20 = comparison_data["close"].rolling(window=20).mean()
    sma50 = comparison_data["close"].rolling(window=50).mean()
    sma_rule = (sma20 > sma50).astype(int)
    sma_rule[sma20.isna() | sma50.isna()] = np.nan
    comparison_rules = [
        ("XGBoost", comparison_data["prediction"]),
        ("Always Up", pd.Series(1, index=comparison_data.index)),
        ("Always Down", pd.Series(0, index=comparison_data.index)),
        ("Last Candle Direction", (comparison_data["close"].diff() > 0).astype(int).shift(1)),
        ("SMA 20 > SMA 50 Rule", sma_rule),
    ]
    for name, rule_prediction in comparison_rules:
        valid = rule_prediction.notna()
        rows_tested = int(valid.sum())
        correct_count = int((rule_prediction[valid].astype(int) == comparison_data.loc[valid, "actual_direction"]).sum())
        rule_accuracy = correct_count / rows_tested if rows_tested > 0 else 0
        comparison_scores.append((name, rule_accuracy))
        comparison_rows.append({
            "Model / Rule": name,
            "Accuracy": f"{rule_accuracy * 100:.1f}%",
            "Correct": correct_count,
            "Rows Tested": rows_tested,
        })

    xgboost_accuracy = next(score for name, score in comparison_scores if name == "XGBoost")
    baseline_scores = [(name, score) for name, score in comparison_scores if name != "XGBoost"]
    best_baseline_name, best_baseline_accuracy = max(baseline_scores, key=lambda item: item[1])
    baseline_gap = xgboost_accuracy - best_baseline_accuracy
    baseline_gap_pct = abs(baseline_gap) * 100
    if baseline_gap > 0:
        gap_text = f"XGBoost beats best baseline ({best_baseline_name}) by {baseline_gap_pct:.1f}%"
        badge_text = "Model beats baselines"
        badge_color = "success"
    elif baseline_gap >= -0.005:
        gap_text = f"XGBoost is close to best baseline ({best_baseline_name}) by {baseline_gap_pct:.1f}%"
        badge_text = "Close to baseline"
        badge_color = "warning"
    else:
        gap_text = f"XGBoost trails best baseline ({best_baseline_name}) by {baseline_gap_pct:.1f}%"
        badge_text = "Baseline beats model"
        badge_color = "danger"

    comparison_scope_text = "Comparison uses out-of-sample rows only" if oos_total > 0 else "Comparison uses visible rows"
    comparison_summary = dbc.Row(
        [
            dbc.Col([
                html.P(gap_text, className="text-muted mb-0"),
                html.Small(comparison_scope_text, className="text-muted"),
            ], width=True),
            dbc.Col(dbc.Badge(badge_text, color=badge_color, className="p-2"), width="auto"),
        ],
        align="center",
        className="mb-2",
    )

    comparison_table = dbc.Table.from_dataframe(
        pd.DataFrame(comparison_rows),
        striped=True,
        bordered=True,
        hover=True,
        color="dark",
        className="mb-3",
    )

    up_pred_pct = (results["prediction"] == 1).sum() / total * 100

    MAX_CHART_POINTS = 2000
    MAX_MARKERS = 300
    if len(results) > MAX_CHART_POINTS:
        step = max(1, len(results) // MAX_CHART_POINTS)
        chart_data = results.iloc[::step].copy()
    else:
        chart_data = results

    if len(results) > MAX_MARKERS:
        marker_data = results.iloc[-MAX_MARKERS:]
    else:
        marker_data = results

    interval_label = INTERVAL_LABELS.get(interval, interval)
    prediction_direction = "UP" if latest_prediction["prediction"] == 1 else "DOWN"
    prediction_color = "#26a69a" if prediction_direction == "UP" else "#ef5350"
    prediction_confidence = latest_prediction["confidence"] * 100
    prediction_date = pd.to_datetime(latest_prediction["date"]).strftime("%Y-%m-%d %H:%M UTC")
    next_prediction_card = dbc.Card(
        dbc.CardBody([
            html.P("Next Prediction", className="text-muted small mb-1"),
            html.H4(f"{asset_symbol} {interval_label}", className="text-light mb-2"),
            html.H2(prediction_direction, style={"color": prediction_color}, className="mb-2"),
            html.P(
                f"Confidence: {prediction_confidence:.1f}%",
                className="text-muted mb-1",
            ),
            html.P(
                f"As of: {prediction_date}",
                className="text-muted small mb-0",
            ),
        ]),
        color="dark",
        outline=True,
        className="mb-3",
    )

    correct_pct = accuracy * 100
    wrong_pct = (1 - accuracy) * 100
    summary_cards = dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5(
                            f"Correct: {correct_pct:.1f}% | Wrong: {wrong_pct:.1f}%",
                            className="card-title text-info",
                        ),
                        html.P("Overall Accuracy", className="card-text text-muted small"),
                    ]),
                    color="dark", outline=True,
                ),
                width=6,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5(
                            f"{up_pred_pct:.1f}% UP / {100 - up_pred_pct:.1f}% DOWN",
                            className="card-title text-info",
                        ),
                        html.P("Predicted Direction Split", className="card-text text-muted small"),
                    ]),
                    color="dark", outline=True,
                ),
                width=6,
            ),
        ],
        className="mb-3",
    )

    fig_overlay = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=("Close Price with Prediction Markers", "Confidence Over Time"),
    )

    fig_overlay.add_trace(
        go.Scatter(
            x=chart_data["date"], y=chart_data["close"],
            mode="lines", name="Close Price",
            line=dict(color="#17a2b8", width=1),
        ),
        row=1, col=1,
    )

    marker_data = marker_data.copy()
    marker_data["correct"] = marker_data["prediction"] == marker_data["actual_direction"]
    marker_data["label"] = np.where(marker_data["correct"], "✅", "❌")
    marker_data["pred_dir"] = np.where(marker_data["prediction"] == 1, "UP", "DOWN")
    marker_data["actual_dir"] = np.where(marker_data["actual_direction"] == 1, "UP", "DOWN")

    for filter_mask, color, name in [
        (marker_data["correct"], "#26a69a", "Correct ✅"),
        (~marker_data["correct"], "#ef5350", "Wrong ❌"),
    ]:
        subset = marker_data[filter_mask]
        if not subset.empty:
            fig_overlay.add_trace(
                go.Scatter(
                    x=subset["date"], y=subset["close"],
                    mode="text",
                    name=name,
                    text=subset["label"],
                    textfont=dict(size=8, color=color),
                    customdata=np.column_stack([
                        subset["date"].dt.strftime("%Y-%m-%d %H:%M"),
                        subset["close"].round(2),
                        subset["pred_dir"],
                        subset["actual_dir"],
                        (subset["confidence"] * 100).round(1),
                        np.where(subset["correct"], "Correct ✅", "Wrong ❌"),
                    ]),
                    hovertemplate=(
                        "Predicted %{customdata[2]} → Actual %{customdata[3]} (Confidence: %{customdata[4]}%)"
                        "<extra></extra>"
                    ),
                ),
                row=1, col=1,
            )

    fig_overlay.add_trace(
        go.Scatter(
            x=chart_data["date"], y=chart_data["confidence"],
            mode="lines", name="Confidence",
            line=dict(color="#ffc107", width=1),
            fill="tozeroy", fillcolor="rgba(255,193,7,0.1)",
        ),
        row=2, col=1,
    )

    fig_overlay.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=650,
        hovermode="x unified",
        dragmode="pan",
        hoverlabel=dict(bgcolor="#212529", font_size=13),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig_overlay.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig_overlay.update_yaxes(title_text="Confidence", row=2, col=1)

    fig_hist = go.Figure()
    fig_hist.add_trace(
        go.Histogram(
            x=results["confidence"], nbinsx=40,
            marker_color="#17a2b8", opacity=0.8,
            name="Confidence",
        )
    )
    fig_hist.add_vline(
        x=0.5, line_dash="dash", line_color="#ef5350",
        annotation_text="Random (0.5)", annotation_position="top left",
    )
    fig_hist.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
        dragmode="pan",
        hoverlabel=dict(bgcolor="#212529", font_size=13),
        title="Confidence Distribution",
        xaxis_title="Prediction Confidence",
        yaxis_title="Count",
        margin=dict(l=10, r=10, t=40, b=10),
    )

    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=oos_accuracy * 100,
            number={"suffix": "%", "font": {"size": 48, "color": "#17a2b8"}},
            title={"text": "Out-of-Sample Accuracy", "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#adb5bd"},
                "bar": {"color": "#26a69a" if oos_accuracy >= 0.5 else "#ef5350"},
                "steps": [
                    {"range": [0, 50], "color": "rgba(239,83,80,0.3)"},
                    {"range": [50, 52], "color": "rgba(255,193,7,0.3)"},
                    {"range": [52, 60], "color": "rgba(38,166,154,0.3)"},
                    {"range": [60, 100], "color": "rgba(38,166,154,0.5)"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 2},
                    "value": 52.6,
                },
            },
        )
    )
    fig_gauge.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
    )

    range_label = f" ({range_value})" if range_value and range_value != "all" else " (all time)"
    symbol_label = f"{asset_symbol}/USDT" if asset_class == "crypto" else asset_symbol
    title = f"{symbol_label} {interval_label}{range_label} -- XGBoost Direction Predictions"

    return html.Div([
        html.H3(title, className="text-light mb-3"),
        next_prediction_card,
        summary_cards,
        html.H5("Model Comparison", className="text-light mb-2"),
        comparison_summary,
        comparison_table,
        dbc.Row(
            [
                dbc.Col(dcc.Graph(figure=fig_gauge, config={"responsive": True}), width=4),
                dbc.Col(dcc.Graph(figure=fig_hist, config={"responsive": True}), width=8),
            ],
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(
                dcc.Graph(figure=fig_overlay, config={"displayModeBar": True, "responsive": True}),
                width=12,
            )
        ),
    ])


@app.callback(
    dash.Output("ind-asset-dropdown", "options"),
    dash.Output("ind-asset-dropdown", "value"),
    dash.Input("ind-class-dropdown", "value"),
)
def update_ind_asset_dropdown(asset_class):
    """When asset class changes, update the indicators asset dropdown."""
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = "BTC" if "BTC" in assets else (assets[0] if assets else None)
    else:
        assets = STOCK_ASSETS
        default = assets[0] if assets else None
    options = [{"label": a, "value": a} for a in assets]
    return options, default


@app.callback(
    dash.Output("ind-interval-dropdown", "options"),
    dash.Output("ind-interval-dropdown", "value"),
    dash.Input("ind-class-dropdown", "value"),
)
def update_ind_interval_dropdown(asset_class):
    """When asset class changes, update the indicators interval dropdown."""
    if asset_class == "crypto":
        intervals = CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = STOCK_INTERVALS
        default = "1h"
    options = [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals]
    return options, default


@app.callback(
    dash.Output("ind-content", "children"),
    dash.Input("ind-class-dropdown", "value"),
    dash.Input("ind-asset-dropdown", "value"),
    dash.Input("ind-interval-dropdown", "value"),
    dash.Input("ind-range-dropdown", "value"),
)
def build_indicators_chart(asset_class, asset_symbol, interval, range_value):
    """Query the database, compute technical indicators, and render multi-panel chart."""
    if not asset_symbol or not interval or not asset_class:
        return dbc.Alert("Select an asset and interval.", color="info")

    table = "gold_crypto_analytics" if asset_class == "crypto" else "gold_stock_analytics"

    conn = duckdb.connect(DB_PATH, read_only=True)

    if range_value == "all":
        df = conn.execute(f"""
            SELECT date, open, high, low, close, volume
            FROM {table}
            WHERE asset_symbol = ? AND interval = ?
            ORDER BY date
        """, [asset_symbol, interval]).df()
    else:
        days = PRICE_RANGE_MAP.get(range_value, 90)
        df = conn.execute(f"""
            SELECT date, open, high, low, close, volume
            FROM {table}
            WHERE asset_symbol = ? AND interval = ?
              AND date >= (SELECT MAX(date) FROM {table}
                           WHERE asset_symbol = ? AND interval = ?)
                           - INTERVAL '{days} days'
            ORDER BY date
        """, [asset_symbol, interval, asset_symbol, interval]).df()

    conn.close()

    if df.empty:
        return dbc.Alert(
            f"No data for {asset_symbol} @ {INTERVAL_LABELS.get(interval, interval)}",
            color="warning",
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df["rsi"] = 100.0 - (100.0 / (1.0 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    sma20 = df["close"].rolling(window=20).mean()
    std20 = df["close"].rolling(window=20).std()
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_middle"] = sma20
    df["bb_lower"] = sma20 - 2 * std20

    df["sma50"] = df["close"].rolling(window=50).mean()
    df["sma200"] = df["close"].rolling(window=200).mean()

    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = true_range.rolling(window=14).mean()

    close_diff = df["close"].diff()
    df["obv"] = (
        df["volume"]
        * (close_diff.gt(0).astype(int) - close_diff.lt(0).astype(int))
    ).fillna(0).cumsum()

    symbol_label = f"{asset_symbol}/USDT" if asset_class == "crypto" else asset_symbol
    interval_label = INTERVAL_LABELS.get(interval, interval)

    fig = make_subplots(
        rows=6, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.28, 0.14, 0.14, 0.14, 0.12, 0.18],
        subplot_titles=(
            f"{symbol_label} — Bollinger Bands ({interval_label})",
            "RSI (14)",
            "MACD (12, 26, 9)",
            "SMA Crossover (50 / 200)",
            "ATR (14)",
            "OBV (On-Balance Volume)",
        ),
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["close"], mode="lines",
            name="Close", line=dict(color="#17a2b8", width=1.5),
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["bb_upper"], mode="lines",
            name="BB Upper", line=dict(color="rgba(255,255,255,0.3)", width=0.8),
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["bb_middle"], mode="lines",
            name="BB Middle", line=dict(color="rgba(255,255,255,0.5)", width=0.8, dash="dash"),
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["bb_lower"], mode="lines",
            name="BB Lower", line=dict(color="rgba(255,255,255,0.3)", width=0.8),
            fill="tonexty", fillcolor="rgba(23,162,184,0.08)",
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["rsi"], mode="lines",
            name="RSI", line=dict(color="#f39c12", width=1.5),
        ),
        row=2, col=1,
    )
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(239,83,80,0.6)", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(38,166,154,0.6)", row=2, col=1)

    fig.add_trace(
        go.Bar(
            x=df["date"], y=df["macd_hist"],
            name="MACD Hist",
            marker_color=[
                "#26a69a" if v >= 0 else "#ef5350" for v in df["macd_hist"]
            ],
            opacity=0.7,
        ),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["macd"], mode="lines",
            name="MACD", line=dict(color="#17a2b8", width=1.5),
        ),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["macd_signal"], mode="lines",
            name="Signal", line=dict(color="#e83e8c", width=1.2),
        ),
        row=3, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["close"], mode="lines",
            name="Close", line=dict(color="rgba(255,255,255,0.4)", width=1),
            showlegend=False,
        ),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["sma50"], mode="lines",
            name="SMA 50", line=dict(color="#f39c12", width=1.5),
        ),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["sma200"], mode="lines",
            name="SMA 200", line=dict(color="#e83e8c", width=1.5),
        ),
        row=4, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["atr"], mode="lines",
            name="ATR", line=dict(color="#6c5ce7", width=1.5),
            fill="tozeroy", fillcolor="rgba(108,92,231,0.10)",
        ),
        row=5, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"], y=df["obv"], mode="lines",
            name="OBV", line=dict(color="#00b894", width=1.5),
            fill="tozeroy", fillcolor="rgba(0,184,148,0.10)",
        ),
        row=6, col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=1200,
        hovermode="x unified",
        dragmode="pan",
        hoverlabel=dict(bgcolor="#212529", font_size=13),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    fig.update_yaxes(title_text="Price", row=4, col=1)
    fig.update_yaxes(title_text="ATR", row=5, col=1)
    fig.update_yaxes(title_text="OBV", row=6, col=1)

    return dcc.Graph(figure=fig, config={"displayModeBar": True, "responsive": True})

def _get_age_color(age_hours: float, is_crypto: bool):
    """Return Bootstrap color string based on age and asset class.

    Crypto thresholds (24/7 markets, strict):
        green < 1h, yellow 1-24h, red > 24h

    Stock thresholds (market hours, relaxed for nights/weekends):
        green < 24h, yellow 24-72h, red > 72h
    """
    if is_crypto:
        if age_hours < 1:
            return "success"
        elif age_hours < 24:
            return "warning"
        else:
            return "danger"
    else:
        if age_hours < 24:
            return "success"
        elif age_hours < 72:
            return "warning"
        else:
            return "danger"


def _build_freshness_badge(max_date, now_utc, asset_label: str, is_crypto: bool):
    """Build a dbc.Badge for a single asset class given its MAX(date)."""
    if max_date is None:
        return dbc.Badge(
            f"{asset_label}: No data",
            color="danger",
            className="px-3 py-2 fs-6",
        )
    if isinstance(max_date, str):
        latest = datetime.fromisoformat(max_date)
    else:
        latest = max_date
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    age_hours = (now_utc - latest).total_seconds() / 3600
    color = _get_age_color(age_hours, is_crypto)

    label = latest.astimezone(ZoneInfo("Europe/Lisbon")).strftime("%Y-%m-%d %H:%M %Z")
    return dbc.Badge(
        f"{asset_label}: {label} ({age_hours:.1f}h ago)",
        color=color,
        className="px-3 py-2 fs-6",
    )


@app.callback(
    dash.Output("freshness-crypto-badge", "children"),
    dash.Input("freshness-interval", "n_intervals"),
)
def update_crypto_freshness(_n):
    """Crypto freshness badge with strict 24/7 thresholds."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        crypto_date = conn.execute(
            "SELECT MAX(date) FROM gold_crypto_analytics"
        ).fetchone()[0]
        conn.close()
        return _build_freshness_badge(crypto_date, datetime.now(timezone.utc), "Crypto", True)
    except Exception:
        return dbc.Badge("Crypto: unavailable", color="secondary", className="px-3 py-2 fs-6")


@app.callback(
    dash.Output("freshness-stock-badge", "children"),
    dash.Input("freshness-interval", "n_intervals"),
)
def update_stock_freshness(_n):
    """Stock freshness badge with relaxed thresholds for market-hours trading."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        stock_date = conn.execute(
            "SELECT MAX(date) FROM gold_stock_analytics"
        ).fetchone()[0]
        conn.close()
        return _build_freshness_badge(stock_date, datetime.now(timezone.utc), "Stocks", False)
    except Exception:
        return dbc.Badge("Stocks: unavailable", color="secondary", className="px-3 py-2 fs-6")


@app.callback(
    dash.Output("fi-asset-dropdown", "options"),
    dash.Output("fi-asset-dropdown", "value"),
    dash.Input("fi-class-dropdown", "value"),
)
def update_fi_asset_dropdown(asset_class):
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = "BTC" if "BTC" in assets else (assets[0] if assets else None)
    else:
        assets = STOCK_ASSETS
        default = assets[0] if assets else None
    options = [{"label": a, "value": a} for a in assets]
    return options, default


@app.callback(
    dash.Output("fi-interval-dropdown", "options"),
    dash.Output("fi-interval-dropdown", "value"),
    dash.Input("fi-class-dropdown", "value"),
)
def update_fi_interval_dropdown(asset_class):
    if asset_class == "crypto":
        intervals = PRED_CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = PRED_STOCK_INTERVALS
        default = "1h"
    options = [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals]
    return options, default


@app.callback(
    dash.Output("fi-chart-container", "children"),
    dash.Input("fi-class-dropdown", "value"),
    dash.Input("fi-asset-dropdown", "value"),
    dash.Input("fi-interval-dropdown", "value"),
)
def build_feature_importance_chart(asset_class, asset_symbol, interval):
    import json
    import xgboost as xgb

    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    subdir = "crypto" if asset_class == "crypto" else "stocks"
    model_path = os.path.join("src", "models", subdir, f"{asset_symbol}_{interval}_xgboost_model.json")
    meta_path = os.path.join("src", "models", subdir, f"{asset_symbol}_{interval}_xgboost_metadata.json")

    if not os.path.exists(model_path):
        return dbc.Alert(
            f"No trained model found for {asset_symbol} @ {interval}. Run the pipeline first.",
            color="warning",
        )

    try:
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        booster = model.get_booster()

        importance = booster.get_score(importance_type="gain")
        if not importance:
            importance = booster.get_score(fmap="", importance_type="gain")

        if not importance:
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                features = meta.get("features", [])
                scores = model.feature_importances_
                importance = {feat: score for feat, score in zip(features, scores) if score > 0}
            else:
                importance = {}

        if not importance:
            return dbc.Alert(
                f"No feature importance data available for {asset_symbol} @ {interval}.",
                color="warning",
            )

        sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:15]
        feat_names = [x[0] for x in sorted_items]
        feat_values = [x[1] for x in sorted_items]

        fig = go.Figure(go.Bar(
            x=feat_values,
            y=feat_names,
            orientation="h",
            marker_color="#3498db",
            text=[f"{v:.2f}" for v in feat_values],
            textposition="outside",
        ))
        fig.update_layout(
            template="plotly_dark",
            title=f"Top 15 Feature Importance (Gain) - {asset_symbol} {interval}",
            xaxis_title="Feature Importance (Gain)",
            yaxis=dict(autorange="reversed"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=500,
            margin=dict(l=160, r=40, t=60, b=40),
        )

        return dcc.Graph(figure=fig, config={"displayModeBar": False})

    except Exception as e:
        return dbc.Alert(f"Error loading feature importance: {e}", color="danger")


@app.callback(
    dash.Output("cm-asset-dropdown", "options"),
    dash.Output("cm-asset-dropdown", "value"),
    dash.Input("cm-class-dropdown", "value"),
)
def update_cm_asset_dropdown(asset_class):
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = "BTC" if "BTC" in assets else (assets[0] if assets else None)
    else:
        assets = STOCK_ASSETS
        default = assets[0] if assets else None
    options = [{"label": a, "value": a} for a in assets]
    return options, default


@app.callback(
    dash.Output("cm-interval-dropdown", "options"),
    dash.Output("cm-interval-dropdown", "value"),
    dash.Input("cm-class-dropdown", "value"),
)
def update_cm_interval_dropdown(asset_class):
    if asset_class == "crypto":
        intervals = PRED_CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = PRED_STOCK_INTERVALS
        default = "1h"
    options = [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals]
    return options, default


@app.callback(
    dash.Output("cm-chart-container", "children"),
    dash.Input("cm-class-dropdown", "value"),
    dash.Input("cm-asset-dropdown", "value"),
    dash.Input("cm-interval-dropdown", "value"),
)
def build_confusion_matrix(asset_class, asset_symbol, interval):
    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        df = run_prediction(asset_symbol, interval, asset_class)
    except FileNotFoundError:
        return dbc.Alert(
            f"No trained model for {asset_symbol} @ {interval}. Train one first.",
            color="warning",
        )

    if df is None or df.empty:
        return dbc.Alert(
            f"No prediction data for {asset_symbol} @ {interval}.",
            color="warning",
        )

    oos = df[df["is_oos"]] if "is_oos" in df.columns else df
    oos = oos[oos["actual_direction"].notna()]
    if oos.empty:
        oos = df[df["actual_direction"].notna()]

    tp = int(((oos["prediction"] == 1) & (oos["actual_direction"] == 1)).sum())
    fp = int(((oos["prediction"] == 1) & (oos["actual_direction"] == 0)).sum())
    tn = int(((oos["prediction"] == 0) & (oos["actual_direction"] == 0)).sum())
    fn = int(((oos["prediction"] == 0) & (oos["actual_direction"] == 1)).sum())

    total = tp + fp + tn + fn
    if total == 0:
        return dbc.Alert("No valid predictions to compute confusion matrix.", color="warning")

    tp_pct = tp / total * 100
    fp_pct = fp / total * 100
    tn_pct = tn / total * 100
    fn_pct = fn / total * 100

    text = [
        [f"TN: Correct Down\n{tn} ({tn_pct:.1f}%)", f"FP: False Up\n{fp} ({fp_pct:.1f}%)"],
        [f"FN: Missed Up\n{fn} ({fn_pct:.1f}%)", f"TP: Correct Up\n{tp} ({tp_pct:.1f}%)"],
    ]

    z = [[1, 0], [0, 1]]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=["Predicted Down", "Predicted Up"],
        y=["Actual Down", "Actual Up"],
        text=text,
        texttemplate="%{text}",
        textfont={"size": 15, "color": "white"},
        colorscale=[[0, "#c0392b"], [1, "#27ae60"]],
        showscale=False,
        zmin=0,
        zmax=1,
    ))

    accuracy = (tp + tn) / total * 100

    fig.update_layout(
        template="plotly_dark",
        title=f"{asset_symbol} {interval} Confusion Matrix (Rows = actual, columns = predicted, out-of-sample, n={total}, accuracy={accuracy:.1f}%)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=400,
        margin=dict(l=80, r=40, t=60, b=40),
        xaxis=dict(title="Predicted"),
        yaxis=dict(title="Actual", autorange="reversed"),
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


@app.callback(
    dash.Output("ch-asset-dropdown", "options"),
    dash.Output("ch-asset-dropdown", "value"),
    dash.Input("ch-class-dropdown", "value"),
)
def update_ch_asset_dropdown(asset_class):
    if asset_class == "crypto":
        assets = CRYPTO_ASSETS
        default = "BTC" if "BTC" in assets else (assets[0] if assets else None)
    else:
        assets = STOCK_ASSETS
        default = assets[0] if assets else None
    options = [{"label": a, "value": a} for a in assets]
    return options, default


@app.callback(
    dash.Output("ch-interval-dropdown", "options"),
    dash.Output("ch-interval-dropdown", "value"),
    dash.Input("ch-class-dropdown", "value"),
)
def update_ch_interval_dropdown(asset_class):
    if asset_class == "crypto":
        intervals = PRED_CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = PRED_STOCK_INTERVALS
        default = "1h"
    options = [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals]
    return options, default


def build_confidence_threshold_rows(df, interval, asset_class):
    from backtesting.metrics import compute_metrics
    from backtesting.strategy import run_strategy

    oos = df[df["is_oos"]] if "is_oos" in df.columns else df
    oos = oos[oos["actual_direction"].notna()]
    if oos.empty:
        oos = df[df["actual_direction"].notna()]

    total = len(oos)
    rows = []
    for threshold in (0.50, 0.52, 0.54, 0.56, 0.58):
        selected = oos[oos["confidence"] >= threshold]
        correct = int((selected["prediction"] == selected["actual_direction"]).sum())
        wrong = int(len(selected) - correct)
        accuracy = correct / len(selected) * 100 if len(selected) else 0.0
        coverage = len(selected) / total * 100 if total else 0.0

        trades, equity = run_strategy(
            predictions_df=oos,
            confidence_threshold=threshold,
            return_data=True,
        )
        metrics = compute_metrics(
            trades,
            equity,
            interval=interval,
            asset_class=asset_class,
        )
        rows.append({
            "threshold": threshold,
            "accuracy": accuracy,
            "coverage": coverage,
            "correct": correct,
            "wrong": wrong,
            "trades": metrics["total_trades"],
            "return": metrics["total_return_pct"],
            "drawdown": metrics["max_drawdown_pct"],
        })

    return rows


@app.callback(
    dash.Output("cte-table-container", "children"),
    dash.Input("ch-class-dropdown", "value"),
    dash.Input("ch-asset-dropdown", "value"),
    dash.Input("ch-interval-dropdown", "value"),
)
def build_confidence_threshold_table(asset_class, asset_symbol, interval):
    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        df = run_prediction(asset_symbol, interval, asset_class)
    except FileNotFoundError:
        return dbc.Alert(
            f"No trained model for {asset_symbol} @ {interval}. Train one first.",
            color="warning",
        )

    if df is None or df.empty:
        return dbc.Alert(
            f"No prediction data for {asset_symbol} @ {interval}.",
            color="warning",
        )

    rows = build_confidence_threshold_rows(df, interval, asset_class)
    if not rows:
        return dbc.Alert("No valid predictions with known outcomes.", color="warning")

    table_rows = []
    for row in rows:
        table_rows.append(html.Tr([
            html.Td(f"{row['threshold']:.2f}", className="text-center"),
            html.Td(f"{row['accuracy']:.1f}%", className="text-center"),
            html.Td(f"{row['coverage']:.1f}%", className="text-center"),
            html.Td(str(row["correct"]), className="text-center"),
            html.Td(str(row["wrong"]), className="text-center"),
            html.Td(str(row["trades"]), className="text-center"),
            html.Td(f"{row['return']:+.2f}%", className="text-center"),
            html.Td(f"{row['drawdown']:.2f}%", className="text-center"),
        ]))

    return dbc.Table([
        html.Thead(html.Tr([
            html.Th("Threshold"),
            html.Th("Accuracy"),
            html.Th("Coverage"),
            html.Th("Correct"),
            html.Th("Wrong"),
            html.Th("Trades"),
            html.Th("Return"),
            html.Th("Drawdown"),
        ])),
        html.Tbody(table_rows),
    ], bordered=True, hover=True, size="sm", striped=True, responsive=True)


@app.callback(
    dash.Output("baseline-significance-container", "children"),
    dash.Input("ch-class-dropdown", "value"),
    dash.Input("ch-asset-dropdown", "value"),
    dash.Input("ch-interval-dropdown", "value"),
)
def build_baseline_significance_section(asset_class, asset_symbol, interval):
    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        predictions = run_prediction(asset_symbol, interval, asset_class)
    except FileNotFoundError:
        return dbc.Alert(
            f"No trained model for {asset_symbol} @ {interval}. Train one first.",
            color="warning",
        )

    result = build_baseline_significance(predictions)
    if result["status"] == "missing":
        return dbc.Alert("No known out-of-sample predictions are available.", color="warning")
    if result["status"] == "insufficient":
        return dbc.Alert(
            "At least two paired out-of-sample predictions are required.",
            color="warning",
        )

    model_low, model_high = result["model_interval"]
    baseline_low, baseline_high = result["baseline_interval"]
    difference_low, difference_high = result["difference_interval"]
    significant = (
        result["mcnemar_p_value"] < 0.05
        and (difference_low > 0 or difference_high < 0)
    )
    conclusion = "Statistically significant" if significant else "Not statistically significant"
    conclusion_color = "success" if significant else "warning"
    date_format = "%Y-%m-%d %H:%M UTC"

    summary = pd.DataFrame([
        {
            "Comparison": "XGBoost",
            "Accuracy": f"{result['model_accuracy']:.1%}",
            "95% Confidence Interval": f"{model_low:.1%} to {model_high:.1%}",
        },
        {
            "Comparison": result["baseline_name"],
            "Accuracy": f"{result['baseline_accuracy']:.1%}",
            "95% Confidence Interval": f"{baseline_low:.1%} to {baseline_high:.1%}",
        },
    ])

    return html.Div([
        dbc.Alert(conclusion, color=conclusion_color, className="mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{result['difference']:+.1%}", className="card-title text-info text-center"),
                html.P("Accuracy Difference", className="card-text text-muted small text-center mb-0"),
            ]), color="dark", outline=True), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{difference_low:+.1%} to {difference_high:+.1%}", className="card-title text-info text-center"),
                html.P("95% Bootstrap CI", className="card-text text-muted small text-center mb-0"),
            ]), color="dark", outline=True), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{result['mcnemar_p_value']:.4f}", className="card-title text-info text-center"),
                html.P("McNemar p-value", className="card-text text-muted small text-center mb-0"),
            ]), color="dark", outline=True), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(str(result["sample_size"]), className="card-title text-info text-center"),
                html.P("Paired OOS Rows", className="card-text text-muted small text-center mb-0"),
            ]), color="dark", outline=True), width=3),
        ], className="mb-3"),
        html.P(
            f"Best baseline: {result['baseline_name']} | "
            f"Period: {result['start_date'].strftime(date_format)} to {result['end_date'].strftime(date_format)}",
            className="text-muted small",
        ),
        dbc.Table.from_dataframe(
            summary,
            striped=True,
            bordered=True,
            hover=True,
            color="dark",
            className="mb-0",
        ),
    ])


@app.callback(
    dash.Output("calibration-container", "children"),
    dash.Input("ch-class-dropdown", "value"),
    dash.Input("ch-asset-dropdown", "value"),
    dash.Input("ch-interval-dropdown", "value"),
)
def build_calibration_reliability(asset_class, asset_symbol, interval):

    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        predictions = run_prediction(asset_symbol, interval, asset_class)
    except FileNotFoundError:
        return dbc.Alert(
            f"No trained model for {asset_symbol} @ {interval}. Train one first.",
            color="warning",
        )

    if predictions is None or predictions.empty:
        return dbc.Alert(
            f"No prediction data for {asset_symbol} @ {interval}.",
            color="warning",
        )

    metrics = _calculate_calibration_metrics(predictions)
    calibration_bins = metrics["calibration_bins"]
    if calibration_bins.empty:
        return dbc.Alert("No valid predictions with known outcomes.", color="warning")

    known = predictions[predictions["actual_direction"].notna()]
    if "is_oos" in known.columns:
        oos = known[known["is_oos"]]
        scored = oos if not oos.empty else known
    else:
        scored = known
    confidence = pd.to_numeric(scored["confidence"], errors="coerce")
    correctness = (scored["prediction"].astype(int) == scored["actual_direction"].astype(int)).astype(int)
    valid = confidence.between(0.5, 1.0) & confidence.notna()
    brier_score = float(brier_score_loss(correctness[valid], confidence[valid]))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0.5, 1.0],
        y=[0.5, 1.0],
        mode="lines",
        name="Perfect calibration",
        line=dict(color="#ffffff", dash="dash"),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=calibration_bins["confidence"],
        y=calibration_bins["accuracy"],
        mode="lines+markers",
        name="Model reliability",
        marker=dict(color="#3498db", size=9),
        line=dict(color="#3498db", width=2),
        customdata=calibration_bins["count"],
        hovertemplate=(
            "Average confidence: %{x:.1%}<br>"
            "Actual accuracy: %{y:.1%}<br>"
            "Predictions: %{customdata}<extra></extra>"
        ),
    ))
    fig.update_layout(
        template="plotly_dark",
        title=f"{asset_symbol} {interval} Calibration Curve (out-of-sample, n={int(calibration_bins['count'].sum())})",
        xaxis=dict(title="Predicted Confidence", range=[0.49, 1.01], tickformat=".0%"),
        yaxis=dict(title="Actual Correctness", range=[0.0, 1.01], tickformat=".0%"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=430,
        margin=dict(l=60, r=40, t=60, b=50),
    )

    table_rows = [html.Tr([
        html.Td(f"{row.confidence:.1%}", className="text-center"),
        html.Td(f"{row.accuracy:.1%}", className="text-center"),
        html.Td(str(int(row.count)), className="text-center"),
    ]) for row in calibration_bins.itertuples(index=False)]

    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{brier_score:.3f}", className="card-title text-info text-center"),
                html.P("Brier Score", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics['expected_calibration_error']:.1%}", className="card-title text-info text-center"),
                html.P("Expected Calibration Error", className="card-text text-muted small text-center"),
            ]), color="dark", outline=True), width=3),
        ], className="mb-3"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        dbc.Table([
            html.Thead(html.Tr([
                html.Th("Average Confidence"),
                html.Th("Actual Accuracy"),
                html.Th("Predictions"),
            ])),
            html.Tbody(table_rows),
        ], bordered=True, hover=True, size="sm", striped=True, responsive=True),
    ])


@app.callback(
    dash.Output("ch-chart-container", "children"),
    dash.Input("ch-class-dropdown", "value"),
    dash.Input("ch-asset-dropdown", "value"),
    dash.Input("ch-interval-dropdown", "value"),
)
def build_confidence_histogram(asset_class, asset_symbol, interval):
    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        df = run_prediction(asset_symbol, interval, asset_class)
    except FileNotFoundError:
        return dbc.Alert(
            f"No trained model for {asset_symbol} @ {interval}. Train one first.",
            color="warning",
        )

    if df is None or df.empty:
        return dbc.Alert(
            f"No prediction data for {asset_symbol} @ {interval}.",
            color="warning",
        )

    oos = df[df["is_oos"]] if "is_oos" in df.columns else df
    oos = oos[oos["actual_direction"].notna()]
    if oos.empty:
        oos = df[df["actual_direction"].notna()]

    if oos.empty:
        return dbc.Alert("No valid predictions with known outcomes.", color="warning")

    correct_mask = oos["prediction"] == oos["actual_direction"]
    correct_conf = oos[correct_mask]["confidence"]
    wrong_conf = oos[~correct_mask]["confidence"]

    total = len(oos)
    n_correct = len(correct_conf)
    n_wrong = len(wrong_conf)
    accuracy = n_correct / total * 100 if total else 0

    traces = []
    if not correct_conf.empty:
        traces.append(go.Histogram(
            x=correct_conf,
            name=f"Correct ({n_correct})",
            marker_color="#27ae60",
            opacity=0.6,
            nbinsx=20,
        ))
    if not wrong_conf.empty:
        traces.append(go.Histogram(
            x=wrong_conf,
            name=f"Wrong ({n_wrong})",
            marker_color="#c0392b",
            opacity=0.6,
            nbinsx=20,
        ))

    if not traces:
        return dbc.Alert("No prediction data to display.", color="warning")

    fig = go.Figure(traces)
    fig.update_layout(
        barmode="overlay",
        template="plotly_dark",
        title=f"{asset_symbol} {interval} Prediction Confidence (out-of-sample, n={total}, accuracy={accuracy:.1f}%)",
        xaxis_title="Confidence",
        yaxis_title="Count",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=400,
        margin=dict(l=60, r=40, t=60, b=40),
        bargap=0.05,
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


@app.callback(
    dash.Output("stability-chart-container", "children"),
    dash.Input("ch-class-dropdown", "value"),
    dash.Input("ch-asset-dropdown", "value"),
    dash.Input("ch-interval-dropdown", "value"),
    dash.Input("stability-window-dropdown", "value"),
)
def build_performance_stability(asset_class, asset_symbol, interval, trading_window_days):
    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        predictions = run_prediction(asset_symbol, interval, asset_class)
    except FileNotFoundError:
        return dbc.Alert(
            f"No trained model for {asset_symbol} @ {interval}. Train one first.",
            color="warning",
        )

    stability = calculate_performance_stability(predictions, trading_window_days)
    monthly = stability["monthly_accuracy"]
    quarterly = stability["quarterly_accuracy"]
    rolling_accuracy = stability["rolling_accuracy"]
    rolling_trading = stability["rolling_trading"]
    if monthly.empty and quarterly.empty and rolling_trading.empty:
        return dbc.Alert("No valid out-of-sample data is available for stability analysis.", color="warning")

    accuracy_fig = go.Figure()
    if not monthly.empty:
        accuracy_fig.add_trace(go.Scatter(
            x=monthly["date"],
            y=monthly["accuracy"],
            mode="lines+markers",
            name="Monthly accuracy",
            customdata=monthly["count"],
            hovertemplate="Period end: %{x}<br>Accuracy: %{y:.1%}<br>Predictions: %{customdata}<extra></extra>",
        ))
    if not quarterly.empty:
        accuracy_fig.add_trace(go.Scatter(
            x=quarterly["date"],
            y=quarterly["accuracy"],
            mode="lines+markers",
            name="Quarterly accuracy",
            customdata=quarterly["count"],
            hovertemplate="Period end: %{x}<br>Accuracy: %{y:.1%}<br>Predictions: %{customdata}<extra></extra>",
        ))
    if not rolling_accuracy.empty:
        accuracy_fig.add_trace(go.Scatter(
            x=rolling_accuracy["date"],
            y=rolling_accuracy["accuracy_30d"],
            mode="lines",
            name="Rolling 30-day accuracy",
            line=dict(color="#3498db"),
            hovertemplate="Date: %{x}<br>Accuracy: %{y:.1%}<extra></extra>",
        ))
        accuracy_fig.add_trace(go.Scatter(
            x=rolling_accuracy["date"],
            y=rolling_accuracy["accuracy_90d"],
            mode="lines",
            name="Rolling 90-day accuracy",
            line=dict(color="#f39c12"),
            hovertemplate="Date: %{x}<br>Accuracy: %{y:.1%}<extra></extra>",
        ))
    accuracy_fig.add_hline(y=0.5, line_dash="dash", line_color="#ffffff", annotation_text="50% baseline")
    accuracy_fig.update_layout(
        template="plotly_dark",
        title=f"{asset_symbol} {interval} Classification Stability (out-of-sample)",
        xaxis_title="Date",
        yaxis=dict(title="Accuracy", tickformat=".0%", range=[0, 1]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=430,
        margin=dict(l=60, r=40, t=60, b=50),
    )

    trading_fig = go.Figure()
    if not rolling_trading.empty:
        trading_fig.add_trace(go.Scatter(
            x=rolling_trading["date"],
            y=rolling_trading["rolling_return"],
            mode="lines",
            name=f"Rolling {trading_window_days}-day return",
            line=dict(color="#27ae60"),
            hovertemplate="Date: %{x}<br>Return: %{y:.2f}%<extra></extra>",
        ))
        trading_fig.add_trace(go.Scatter(
            x=rolling_trading["date"],
            y=rolling_trading["rolling_drawdown"],
            mode="lines",
            name=f"Rolling {trading_window_days}-day drawdown",
            line=dict(color="#c0392b"),
            hovertemplate="Date: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>",
        ))
    else:
        trading_fig.add_annotation(
            text=f"Not enough data for a {trading_window_days}-day trading window.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    trading_fig.update_layout(
        template="plotly_dark",
        title=f"{asset_symbol} {interval} Trading Stability ({trading_window_days}-day window)",
        xaxis_title="Date",
        yaxis_title="Percent",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=430,
        margin=dict(l=60, r=40, t=60, b=50),
    )

    return dbc.Row([
        dbc.Col(dcc.Graph(figure=accuracy_fig, config={"displayModeBar": False}), width=6),
        dbc.Col(dcc.Graph(figure=trading_fig, config={"displayModeBar": False}), width=6),
    ])


@app.callback(
    dash.Output("ct-chart-container", "children"),
    dash.Input("ch-class-dropdown", "value"),
    dash.Input("ch-asset-dropdown", "value"),
    dash.Input("ch-interval-dropdown", "value"),
)
def build_confidence_timeline(asset_class, asset_symbol, interval):
    if not asset_symbol or not interval:
        return dbc.Alert("Select an asset and interval.", color="info")

    try:
        df = run_prediction(asset_symbol, interval, asset_class)
    except FileNotFoundError:
        return dbc.Alert(
            f"No trained model for {asset_symbol} @ {interval}. Train one first.",
            color="warning",
        )

    if df is None or df.empty:
        return dbc.Alert(
            f"No prediction data for {asset_symbol} @ {interval}.",
            color="warning",
        )

    oos = df[df["is_oos"]] if "is_oos" in df.columns else df
    oos = oos[oos["actual_direction"].notna()]
    if oos.empty:
        oos = df[df["actual_direction"].notna()]

    if oos.empty:
        return dbc.Alert("No valid predictions with known outcomes.", color="warning")

    correct_mask = oos["prediction"] == oos["actual_direction"]
    correct = oos[correct_mask]
    wrong = oos[~correct_mask]

    total = len(oos)
    n_correct = len(correct)
    accuracy = n_correct / total * 100 if total else 0

    traces = []
    if not correct.empty:
        traces.append(go.Scatter(
            x=correct["date"],
            y=correct["confidence"],
            mode="markers",
            name=f"Correct ({n_correct})",
            marker=dict(color="#27ae60", size=7),
            hovertemplate="Date: %{x}<br>Confidence: %{y:.2f}<br>Correct<extra></extra>",
        ))
    if not wrong.empty:
        traces.append(go.Scatter(
            x=wrong["date"],
            y=wrong["confidence"],
            mode="markers",
            name=f"Wrong ({len(wrong)})",
            marker=dict(color="#c0392b", size=7),
            hovertemplate="Date: %{x}<br>Confidence: %{y:.2f}<br>Wrong<extra></extra>",
        ))

    if not traces:
        return dbc.Alert("No prediction data to display.", color="warning")

    fig = go.Figure(traces)
    fig.add_hline(y=0.5, line_dash="dash", line_color="white",
                  annotation_text="coin flip", annotation_position="top left")
    fig.update_layout(
        template="plotly_dark",
        title=f"{asset_symbol} {interval} Confidence Over Time (out-of-sample, n={total}, accuracy={accuracy:.1f}%)",
        xaxis_title="Date",
        yaxis_title="Confidence",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=400,
        margin=dict(l=60, r=40, t=60, b=40),
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)