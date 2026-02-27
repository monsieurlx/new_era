"""
dashboard.py — Always-on unified dashboard.

Reads state.json every 30 seconds (written by bot.py).
No shared memory. No WebSocket. Simple and reliable.

Layout:
  Top bar     — Regime banner + session status + session stats
  Left col    — Watchlist table + activity feed
  Right col   — Selected ticker view (tabs: Strategy / Pattern / History)
                  Strategy tab: LWC candlestick + Fib + levels + RSI + ADX
                  Pattern tab:  zoomed pattern chart image
                  History tab:  trade log for this ticker + screenshots

Usage:
    python run.py --mode dashboard
    Open: http://127.0.0.1:8050
"""

import base64
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

try:
    import dash
    from dash import dcc, html, dash_table, Input, Output, callback
    import plotly.graph_objects as go
    DASH_OK = True
except ImportError:
    DASH_OK = False
    log.warning("pip install dash plotly")

from state_manager import StateManager

# ── Colours ───────────────────────────────────────────────────────────────────
C = {
    "bg":     "#0d1117", "panel":  "#161b22", "border": "#30363d",
    "text":   "#e6edf3", "muted":  "#8b949e", "accent": "#58a6ff",
    "bull":   "#26a69a", "bear":   "#ef5350", "warn":   "#ff9800",
    "sma20":  "#2196f3", "sma50":  "#ff9800", "ema20":  "#4caf50",
    "bb":     "#9c27b0", "entry":  "#26a69a", "stop":   "#ef5350",
    "target": "#2196f3", "fib":    "#ffd700", "rsi":    "#e040fb",
    "adx":    "#40c4ff",
}
REGIME_C = {"bull": C["bull"], "neutral": C["warn"], "bear": C["bear"]}
LWC_CDN  = ("https://unpkg.com/lightweight-charts@4.1.1/dist/"
             "lightweight-charts.standalone.production.js")


# ═══════════════════════════════════════════════════════════════════════════════
# LIGHTWEIGHT CHARTS HTML
# ═══════════════════════════════════════════════════════════════════════════════

def _lwc_html(df, row, title=""):
    import json, numpy as np

    BG="#0d1117";PANEL="#161b22";BORDER="#30363d";MUTED="#8b949e";TEXT="#e6edf3"
    BULL="#26a69a";BEAR="#ef5350";SMA20C="#2196f3";SMA50C="#ff9800";EMA20C="#4caf50"
    LWC_SRC="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"

    if df.empty:
        return "<html><body style='background:#0d1117;color:#8b949e;font-family:monospace;padding:30px'>No data</body></html>"

    close = df["close"].values

    def rm(a,n):
        o=[None]*len(a)
        for i in range(n-1,len(a)): o[i]=float(np.mean(a[i-n+1:i+1]))
        return o

    def ec(a,n):
        o,k=[None]*len(a),2/(n+1); o[0]=float(a[0])
        for i in range(1,len(a)): o[i]=float(a[i])*k+o[i-1]*(1-k)
        return o

    s20,s50,e20 = rm(close,20),rm(close,50),ec(close,20)

    def jcandle():
        o=[]
        for idx,r in df.iterrows():
            try: o.append({"time":int(pd.Timestamp(idx).timestamp()),"open":round(float(r["open"]),4),"high":round(float(r["high"]),4),"low":round(float(r["low"]),4),"close":round(float(r["close"]),4)})
            except: pass
        return json.dumps(o)

    def jvol():
        o=[]
        for idx,r in df.iterrows():
            try:
                bull=r["close"]>=r["open"]
                o.append({"time":int(pd.Timestamp(idx).timestamp()),"value":int(r["volume"]),"color":"rgba(38,166,154,0.45)" if bull else "rgba(239,83,80,0.45)"})
            except: pass
        return json.dumps(o)

    def jline(vals):
        o=[]
        for idx,v in zip(df.index,vals):
            if v is None: continue
            try: o.append({"time":int(pd.Timestamp(idx).timestamp()),"value":round(v,4)})
            except: pass
        return json.dumps(o)

    def jflat(p):
        o=[]
        for idx in df.index:
            try: o.append({"time":int(pd.Timestamp(idx).timestamp()),"value":round(float(p),4)})
            except: pass
        return json.dumps(o)

    jc=jcandle(); jv=jvol(); j20=jline(s20); j50=jline(s50); je=jline(e20)

    entry=float(row.get("entry",0)); stop=float(row.get("stop",0))
    target=float(row.get("target",0)); shares=int(row.get("shares",1))

    # Fib lines
    fib=""
    slo=row.get("swing_low"); shi=row.get("swing_high")
    if slo and shi and float(shi)>float(slo)>0:
        d=float(shi)-float(slo)
        for r2,l in [(0.382,"0.382"),(0.5,"0.5"),(0.618,"0.618")]:
            p=round(float(shi)-r2*d,4)
            fib+="cs.createPriceLine({price:"+str(p)+",color:'rgba(255,215,0,0.22)',lineWidth:1,lineStyle:LWC.LineStyle.Dotted,axisLabelVisible:false,title:'"+l+"'});\n"

    # Header chips
    chips=""
    if entry>0:
        chips+='<span class="chip en"><span class="cl">ENTRY</span><span class="cv">$'+f"{entry:.2f}"+'</span></span>'
    if stop>0 and entry>stop:
        ru=round((entry-stop)*shares,2)
        chips+='<span class="chip sl"><span class="cl">STOP</span><span class="cv">$'+f"{stop:.2f}"+'</span><span class="cs">&#8209;$'+f"{ru}"+'</span></span>'
    if target>0 and entry>0 and target>entry:
        ru=round((target-entry)*shares,2)
        rr=round((target-entry)/(entry-stop),2) if stop>0 and entry>stop else 0
        chips+='<span class="chip tp"><span class="cl">TARGET</span><span class="cv">$'+f"{target:.2f}"+'</span><span class="cs">+$'+f"{ru}"+'</span></span>'
        if rr>0: chips+='<span class="chip rr"><span class="cl">R:R</span><span class="cv">'+f"{rr}:1"+'</span></span>'

    # Level lines (left scale) and zone (right scale baseline)
    lvl_lines=""
    if entry>0:
        lvl_lines+="lvl.createPriceLine({price:"+str(round(entry,4))+",color:'#ffffff',lineWidth:2,lineStyle:LWC.LineStyle.Solid,axisLabelVisible:true,title:'\\u2500 Entry'});\n"
    if stop>0 and entry>stop:
        lvl_lines+="lvl.createPriceLine({price:"+str(round(stop,4))+",color:'#ef5350',lineWidth:1.5,lineStyle:LWC.LineStyle.Dashed,axisLabelVisible:true,title:'\\u25bc SL'});\n"
    if target>0 and entry>0 and target>entry:
        lvl_lines+="lvl.createPriceLine({price:"+str(round(target,4))+",color:'#26a69a',lineWidth:1.5,lineStyle:LWC.LineStyle.Dashed,axisLabelVisible:true,title:'\\u25b2 TP'});\n"

    zone=""
    if entry>0 and stop>0 and target>0 and entry>stop and target>entry:
        jb=jflat(entry)
        zone=("const bl=chart.addBaselineSeries({baseValue:{type:'price',price:"+str(round(entry,4))+"},topFillColor1:'rgba(38,166,154,0.28)',topFillColor2:'rgba(38,166,154,0.05)',topLineColor:'rgba(38,166,154,0)',bottomFillColor1:'rgba(239,83,80,0.05)',bottomFillColor2:'rgba(239,83,80,0.25)',bottomLineColor:'rgba(239,83,80,0)',lineWidth:0,lastValueVisible:false,crosshairMarkerVisible:false,priceScaleId:'right'});\n"
              "bl.setData("+jb+");\n")

    # Invisible left-scale anchor series for price lines
    mid=round((stop+target)/2,4) if stop and target else round(entry,4)
    jmid=jflat(mid)
    mn=round(min(stop,entry,target)*0.97,4) if stop and entry and target else 0
    mx=round(max(stop,entry,target)*1.03,4) if stop and entry and target else 0
    lvl_series=("const lvl=chart.addLineSeries({priceScaleId:'left',color:'rgba(0,0,0,0)',lineWidth:1,lastValueVisible:false,crosshairMarkerVisible:false"
                +((",autoscaleInfoProvider:()=>({priceRange:{minValue:"+str(mn)+",maxValue:"+str(mx)+"},margins:{above:10,below:10}})") if mn and mx else "")
                +"});\n"
                "lvl.setData("+jmid+");\n")

    css=("<style>*{margin:0;padding:0;box-sizing:border-box}"
         "body{background:"+BG+";color:"+TEXT+";font-family:'SF Mono',monospace;font-size:11px}"
         "#hdr{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:6px 10px;background:"+BG+";border-bottom:1px solid "+BORDER+"}"
         ".ttl{color:"+MUTED+";margin-right:4px}"
         ".chip{display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;border:1px solid transparent}"
         ".chip.en{background:rgba(255,255,255,0.10);border-color:rgba(255,255,255,0.28);color:#fff}"
         ".chip.sl{background:rgba(239,83,80,0.14);border-color:rgba(239,83,80,0.45);color:#ef5350}"
         ".chip.tp{background:rgba(38,166,154,0.12);border-color:rgba(38,166,154,0.4);color:#26a69a}"
         ".chip.rr{background:rgba(88,166,255,0.10);border-color:rgba(88,166,255,0.35);color:#58a6ff}"
         ".cl{font-size:9px;opacity:0.65;letter-spacing:0.5px}.cv{font-weight:bold;font-size:12px}.cs{font-size:9px;opacity:0.75}"
         "#c{width:100%;height:390px}#v{width:100%;height:85px}</style>")

    opts=("const LWC=LightweightCharts;"
          "const OPTS={layout:{background:{color:'"+PANEL+"'},textColor:'"+MUTED+"'},grid:{vertLines:{color:'"+BORDER+"'},horzLines:{color:'"+BORDER+"'}},crosshair:{mode:LWC.CrosshairMode.Normal},"
          "leftPriceScale:{visible:true,borderColor:'"+BORDER+"',textColor:'"+MUTED+"',entireTextOnly:true},"
          "rightPriceScale:{borderColor:'"+BORDER+"'},timeScale:{borderColor:'"+BORDER+"',timeVisible:true,secondsVisible:false}};")

    ma_js=("chart.addLineSeries({color:'"+SMA20C+"',lineWidth:1.2,title:'SMA20',lastValueVisible:false,crosshairMarkerVisible:false,priceScaleId:'right'}).setData("+j20+");\n"
           "chart.addLineSeries({color:'"+SMA50C+"',lineWidth:1.2,title:'SMA50',lastValueVisible:false,crosshairMarkerVisible:false,priceScaleId:'right'}).setData("+j50+");\n"
           "chart.addLineSeries({color:'"+EMA20C+"',lineWidth:1,lineStyle:LWC.LineStyle.Dashed,title:'EMA20',lastValueVisible:false,crosshairMarkerVisible:false,priceScaleId:'right'}).setData("+je+");\n")

    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><script src='"+LWC_SRC+"'></script>"+css+"</head><body>"
            "<div id='hdr'><span class='ttl'>"+title+"</span>"+chips+"</div>"
            "<div id='c'></div><div id='v'></div><script>"
            +opts+
            "const chart=LWC.createChart(document.getElementById('c'),{...OPTS,width:document.getElementById('c').clientWidth,height:390});\n"
            +zone+
            "const cs=chart.addCandlestickSeries({upColor:'"+BULL+"',downColor:'"+BEAR+"',borderUpColor:'"+BULL+"',borderDownColor:'"+BEAR+"',wickUpColor:'"+BULL+"',wickDownColor:'"+BEAR+"',priceScaleId:'right'});\n"
            "cs.setData("+jc+");\n"
            +ma_js+fib+lvl_series+lvl_lines+
            "chart.timeScale().fitContent();\n"
            "const vc=LWC.createChart(document.getElementById('v'),{...OPTS,width:document.getElementById('v').clientWidth,height:85});\n"
            "vc.addHistogramSeries({priceFormat:{type:'volume'}}).setData("+jv+");\n"
            "vc.timeScale().fitContent();\n"
            "chart.timeScale().subscribeVisibleLogicalRangeChange(r=>{if(r)vc.timeScale().setVisibleLogicalRange(r)});\n"
            "vc.timeScale().subscribeVisibleLogicalRangeChange(r=>{if(r)chart.timeScale().setVisibleLogicalRange(r)});\n"
            "window.addEventListener('resize',()=>{chart.applyOptions({width:document.getElementById('c').clientWidth});vc.applyOptions({width:document.getElementById('v').clientWidth})});\n"
            "</script></body></html>")


