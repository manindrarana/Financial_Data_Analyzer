"""
Financial Data Analyzer — Plotly Dash Dashboard
Multi-tab web UI reading directly from DuckDB gold tables.
"""

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    """BTC/USDT candlestick chart + volume bars from gold_crypto_analytics."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        df = conn.execute("""
            SELECT date, open, high, low, close, volume
            FROM gold_crypto_analytics
            WHERE asset_symbol = 'BTC' AND interval = '1h'
            ORDER BY date
        """).df()
        conn.close()

        if df.empty:
            return dbc.Alert("No data found in gold_crypto_analytics for BTC 1h.", color="warning")

        df["date"] = pd.to_datetime(df["date"])

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=("BTC/USDT — 1H Candlesticks", "Volume"),
        )

        fig.add_trace(
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="BTC/USDT",
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
            height=700,
            hovermode="x unified",
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_rangeslider_visible=False,
        )
        fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

        return dbc.Row(
            dbc.Col(
                [
                    html.H3(" BTC/USDT — Price History", className="text-light mb-3"),
                    dcc.Graph(figure=fig, config={"displayModeBar": True, "responsive": True}),
                ],
                width=12,
            )
        )
    except Exception as e:
        return dbc.Alert(f"Error loading price dashboard: {e}", color="danger")

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
    
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)