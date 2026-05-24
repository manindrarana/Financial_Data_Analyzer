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