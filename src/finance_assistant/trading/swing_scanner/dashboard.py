"""
dashboard.py — Live watchlist dashboard.

Architecture:
  - Dash handles the app shell: table, controls, callbacks, layout
  - TradingView Lightweight Charts renders the candlestick panel
    (via an embedded HTML component — looks and feels like TradingView)
  - Plotly renders RSI, ADX, and the radar score chart (these are fine in Plotly)

Panels:
  Left   — Regime banner + scored watchlist table (sortable, filterable)
  Right  — TradingView-style candlestick chart with:
              SMA20 / SMA50 / EMA20 overlaid as line series
              Entry / Stop / Target as horizontal price lines
              Fibonacci levels as additional price lines
              Volume histogram below the main chart
  Bottom right — RSI panel (Plotly) + ADX panel (Plotly)
  Far right     — Score radar chart for selected ticker

Usage:
    python run.py --mode dashboard
    Open: http://127.0.0.1:8050
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import dash
    from dash import dcc, html, dash_table, Input, Output, State
    import plotly.graph_objects as go
    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False
    logger.warning("pip install dash plotly")

# ── Colors (shared with order_logger.py dark theme) ───────────────────────────
C = {
    "bg":      "#0d1117",
    "panel":   "#161b22",
    "border":  "#30363d",
    "text":    "#e6edf3",
    "muted":   "#8b949e",
    "bull":    "#26a69a",
    "bear":    "#ef5350",
    "sma20":   "#2196f3",
    "sma50":   "#ff9800",
    "ema20":   "#4caf50",
    "entry":   "#26a69a",
    "stop":    "#ef5350",
    "target":  "#2196f3",
    "fib":     "#ffd700",
    "accent":  "#58a6ff",
    "rsi":     "#e040fb",
    "adx":     "#40c4ff",
}

REGIME_COLOR = {"bull": C["bull"], "neutral": "#ff9800", "bear": C["bear"]}

# ── Lightweight Charts CDN ─────────────────────────────────────────────────────
LWC_CDN = "https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"


# ═══════════════════════════════════════════════════════════════════════════════
# LIGHTWEIGHT CHARTS HTML COMPONENT
# ═══════════════════════════════════════════════════════════════════════════════

def build_lwc_html(
    df: pd.DataFrame,
    inds: dict,
    trade_levels: dict,
    title: str = "",
) -> str:
    """
    Generate a self-contained HTML string that renders a TradingView
    Lightweight Charts candlestick chart with overlays.

    Args:
        df:           OHLCV DataFrame (index = datetime)
        inds:         dict with keys sma20, sma50, ema20 (pd.Series)
        trade_levels: dict with keys entry, stop, target, swing_low, swing_high
        title:        chart title string

    Returns:
        HTML string — embedded in an <iframe> inside Dash.
    """
    if df.empty:
        return "<html><body style='background:#0d1117;color:#8b949e;font-family:monospace;padding:20px'>No data</body></html>"

    # Build OHLCV data as JS-friendly list
    ohlcv = []
    for idx, row in df.iterrows():
        try:
            ts = int(pd.Timestamp(idx).timestamp())
        except Exception:
            continue
        ohlcv.append({
            "time":  ts,
            "open":  round(float(row["open"]),  4),
            "high":  round(float(row["high"]),  4),
            "low":   round(float(row["low"]),   4),
            "close": round(float(row["close"]), 4),
        })

    volume = []
    for idx, row in df.iterrows():
        try:
            ts = int(pd.Timestamp(idx).timestamp())
        except Exception:
            continue
        is_bull = row["close"] >= row["open"]
        volume.append({
            "time":  ts,
            "value": int(row["volume"]),
            "color": "rgba(38,166,154,0.5)" if is_bull else "rgba(239,83,80,0.5)",
        })

    def _series(series: pd.Series, color: str) -> list:
        out = []
        for idx, val in series.items():
            if pd.isna(val):
                continue
            try:
                ts = int(pd.Timestamp(idx).timestamp())
                out.append({"time": ts, "value": round(float(val), 4)})
            except Exception:
                pass
        return out

    sma20_data = _series(inds.get("sma20", pd.Series(dtype=float)), C["sma20"])
    sma50_data = _series(inds.get("sma50", pd.Series(dtype=float)), C["sma50"])
    ema20_data = _series(inds.get("ema20", pd.Series(dtype=float)), C["ema20"])

    # Fibonacci levels
    sl = trade_levels.get("swing_low", 0)
    sh = trade_levels.get("swing_high", 0)
    fib_levels = []
    if sh > sl > 0:
        diff = sh - sl
        for ratio, label in [
            (0.0,   "Fib 0"),
            (0.236, "Fib 0.236"),
            (0.382, "Fib 0.382"),
            (0.500, "Fib 0.5"),
            (0.618, "Fib 0.618"),
            (0.786, "Fib 0.786"),
            (1.0,   "Fib 1"),
        ]:
            price = sh - ratio * diff
            fib_levels.append({"price": round(price, 4), "label": label})

    entry  = trade_levels.get("entry",  0)
    stop   = trade_levels.get("stop",   0)
    target = trade_levels.get("target", 0)

    # Serialize everything
    ohlcv_js  = json.dumps(ohlcv)
    volume_js = json.dumps(volume)
    sma20_js  = json.dumps(sma20_data)
    sma50_js  = json.dumps(sma50_data)
    ema20_js  = json.dumps(ema20_data)
    fib_js    = json.dumps(fib_levels)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="{LWC_CDN}"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0d1117; color:#e6edf3; font-family:monospace; }}
  #title {{ padding:8px 12px; font-size:12px; color:#8b949e; }}
  #chart {{ width:100%; height:420px; }}
  #vol   {{ width:100%; height:100px; }}
</style>
</head>
<body>
<div id="title">{title}</div>
<div id="chart"></div>
<div id="vol"></div>
<script>
const LWC = LightweightCharts;

// ── Main price chart ──────────────────────────────────────────────────────────
const chartEl = document.getElementById('chart');
const chart = LWC.createChart(chartEl, {{
  width:  chartEl.clientWidth,
  height: 420,
  layout: {{
    background: {{ color: '#161b22' }},
    textColor:  '#8b949e',
  }},
  grid: {{
    vertLines: {{ color: '#21262d' }},
    horzLines: {{ color: '#21262d' }},
  }},
  crosshair: {{ mode: LWC.CrosshairMode.Normal }},
  rightPriceScale: {{ borderColor: '#30363d' }},
  timeScale: {{
    borderColor:    '#30363d',
    timeVisible:    true,
    secondsVisible: false,
  }},
}});

// Candlestick series
const candleSeries = chart.addCandlestickSeries({{
  upColor:         '#26a69a',
  downColor:       '#ef5350',
  borderUpColor:   '#26a69a',
  borderDownColor: '#ef5350',
  wickUpColor:     '#26a69a',
  wickDownColor:   '#ef5350',
}});
candleSeries.setData({ohlcv_js});

// SMA 20
const sma20 = chart.addLineSeries({{ color: '{C["sma20"]}', lineWidth: 1, title: 'SMA20' }});
sma20.setData({sma20_js});

// SMA 50
const sma50 = chart.addLineSeries({{ color: '{C["sma50"]}', lineWidth: 1, title: 'SMA50' }});
sma50.setData({sma50_js});

// EMA 20
const ema20 = chart.addLineSeries({{ color: '{C["ema20"]}', lineWidth: 1,
  lineStyle: LWC.LineStyle.Dashed, title: 'EMA20' }});
ema20.setData({ema20_js});

// ── Trade levels as horizontal price lines ────────────────────────────────────
{"candleSeries.createPriceLine({ price: " + str(entry) + ", color: '" + C["entry"] + "', lineWidth: 1, lineStyle: LWC.LineStyle.Dotted, axisLabelVisible: true, title: 'Entry' });" if entry > 0 else ""}
{"candleSeries.createPriceLine({ price: " + str(stop) + ", color: '" + C["stop"] + "', lineWidth: 1, lineStyle: LWC.LineStyle.Dashed, axisLabelVisible: true, title: 'Stop' });" if stop > 0 else ""}
{"candleSeries.createPriceLine({ price: " + str(target) + ", color: '" + C["target"] + "', lineWidth: 1, lineStyle: LWC.LineStyle.Dashed, axisLabelVisible: true, title: 'Target' });" if target > 0 else ""}

// ── Fibonacci price lines ─────────────────────────────────────────────────────
const fibLevels = {fib_js};
fibLevels.forEach(function(f) {{
  candleSeries.createPriceLine({{
    price:             f.price,
    color:             '{C["fib"]}',
    lineWidth:         1,
    lineStyle:         LWC.LineStyle.Dotted,
    axisLabelVisible:  false,
    title:             f.label,
  }});
}});

// Fit content
chart.timeScale().fitContent();

// ── Volume chart ──────────────────────────────────────────────────────────────
const volEl = document.getElementById('vol');
const volChart = LWC.createChart(volEl, {{
  width:  volEl.clientWidth,
  height: 100,
  layout: {{ background: {{ color: '#0d1117' }}, textColor: '#8b949e' }},
  grid:   {{ vertLines: {{ color: '#21262d' }}, horzLines: {{ color: '#21262d' }} }},
  rightPriceScale: {{ borderColor: '#30363d' }},
  timeScale: {{
    borderColor: '#30363d',
    timeVisible: true,
    secondsVisible: false,
  }},
}});
const volSeries = volChart.addHistogramSeries({{ priceFormat: {{ type: 'volume' }} }});
volSeries.setData({volume_js});
volChart.timeScale().fitContent();

// ── Sync crosshair and scroll between charts ──────────────────────────────────
chart.timeScale().subscribeVisibleLogicalRangeChange(function(range) {{
  if (range) volChart.timeScale().setVisibleLogicalRange(range);
}});
volChart.timeScale().subscribeVisibleLogicalRangeChange(function(range) {{
  if (range) chart.timeScale().setVisibleLogicalRange(range);
}});

// Responsive resize
window.addEventListener('resize', function() {{
  chart.applyOptions({{ width: chartEl.clientWidth }});
  volChart.applyOptions({{ width: volEl.clientWidth }});
}});
</script>
</body>
</html>"""
    return html


