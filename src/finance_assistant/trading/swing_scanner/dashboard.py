"""
dashboard.py — Plotly Dash visualization dashboard.

Displays:
  - Regime banner (market context)
  - Ranked watchlist table (clickable rows)
  - Score radar chart (component breakdown for selected ticker)
  - Candlestick chart (price + MAs + entry/stop/target levels)
  - Volume subplot

Run: python run.py --mode dashboard
Then open: http://127.0.0.1:8050
"""

import logging
import os
import pickle

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── Try importing Dash. Fail gracefully if not installed ─────────────────────
try:
    import dash
    from dash import dcc, html, dash_table, Input, Output, State, callback
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False
    logger.warning("Dash not installed. Run: pip install dash plotly")


# ─── Color palette ────────────────────────────────────────────────────────────
COLORS = {
    "bg":          "#0d1117",
    "card":        "#161b22",
    "border":      "#30363d",
    "text":        "#e6edf3",
    "muted":       "#8b949e",
    "bull":        "#3fb950",
    "bear":        "#f85149",
    "neutral":     "#d29922",
    "accent":      "#58a6ff",
    "entry_line":  "#3fb950",
    "stop_line":   "#f85149",
    "target_line": "#58a6ff",
    "sma20":       "#58a6ff",
    "sma50":       "#d29922",
    "ema20":       "#3fb950",
}

REGIME_COLOR = {
    "bull":    COLORS["bull"],
    "neutral": COLORS["neutral"],
    "bear":    COLORS["bear"],
}


# ─── Chart builders ───────────────────────────────────────────────────────────

def build_candlestick(df: pd.DataFrame, inds: dict, risk: dict, ticker: str, score: float) -> go.Figure:
    """
    Build a candlestick chart with MA overlays and trade level annotations.

    Args:
        df:     OHLCV DataFrame (last 100 bars used)
        inds:   indicators dict from calc_all()
        risk:   risk dict (entry, stop, target)
        ticker: ticker string for title
        score:  composite score for subtitle
    """
    df_plot = df.iloc[-100:]

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.75, 0.25],
        shared_xaxes=True,
        vertical_spacing=0.03,
    )

    # ── Candlestick ──────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df_plot.index,
        open=df_plot["open"],
        high=df_plot["high"],
        low=df_plot["low"],
        close=df_plot["close"],
        name="Price",
        increasing_line_color=COLORS["bull"],
        decreasing_line_color=COLORS["bear"],
        increasing_fillcolor=COLORS["bull"],
        decreasing_fillcolor=COLORS["bear"],
    ), row=1, col=1)

    # ── Moving averages ───────────────────────────────────────────────────────
    x_axis = df_plot.index

    for series, color, name, dash in [
        (inds["sma20"].iloc[-100:], COLORS["sma20"],  "SMA20", "solid"),
        (inds["sma50"].iloc[-100:], COLORS["sma50"],  "SMA50", "solid"),
        (inds["ema20"].iloc[-100:], COLORS["ema20"],  "EMA20", "dash"),
    ]:
        fig.add_trace(go.Scatter(
            x=x_axis, y=series,
            name=name,
            line=dict(color=color, width=1.5, dash=dash),
            opacity=0.9,
        ), row=1, col=1)

    # ── Trade levels (horizontal lines) ──────────────────────────────────────
    if risk and risk.get("valid", False):
        for val, color, label in [
            (risk["entry"],  COLORS["entry_line"],  f"Entry ${risk['entry']:.2f}"),
            (risk["stop"],   COLORS["stop_line"],   f"Stop ${risk['stop']:.2f}"),
            (risk["target"], COLORS["target_line"], f"Target ${risk['target']:.2f}"),
        ]:
            fig.add_hline(
                y=val, row=1, col=1,
                line_color=color,
                line_width=1.5,
                line_dash="dot",
                annotation_text=label,
                annotation_position="right",
                annotation_font_color=color,
                annotation_font_size=11,
            )

    # ── Volume bars ───────────────────────────────────────────────────────────
    vol_colors = [
        COLORS["bull"] if c >= o else COLORS["bear"]
        for c, o in zip(df_plot["close"], df_plot["open"])
    ]
    fig.add_trace(go.Bar(
        x=df_plot.index,
        y=df_plot["volume"],
        name="Volume",
        marker_color=vol_colors,
        opacity=0.7,
    ), row=2, col=1)

    # ── Layout ───────────────────────────────────────────────────────────────
    pattern_label = ""
    if risk:
        pattern_label = f" [{risk.get('pattern', '').upper()}]"

    fig.update_layout(
        title=dict(
            text=f"<b>{ticker}</b>  Score: {score:.0f}{pattern_label}",
            font=dict(color=COLORS["text"], size=16),
        ),
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["card"],
        font=dict(color=COLORS["text"]),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        margin=dict(l=10, r=80, t=50, b=10),
        height=500,
    )
    fig.update_xaxes(
        gridcolor=COLORS["border"],
        showgrid=True,
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor=COLORS["border"],
        showgrid=True,
        zeroline=False,
    )

    return fig