def _img_b64(path: Path) -> str:
    """Load a PNG as base64 for embedding in Dash."""
    if not path or not path.exists():
        return ""
    try:
        return base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return ""


def _rsi_fig(df: pd.DataFrame) -> "go.Figure":
    import numpy as np
    c = df["close"].values
    d = np.diff(c, prepend=c[0])
    g, l = np.where(d>0,d,0.0), np.where(d<0,-d,0.0)
    def rm(a,n=14):
        o=np.full(len(a),np.nan)
        for i in range(n-1,len(a)): o[i]=a[i-n+1:i+1].mean()
        return o
    rsi = 100-(100/(1+rm(g)/(rm(l)+1e-10)))
    x   = list(range(len(df)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x,y=rsi,line=dict(color=C["rsi"],width=1.2),name="RSI"))
    fig.add_hline(y=70,line_dash="dot",line_color=C["bear"],  line_width=0.8)
    fig.add_hline(y=50,line_dash="dot",line_color=C["muted"], line_width=0.6)
    fig.add_hline(y=30,line_dash="dot",line_color=C["bull"],  line_width=0.8)
    fig.update_layout(height=100,margin=dict(l=5,r=5,t=2,b=2),
                      paper_bgcolor=C["bg"],plot_bgcolor=C["panel"],
                      font=dict(color=C["muted"],size=8),showlegend=False,
                      yaxis=dict(range=[0,100],tickvals=[30,50,70],gridcolor=C["border"]),
                      xaxis=dict(showticklabels=False,gridcolor=C["border"]))
    return fig


def _adx_fig(df: pd.DataFrame) -> "go.Figure":
    import numpy as np
    h,l,c=df["high"].values,df["low"].values,df["close"].values
    def rm(a,n=14):
        o=np.full(len(a),np.nan)
        for i in range(n-1,len(a)): o[i]=a[i-n+1:i+1].mean()
        return o
    up=np.diff(h,prepend=h[0]); dn=-np.diff(l,prepend=l[0])
    pdm=np.where((up>dn)&(up>0),up,0.0); mdm=np.where((dn>up)&(dn>0),dn,0.0)
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    atr=rm(tr); pdi=100*rm(pdm)/(atr+1e-10); mdi=100*rm(mdm)/(atr+1e-10)
    adx=rm(100*np.abs(pdi-mdi)/(pdi+mdi+1e-10))
    x=list(range(len(df)))
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=x,y=adx,line=dict(color=C["adx"],width=1.2),name="ADX"))
    fig.add_trace(go.Scatter(x=x,y=pdi,line=dict(color=C["bull"],width=0.8),name="+DI"))
    fig.add_trace(go.Scatter(x=x,y=mdi,line=dict(color=C["bear"],width=0.8),name="-DI"))
    fig.add_hline(y=25,line_dash="dot",line_color=C["muted"],line_width=0.7)
    fig.update_layout(height=100,margin=dict(l=5,r=5,t=2,b=2),
                      paper_bgcolor=C["bg"],plot_bgcolor=C["panel"],
                      font=dict(color=C["muted"],size=8),
                      legend=dict(orientation="h",y=1,font=dict(size=7),bgcolor="rgba(0,0,0,0)"),
                      yaxis=dict(range=[0,60],gridcolor=C["border"]),
                      xaxis=dict(showticklabels=False,gridcolor=C["border"]))
    return fig


def _radar_fig(row: dict) -> "go.Figure":
    cats = ["Trend","Pattern","RS","RVOL","RSI","R:R","ATR","OBV"]
    keys = ["c_trend","c_pattern","c_rs","c_rvol","c_rsi","c_rr","c_atr","c_obv"]
    vals = [float(row.get(k,0)) for k in keys]
    score= float(row.get("score",0))
    col  = C["bull"] if score>=60 else (C["warn"] if score>=45 else C["bear"])
    fill = ("rgba(38,166,154,0.2)" if score>=60 else
            "rgba(255,152,0,0.2)"  if score>=45 else "rgba(239,83,80,0.15)")
    fig=go.Figure()
    fig.add_trace(go.Scatterpolar(r=vals+[vals[0]],theta=cats+[cats[0]],
        fill="toself",fillcolor=fill,line=dict(color=col,width=2)))
    fig.update_layout(height=240,margin=dict(l=15,r=15,t=30,b=10),
        paper_bgcolor=C["bg"],
        polar=dict(bgcolor=C["panel"],
                   radialaxis=dict(range=[0,1],showticklabels=False,
                                   gridcolor=C["border"]),
                   angularaxis=dict(gridcolor=C["border"],
                                    tickfont=dict(color=C["text"],size=9))),
        showlegend=False,
        title=dict(text=f"Score: {score:.0f}",
                   font=dict(color=C["text"],size=11)))
    return fig