# ═══════════════════════════════════════════════════════════════════════════════
# PLOTLY SUB-PANELS (RSI, ADX, Radar)
# ═══════════════════════════════════════════════════════════════════════════════

def build_rsi_chart(df: pd.DataFrame) -> go.Figure:
    close = df["close"].values
    delta = np.diff(close, prepend=close[0])
    gain  = np.where(delta > 0, delta, 0.0)
    loss  = np.where(delta < 0, -delta, 0.0)

    def _rm(arr, n=14):
        out = np.full(len(arr), np.nan)
        for i in range(n-1, len(arr)):
            out[i] = arr[i-n+1:i+1].mean()
        return out

    ag, al = _rm(gain), _rm(loss)
    rsi = 100 - (100 / (1 + ag / (al + 1e-10)))
    x   = list(range(len(df)))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=rsi, line=dict(color=C["rsi"], width=1.2),
                             name="RSI 14"))
    fig.add_hline(y=70, line_dash="dot", line_color=C["bear"],  line_width=0.8)
    fig.add_hline(y=50, line_dash="dot", line_color=C["muted"], line_width=0.6)
    fig.add_hline(y=30, line_dash="dot", line_color=C["bull"],  line_width=0.8)
    fig.add_hrect(y0=70, y1=100, fillcolor=C["bear"], opacity=0.05, line_width=0)
    fig.add_hrect(y0=0,  y1=30,  fillcolor=C["bull"], opacity=0.05, line_width=0)
    fig.update_layout(
        height=120, margin=dict(l=5,r=5,t=5,b=5),
        paper_bgcolor=C["bg"], plot_bgcolor=C["panel"],
        font=dict(color=C["muted"], size=9),
        showlegend=False,
        yaxis=dict(range=[0,100], tickvals=[30,50,70], gridcolor=C["border"]),
        xaxis=dict(showticklabels=False, gridcolor=C["border"]),
    )
    return fig