def build_radar_chart(row: dict) -> go.Figure:
    """
    Build a radar (spider) chart of the 8 scoring components.

    Args:
        row: dict containing c_trend, c_rsi, c_atr, c_rvol, c_rs,
             c_pattern, c_obv, c_rr, and score
    """
    categories = ["Trend", "RSI", "ATR Fit", "Rel Vol", "RS", "Pattern", "OBV", "R:R"]
    keys       = ["c_trend", "c_rsi", "c_atr", "c_rvol", "c_rs", "c_pattern", "c_obv", "c_rr"]
    values     = [float(row.get(k, 0.0)) for k in keys]
    values_closed = values + [values[0]]   # close the polygon
    cats_closed   = categories + [categories[0]]

    # Color based on overall score
    score = float(row.get("score", 0.0))
    if score >= 60:
        fill_color = "rgba(63, 185, 80, 0.2)"
        line_color = COLORS["bull"]
    elif score >= 45:
        fill_color = "rgba(210, 153, 34, 0.2)"
        line_color = COLORS["neutral"]
    else:
        fill_color = "rgba(248, 81, 73, 0.15)"
        line_color = COLORS["bear"]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=cats_closed,
        fill="toself",
        fillcolor=fill_color,
        line=dict(color=line_color, width=2),
        name=row.get("ticker", ""),
        hovertemplate="%{theta}: %{r:.2f}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=COLORS["card"],
            radialaxis=dict(
                range=[0, 1],
                showticklabels=False,
                gridcolor=COLORS["border"],
            ),
            angularaxis=dict(
                gridcolor=COLORS["border"],
                tickfont=dict(color=COLORS["text"], size=11),
            ),
        ),
        paper_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"]),
        showlegend=False,
        margin=dict(l=30, r=30, t=30, b=30),
        height=300,
    )
    return fig


# ─── Dash App Builder ─────────────────────────────────────────────────────────

