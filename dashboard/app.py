"""
Financial Data Analyzer — Plotly Dash Dashboard
Multi-tab web UI reading directly from DuckDB gold tables.
"""

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import duckdb
import os
from dotenv import load_dotenv

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
    return dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.H3("BTC/USDT — Price History", className="text-light"),
                    html.P("Candlestick chart and volume bars.", className="text-muted"),
                ]
            ),
            width=12,
        )
    )

def render_predictions():
    return dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.H3("Model Predictions — Actual vs Predicted", className="text-light"),
                    html.P("Accuracy gauge, confusion matrix, and prediction overlay charts.", className="text-muted"),
                ]
            ),
            width=12,
        )
    )

def render_indicators():
    return dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.H3("Technical Indicators", className="text-light"),
                    html.P("RSI, MACD, Bollinger Bands, and SMA crossovers.", className="text-muted"),
                ]
            ),
            width=12,
        )
    )

def render_explorer():
    return dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.H3("Data Explorer", className="text-light"),
                    html.P("Sortable tables from gold_crypto_analytics, gold_crypto_features, gold_crypto_predictions, and gold_stock_analytics.", className="text-muted"),
                ]
            ),
            width=12,
        )
    )