def build_adx_chart(df: pd.DataFrame) -> go.Figure:
    h, l, c = df["high"].values, df["low"].values, df["close"].values

    def _rm(arr, n=14):
        out = np.full(len(arr), np.nan)
        for i in range(n-1, len(arr)):
            out[i] = arr[i-n+1:i+1].mean()
        return out

    up  = np.diff(h, prepend=h[0])
    dn  = -np.diff(l, prepend=l[0])
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr  = np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))))
    atr = _rm(tr)
    pdi = 100 * _rm(pdm) / (atr + 1e-10)
    mdi = 100 * _rm(mdm) / (atr + 1e-10)
    dx  = 100 * np.abs(pdi - mdi) / (pdi + mdi + 1e-10)
    adx = _rm(dx)
    x   = list(range(len(df)))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=adx, line=dict(color=C["adx"],  width=1.2), name="ADX"))
    fig.add_trace(go.Scatter(x=x, y=pdi, line=dict(color=C["bull"], width=0.8), name="+DI"))
    fig.add_trace(go.Scatter(x=x, y=mdi, line=dict(color=C["bear"], width=0.8), name="-DI"))
    fig.add_hline(y=25, line_dash="dot", line_color=C["muted"], line_width=0.7)
    fig.update_layout(
        height=120, margin=dict(l=5,r=5,t=5,b=5),
        paper_bgcolor=C["bg"], plot_bgcolor=C["panel"],
        font=dict(color=C["muted"], size=9),
        legend=dict(orientation="h", y=1.0, font=dict(size=8),
                    bgcolor="rgba(0,0,0,0)"),
        yaxis=dict(range=[0,60], gridcolor=C["border"]),
        xaxis=dict(showticklabels=False, gridcolor=C["border"]),
    )
    return fig


