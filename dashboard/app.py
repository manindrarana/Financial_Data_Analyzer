"""
Financial Data Analyzer — Plotly Dash Dashboard
Multi-tab web UI reading directly from DuckDB gold tables.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
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
from dashboard.predictor import run_prediction
import diskcache

load_dotenv()
DB_PATH = os.path.join("database", "financial_data.duckdb")

_cache = diskcache.Cache(os.path.join(os.path.dirname(__file__), "..", ".dash_cache"))

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
            .DateInput_input, .DateInput_input:focus, .DateInput_input:hover {
                color: #fff !important;
                background-color: #222 !important;
                border-color: #444 !important;
            }
            .DateInput_displayText, .DateInput_displayText:focus {
                color: #ccc !important;
            }
            .CalendarDay__default {
                color: #ccc !important;
            }
            .CalendarDay__default:hover {
                color: #000 !important;
            }
            .DateRangePickerInput {
                background-color: #222 !important;
                border-color: #444 !important;
            }
            .DateRangePickerInput_arrow {
                fill: #ccc !important;
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
            active_tab="tab-price",
            children=[
                dbc.Tab(label=" Price Dashboard", tab_id="tab-price"),
                dbc.Tab(label=" Predictions", tab_id="tab-predictions"),
                dbc.Tab(label=" Backtest", tab_id="tab-backtest"),
                dbc.Tab(label=" Technical Indicators", tab_id="tab-indicators"),
                dbc.Tab(label=" Data Explorer", tab_id="tab-explorer"),
            ],
        ),
        html.Hr(),
        dbc.Checklist(
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
        html.Div(
            id="price-chart-area",
            children=[
                html.H3("Price Dashboard", className="text-light mb-3"),
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
    if active_tab == "tab-price":
        return render_price_dashboard()
    elif active_tab == "tab-predictions":
        return render_predictions()
    elif active_tab == "tab-backtest":
        return render_backtest()
    elif active_tab == "tab-indicators":
        return render_indicators()
    elif active_tab == "tab-explorer":
        return render_explorer()
    return html.P("Select a tab.", className="text-muted")


@app.callback(
    dash.Output("price-chart-area", "style"),
    dash.Input("main-tabs", "active_tab"),
)
def toggle_price_chart_area(active_tab):
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
                    html.H3("XGBoost Direction Predictions", className="text-light mb-3"),
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
                html.H3("Walk-Forward Backtest", className="text-light mb-3"),
                dbc.Row(
                    [
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
                                html.Label("Confidence", className="text-muted small mb-1"),
                                dbc.Input(id="bt-confidence", type="number", min=0.5, max=0.95, step=0.01, value=0.52, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Stop Loss %", className="text-muted small mb-1"),
                                dbc.Input(id="bt-stop-loss", type="number", min=0.5, max=10, step=0.5, value=2.0, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Take Profit %", className="text-muted small mb-1"),
                                dbc.Input(id="bt-take-profit", type="number", min=1, max=20, step=0.5, value=4.0, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Max Hold Bars", className="text-muted small mb-1"),
                                dbc.Input(id="bt-max-hold", type="number", min=4, max=200, step=1, value=24, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Initial Capital", className="text-muted small mb-1"),
                                dbc.Input(id="bt-capital", type="number", min=1000, max=1000000, step=1000, value=10000, style={"color": "#000"}),
                            ],
                            width=2,
                        ),
                        dbc.Col(
                            [
                                html.Label("Train Months", className="text-muted small mb-1"),
                                dbc.Input(id="bt-train-months", type="number", min=3, max=24, step=1, value=6, style={"color": "#000"}),
                            ],
                            width=1,
                        ),
                        dbc.Col(
                            [
                                html.Label("Test Months", className="text-muted small mb-1"),
                                dbc.Input(id="bt-test-months", type="number", min=1, max=6, step=1, value=1, style={"color": "#000"}),
                            ],
                            width=1,
                        ),
                        dbc.Col(
                            [
                                html.Label("Step Months", className="text-muted small mb-1"),
                                dbc.Input(id="bt-step-months", type="number", min=1, max=6, step=1, value=1, style={"color": "#000"}),
                            ],
                            width=1,
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


def _build_backtest_results(metrics, equity_df, trades_df):
    """Build Dash UI components from backtest results."""
    if trades_df.empty:
        return dbc.Alert("No trades executed — try relaxing the confidence threshold or date range.", color="warning")

    metric_cards = dbc.Row(
        [
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('total_return_pct', 0):+.2f}%", className="card-title text-info"),
                html.P("Total Return", className="card-text text-muted small"),
            ]), color="dark", outline=True), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5(f"{metrics.get('sharpe_ratio', 0):.2f}", className="card-title text-info"),
                html.P("Sharpe Ratio", className="card-text text-muted small"),
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
    fig_equity.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=400, title="Equity Curve", hovermode="x unified",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig_equity.update_yaxes(title_text="Equity ($)")

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

    return html.Div([
        metric_cards,
        exit_html,
        dbc.Row(dbc.Col(dcc.Graph(figure=fig_equity, config={"displayModeBar": True, "responsive": True}), width=12)),
        dbc.Row(dbc.Col(dcc.Graph(figure=fig_trades, config={"displayModeBar": True, "responsive": True}), width=12)),
        html.H6("Per-Fold Breakdown", className="text-light mt-3") if fold_table else None,
        fold_table,
    ])


@app.callback(
    dash.Output("bt-results", "children"),
    dash.Input("bt-run-btn", "n_clicks"),
    dash.State("bt-class-dropdown", "value"),
    dash.State("bt-asset-dropdown", "value"),
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
    background=True,
    running=[(dash.Output("bt-run-btn", "disabled"), True, False)],
    progress=[dash.Output("bt-progress-bar", "children")],
    prevent_initial_call=True,
)
def run_backtest_pipeline(set_progress, n_clicks, asset_class, asset, interval,
                           date_start, date_end, confidence, stop_loss, take_profit,
                           max_hold, capital, train_months, test_months, step_months):
    """Background callback: runs the full walk-forward → strategy → metrics pipeline."""
    if not n_clicks or not asset:
        raise dash.exceptions.PreventUpdate

    try:
        set_progress(dbc.Alert("Loading data & training walk-forward model...", color="info"))

        if asset_class == "stocks":
            set_progress(dbc.Alert("Stock backtesting not yet supported. Please select Crypto.", color="warning"))
            return html.Div()

        from backtesting.walk_forward import run_walk_forward
        from backtesting.strategy import run_strategy
        from backtesting.metrics import run_metrics

        predictions_df, _summary = run_walk_forward(
            asset=asset,
            interval=interval,
            train_months=int(train_months),
            test_months=int(test_months),
            step_months=int(step_months),
            date_start=date_start if date_start else None,
            date_end=date_end if date_end else None,
            return_data=True,
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
        )

        set_progress(dbc.Alert("Computing metrics...", color="info"))
        metrics = run_metrics(
            trades_df=trades_df,
            equity_df=equity_df,
            initial_capital=float(capital),
            return_data=True,
        )

        set_progress(dbc.Alert("Rendering results...", color="success"))
        return _build_backtest_results(metrics, equity_df, trades_df)

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
)
def _update_bt_interval_dropdown(asset_class):
    if asset_class == "crypto":
        intervals = CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = STOCK_INTERVALS
        default = "1h"
    return [{"label": INTERVAL_LABELS.get(iv, iv), "value": iv} for iv in intervals], default


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
                    html.H3("Technical Indicators", className="text-light mb-3"),
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
        {"label": "Crypto Predictions (gold_crypto_predictions)", "value": "gold_crypto_predictions"},
        {"label": "Stock Analytics (gold_stock_analytics)", "value": "gold_stock_analytics"},
        {"label": "Stock Features (gold_stock_features)", "value": "gold_stock_features"},
    ]
    return html.Div([
        html.H3("Data Explorer", className="text-light mb-3"),
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
                width=6,
            ),
            dbc.Col(html.Div(id="explorer-row-count", className="text-muted mt-2"), width=6),
        ]),
        dbc.Row(dbc.Col(html.Div(id="explorer-table-container"), width=12)),
    ])

@app.callback(
    dash.Output("explorer-table-container", "children"),
    dash.Output("explorer-row-count", "children"),
    dash.Input("explorer-table-selector", "value"),
)
def update_explorer_table(table_name):
    """Query the selected gold table and render a sortable DataTable."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        df = conn.execute(f"SELECT * FROM {table_name} ORDER BY date DESC LIMIT 5000").df()
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
    
