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