def build_radar_chart(row: dict) -> go.Figure:
    cats   = ["Trend", "Pattern", "RS", "RVOL", "RSI", "R:R", "ATR", "OBV"]
    keys   = ["c_trend", "c_pattern", "c_rs", "c_rvol", "c_rsi", "c_rr", "c_atr", "c_obv"]
    vals   = [float(row.get(k, 0)) for k in keys]
    score  = float(row.get("score", 0))

    color = C["bull"] if score >= 60 else ("#ff9800" if score >= 45 else C["bear"])
    fill  = f"rgba(38,166,154,0.2)" if score >= 60 else (
            f"rgba(255,152,0,0.2)"  if score >= 45 else "rgba(239,83,80,0.15)")

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]],
        fill="toself", fillcolor=fill,
        line=dict(color=color, width=2),
        hovertemplate="%{theta}: %{r:.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=280, margin=dict(l=20,r=20,t=30,b=20),
        paper_bgcolor=C["bg"],
        polar=dict(
            bgcolor=C["panel"],
            radialaxis=dict(range=[0,1], showticklabels=False,
                            gridcolor=C["border"]),
            angularaxis=dict(gridcolor=C["border"],
                             tickfont=dict(color=C["text"], size=10)),
        ),
        showlegend=False,
        title=dict(text=f"Score: {score:.0f}", font=dict(color=C["text"], size=12)),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# DASH APP
# ═══════════════════════════════════════════════════════════════════════════════