def _empty_fig(h=100):
    fig=go.Figure()
    fig.update_layout(height=h,margin=dict(l=5,r=5,t=2,b=2),
                      paper_bgcolor=C["bg"],plot_bgcolor=C["panel"])
    return fig


def _no_data_html(ticker: str) -> str:
    msg = (f"Fetching data for {ticker}..." if ticker
           else "Select a ticker from the watchlist")
    return (f"<html><body style='background:{C['bg']};color:{C['muted']};"
            f"font-family:monospace;padding:40px;font-size:13px'>{msg}</body></html>")


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _label(text):
    return html.Span(text, style={"color":C["muted"],"fontSize":"10px",
                                   "letterSpacing":"1px","textTransform":"uppercase"})


def _stat(label, value, color=None):
    return html.Div([
        html.Div(label, style={"color":C["muted"],"fontSize":"10px"}),
        html.Div(value, style={"color":color or C["text"],
                                "fontSize":"20px","fontWeight":"bold"}),
    ], style={"textAlign":"center","minWidth":"80px"})


# ═══════════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════════

# IB bar_size string and max duration for each dashboard barsize code
_IB_BAR_PARAMS = {
    "5m":  ("5 mins",  "10 D"),   # IB max ~10 days for 5-min
    "15m": ("15 mins", "20 D"),
    "1h":  ("1 hour",  "30 D"),
    "4h":  ("4 hours", "30 D"),
    "1D":  ("1 day",   "1 Y"),
    "1W":  ("1 day",   "1 Y"),    # fetched as 1D, resampled to weekly
    "1M":  ("1 day",   "1 Y"),    # fetched as 1D, resampled to monthly
}


def _fetch_ticker(ticker: str, cfg: dict, barsize: str = "1D") -> pd.DataFrame:
    """
    Fetch OHLCV for a single ticker at the requested bar granularity.

    For daily/weekly/monthly: reads from ohlcv_cache/{ticker}.csv (written by bot)
    then falls back to IB live fetch.

    For intraday (5m/15m/1h/4h): always fetches live from IB — no disk cache
    for intraday since it changes every session.
    """
    from pathlib import Path

    intraday = barsize in ("5m", "15m", "1h", "4h")

    if not intraday:
        # Try disk cache first (daily data written by bot)
        cache_path = Path(cfg.get("ohlcv_cache_dir", "ohlcv_cache")) / f"{ticker}.csv"
        if cache_path.exists():
            try:
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                df.columns = [c.lower() for c in df.columns]
                if {"open","high","low","close","volume"}.issubset(df.columns):
                    log.info(f"[{ticker}] loaded from ohlcv_cache/")
                    return df
            except Exception as e:
                log.warning(f"Cache read failed {ticker}: {e}")

    # Live IB fetch (always for intraday, fallback for daily)
    ib_bar, ib_dur = _IB_BAR_PARAMS.get(barsize, ("1 day", "1 Y"))
    log.info(f"[{ticker}] IB fetch: bar={ib_bar} dur={ib_dur}")
    try:
        import asyncio
        from ib_client import get_client
        async def _fetch():
            client = get_client(cfg)
            await client.connect()
            df = await client.fetch_historical(
                client.make_stock(ticker),
                duration=ib_dur,
                bar_size=ib_bar,
            )
            await client.disconnect()
            return df
        df = asyncio.run(_fetch())
        if not df.empty and not intraday:
            from bot import _save_ohlcv_cache
            _save_ohlcv_cache({ticker: df}, cfg)
        return df
    except Exception as e:
        log.warning(f"IB fetch failed for {ticker}: {e}")
        return pd.DataFrame()


def build_app(cfg: dict, data_store: dict = None) -> "dash.Dash":
    if not DASH_OK:
        raise ImportError("pip install dash plotly")

    data_store = data_store or {}

    app = dash.Dash(__name__, title="Swing Scanner",
                    suppress_callback_exceptions=True)
    app.layout = _build_layout(cfg)
    _register_callbacks(app, cfg, data_store)
    return app


def _slice_period(df: pd.DataFrame, period: str, barsize: str = "1D") -> pd.DataFrame:
    """Return rows within the selected lookback period.
    For intraday data, period is in trading days × bars/day.
    """
    if df.empty or period == "ALL":
        return df
    # Bars per day for each barsize
    bars_per_day = {"5m": 78, "15m": 26, "1h": 7, "4h": 2, "1D": 1, "1W": 1, "1M": 1}
    bpd = bars_per_day.get(barsize, 1)
    # Trading days per period
    td = {"1D":1,"3D":3,"5D":5,"1M":21,"3M":63,"6M":126,"1Y":252}
    days = td.get(period, 252)
    n = days * bpd
    return df.iloc[-n:] if len(df) > n else df


def _resample_df(df: pd.DataFrame, barsize: str) -> pd.DataFrame:
    """Resample a daily OHLCV DataFrame to weekly or monthly bars."""
    if df.empty or barsize == "1D":
        return df
    rule = {"1W": "W-FRI", "1M": "MS"}.get(barsize, "W-FRI")
    try:
        agg = {"open": "first", "high": "max", "low": "min",
               "close": "last", "volume": "sum"}
        present = {k: v for k, v in agg.items() if k in df.columns}
        rs = df.resample(rule).agg(present).dropna(subset=["close"])
        return rs
    except Exception:
        return df