def build_app(cfg: dict, results_csv: str = "swing_results.csv", data_store: dict = None):
    """
    Build and return the Dash app.

    Args:
        cfg:         CONFIG dict
        results_csv: path to the CSV produced by run_scanner
        data_store:  optional dict of {ticker: DataFrame} for chart data.
                     If None, charts will be empty.
    """
    if not DASH_AVAILABLE:
        raise ImportError("Install dash and plotly: pip install dash plotly")

    # ── Load results data ─────────────────────────────────────────────────────
    try:
        df_results = pd.read_csv(results_csv, index_col=0)
        df_results = df_results.fillna(0)
    except FileNotFoundError:
        logger.warning(f"Results file not found: {results_csv}. Run the scanner first.")
        df_results = pd.DataFrame(columns=["ticker", "score"])

    # ── Regime info from first row (store regime in CSV or pass separately) ───
    regime_trend   = "unknown"
    regime_color   = COLORS["muted"]

    # ── Prepare table columns ─────────────────────────────────────────────────
    table_cols = ["ticker", "score", "price", "pattern", "rsi",
                  "atr_pct", "rvol", "rr", "entry", "stop", "target"]
    table_cols = [c for c in table_cols if c in df_results.columns]

    col_defs = [
        {"name": c.replace("_", " ").upper(), "id": c,
         "type": "numeric" if c not in ("ticker", "pattern") else "text",
         "format": {"specifier": ".2f"} if c not in ("ticker", "pattern") else None}
        for c in table_cols
    ]

    # ── App layout ────────────────────────────────────────────────────────────
    app = dash.Dash(
        __name__,
        title="Swing Scanner",
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )

    app.layout = html.Div(style={"backgroundColor": COLORS["bg"], "minHeight": "100vh", "padding": "16px"}, children=[

        # Title bar
        html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}, children=[
            html.H2("⚡ Swing Scanner", style={"color": COLORS["accent"], "margin": 0, "marginRight": "24px"}),
            html.Div(id="regime-banner", style={
                "padding": "6px 16px", "borderRadius": "6px",
                "fontSize": "14px", "fontWeight": "bold",
                "backgroundColor": COLORS["card"], "color": COLORS["muted"],
            }, children="Run scanner to load regime"),
            html.Div(style={"marginLeft": "auto"}, children=[
                html.Button("↻ Refresh Data", id="refresh-btn", n_clicks=0, style={
                    "backgroundColor": COLORS["accent"], "color": "#000",
                    "border": "none", "borderRadius": "6px",
                    "padding": "8px 16px", "cursor": "pointer", "fontWeight": "bold",
                }),
            ]),
        ]),

        # Pattern filter + score slider
        html.Div(style={"display": "flex", "gap": "24px", "marginBottom": "12px",
                        "alignItems": "center", "color": COLORS["muted"], "fontSize": "13px"}, children=[
            html.Label("Pattern:"),
            dcc.Dropdown(
                id="pattern-filter",
                options=[
                    {"label": "All",       "value": "all"},
                    {"label": "Breakout",  "value": "breakout"},
                    {"label": "Pullback",  "value": "pullback"},
                    {"label": "Squeeze",   "value": "squeeze"},
                ],
                value="all",
                clearable=False,
                style={"width": "160px", "backgroundColor": COLORS["card"], "color": COLORS["text"]},
            ),
            html.Label("Min Score:"),
            dcc.Slider(
                id="score-slider",
                min=0, max=100, step=5,
                value=int(cfg.get("min_score_display", 40)),
                marks={i: str(i) for i in range(0, 101, 20)},
                tooltip={"placement": "bottom"},
            ),
        ]),

        # Main two-column layout
        html.Div(style={"display": "flex", "gap": "16px"}, children=[

            # Left: watchlist table
            html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                html.Div("RANKED WATCHLIST", style={
                    "color": COLORS["muted"], "fontSize": "11px",
                    "letterSpacing": "1px", "marginBottom": "8px",
                }),
                dash_table.DataTable(
                    id="watchlist-table",
                    columns=col_defs,
                    data=df_results[table_cols].head(50).to_dict("records"),
                    row_selectable="single",
                    selected_rows=[0],
                    sort_action="native",
                    filter_action="native",
                    page_size=20,
                    style_table={"overflowX": "auto"},
                    style_cell={
                        "backgroundColor": COLORS["card"],
                        "color": COLORS["text"],
                        "border": f"1px solid {COLORS['border']}",
                        "padding": "8px 12px",
                        "fontSize": "13px",
                        "fontFamily": "monospace",
                        "textAlign": "right",
                    },
                    style_header={
                        "backgroundColor": COLORS["bg"],
                        "color": COLORS["muted"],
                        "fontWeight": "bold",
                        "fontSize": "11px",
                        "letterSpacing": "0.5px",
                        "border": f"1px solid {COLORS['border']}",
                        "textAlign": "right",
                    },
                    style_data_conditional=[
                        {"if": {"row_index": "odd"},  "backgroundColor": "#1c2128"},
                        {"if": {"state": "selected"},  "backgroundColor": "#1f3d5c", "border": f"1px solid {COLORS['accent']}"},
                        {"if": {"filter_query": '{pattern} = "breakout"'},  "color": COLORS["bull"]},
                        {"if": {"filter_query": '{pattern} = "pullback"'},  "color": COLORS["accent"]},
                        {"if": {"filter_query": '{pattern} = "squeeze"'},   "color": COLORS["neutral"]},
                        {"if": {"filter_query": '{score} >= 60'},           "fontWeight": "bold"},
                    ],
                    style_cell_conditional=[
                        {"if": {"column_id": "ticker"}, "textAlign": "left", "fontWeight": "bold"},
                        {"if": {"column_id": "pattern"}, "textAlign": "center"},
                    ],
                ),
            ]),

            # Right: charts
            html.Div(style={"flex": "1.3", "minWidth": "0"}, children=[
                dcc.Graph(id="radar-chart",        config={"displayModeBar": False}),
                dcc.Graph(id="candlestick-chart",  config={"displayModeBar": False}),
            ]),
        ]),

        # Hidden state
        dcc.Store(id="selected-ticker", data=None),
    ])

    # ─── Callbacks ────────────────────────────────────────────────────────────

    @app.callback(
        Output("watchlist-table", "data"),
        Input("pattern-filter",   "value"),
        Input("score-slider",     "value"),
    )
    def filter_table(pattern_filter, min_score):
        df = df_results.copy()
        if pattern_filter != "all" and "pattern" in df.columns:
            df = df[df["pattern"] == pattern_filter]
        if "score" in df.columns:
            df = df[df["score"] >= min_score]
        return df[table_cols].head(50).to_dict("records")

    @app.callback(
        Output("radar-chart",       "figure"),
        Output("candlestick-chart", "figure"),
        Input("watchlist-table",    "selected_rows"),
        Input("watchlist-table",    "data"),
    )
    def update_charts(selected_rows, table_data):
        if not selected_rows or not table_data:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                paper_bgcolor=COLORS["bg"],
                plot_bgcolor=COLORS["card"],
                font=dict(color=COLORS["muted"]),
                annotations=[dict(text="Select a ticker from the table", showarrow=False,
                                  font=dict(color=COLORS["muted"], size=14))],
            )
            return empty_fig, empty_fig

        idx    = selected_rows[0]
        row    = table_data[idx]
        ticker = row.get("ticker", "")

        # Find full row in df_results for component scores
        full_rows = df_results[df_results["ticker"] == ticker]
        full_row  = full_rows.iloc[0].to_dict() if not full_rows.empty else row

        # Radar chart — always possible
        radar_fig = build_radar_chart(full_row)

        # Candlestick — needs OHLCV data
        if data_store and ticker in data_store:
            df_ticker = data_store[ticker]
            # We need indicators too — recompute lazily here
            try:
                from indicators import calc_all
                from config import CONFIG as _cfg
                inds = calc_all(df_ticker, _cfg)
                # Reconstruct minimal risk dict from the table row
                risk_dict = {
                    "valid":   True,
                    "entry":   row.get("entry", 0),
                    "stop":    row.get("stop", 0),
                    "target":  row.get("target", 0),
                    "pattern": row.get("pattern", "none"),
                }
                candle_fig = build_candlestick(df_ticker, inds, risk_dict, ticker, full_row.get("score", 0))
            except Exception as e:
                logger.warning(f"Chart error for {ticker}: {e}")
                candle_fig = _empty_chart(f"Chart error for {ticker}: {e}")
        else:
            candle_fig = _empty_chart(
                f"{ticker} — no OHLCV data.\nPass data_store to build_app() for charts."
            )

        return radar_fig, candle_fig

    return app


def _empty_chart(msg: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["card"],
        font=dict(color=COLORS["muted"]),
        annotations=[dict(text=msg, showarrow=False,
                          font=dict(color=COLORS["muted"], size=13),
                          xref="paper", yref="paper", x=0.5, y=0.5)],
        height=400,
    )
    return fig