PRICE_RANGE_MAP = {
    "1d": 1, "3d": 3, "7d": 7, "30d": 30,
    "90d": 90, "180d": 180, "365d": 365,
}

MAX_CANDLES_DISPLAY = 2000

CRYPTO_INTERVALS = ["1h", "4h", "1d", "W", "M"]
STOCK_INTERVALS  = ["1h", "1d", "1wk", "1mo"]

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
            v = pt.get("hovertext") or None
        if hovered_x is None and pt.get("x"):
            hovered_x = pt["x"]
    parts = []
    if o is not None:
        vol_txt = f"  V: {v:,.0f}" if v is not None else ""
        parts.append(f"O: {o:.4f}  H: {h:.4f}  L: {l:.4f}  C: {c:.4f}{vol_txt}")
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
                parts.append(f"{name}: {val:.4f}")
    return "  |  ".join(parts) if parts else ""


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
        intervals = CRYPTO_INTERVALS
        default = "1h"
    else:
        intervals = STOCK_INTERVALS
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
        oos = results[results["is_oos"]]
        oos_total = len(oos)
    else:
        oos = results
        oos_total = len(oos)

    total = len(results)
    correct = (results["prediction"] == results["actual_direction"]).sum()
    accuracy = correct / total if total > 0 else 0

    oos_correct = (oos["prediction"] == oos["actual_direction"]).sum()
    oos_accuracy = oos_correct / oos_total if oos_total > 0 else 0

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
                width=12,
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
            title={"text": "OOS Accuracy", "font": {"size": 14}},
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

    interval_label = INTERVAL_LABELS.get(interval, interval)
    range_label = f" ({range_value})" if range_value and range_value != "all" else " (all time)"
    title = f"{asset_symbol}/USDT {interval_label}{range_label} -- XGBoost Direction Predictions"

    return html.Div([
        html.H3(title, className="text-light mb-3"),
        summary_cards,
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

    WEST = timezone(timedelta(hours=1))
    label = latest.astimezone(WEST).strftime("%Y-%m-%d %H:%M WEST")
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)