def _build_layout(cfg: dict):
    TABLE_COLS = ["ticker","score","pattern","rsi","adx","rvol","rr",
                  "entry","stop","target","status"]
    col_defs = [{"name": c.upper().replace("_"," "), "id": c,
                 "type": "text" if c in ("ticker","pattern","status") else "numeric",
                 **({} if c in ("ticker","pattern","status")
                    else {"format":{"specifier":".2f"}})}
                for c in TABLE_COLS]

    return html.Div(style={"backgroundColor":C["bg"],"minHeight":"100vh",
                           "padding":"10px","fontFamily":"monospace",
                           "color":C["text"]}, children=[

        # ── Auto-refresh every 30s ─────────────────────────────────────────
        dcc.Interval(id="refresh", interval=30_000, n_intervals=0),
        dcc.Store(id="state-store", data={}),
        # Central source of truth for which ticker is displayed.
        # Written by: watchlist click, position card click, search bar.
        # Read by: all chart/title callbacks.
        dcc.Store(id="selected-ticker", data=""),

        # ── Top bar: regime + session + stats ──────────────────────────────
        _card(id="top-bar", children=[
            html.Div(id="regime-banner", style={"marginBottom":"8px"}),
            html.Div(id="stats-bar"),
        ], style={"marginBottom":"10px"}),

        # ── Main layout ────────────────────────────────────────────────────
        html.Div(style={"display":"flex","gap":"10px"}, children=[

            # Left column: watchlist + activity feed
            html.Div(style={"width":"380px","flexShrink":"0",
                            "display":"flex","flexDirection":"column","gap":"8px"},
            children=[
                _card(children=[
                    html.Div(style={"display":"flex","justifyContent":"space-between",
                                    "alignItems":"center","marginBottom":"6px"},
                    children=[
                        _label("Watchlist"),
                        html.Div(style={"position":"relative"}, children=[
                            dcc.Input(
                                id="ticker-search",
                                placeholder="⌕  AAPL, XOM…",
                                debounce=False,
                                type="text",
                                autoComplete="off",
                                style={"backgroundColor":C["bg"],"color":C["text"],
                                       "border":f"1px solid {C['accent']}",
                                       "borderRadius":"4px",
                                       "padding":"4px 10px",
                                       "fontSize":"12px","width":"150px",
                                       "outline":"none",
                                       "letterSpacing":"0.3px"},
                            ),
                        ]),
                    ]),
                    html.Div(style={"marginTop":"6px"}, children=[
                        # Pattern filter
                        html.Div(style={"display":"flex","gap":"8px",
                                        "marginBottom":"6px","alignItems":"center"},
                        children=[
                            dcc.Dropdown(id="pat-filter",
                                options=[{"label":x,"value":x}
                                         for x in ["all","breakout","pullback","squeeze"]],
                                value="all", clearable=False,
                                style={"width":"130px","fontSize":"11px"}),
                            html.Div(dcc.Slider(id="score-filter",min=0,max=100,step=5,
                                       value=int(cfg.get("min_score_display",40)),
                                       marks={0:"0",50:"50",100:"100"},
                                       tooltip={"placement":"bottom"}),
                                       style={"flex":"1"}),
                        ]),
                        dash_table.DataTable(
                            id="watchlist-table",
                            columns=col_defs,
                            data=[],
                            row_selectable="single",
                            selected_rows=[0],
                            sort_action="native",
                            page_size=15,
                            style_table={"overflowX":"auto"},
                            style_cell={"backgroundColor":C["panel"],"color":C["text"],
                                        "border":f"1px solid {C['border']}",
                                        "padding":"5px 8px","fontSize":"11px",
                                        "textAlign":"right"},
                            style_header={"backgroundColor":C["bg"],"color":C["muted"],
                                          "fontSize":"9px","fontWeight":"bold",
                                          "border":f"1px solid {C['border']}"},
                            style_data_conditional=[
                                {"if":{"row_index":"odd"},"backgroundColor":"#1c2128"},
                                {"if":{"state":"selected"},"backgroundColor":"#1f3d5c",
                                 "border":f"1px solid {C['accent']}"},
                                {"if":{"filter_query":'{pattern} = "breakout"'},
                                 "color":C["bull"]},
                                {"if":{"filter_query":'{pattern} = "pullback"'},
                                 "color":C["accent"]},
                                {"if":{"filter_query":'{pattern} = "squeeze"'},
                                 "color":C["warn"]},
                                {"if":{"filter_query":'{status} = "filled"'},
                                 "fontWeight":"bold"},
                            ],
                            style_cell_conditional=[
                                {"if":{"column_id":"ticker"},"textAlign":"left",
                                 "fontWeight":"bold"},
                                {"if":{"column_id":"pattern"},"textAlign":"center"},
                                {"if":{"column_id":"status"},"textAlign":"center"},
                            ],
                        ),
                    ]),
                ]),

                # Open positions
                _card(children=[
                    _label("Open Positions"),
                    html.Div(id="positions-panel",style={"marginTop":"6px"}),
                ]),

                # Activity feed
                _card(children=[
                    _label("Activity Feed"),
                    html.Div(id="activity-feed",style={"marginTop":"6px",
                             "maxHeight":"200px","overflowY":"auto"}),
                ]),
            ]),

            # Right column: ticker detail
            html.Div(style={"flex":"1","minWidth":"0"}, children=[
                _card(children=[
                    html.Div(id="ticker-title",
                             style={"fontSize":"14px","fontWeight":"bold",
                                    "marginBottom":"8px","color":C["text"]}),
                    dcc.Tabs(id="detail-tabs", value="strategy",
                             style={"marginBottom":"8px"},
                    children=[
                        dcc.Tab(label="Strategy Chart", value="strategy",
                                style={"color":C["muted"],"backgroundColor":C["bg"],
                                       "fontSize":"11px","padding":"6px 12px"},
                                selected_style={"color":C["text"],"backgroundColor":C["panel"],
                                                "fontSize":"11px","padding":"6px 12px",
                                                "borderTop":f"2px solid {C['accent']}"}),
                        dcc.Tab(label="Pattern", value="pattern",
                                style={"color":C["muted"],"backgroundColor":C["bg"],
                                       "fontSize":"11px","padding":"6px 12px"},
                                selected_style={"color":C["text"],"backgroundColor":C["panel"],
                                                "fontSize":"11px","padding":"6px 12px",
                                                "borderTop":f"2px solid {C['accent']}"}),
                        dcc.Tab(label="Trade History", value="history",
                                style={"color":C["muted"],"backgroundColor":C["bg"],
                                       "fontSize":"11px","padding":"6px 12px"},
                                selected_style={"color":C["text"],"backgroundColor":C["panel"],
                                                "fontSize":"11px","padding":"6px 12px",
                                                "borderTop":f"2px solid {C['accent']}"}),
                        dcc.Tab(label="Backtest", value="backtest",
                                style={"color":C["muted"],"backgroundColor":C["bg"],
                                       "fontSize":"11px","padding":"6px 12px"},
                                selected_style={"color":C["text"],"backgroundColor":C["panel"],
                                                "fontSize":"11px","padding":"6px 12px",
                                                "borderTop":f"2px solid #f0a500"}),
                    ]),

                    # ── STRATEGY TAB (static IDs — always in DOM) ──────────
                    html.Div(id="strategy-panel", children=[

                        # Timeframe toolbar
                        html.Div(style={
                            "display":"flex","gap":"6px","alignItems":"center",
                            "marginBottom":"6px","flexWrap":"wrap",
                        }, children=[
                            # Bar-size buttons (intraday + daily+ )
                            _label("TF"),
                            html.Div(style={"display":"flex","gap":"2px"}, children=[
                                html.Button(b, id={"type":"barsize-btn","index":b},
                                    n_clicks=0,
                                    style={"backgroundColor": C["accent"] if b=="1D" else C["panel"],
                                           "color":           "#fff"       if b=="1D" else C["muted"],
                                           "border":          f"1px solid {C['border']}",
                                           "borderRadius":"3px","padding":"3px 8px",
                                           "fontSize":"11px","cursor":"pointer",
                                           "fontFamily":"monospace","fontWeight":"600"},
                                ) for b in ["5m","15m","1h","4h","1D","1W","1M"]
                            ]),
                            html.Span("│", style={"color":C["border"],"margin":"0 2px"}),
                            # Period buttons — smart range (intraday auto-limits)
                            _label("Range"),
                            html.Div(style={"display":"flex","gap":"2px"}, children=[
                                html.Button(p, id={"type":"period-btn","index":p},
                                    n_clicks=0,
                                    style={"backgroundColor": C["accent"] if p=="1Y" else C["panel"],
                                           "color":           "#fff"       if p=="1Y" else C["muted"],
                                           "border":          f"1px solid {C['border']}",
                                           "borderRadius":"3px","padding":"3px 8px",
                                           "fontSize":"11px","cursor":"pointer",
                                           "fontFamily":"monospace","fontWeight":"600"},
                                ) for p in ["1D","3D","5D","1M","3M","6M","1Y","ALL"]
                            ]),
                            # Stores
                            dcc.Store(id="chart-period",  data="1Y"),
                            dcc.Store(id="chart-barsize", data="1D"),
                        ]),

                        dcc.Loading(type="circle", color=C["accent"], children=[
                            html.Iframe(id="lwc-frame", srcDoc="",
                                style={"width":"100%","height":"490px",
                                       "border":f"1px solid {C['border']}",
                                       "borderRadius":"4px",
                                       "background":C["panel"]}),
                        ]),
                        html.Div(style={"display":"flex","gap":"6px","marginTop":"6px"},
                        children=[
                            html.Div(dcc.Graph(id="rsi-chart",
                                               figure=_empty_fig(),
                                               config={"displayModeBar":False}),
                                     style={"flex":"1"}),
                            html.Div(dcc.Graph(id="adx-chart",
                                               figure=_empty_fig(),
                                               config={"displayModeBar":False}),
                                     style={"flex":"1"}),
                            html.Div(dcc.Graph(id="radar-chart",
                                               figure=_empty_fig(240),
                                               config={"displayModeBar":False}),
                                     style={"width":"220px"}),
                        ]),
                    ]),

                    # ── PATTERN TAB ────────────────────────────────────────
                    html.Div(id="pattern-panel", style={"display":"none"}, children=[
                        html.Img(id="pattern-img", src="",
                                 style={"width":"100%","borderRadius":"4px",
                                        "display":"none"}),
                        html.Div(id="pattern-msg",
                                 style={"color":C["muted"],"padding":"30px",
                                        "fontSize":"12px"}),
                    ]),

                    # ── HISTORY TAB ────────────────────────────────────────
                    html.Div(id="history-panel", style={"display":"none"}, children=[
                        html.Div(id="history-content"),
                    ]),

                    # ── BACKTEST TAB ───────────────────────────────────────
                    html.Div(id="backtest-panel", style={"display":"none"}, children=[

                        # Controls bar
                        html.Div(style={
                            "display":"flex","gap":"12px","alignItems":"center",
                            "flexWrap":"wrap","padding":"10px 0 12px",
                            "borderBottom":f"1px solid {C['border']}","marginBottom":"12px",
                        }, children=[
                            html.Div(style={"display":"flex","flexDirection":"column","gap":"2px"}, children=[
                                _label("Min Score"),
                                dcc.Slider(id="bt-score", min=30, max=80, step=5, value=50,
                                           marks={i:str(i) for i in range(30,85,10)},
                                           tooltip={"always_visible":False},
                                           updatemode="mouseup",
                                           style={"width":"180px"}),
                            ]),
                            html.Div(style={"display":"flex","flexDirection":"column","gap":"2px"}, children=[
                                _label("Capital ($)"),
                                dcc.Input(id="bt-capital", type="number", value=100000,
                                          step=10000, debounce=True,
                                          style={"backgroundColor":C["bg"],"color":C["text"],
                                                 "border":f"1px solid {C['border']}",
                                                 "borderRadius":"4px","padding":"3px 8px",
                                                 "fontSize":"11px","width":"110px"}),
                            ]),
                            html.Div(style={"display":"flex","flexDirection":"column","gap":"2px"}, children=[
                                _label("From Date"),
                                dcc.Input(id="bt-from", type="text", value="", debounce=True,
                                          placeholder="YYYY-MM-DD",
                                          style={"backgroundColor":C["bg"],"color":C["text"],
                                                 "border":f"1px solid {C['border']}",
                                                 "borderRadius":"4px","padding":"3px 8px",
                                                 "fontSize":"11px","width":"110px"}),
                            ]),
                            html.Div(style={"display":"flex","flexDirection":"column","gap":"2px"}, children=[
                                _label("Tickers"),
                                dcc.Input(id="bt-tickers", type="text", value="", debounce=True,
                                          placeholder="all  or  AAPL XOM",
                                          style={"backgroundColor":C["bg"],"color":C["text"],
                                                 "border":f"1px solid {C['border']}",
                                                 "borderRadius":"4px","padding":"3px 8px",
                                                 "fontSize":"11px","width":"140px"}),
                            ]),
                            html.Button("▶  Run Backtest",
                                id="bt-run", n_clicks=0,
                                style={"backgroundColor":"#f0a500","color":"#0d1117",
                                       "border":"none","borderRadius":"4px",
                                       "padding":"6px 16px","fontSize":"12px",
                                       "fontWeight":"bold","cursor":"pointer",
                                       "fontFamily":"monospace","marginTop":"14px"}),
                            dcc.Store(id="bt-results", data={}),
                        ]),

                        # Results area
                        dcc.Loading(id="bt-loading", type="circle", color="#f0a500",
                            children=[html.Div(id="bt-output")]),
                    ]),
                ]),
            ]),
        ]),
    ])


