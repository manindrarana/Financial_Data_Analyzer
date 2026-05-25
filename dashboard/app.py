"""
Financial Data Analyzer — Plotly Dash Dashboard
Multi-tab web UI reading directly from DuckDB gold tables.
"""

import os
import sys
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from dashboard.predictor import run_prediction

load_dotenv()
DB_PATH = os.path.join("database", "financial_data.duckdb")

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="Financial Data Analyzer",
)

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
        dbc.Tabs(
            id="main-tabs",
            active_tab="tab-price",
            children=[
                dbc.Tab(label=" Price Dashboard", tab_id="tab-price"),
                dbc.Tab(label=" Predictions", tab_id="tab-predictions"),
                dbc.Tab(label=" Technical Indicators", tab_id="tab-indicators"),
                dbc.Tab(label=" Data Explorer", tab_id="tab-explorer"),
            ],
        ),
        html.Hr(),
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
    elif active_tab == "tab-indicators":
        return render_indicators()
    elif active_tab == "tab-explorer":
        return render_explorer()
    return html.P("Select a tab.", className="text-muted")

def render_price_dashboard():
    """Multi-asset candlestick chart with asset class, asset, interval, and time-range selectors."""
    try:
        range_options = [
            {"label": "1 Day", "value": "1d"},
            {"label": "3 Days", "value": "3d"},
            {"label": "1 Week", "value": "7d"},
            {"label": "1 Month", "value": "30d"},
            {"label": "3 Months", "value": "90d"},
            {"label": "6 Months", "value": "180d"},
            {"label": "1 Year", "value": "365d"},
            {"label": "All Data", "value": "all"},
        ]

        return dbc.Row(
            dbc.Col(
                [
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
                                        options=range_options,
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
                    dcc.Loading(
                        id="loading-price",
                        type="circle",
                        children=dcc.Graph(
                            id="price-chart",
                            config={"displayModeBar": True, "responsive": True},
                        ),
                    ),
                ],
                width=12,
            )
        )
    except Exception as e:
        return dbc.Alert(f"Error: {e}", color="danger")

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
    dash.Input("price-class-dropdown", "value"),
    dash.Input("price-asset-dropdown", "value"),
    dash.Input("price-interval-dropdown", "value"),
    dash.Input("price-range-dropdown", "value"),
)
def build_price_chart(asset_class, asset_symbol, interval, range_value):
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

    symbol_label = f"{asset_symbol}/USDT" if asset_class == "crypto" else asset_symbol
    interval_label = INTERVAL_LABELS.get(interval, interval)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.78, 0.22],
        subplot_titles=(
            f"{symbol_label} · {interval_label}",
            "Volume",
        ),
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
        ),
        row=1, col=1,
    )

    colors = ["#26a69a" if c >= o else "#ef5350" for o, c in zip(df["open"], df["close"])]
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["volume"],
            name="Volume",
            marker_color=colors,
            opacity=0.6,
        ),
        row=2, col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=800,
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=15, r=15, t=45, b=10),
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
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
    )
    fig.update_yaxes(
        title_text="Volume", row=2, col=1,
        showgrid=True, gridcolor="rgba(255,255,255,0.04)",
    )

    return fig


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
        results = run_prediction(asset=asset_symbol, interval=interval)
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

    total = len(results)
    correct = (results["prediction"] == results["actual_direction"]).sum()
    accuracy = correct / total if total > 0 else 0
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

    summary_cards = dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5(f"{total:,}", className="card-title text-info"),
                        html.P("Total Predictions", className="card-text text-muted small"),
                    ]),
                    color="dark", outline=True,
                ),
                width=3,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5(f"{accuracy:.1%}", className="card-title text-info"),
                        html.P("Accuracy (52.6% baseline)", className="card-text text-muted small"),
                    ]),
                    color="dark", outline=True,
                ),
                width=3,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5(f"{up_pred_pct:.1f}%", className="card-title text-info"),
                        html.P("UP Predictions", className="card-text text-muted small"),
                    ]),
                    color="dark", outline=True,
                ),
                width=3,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5(f"{correct:,}", className="card-title text-info"),
                        html.P("Correct Predictions", className="card-text text-muted small"),
                    ]),
                    color="dark", outline=True,
                ),
                width=3,
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

    correct_mask = marker_data["prediction"] == marker_data["actual_direction"]
    wrong_mask = ~correct_mask

    for mask, color, label in [
        (correct_mask, "#26a69a", "Correct"),
        (wrong_mask, "#ef5350", "Wrong"),
    ]:
        subset = marker_data[mask]
        if not subset.empty:
            fig_overlay.add_trace(
                go.Scatter(
                    x=subset["date"], y=subset["close"],
                    mode="markers", name=label,
                    marker=dict(color=color, size=5, symbol="circle"),
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
            value=accuracy * 100,
            number={"suffix": "%", "font": {"size": 48, "color": "#17a2b8"}},
            title={"text": "Model Accuracy", "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#adb5bd"},
                "bar": {"color": "#26a69a" if accuracy >= 0.5 else "#ef5350"},
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)