def build_app(cfg: dict, data_store: dict = None,
              results_csv: str = None) -> "dash.Dash":

    if not DASH_AVAILABLE:
        raise ImportError("pip install dash plotly")

    # Auto-detect latest CSV if not specified
    if results_csv is None:
        scan_dir = Path(__file__).parent / "Scan_result"
        csv_files = sorted(scan_dir.glob("*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
        if csv_files:
            results_csv = str(csv_files[0])
        else:
            results_csv = "watchlist.csv"
    try:
        df_wl = pd.read_csv(results_csv).fillna(0)
    except FileNotFoundError:
        logger.warning(f"{results_csv} not found — run scanner + filter first")
        df_wl = pd.DataFrame(columns=["ticker", "score"])

    data_store = data_store or {}

    TABLE_COLS = ["ticker", "score", "price", "pattern", "rsi",
                  "adx", "rvol", "rr", "entry", "stop", "target"]
    table_cols = [c for c in TABLE_COLS if c in df_wl.columns]

    col_defs = []
    for c in table_cols:
        is_text = c in ("ticker", "pattern")
        col_defs.append({
            "name": c.upper().replace("_", " "),
            "id":   c,
            "type": "text" if is_text else "numeric",
            **({"format": {"specifier": ".2f"}} if not is_text else {}),
        })

    app = dash.Dash(__name__, title="Swing Scanner",
                    suppress_callback_exceptions=True)

    # ── Layout ────────────────────────────────────────────────────────────────
    app.layout = html.Div(
        style={"backgroundColor": C["bg"], "minHeight": "100vh",
               "padding": "12px", "fontFamily": "monospace"},
        children=[

            # Regime banner
            html.Div(id="regime-banner", style={
                "padding": "8px 16px", "marginBottom": "12px",
                "borderRadius": "6px", "backgroundColor": C["panel"],
                "color": C["muted"], "fontSize": "13px",
            }, children="Run scanner to load regime"),

            # Controls bar
            html.Div(style={"display": "flex", "gap": "16px",
                            "marginBottom": "10px", "alignItems": "center"}, children=[
                html.Label("Pattern:", style={"color": C["muted"], "fontSize": "12px"}),
                dcc.Dropdown(
                    id="pattern-filter",
                    options=[{"label": x, "value": x} for x in
                             ["all", "breakout", "pullback", "squeeze"]],
                    value="all", clearable=False,
                    style={"width": "140px", "fontSize": "12px"},
                ),
                html.Label("Min score:", style={"color": C["muted"], "fontSize": "12px"}),
                dcc.Slider(id="score-slider", min=0, max=100, step=5,
                           value=int(cfg.get("min_score_display", 40)),
                           marks={i: str(i) for i in range(0, 101, 20)},
                           tooltip={"placement": "bottom"}),
                html.Label("Bars:", style={"color": C["muted"], "fontSize": "12px"}),
                dcc.Slider(id="bars-slider", min=30, max=200, step=10,
                           value=80, marks={30:"30", 80:"80", 150:"150", 200:"200"},
                           tooltip={"placement": "bottom"}),
            ]),

            # Main layout: left table | right charts
            html.Div(style={"display": "flex", "gap": "12px"}, children=[

                # Left: watchlist table + radar
                html.Div(style={"width": "420px", "flexShrink": "0"}, children=[
                    html.Div("WATCHLIST", style={"color": C["muted"],
                                                  "fontSize": "10px",
                                                  "letterSpacing": "1px",
                                                  "marginBottom": "6px"}),
                    dash_table.DataTable(
                        id="watchlist-table",
                        columns=col_defs,
                        data=df_wl[table_cols].to_dict("records"),
                        row_selectable="single",
                        selected_rows=[0],
                        sort_action="native",
                        page_size=18,
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "backgroundColor": C["panel"],
                            "color":           C["text"],
                            "border":          f"1px solid {C['border']}",
                            "padding":         "6px 10px",
                            "fontSize":        "12px",
                            "textAlign":       "right",
                        },
                        style_header={
                            "backgroundColor": C["bg"],
                            "color":           C["muted"],
                            "fontSize":        "10px",
                            "fontWeight":      "bold",
                            "border":          f"1px solid {C['border']}",
                        },
                        style_data_conditional=[
                            {"if": {"row_index": "odd"},
                             "backgroundColor": "#1c2128"},
                            {"if": {"state": "selected"},
                             "backgroundColor": "#1f3d5c",
                             "border": f"1px solid {C['accent']}"},
                            {"if": {"filter_query": '{score} >= 70'},
                             "fontWeight": "bold"},
                            {"if": {"filter_query": '{pattern} = "breakout"'},
                             "color": C["bull"]},
                            {"if": {"filter_query": '{pattern} = "pullback"'},
                             "color": C["accent"]},
                            {"if": {"filter_query": '{pattern} = "squeeze"'},
                             "color": "#ff9800"},
                        ],
                        style_cell_conditional=[
                            {"if": {"column_id": "ticker"},
                             "textAlign": "left", "fontWeight": "bold"},
                            {"if": {"column_id": "pattern"},
                             "textAlign": "center"},
                        ],
                    ),
                    # Radar chart below table
                    html.Div(style={"marginTop": "10px"}, children=[
                        dcc.Graph(id="radar-chart",
                                  config={"displayModeBar": False})
                    ]),
                ]),

                # Right: LWC chart + RSI + ADX
                html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                    # TradingView Lightweight Charts in iframe
                    html.Iframe(
                        id="lwc-frame",
                        srcDoc="",
                        style={
                            "width":   "100%",
                            "height":  "540px",
                            "border":  f"1px solid {C['border']}",
                            "borderRadius": "6px",
                            "background":   C["panel"],
                        },
                    ),
                    # RSI
                    html.Div(style={"marginTop": "6px"}, children=[
                        dcc.Graph(id="rsi-chart",
                                  config={"displayModeBar": False}),
                    ]),
                    # ADX
                    html.Div(style={"marginTop": "4px"}, children=[
                        dcc.Graph(id="adx-chart",
                                  config={"displayModeBar": False}),
                    ]),
                ]),
            ]),

            # Hidden stores
            dcc.Store(id="selected-ticker", data=""),
            dcc.Interval(id="refresh-interval",
                         interval=cfg.get("dashboard_refresh_sec", 300) * 1000,
                         n_intervals=0),
        ]
    )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("watchlist-table", "data"),
        Input("pattern-filter",  "value"),
        Input("score-slider",    "value"),
    )
    def filter_table(pattern, min_score):
        df = df_wl.copy()
        if pattern != "all" and "pattern" in df.columns:
            df = df[df["pattern"] == pattern]
        if "score" in df.columns:
            df = df[df["score"] >= min_score]
        return df[table_cols].to_dict("records")

    @app.callback(
        Output("lwc-frame",   "srcDoc"),
        Output("rsi-chart",   "figure"),
        Output("adx-chart",   "figure"),
        Output("radar-chart", "figure"),
        Input("watchlist-table", "selected_rows"),
        Input("watchlist-table", "data"),
        Input("bars-slider",     "value"),
    )
    def update_charts(selected_rows, table_data, n_bars):
        empty_fig = _empty_fig()

        if not selected_rows or not table_data:
            return "", empty_fig, empty_fig, empty_fig

        row    = table_data[selected_rows[0]]
        ticker = row.get("ticker", "")

        # Full row from original df for component scores
        matches  = df_wl[df_wl["ticker"] == ticker]
        full_row = matches.iloc[0].to_dict() if not matches.empty else row

        # Get OHLCV from data_store
        df = data_store.get(ticker, pd.DataFrame())
        if df.empty:
            return (_no_data_html(ticker), empty_fig, empty_fig,
                    build_radar_chart(full_row))

        df_plot = df.iloc[-n_bars:]

        # Compute MAs for LWC
        close   = df_plot["close"]
        inds    = {
            "sma20": close.rolling(20).mean(),
            "sma50": close.rolling(50).mean(),
            "ema20": close.ewm(span=20, adjust=False).mean(),
        }

        trade_levels = {
            "entry":      float(row.get("entry",      0)),
            "stop":       float(row.get("stop",       0)),
            "target":     float(row.get("target",     0)),
            "swing_low":  float(row.get("swing_low",  df_plot["low"].min())),
            "swing_high": float(row.get("swing_high", df_plot["high"].max())),
        }

        title = (f"{ticker}  |  {row.get('pattern','').upper()}  |  "
                 f"Score {row.get('score',0):.0f}  |  R:R {row.get('rr',0):.1f}:1")

        lwc_html = build_lwc_html(df_plot, inds, trade_levels, title)
        rsi_fig  = build_rsi_chart(df_plot)
        adx_fig  = build_adx_chart(df_plot)
        radar    = build_radar_chart(full_row)

        return lwc_html, rsi_fig, adx_fig, radar

    return app


# ── Helpers ───────────────────────────────────────────────────────────────────

def _empty_fig() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        height=120, margin=dict(l=5,r=5,t=5,b=5),
        paper_bgcolor=C["bg"], plot_bgcolor=C["panel"],
        font=dict(color=C["muted"]),
    )
    return fig


def _no_data_html(ticker: str) -> str:
    return f"""<html><body style="background:{C['bg']};color:{C['muted']};
font-family:monospace;padding:30px;font-size:13px">
{ticker} — no OHLCV data in memory.<br>
Pass <code>data_store={{ticker: df}}</code> to <code>build_app()</code>.
</body></html>"""