def _register_callbacks(app, cfg: dict, data_store: dict):

    # ── Pull fresh state every 30s ────────────────────────────────────────────
    @app.callback(
        Output("state-store", "data"),
        Input("refresh", "n_intervals"),
    )
    def refresh_state(_):
        return StateManager.read()

    # ── Regime banner ─────────────────────────────────────────────────────────
    @app.callback(
        Output("regime-banner", "children"),
        Input("state-store", "data"),
    )
    def update_regime(state):
        if not state:
            return "Waiting for bot..."
        r      = state.get("regime", {})
        trend  = r.get("trend", "neutral")
        vix    = r.get("vix", 0)
        mult   = r.get("size_mult", 1.0)
        sess   = state.get("market_status", "closed")
        window = state.get("trading_window", False)
        mode   = state.get("mode", "paper").upper()
        updated= state.get("last_updated","")[:16].replace("T"," ")

        sess_labels = {
            "pre_market":     ("PRE-MARKET",     C["muted"]),
            "avoid_open":     ("AVOID — OPEN",   C["bear"]),
            "entry_morning":  ("ENTRY WINDOW ✓", C["bull"]),
            "midday":         ("MIDDAY",         C["muted"]),
            "entry_afternoon":("ENTRY WINDOW ✓", C["bull"]),
            "avoid_close":    ("AVOID — CLOSE",  C["bear"]),
            "market_close":   ("CLOSING",        C["warn"]),
            "closed":         ("CLOSED",         C["muted"]),
        }
        slabel, scol = sess_labels.get(sess, ("UNKNOWN", C["muted"]))

        return html.Div(style={"display":"flex","gap":"20px","alignItems":"center",
                               "flexWrap":"wrap"}, children=[
            html.Div([
                html.Span("REGIME  ", style={"color":C["muted"],"fontSize":"10px"}),
                html.Span(trend.upper(),
                          style={"color":REGIME_C.get(trend,C["muted"]),
                                 "fontSize":"16px","fontWeight":"bold"}),
                html.Span(f"  VIX {vix:.1f}  ×{mult:.1f}",
                          style={"color":C["muted"],"fontSize":"12px"}),
            ]),
            html.Div([
                html.Span("SESSION  ", style={"color":C["muted"],"fontSize":"10px"}),
                html.Span(slabel, style={"color":scol,"fontSize":"14px",
                                         "fontWeight":"bold"}),
            ]),
            html.Div([
                html.Span("MODE  ", style={"color":C["muted"],"fontSize":"10px"}),
                html.Span(mode,
                          style={"color":C["warn"] if mode=="LIVE" else C["accent"],
                                 "fontSize":"14px","fontWeight":"bold"}),
            ]),
            html.Div(f"Updated {updated}",
                     style={"color":C["muted"],"fontSize":"10px",
                            "marginLeft":"auto"}),
        ])

    # ── Stats bar ─────────────────────────────────────────────────────────────
    @app.callback(Output("stats-bar","children"), Input("state-store","data"))
    def update_stats(state):
        if not state:
            return ""
        s     = state.get("session_stats", {})
        ls    = state.get("last_scan", {})
        pnl   = s.get("pnl_today", 0)
        total = s.get("total_pnl", 0)
        return html.Div(style={"display":"flex","gap":"16px","flexWrap":"wrap",
                                "marginTop":"6px"}, children=[
            _stat("Today Trades",   str(s.get("trades_today",0))),
            _stat("Today Wins",     str(s.get("wins_today",0)),    C["bull"]),
            _stat("Today Losses",   str(s.get("losses_today",0)),  C["bear"]),
            _stat("Open",           str(s.get("open_today",0)),    C["accent"]),
            _stat("Today P&L",      f"${pnl:+.2f}",
                  C["bull"] if pnl >= 0 else C["bear"]),
            _stat("Total P&L",      f"${total:+.2f}",
                  C["bull"] if total >= 0 else C["bear"]),
            _stat("Win Rate",       f"{s.get('win_rate',0):.1f}%", C["bull"]),
            _stat("Watchlist",
                  str(ls.get("watchlist", len(state.get("watchlist",[])))),
                  C["muted"]),
            _stat("Weekly scan",
                  (ls.get("weekly","—") or "—")[:10],    C["muted"]),
            _stat("Daily scan",
                  (ls.get("daily","—")  or "—")[:10],    C["muted"]),
        ])

    # ── Watchlist table ───────────────────────────────────────────────────────
    @app.callback(
        Output("watchlist-table", "data"),
        Output("watchlist-table", "selected_rows"),
        Input("state-store",  "data"),
        Input("pat-filter",   "value"),
        Input("score-filter", "value"),
        Input("ticker-search","value"),
    )
    def update_table(state, pat, min_score, search):
        rows = (state or {}).get("watchlist", [])
        if pat != "all":
            rows = [r for r in rows if r.get("pattern") == pat]
        rows = [r for r in rows if float(r.get("score", 0)) >= min_score]

        sel = [0]   # default: select first row
        if search and len(search) >= 1:
            q      = search.upper().strip()
            exact  = [r for r in rows if r.get("ticker","").upper() == q]
            prefix = [r for r in rows if r.get("ticker","").upper().startswith(q)
                      and r not in exact]
            rest   = [r for r in rows if r not in exact and r not in prefix
                      and q in r.get("ticker","").upper()]
            rows   = exact + prefix + rest
            # Auto-highlight first match
            if rows:
                sel = [0]

        return rows, sel

    # ── Open positions (clickable cards) ────────────────────────────────────────
    @app.callback(Output("positions-panel","children"), Input("state-store","data"))
    def update_positions(state):
        positions = (state or {}).get("open_positions", [])
        if not positions:
            return html.Div("No open positions",
                           style={"color":C["muted"],"fontSize":"11px"})
        items = []
        for p in positions:
            ticker = p.get("ticker","")
            pnl    = p.get("unrealized_pnl", 0)
            pnl_r  = p.get("unrealized_r",   0)
            pct    = p.get("unrealized_pct",  0)
            col    = C["bull"] if pnl >= 0 else C["bear"]
            entry  = p.get("fill_price",    0)
            stop   = p.get("stop",          0)
            target = p.get("target",        0)
            shares = p.get("shares",        0)
            cur    = p.get("current_price", 0)
            risk_r = (entry - stop)  if entry > stop  else 0
            dist_t = (target - cur)  if target > cur  else 0
            dist_s = (cur - stop)    if cur > stop     else 0
            # Progress bar: how far between entry and target
            progress = 0.0
            if target > entry > 0:
                progress = max(0.0, min(1.0, (cur - entry) / (target - entry)))
            items.append(html.Div(
                id={"type": "pos-card", "index": ticker},
                n_clicks=0,
                style={
                    "padding":"8px 10px",
                    "marginBottom":"6px",
                    "borderRadius":"5px",
                    "border":f"1px solid {C['border']}",
                    "backgroundColor":"#1c2128",
                    "cursor":"pointer",
                    "transition":"border-color 0.15s",
                },
                children=[
                    # Row 1: ticker + pattern + live P&L
                    html.Div(style={"display":"flex","justifyContent":"space-between",
                                    "alignItems":"center","marginBottom":"4px"},
                    children=[
                        html.Span(ticker,
                                  style={"fontWeight":"bold","fontSize":"13px",
                                         "color":C["text"]}),
                        html.Span(p.get("pattern",""),
                                  style={"color":C["muted"],"fontSize":"10px"}),
                        html.Span(f"{pnl:+.2f}  ({pnl_r:+.2f}R)",
                                  style={"color":col,"fontWeight":"bold",
                                         "fontSize":"12px"}),
                    ]),
                    # Row 2: entry / stop / target levels
                    html.Div(style={"display":"flex","gap":"12px","fontSize":"10px",
                                    "marginBottom":"5px"},
                    children=[
                        html.Span([html.Span("Entry ", style={"color":C["muted"]}),
                                   html.Span(f"${entry:.2f}", style={"color":C["entry"]})]),
                        html.Span([html.Span("Stop ",  style={"color":C["muted"]}),
                                   html.Span(f"${stop:.2f}",  style={"color":C["stop"]})]),
                        html.Span([html.Span("Target ",style={"color":C["muted"]}),
                                   html.Span(f"${target:.2f}",style={"color":C["target"]})]),
                        html.Span([html.Span("Now ",   style={"color":C["muted"]}),
                                   html.Span(f"${cur:.2f}",   style={"color":C["text"]})]),
                        html.Span([html.Span("Shares ",style={"color":C["muted"]}),
                                   html.Span(str(shares),     style={"color":C["text"]})]),
                    ]),
                    # Row 3: progress bar (entry → target)
                    html.Div(style={"position":"relative","height":"6px",
                                    "borderRadius":"3px",
                                    "backgroundColor":C["border"]},
                    children=[
                        html.Div(style={
                            "position":"absolute","left":"0","top":"0","bottom":"0",
                            "width":f"{progress*100:.1f}%",
                            "borderRadius":"3px",
                            "backgroundColor": col,
                            "transition":"width 0.5s",
                        }),
                        # Entry marker at 0%
                        html.Div(style={"position":"absolute","left":"0","top":"-2px",
                                        "width":"2px","height":"10px",
                                        "backgroundColor":C["entry"]}),
                        # Target marker at 100%
                        html.Div(style={"position":"absolute","right":"0","top":"-2px",
                                        "width":"2px","height":"10px",
                                        "backgroundColor":C["target"]}),
                    ]),
                    # Row 4: distance labels
                    html.Div(style={"display":"flex","justifyContent":"space-between",
                                    "fontSize":"9px","color":C["muted"],"marginTop":"2px"},
                    children=[
                        html.Span(f"▼ ${dist_s:.2f} to stop"),
                        html.Span(f"{progress*100:.0f}% to target"),
                        html.Span(f"▲ ${dist_t:.2f} to target"),
                    ]),
                ]
            ))
        return items

    # ── Activity feed ─────────────────────────────────────────────────────────
    @app.callback(Output("activity-feed","children"), Input("state-store","data"))
    def update_feed(state):
        fills = (state or {}).get("recent_fills", [])
        if not fills:
            return html.Div("No recent activity",
                           style={"color":C["muted"],"fontSize":"11px"})
        items = []
        for f in fills[:12]:
            event = f.get("event","")
            cols  = {"entry":C["bull"],"tp":C["accent"],"sl":C["bear"]}
            col   = cols.get(event, C["muted"])
            pnl   = f.get("pnl_usd")
            pnl_s = f" ${pnl:+.2f}" if pnl is not None else ""
            items.append(html.Div(
                f"{f.get('time','')[11:16]}  "
                f"{f.get('ticker','')}  {event.upper()}  "
                f"${f.get('price',0):.2f}{pnl_s}",
                style={"color":col,"fontSize":"10px","padding":"2px 0",
                       "borderBottom":f"1px solid {C['border']}"}
            ))
        return items

    # ── selected-ticker store ─────────────────────────────────────────────────
    # Three ways to select a ticker:
    #   1. Click a row in the watchlist table
    #   2. Click an open-position card
    #   3. Type in the search bar and press Enter
    from dash import ctx, ALL

    @app.callback(
        Output("selected-ticker", "data"),
        Input("watchlist-table", "selected_rows"),
        Input("watchlist-table", "data"),
        Input({"type": "pos-card", "index": ALL}, "n_clicks"),
        Input("ticker-search", "value"),
        prevent_initial_call=True,
    )
    def set_selected_ticker(sel, table_data, pos_clicks, search_val):
        import re
        triggered = ctx.triggered_id

        # Position card clicked
        if isinstance(triggered, dict) and triggered.get("type") == "pos-card":
            return triggered["index"]

        # Search bar typed
        if triggered == "ticker-search" and search_val:
            q = search_val.upper().strip()
            if table_data:
                # Exact match in watchlist → select immediately
                exact = [r for r in table_data if r.get("ticker","").upper() == q]
                if exact:
                    return exact[0]["ticker"]
                # Prefix filtered down to 1 result → select it
                partial = [r for r in table_data
                           if r.get("ticker","").upper().startswith(q)]
                if len(partial) == 1:
                    return partial[0]["ticker"]
            # Valid ticker format but not in watchlist → try IB fetch
            if re.match(r'^[A-Z]{1,5}$', q):
                return q
            return dash.no_update

        # Watchlist row clicked
        if sel and table_data:
            return table_data[sel[0]].get("ticker", "")

        return ""

    # ── Ticker title ──────────────────────────────────────────────────────────
    @app.callback(
        Output("ticker-title","children"),
        Input("selected-ticker", "data"),
        Input("state-store",     "data"),
    )
    def update_ticker_title(ticker, state):
        if not ticker:
            return "Select a ticker from the watchlist or click an open position"
        # Look in watchlist first, then open positions
        wl  = (state or {}).get("watchlist",        [])
        pos = (state or {}).get("open_positions",    [])
        row = next((r for r in wl  if r.get("ticker") == ticker), None)
        pos_row = next((r for r in pos if r.get("ticker") == ticker), None)

        if row:
            pnl_s = ""
            if pos_row:
                pnl = pos_row.get("unrealized_pnl", 0)
                col = "🟢" if pnl >= 0 else "🔴"
                pnl_s = f"  {col} P&L ${pnl:+.2f} ({pos_row.get('unrealized_r',0):+.2f}R)"
            return (f"{row.get('ticker','')}  ·  {row.get('pattern','').upper()}  ·  "
                    f"Score {row.get('score',0):.0f}  ·  R:R {row.get('rr',0):.1f}:1  ·  "
                    f"Entry ${row.get('entry',0):.2f}  "
                    f"Stop ${row.get('stop',0):.2f}  "
                    f"Target ${row.get('target',0):.2f}"
                    f"{pnl_s}")
        if pos_row:
            pnl = pos_row.get("unrealized_pnl", 0)
            return (f"{ticker}  ·  {pos_row.get('pattern','').upper()}  ·  OPEN POSITION  ·  "
                    f"Entry ${pos_row.get('fill_price',0):.2f}  "
                    f"Stop ${pos_row.get('stop',0):.2f}  "
                    f"Target ${pos_row.get('target',0):.2f}  ·  "
                    f"P&L ${pnl:+.2f} ({pos_row.get('unrealized_r',0):+.2f}R)")
        return f"{ticker}  —  not in current watchlist or positions" 

    # ── Panel visibility — one callback per panel (Dash 4 compatibility) ───────
    @app.callback(
        Output("strategy-panel", "style"),
        Input("detail-tabs", "value"),
    )
    def show_strategy(tab):
        return {"display":"block"} if tab == "strategy" else {"display":"none"}

    @app.callback(
        Output("pattern-panel", "style"),
        Input("detail-tabs", "value"),
    )
    def show_pattern(tab):
        return {"display":"block"} if tab == "pattern" else {"display":"none"}

    @app.callback(
        Output("history-panel", "style"),
        Input("detail-tabs", "value"),
    )
    def show_history(tab):
        return {"display":"block"} if tab == "history" else {"display":"none"}

    @app.callback(
        Output("backtest-panel", "style"),
        Input("detail-tabs", "value"),
    )
    def show_backtest(tab):
        return {"display":"block"} if tab == "backtest" else {"display":"none"}

    @app.callback(
        Output("bt-output", "children"),
        Input("bt-run",     "n_clicks"),
        State("bt-score",   "value"),
        State("bt-capital", "value"),
        State("bt-from",    "value"),
        State("bt-tickers", "value"),
        prevent_initial_call=True,
    )
    def run_bt(n_clicks, score, capital, from_str, tickers_str):
        if not n_clicks:
            raise dash.exceptions.PreventUpdate
        from datetime import date as _date
        from backtest import run_backtest, OUT_DIR

        tickers = [t.strip().upper() for t in tickers_str.split()] if tickers_str else None
        from_dt = None
        if from_str:
            try: from_dt = _date.fromisoformat(from_str.strip())
            except ValueError: pass

        bt_cfg = {**cfg, "min_score_display": float(score or 50)}
        stats  = run_backtest(
            tickers    = tickers,
            from_date  = from_dt,
            cfg        = bt_cfg,
            capital    = float(capital or 100_000),
        )

        if not stats:
            return html.Div("No trades generated. Try lowering Min Score or checking ohlcv_cache/.",
                            style={"color":C["muted"],"padding":"20px","fontFamily":"monospace"})

        report_path = OUT_DIR / "report.html"
        report_html = report_path.read_text() if report_path.exists() else ""

        wr   = stats.get("win_rate_pct", 0)
        tr   = stats.get("total_r", 0)
        pf   = stats.get("profit_factor", 0)
        dd   = stats.get("max_drawdown_pct", 0)
        cagr = stats.get("cagr_pct", 0)
        pnl  = stats.get("total_pnl_usd", 0)
        n    = stats.get("total_trades", 0)

        def chip(label, val, color):
            return html.Span([
                html.Span(label, style={"fontSize":"9px","opacity":"0.65","marginRight":"3px"}),
                html.Span(val,   style={"fontWeight":"bold","fontSize":"13px"}),
            ], style={
                "display":"inline-flex","alignItems":"center","padding":"3px 10px",
                "borderRadius":"4px","marginRight":"6px","fontFamily":"monospace",
                "border":f"1px solid {color}44","backgroundColor":f"{color}18","color":color,
            })

        summary = html.Div(style={"display":"flex","flexWrap":"wrap","gap":"4px","marginBottom":"10px"}, children=[
            chip("TRADES",  str(n),                 "#e6edf3"),
            chip("WIN",     f"{wr}%",               "#26a69a" if wr>50  else "#ef5350"),
            chip("TOTAL R", f"{tr:+.1f}R",          "#26a69a" if tr>0   else "#ef5350"),
            chip("PF",      f"{pf:.2f}",            "#26a69a" if pf>1.5 else "#f0a500"),
            chip("CAGR",    f"{cagr:+.1f}%",        "#26a69a" if cagr>0 else "#ef5350"),
            chip("MAX DD",  f"{dd:.1f}%",           "#ef5350"),
            chip("P&L",     f"${pnl:+,.0f}",        "#26a69a" if pnl>0  else "#ef5350"),
        ])

        return html.Div([
            summary,
            html.Iframe(srcDoc=report_html,
                        style={"width":"100%","height":"660px",
                               "border":f"1px solid {C['border']}",
                               "borderRadius":"4px"}),
        ])

    # ── Strategy chart — split into separate callbacks (Dash 4 compatibility) ──

    def _get_df_and_row(ticker, state):
        """Shared helper: returns (df, row, full_row) for a ticker string.
        
        Priority order for row data:
          1. Open position  (has live fill_price, stop, target)
          2. Watchlist row  (has score, pattern, entry, stop, target)
          3. Empty dict     (ticker typed in search bar, not in watchlist)
        """
        if not ticker:
            return pd.DataFrame(), {}, {}

        wl  = (state or {}).get("watchlist",     [])
        pos = (state or {}).get("open_positions", [])

        wl_row  = next((r for r in wl  if r.get("ticker") == ticker), {})
        pos_row = next((r for r in pos if r.get("ticker") == ticker), {})

        # Merge: position levels override watchlist levels when open
        row = {**wl_row}
        if pos_row:
            # Use actual fill price as entry for chart lines
            row["entry"]  = pos_row.get("fill_price", row.get("entry",  0))
            row["stop"]   = pos_row.get("stop",       row.get("stop",   0))
            row["target"] = pos_row.get("target",     row.get("target", 0))

        # data_store keyed by "TICKER:barsize" so intraday doesn't evict daily
        cache_key = ticker  # barsize injected at call site via kwarg
        df = data_store.get(cache_key, pd.DataFrame())
        if df.empty:
            df = _fetch_ticker(ticker, cfg)
            if not df.empty:
                data_store[cache_key] = df
        return df, row, row

    def _get_df_intraday(ticker, state, barsize):
        """Fetch intraday data, using separate data_store key per barsize."""
        if not ticker:
            return pd.DataFrame(), {}, {}
        cache_key = f"{ticker}:{barsize}"
        df = data_store.get(cache_key, pd.DataFrame())
        if df.empty:
            df = _fetch_ticker(ticker, cfg, barsize=barsize)
            if not df.empty:
                data_store[cache_key] = df
        # Get row metadata same as daily
        wl  = (state or {}).get("watchlist",     [])
        pos = (state or {}).get("open_positions", [])
        wl_row  = next((r for r in wl  if r.get("ticker") == ticker), {})
        pos_row = next((r for r in pos if r.get("ticker") == ticker), {})
        row = {**wl_row}
        if pos_row:
            row["entry"]  = pos_row.get("fill_price", row.get("entry",  0))
            row["stop"]   = pos_row.get("stop",       row.get("stop",   0))
            row["target"] = pos_row.get("target",     row.get("target", 0))
        return df, row, row

    # ── Period and bar-size button state ─────────────────────────────────────
    from dash import ALL as _ALL, ctx as _ctx

    # Max sensible period for each bar size (IB data limits + readability)
    _PERIOD_LIMITS = {
        "5m":  ["1D","3D","5D"],
        "15m": ["1D","3D","5D","1M"],
        "1h":  ["1D","3D","5D","1M"],
        "4h":  ["3D","5D","1M","3M"],
        "1D":  ["1M","3M","6M","1Y","ALL"],
        "1W":  ["3M","6M","1Y","ALL"],
        "1M":  ["6M","1Y","ALL"],
    }
    _DEFAULT_PERIOD = {
        "5m":"5D","15m":"5D","1h":"1M","4h":"3M",
        "1D":"1Y","1W":"1Y","1M":"ALL",
    }
    _ALL_PERIODS  = ["1D","3D","5D","1M","3M","6M","1Y","ALL"]
    _ALL_BARSIZES = ["5m","15m","1h","4h","1D","1W","1M"]

    @app.callback(
        Output("chart-barsize", "data"),
        Output("chart-period",  "data"),
        Output({"type":"barsize-btn","index":_ALL}, "style"),
        Output({"type":"period-btn", "index":_ALL}, "style"),
        Input({"type":"barsize-btn","index":_ALL}, "n_clicks"),
        Input({"type":"period-btn", "index":_ALL}, "n_clicks"),
        Input("chart-barsize", "data"),
        Input("chart-period",  "data"),
    )
    def set_timeframe(bs_clicks, p_clicks, cur_bs, cur_period):
        triggered = _ctx.triggered_id
        bs     = cur_bs     or "1D"
        period = cur_period or "1Y"

        if isinstance(triggered, dict):
            if triggered.get("type") == "barsize-btn":
                bs = triggered["index"]
                # Auto-reset period to sensible default for this bar size
                allowed = _PERIOD_LIMITS.get(bs, _ALL_PERIODS)
                if period not in allowed:
                    period = _DEFAULT_PERIOD.get(bs, allowed[-1])
            elif triggered.get("type") == "period-btn":
                period = triggered["index"]

        allowed  = _PERIOD_LIMITS.get(bs, _ALL_PERIODS)
        btn_base = {"border":f"1px solid {C['border']}","borderRadius":"3px",
                    "padding":"3px 8px","fontSize":"11px","cursor":"pointer",
                    "fontFamily":"monospace","fontWeight":"600"}

        bs_styles = []
        for b in _ALL_BARSIZES:
            bs_styles.append({**btn_base,
                "backgroundColor": C["accent"] if b==bs  else C["panel"],
                "color":           "#fff"       if b==bs  else C["muted"],
            })

        p_styles = []
        for p in _ALL_PERIODS:
            active    = p == period
            available = p in allowed
            p_styles.append({**btn_base,
                "backgroundColor": C["accent"]                    if active    else C["panel"],
                "color":           "#fff"                          if active    else
                                   C["muted"]                      if available else C["border"],
                "cursor":          "pointer"                       if available else "not-allowed",
                "opacity":         "1"                             if available else "0.35",
            })

        return bs, period, bs_styles, p_styles

    @app.callback(
        Output("lwc-frame", "srcDoc"),
        Input("selected-ticker", "data"),
        Input("state-store",     "data"),
        Input("chart-period",    "data"),
        Input("chart-barsize",   "data"),
    )
    def update_lwc(ticker, state, period, barsize):
        barsize = barsize or "1D"
        period  = period  or "1Y"
        intraday = barsize in ("5m","15m","1h","4h")
        if intraday:
            df, row, _ = _get_df_intraday(ticker, state, barsize)
        else:
            df, row, _ = _get_df_and_row(ticker, state)
            df = _resample_df(df, barsize)
        if df.empty:
            return _no_data_html(ticker or "")
        df = _slice_period(df, period, barsize)
        pos = (state or {}).get("open_positions", [])
        is_open = any(p.get("ticker") == ticker for p in pos)
        suffix  = "  ●OPEN" if is_open else ""
        return _lwc_html(df, row,
                         f"{ticker} · {row.get('pattern','').upper()} · {barsize}{suffix}")

    @app.callback(
        Output("rsi-chart", "figure"),
        Input("selected-ticker", "data"),
        Input("state-store",     "data"),
        Input("chart-period",    "data"),
        Input("chart-barsize",   "data"),
    )
    def update_rsi(ticker, state, period, barsize):
        barsize = barsize or "1D"
        intraday = barsize in ("5m","15m","1h","4h")
        df, _, _ = _get_df_intraday(ticker, state, barsize) if intraday else _get_df_and_row(ticker, state)
        if df.empty: return _empty_fig()
        if not intraday: df = _resample_df(df, barsize)
        df = _slice_period(df, period or "1Y", barsize)
        return _rsi_fig(df)

    @app.callback(
        Output("adx-chart", "figure"),
        Input("selected-ticker", "data"),
        Input("state-store",     "data"),
        Input("chart-period",    "data"),
        Input("chart-barsize",   "data"),
    )
    def update_adx(ticker, state, period, barsize):
        barsize = barsize or "1D"
        intraday = barsize in ("5m","15m","1h","4h")
        df, _, _ = _get_df_intraday(ticker, state, barsize) if intraday else _get_df_and_row(ticker, state)
        if df.empty: return _empty_fig()
        if not intraday: df = _resample_df(df, barsize)
        df = _slice_period(df, period or "1Y", barsize)
        return _adx_fig(df)

    @app.callback(
        Output("radar-chart", "figure"),
        Input("selected-ticker", "data"),
        Input("state-store",     "data"),
    )
    def update_radar(ticker, state):
        _, _, full = _get_df_and_row(ticker, state)
        return _radar_fig(full) if full else _empty_fig(240)

    # ── Pattern tab ───────────────────────────────────────────────────────────
    def _find_pattern_b64(ticker):
        hist_root = Path(cfg.get("order_history_dir","order_history"))
        if not hist_root.exists():
            return ""
        for day_dir in sorted(hist_root.iterdir(), reverse=True):
            if not day_dir.is_dir():
                continue
            for trade_dir in sorted(day_dir.iterdir(), reverse=True):
                if trade_dir.name.startswith(ticker + "_"):
                    b64 = _img_b64(trade_dir / "01b_pattern.png")
                    if b64:
                        return b64
        return ""

    @app.callback(
        Output("pattern-img", "src"),
        Input("selected-ticker", "data"),
        Input("detail-tabs",     "value"),
    )
    def update_pattern_src(ticker, tab):
        if tab != "pattern" or not ticker:
            return ""
        b64 = _find_pattern_b64(ticker)
        return f"data:image/png;base64,{b64}" if b64 else ""

    @app.callback(
        Output("pattern-img", "style"),
        Input("selected-ticker", "data"),
        Input("detail-tabs",     "value"),
    )
    def update_pattern_style(ticker, tab):
        if tab != "pattern" or not ticker:
            return {"display":"none"}
        b64 = _find_pattern_b64(ticker)
        return {"width":"100%","borderRadius":"4px"} if b64 else {"display":"none"}

    @app.callback(
        Output("pattern-msg", "children"),
        Input("selected-ticker", "data"),
        Input("detail-tabs",     "value"),
    )
    def update_pattern_msg(ticker, tab):
        if tab != "pattern" or not ticker:
            return ""
        b64 = _find_pattern_b64(ticker)
        return "" if b64 else "No pattern chart yet — appears after first bot entry."

    # ── History tab ───────────────────────────────────────────────────────────
    @app.callback(
        Output("history-content", "children"),
        Input("selected-ticker", "data"),
        Input("detail-tabs",     "value"),
    )
    def update_history(ticker, tab):
        if tab != "history" or not ticker:
            return ""
        ticker = ticker  # already a string
        master = Path(cfg.get("order_history_dir","order_history"))/"trade_log.csv"
        if not master.exists():
            return html.Div("No trade history yet.",
                           style={"color":C["muted"],"padding":"20px"})
        try:
            df_log = pd.read_csv(master)
            if "ticker" in df_log.columns:
                df_log = df_log[df_log["ticker"] == ticker]
        except Exception:
            return html.Div("Could not load trade log.",
                           style={"color":C["muted"],"padding":"20px"})
        if df_log.empty:
            return html.Div(f"No closed trades for {ticker} yet.",
                           style={"color":C["muted"],"padding":"20px"})
        cols = [c for c in ["fill_time","exit_time","exit_event","fill_price",
                             "exit_price","pnl_usd","pnl_r","post_verdict",
                             "pattern","regime","score"]
                if c in df_log.columns]
        return html.Div([
            dash_table.DataTable(
                data=df_log[cols].tail(20).to_dict("records"),
                columns=[{"name":c.replace("_"," ").upper(),"id":c} for c in cols],
                style_table={"overflowX":"auto"},
                style_cell={"backgroundColor":C["panel"],"color":C["text"],
                            "border":f"1px solid {C['border']}",
                            "padding":"5px 8px","fontSize":"10px"},
                style_header={"backgroundColor":C["bg"],"color":C["muted"],
                              "fontSize":"9px","fontWeight":"bold"},
                style_data_conditional=[
                    {"if":{"filter_query":'{exit_event} = "tp"'},"color":C["bull"]},
                    {"if":{"filter_query":'{exit_event} = "sl"'},"color":C["bear"]},
                    {"if":{"filter_query":'{post_verdict} = "premature_sl"'},
                     "color":C["warn"]},
                ],
            ),
            html.Div(_load_screenshots(ticker, cfg), style={"marginTop":"10px"}),
        ])


def _load_screenshots(ticker: str, cfg: dict) -> list:
    """Load all screenshots for a ticker from order_history/."""
    hist_root = Path(cfg.get("order_history_dir","order_history"))
    items     = []
    for day_dir in sorted(hist_root.iterdir(), reverse=True):
        if not day_dir.is_dir():
            continue
        for trade_dir in sorted(day_dir.iterdir(), reverse=True):
            if not trade_dir.name.startswith(ticker + "_"):
                continue
            pngs = sorted(trade_dir.glob("*.png"))
            if not pngs:
                continue
            items.append(html.Div([
                html.Div(f"{day_dir.name}  /  {trade_dir.name}",
                         style={"color":C["muted"],"fontSize":"10px",
                                "margin":"10px 0 4px"}),
                html.Div(style={"display":"flex","gap":"6px","flexWrap":"wrap"},
                children=[
                    html.Img(
                        src=f"data:image/png;base64,{_img_b64(p)}",
                        title=p.stem,
                        style={"width":"48%","borderRadius":"4px",
                               "border":f"1px solid {C['border']}"},
                    ) for p in pngs if _img_b64(p)
                ]),
            ]))
    return items if items else [
        html.Div("No screenshots yet.",
                 style={"color":C["muted"],"fontSize":"11px"})
    ]


def _card(**kwargs):
    children = kwargs.pop("children", [])
    id_      = kwargs.pop("id", None)
    style    = kwargs.pop("style", {})
    s = {"backgroundColor":C["panel"],"borderRadius":"6px",
         "border":f"1px solid {C['border']}","padding":"10px", **style}
    # Only pass id if it's actually set — Dash 4 rejects id=None
    extra = {"id": id_} if id_ is not None else {}
    return html.Div(children, style=s, **extra)