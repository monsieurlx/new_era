"""
backtest.py — Walk-forward portfolio backtester.

Uses the EXACT same pipeline as live trading:
    indicators.calc_all → patterns.detect_best_pattern → risk.compute_risk → scorer.score_ticker

Key design decisions:
  - Portfolio-level: max N concurrent positions (mirrors bot_max_open_trades)
  - Running equity: position sizing off current account balance, not fixed capital
  - No look-ahead: signal bar i → entry at bar i+1 open + slippage
  - Realistic exits: intrabar TP/SL check (high/low, not just close)
  - Cooldown: no re-entry same ticker within N bars of last exit
  - Regime filter: SPY 50-bar SMA for bull/neutral/bear labelling

Usage (CLI):
    python backtest.py                          # all tickers in ohlcv_cache/
    python backtest.py --tickers AAPL XOM NVDA  # specific tickers
    python backtest.py --from 2024-01-01        # start date
    python backtest.py --score 55               # override min_score_display
    python backtest.py --report                 # open HTML report after run

Outputs → backtest_results/
    trades.csv      every simulated trade
    equity.csv      daily equity curve
    summary.json    aggregate stats (by pattern / regime / exit reason)
    report.html     self-contained interactive HTML report
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import CONFIG
from indicators import calc_all
from patterns import detect_best_pattern
from risk import compute_risk
from scorer import score_ticker

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

OUT_DIR = Path("backtest_results")
OUT_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class BT:
    """One simulated trade — all fields set at entry, exits filled when closed."""
    __slots__ = [
        "ticker","pattern","score","regime","rr",
        "entry_date","entry_bar","entry_price",
        "stop_price","target_price","shares","risk_usd",
        "exit_date","exit_price","exit_reason",
        "pnl_usd","pnl_pct","pnl_r",
        "bars_held","mae","mfe",        # max adverse / max favorable excursion
    ]
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)
        # filled at exit
        self.exit_date   = None
        self.exit_price  = 0.0
        self.exit_reason = ""
        self.pnl_usd     = 0.0
        self.pnl_pct     = 0.0
        self.pnl_r       = 0.0
        self.bars_held   = 0
        self.mae         = 0.0
        self.mfe         = 0.0

    def close(self, exit_date, exit_price: float, reason: str):
        self.exit_date   = exit_date
        self.exit_price  = exit_price
        self.exit_reason = reason
        rps              = max(self.entry_price - self.stop_price, 0.01)
        self.pnl_usd     = round((exit_price - self.entry_price) * self.shares, 2)
        self.pnl_pct     = round((exit_price / self.entry_price - 1) * 100, 3)
        self.pnl_r       = round((exit_price - self.entry_price) / rps, 3)

    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _spy_regime(spy_close: pd.Series | None, idx: int) -> str:
    if spy_close is None or idx < 50: return "neutral"
    window = spy_close.iloc[max(0, idx-50):idx]
    cur    = spy_close.iloc[idx]
    return "bull" if cur > window.mean() * 1.01 else ("bear" if cur < window.mean() * 0.99 else "neutral")


def _load_cache(cache_dir: Path) -> dict[str, pd.DataFrame]:
    out = {}
    for f in sorted(cache_dir.glob("*.csv")):
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            if {"open","high","low","close","volume"}.issubset(df.columns):
                df = df.dropna(subset=["close"]).sort_index()
                if len(df) >= 60:
                    out[f.stem] = df
        except Exception as e:
            log.debug(f"Skip {f.name}: {e}")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO SIMULATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_portfolio_backtest(
    data:       dict[str, pd.DataFrame],
    spy_close:  pd.Series | None,
    cfg:        dict,
    capital:    float,
    from_date:  date | None = None,
    min_score:  float | None = None,
) -> tuple[list[BT], pd.DataFrame]:
    """
    True portfolio-level walk-forward simulation.

    All tickers advance together bar-by-bar on a shared calendar.
    At each bar:
      1. Update open positions (check TP/SL/timeout)
      2. If capacity available: scan all tickers for signals, rank by score, enter best

    Returns (trades, equity_df).
    """
    if not data:
        return [], pd.DataFrame()

    min_score  = min_score if min_score is not None else cfg.get("min_score_display", 40)
    max_pos    = cfg.get("bot_max_open_trades", 5)
    max_hold   = cfg.get("backtest_max_hold_bars", 40)
    risk_pct   = cfg.get("risk_per_trade_pct", 1.0) / 100
    slippage   = cfg.get("backtest_slippage_pct", 0.05) / 100
    cooldown   = cfg.get("backtest_cooldown_bars", 5)   # bars before re-entry same ticker
    warmup     = max(cfg.get("sma_slow", 50), 60)

    # Build unified date index across all tickers
    all_dates = sorted(set().union(*[set(df.index) for df in data.values()]))
    if from_date:
        all_dates = [d for d in all_dates if d.date() >= from_date]
    if not all_dates:
        return [], pd.DataFrame()

    # For each ticker, build a lookup: date → bar_index in that ticker's df
    ticker_date_idx: dict[str, dict] = {
        t: {dt: i for i, dt in enumerate(df.index)}
        for t, df in data.items()
    }

    # Pre-compute signals for each ticker at each bar (expensive but honest)
    # We cache the indicator/pattern/score for each bar so the main loop is fast
    log.info(f"Pre-computing signals for {len(data)} tickers ...")
    signals: dict[str, list[dict | None]] = {}   # ticker → list indexed by bar_i

    for ticker, df in data.items():
        sig_list: list[dict | None] = [None] * len(df)
        for i in range(warmup, len(df) - 1):
            df_w = df.iloc[:i+1]
            try:
                inds    = calc_all(df_w, cfg)
                pattern = detect_best_pattern(df_w, inds, cfg)
                if not pattern.get("flag"):
                    continue
                risk    = compute_risk(df_w, inds, pattern, cfg, 1.0)
                sc      = score_ticker(ticker, df_w, inds, pattern, [], {"label":"neutral","size_mult":1.0}, risk, cfg)
                score   = float(sc.get("score", 0))
                if score < min_score:
                    continue
                entry  = float(risk.get("entry",  0))
                stop   = float(risk.get("stop",   0))
                target = float(risk.get("target", 0))
                if not (entry > 0 and stop > 0 and target > entry > stop):
                    continue
                sig_list[i] = {
                    "score":   score,
                    "pattern": pattern.get("type","unknown"),
                    "entry":   entry,
                    "stop":    stop,
                    "target":  target,
                }
            except Exception:
                continue
        signals[ticker] = sig_list
        n_sigs = sum(1 for s in sig_list if s)
        if n_sigs:
            log.debug(f"  {ticker}: {n_sigs} signals")

    total_signals = sum(sum(1 for s in sl if s) for sl in signals.values())
    log.info(f"Signal pre-computation done — {total_signals} raw signals across all tickers")

    # ── Main portfolio loop ───────────────────────────────────────────────────
    equity         = capital
    equity_curve   = []                          # (date, equity)
    open_positions: list[BT] = []                # currently open trades
    closed_trades:  list[BT] = []
    last_exit_bar:  dict[str, int] = {}          # ticker → bar_i of last exit (cooldown)

    for dt in all_dates:
        day_regime = _spy_regime(spy_close, spy_close.index.get_loc(dt) if spy_close is not None and dt in spy_close.index else 0)

        # 1. Update open positions
        still_open = []
        for pos in open_positions:
            df_t  = data[pos.ticker]
            di    = ticker_date_idx[pos.ticker].get(dt)
            if di is None:
                still_open.append(pos)   # no data this day (holiday gap)
                continue

            bar = df_t.iloc[di]
            hi, lo, cl = float(bar["high"]), float(bar["low"]), float(bar["close"])
            pos.bars_held += 1
            move = cl - pos.entry_price
            pos.mae = min(pos.mae, move)
            pos.mfe = max(pos.mfe, move)

            if lo <= pos.stop_price:
                pos.close(dt, pos.stop_price, "stop")
            elif hi >= pos.target_price:
                pos.close(dt, pos.target_price, "target")
            elif pos.bars_held >= max_hold:
                pos.close(dt, cl, "timeout")
            else:
                still_open.append(pos)
                continue

            equity += pos.pnl_usd
            closed_trades.append(pos)
            last_exit_bar[pos.ticker] = di

        open_positions = still_open

        # 2. Scan for new entries if capacity available
        capacity = max_pos - len(open_positions)
        if capacity > 0:
            candidates = []
            active_tickers = {p.ticker for p in open_positions}

            for ticker, df_t in data.items():
                if ticker in active_tickers:
                    continue
                di = ticker_date_idx[ticker].get(dt)
                if di is None or di < warmup or di >= len(df_t) - 1:
                    continue
                # Cooldown check
                if ticker in last_exit_bar and di - last_exit_bar[ticker] < cooldown:
                    continue
                sig = signals[ticker][di]
                if sig is None:
                    continue
                # Check regime — skip bear regime entries (same as live bot)
                if day_regime == "bear" and cfg.get("backtest_skip_bear", True):
                    continue
                candidates.append((ticker, di, sig))

            # Rank by score descending, take top `capacity`
            candidates.sort(key=lambda x: -x[2]["score"])
            for ticker, di, sig in candidates[:capacity]:
                df_t       = data[ticker]
                next_bar   = df_t.iloc[di + 1]
                fill_price = float(next_bar["open"]) * (1 + slippage)
                stop       = sig["stop"]
                target     = sig["target"]
                rps        = fill_price - stop
                if rps <= 0:
                    continue
                shares   = max(1, int((equity * risk_pct) / rps))
                risk_usd = round(rps * shares, 2)

                trade = BT(
                    ticker      = ticker,
                    pattern     = sig["pattern"],
                    score       = sig["score"],
                    regime      = day_regime,
                    rr          = round((target - fill_price) / rps, 2),
                    entry_date  = df_t.index[di + 1],
                    entry_bar   = di + 1,
                    entry_price = round(fill_price, 4),
                    stop_price  = stop,
                    target_price= target,
                    shares      = shares,
                    risk_usd    = risk_usd,
                )
                open_positions.append(trade)

        equity_curve.append({"date": dt, "equity": round(equity, 2)})

    # Close any positions still open at end of data
    for pos in open_positions:
        df_t  = data[pos.ticker]
        last_close = float(df_t.iloc[-1]["close"])
        pos.close(df_t.index[-1], last_close, "end_of_data")
        equity += pos.pnl_usd
        closed_trades.append(pos)

    eq_df = pd.DataFrame(equity_curve)
    if not eq_df.empty:
        eq_df["drawdown_pct"] = (
            (eq_df["equity"] - eq_df["equity"].cummax()) / eq_df["equity"].cummax() * 100
        ).round(3)

    log.info(f"Portfolio simulation complete — {len(closed_trades)} trades closed")
    return closed_trades, eq_df


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_stats(trades: list[BT], capital: float, eq_df: pd.DataFrame) -> dict:
    if not trades:
        return {"total_trades": 0}

    df = pd.DataFrame([t.to_dict() for t in trades])

    wins  = df[df["pnl_r"] > 0]
    loss  = df[df["pnl_r"] <= 0]
    total_r = df["pnl_r"].sum()

    pf = (wins["pnl_r"].sum() / abs(loss["pnl_r"].sum())
          if len(loss) > 0 and loss["pnl_r"].sum() != 0 else 999.0)

    max_dd = eq_df["drawdown_pct"].min() if not eq_df.empty else 0.0
    final_equity = eq_df["equity"].iloc[-1] if not eq_df.empty else capital
    cagr = 0.0
    if not eq_df.empty and len(eq_df) > 1:
        years = (eq_df["date"].iloc[-1] - eq_df["date"].iloc[0]).days / 365.25
        if years > 0.1:
            cagr = round(((final_equity / capital) ** (1 / years) - 1) * 100, 2)

    def _group(col):
        g = df.groupby(col).agg(
            trades=("pnl_r","count"),
            win_rate=("pnl_r", lambda x: round((x>0).mean()*100, 1)),
            avg_r=("pnl_r", lambda x: round(x.mean(), 3)),
            total_r=("pnl_r", lambda x: round(x.sum(), 2)),
        )
        return g.to_dict("index")

    return {
        "total_trades":    len(df),
        "win_rate_pct":    round((df["pnl_r"] > 0).mean() * 100, 1),
        "avg_r":           round(df["pnl_r"].mean(), 3),
        "total_r":         round(total_r, 2),
        "total_pnl_usd":   round(df["pnl_usd"].sum(), 2),
        "profit_factor":   round(pf, 3),
        "avg_win_r":       round(wins["pnl_r"].mean(), 3) if len(wins) else 0,
        "avg_loss_r":      round(loss["pnl_r"].mean(), 3) if len(loss) else 0,
        "max_win_r":       round(df["pnl_r"].max(), 3),
        "max_loss_r":      round(df["pnl_r"].min(), 3),
        "avg_bars_held":   round(df["bars_held"].mean(), 1),
        "max_drawdown_pct":round(max_dd, 2),
        "cagr_pct":        cagr,
        "final_equity":    round(final_equity, 2),
        "starting_capital":capital,
        "by_pattern":      _group("pattern"),
        "by_regime":       _group("regime"),
        "by_exit":         _group("exit_reason"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HTML REPORT  (self-contained, no CDN)
# ═══════════════════════════════════════════════════════════════════════════════

def build_html_report(trades: list[BT], eq_df: pd.DataFrame, stats: dict, cfg: dict) -> str:
    if not trades:
        return "<html><body style='background:#0d1117;color:#8b949e;font-family:monospace;padding:40px'><h2>No trades generated.</h2></body></html>"

    df = pd.DataFrame([t.to_dict() for t in trades])
    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.strftime("%Y-%m-%d")
    df["exit_date"]  = pd.to_datetime(df["exit_date"]).dt.strftime("%Y-%m-%d")

    # ── Equity + drawdown SVG inline charts ──────────────────────────────────
    def _svg(ys, w=700, h=110, color=None):
        ys = [float(v) for v in ys if pd.notna(v)]
        if len(ys) < 2: return ""
        mn, mx = min(ys), max(ys)
        rng    = mx - mn or 1
        color  = color or ("#26a69a" if ys[-1] >= ys[0] else "#ef5350")
        pts    = []
        for i, v in enumerate(ys):
            x = round(i / (len(ys)-1) * w, 1)
            y = round(h - (v - mn) / rng * (h - 4) - 2, 1)
            pts.append(f"{x},{y}")
        d = "M " + " L ".join(pts)
        # Area fill — build polygon down to bottom
        area_pts = pts + [f"{w},{h}", f"0,{h}"]
        fill_col = color.replace(")", ",0.12)").replace("rgb","rgba") if "rgb" in color else color + "22"
        return (f'<svg width="100%" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
                f'style="display:block;height:{h}px">'
                f'<polygon points="{" ".join(area_pts)}" fill="{fill_col}"/>'
                f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"/>'
                f'</svg>')

    eq_svg = _svg(eq_df["equity"].tolist()   if not eq_df.empty else [])
    dd_svg = _svg(eq_df["drawdown_pct"].tolist() if not eq_df.empty else [], color="#ef5350")

    # ── Stat cards ────────────────────────────────────────────────────────────
    def card(label, val, color="#e6edf3", sub=None):
        s = f'<div style="background:#161b22;border:1px solid #30363d;border-radius:6px;padding:10px 14px;min-width:110px">'
        s += f'<div style="color:#8b949e;font-size:9px;letter-spacing:1px;margin-bottom:4px">{label}</div>'
        s += f'<div style="color:{color};font-size:20px;font-weight:bold;line-height:1">{val}</div>'
        if sub: s += f'<div style="color:#8b949e;font-size:9px;margin-top:3px">{sub}</div>'
        s += '</div>'
        return s

    wr  = stats.get("win_rate_pct", 0)
    ar  = stats.get("avg_r", 0)
    tr  = stats.get("total_r", 0)
    pf  = stats.get("profit_factor", 0)
    pnl = stats.get("total_pnl_usd", 0)
    dd  = stats.get("max_drawdown_pct", 0)
    cagr= stats.get("cagr_pct", 0)

    cards = "".join([
        card("TRADES",        stats.get("total_trades", 0)),
        card("WIN RATE",      f"{wr}%",          "#26a69a" if wr > 50 else "#ef5350"),
        card("AVG R",         f"{ar:+.2f}R",     "#26a69a" if ar > 0  else "#ef5350"),
        card("TOTAL R",       f"{tr:+.1f}R",     "#26a69a" if tr > 0  else "#ef5350"),
        card("PROFIT FACTOR", f"{pf:.2f}",       "#26a69a" if pf > 1.5 else "#f0a500"),
        card("TOTAL P&L",     f"${pnl:+,.0f}",   "#26a69a" if pnl > 0 else "#ef5350"),
        card("MAX DRAWDOWN",  f"{dd:.1f}%",       "#ef5350", sub="peak-to-trough"),
        card("CAGR",          f"{cagr:+.1f}%",   "#26a69a" if cagr > 0 else "#ef5350"),
        card("AVG BARS HELD", f"{stats.get('avg_bars_held',0):.0f}d"),
    ])

    # ── Breakdown tables ──────────────────────────────────────────────────────
    def breakdown(by_dict, title):
        if not by_dict: return ""
        rows = ""
        for k, v in sorted(by_dict.items(), key=lambda x: -x[1].get("total_r", 0)):
            wr2 = v.get("win_rate", 0)
            tr2 = v.get("total_r",  0)
            ar2 = v.get("avg_r",    0)
            n   = v.get("trades",   0)
            rows += (f'<tr>'
                     f'<td style="color:#e6edf3">{k}</td>'
                     f'<td>{n}</td>'
                     f'<td style="color:{"#26a69a" if wr2>50 else "#ef5350"}">{wr2}%</td>'
                     f'<td style="color:{"#26a69a" if ar2>0 else "#ef5350"}">{ar2:+.2f}R</td>'
                     f'<td style="color:{"#26a69a" if tr2>0 else "#ef5350"}">{tr2:+.1f}R</td>'
                     f'</tr>')
        return (f'<div style="margin-bottom:20px">'
                f'<div style="color:#8b949e;font-size:10px;letter-spacing:1px;margin-bottom:6px">{title.upper()}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:11px">'
                f'<tr style="color:#8b949e;border-bottom:1px solid #21262d;font-size:10px">'
                f'<th style="text-align:left;padding:4px 0">Group</th>'
                f'<th style="text-align:right;padding:4px 8px">Trades</th>'
                f'<th style="text-align:right;padding:4px 8px">Win%</th>'
                f'<th style="text-align:right;padding:4px 8px">Avg R</th>'
                f'<th style="text-align:right;padding:4px 8px">Total R</th>'
                f'</tr>{rows}</table></div>')

    breakdowns = (breakdown(stats.get("by_pattern",{}), "By Pattern") +
                  breakdown(stats.get("by_regime",{}),  "By Regime") +
                  breakdown(stats.get("by_exit",{}),    "By Exit Reason"))

    # ── Trade log table ───────────────────────────────────────────────────────
    trade_rows = ""
    for _, r in df.iloc[::-1].iterrows():
        c = "#26a69a" if r["pnl_r"] > 0 else "#ef5350"
        trade_rows += (
            f'<tr style="border-bottom:1px solid #21262d">'
            f'<td style="color:#e6edf3;font-weight:600">{r["ticker"]}</td>'
            f'<td style="color:#58a6ff">{r["pattern"]}</td>'
            f'<td style="color:#8b949e">{r["entry_date"]}</td>'
            f'<td>${r["entry_price"]:.2f}</td>'
            f'<td style="color:#ef5350">${r["stop_price"]:.2f}</td>'
            f'<td style="color:#26a69a">${r["target_price"]:.2f}</td>'
            f'<td style="color:#8b949e">{r["exit_date"]}</td>'
            f'<td>${r["exit_price"]:.2f}</td>'
            f'<td style="color:#8b949e;font-size:10px">{r["exit_reason"]}</td>'
            f'<td style="color:{c};font-weight:700">{r["pnl_r"]:+.2f}R</td>'
            f'<td style="color:{c}">${r["pnl_usd"]:+.0f}</td>'
            f'<td style="color:#8b949e">{r["bars_held"]}d</td>'
            f'<td style="color:#f0a500">{r["score"]:.0f}</td>'
            f'</tr>'
        )

    # ── Distribution: pnl_r histogram using CSS bars ─────────────────────────
    bins  = np.arange(-4, 5, 0.5)
    hist, edges = np.histogram(df["pnl_r"].clip(-4, 4.5), bins=bins)
    max_h = max(hist) or 1
    hist_bars = ""
    for count, left in zip(hist, edges[:-1]):
        pct    = round(count / max_h * 100, 1)
        color  = "#26a69a" if left >= 0 else "#ef5350"
        label  = f"{left:+.1f}"
        hist_bars += (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px">'
            f'<div style="color:#8b949e;font-size:8px">{count if count else ""}</div>'
            f'<div style="width:22px;height:{max(2,pct)}px;background:{color};border-radius:2px 2px 0 0"></div>'
            f'<div style="color:#8b949e;font-size:8px">{label}</div>'
            f'</div>'
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    dr  = stats.get("date_range", {})

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Backtest Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#e6edf3;font-family:'SF Mono',Consolas,monospace;font-size:12px;padding:20px;line-height:1.4}}
h1{{font-size:18px;font-weight:700;color:#e6edf3}}
.sub{{color:#8b949e;font-size:11px;margin:4px 0 20px}}
.cards{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}}
.section{{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:16px;margin-bottom:14px}}
.section-title{{color:#8b949e;font-size:10px;letter-spacing:1px;margin-bottom:10px}}
table td, table th{{padding:4px 8px;text-align:right;white-space:nowrap}}
table td:first-child, table th:first-child{{text-align:left}}
tr:hover td{{background:rgba(255,255,255,0.03)}}
</style>
</head><body>

<h1>📊 Backtest Report</h1>
<div class="sub">
  {now} &nbsp;·&nbsp;
  {dr.get("from","?")} → {dr.get("to","?")} &nbsp;·&nbsp;
  {stats.get("tickers_tested",0)} tickers &nbsp;·&nbsp;
  min_score={cfg.get("min_score_display",40)} &nbsp;·&nbsp;
  risk={cfg.get("risk_per_trade_pct",1)}%/trade &nbsp;·&nbsp;
  max_pos={cfg.get("bot_max_open_trades",5)} &nbsp;·&nbsp;
  slippage={cfg.get("backtest_slippage_pct",0.05)}%
</div>

<div class="cards">{cards}</div>

<div class="section">
  <div class="section-title">EQUITY CURVE — ${stats.get("starting_capital",0):,.0f} → ${stats.get("final_equity",0):,.0f}</div>
  {eq_svg}
</div>

<div class="section">
  <div class="section-title">DRAWDOWN %  (worst: {dd:.1f}%)</div>
  {dd_svg}
</div>

<div class="section">
  <div class="section-title">R DISTRIBUTION</div>
  <div style="display:flex;gap:1px;align-items:flex-end;height:80px;padding-bottom:18px">
    {hist_bars}
  </div>
</div>

<div class="section">{breakdowns}</div>

<div class="section">
  <div class="section-title">ALL TRADES ({len(trades)} total)</div>
  <div style="overflow-x:auto;max-height:500px;overflow-y:auto">
  <table style="width:100%;border-collapse:collapse;font-size:11px">
  <thead style="position:sticky;top:0;background:#161b22">
  <tr style="color:#8b949e;border-bottom:1px solid #30363d;font-size:10px">
    <th style="text-align:left">Ticker</th><th style="text-align:left">Pattern</th>
    <th>Entry</th><th>Price</th><th>Stop</th><th>Target</th>
    <th>Exit</th><th>Price</th><th>Reason</th>
    <th>R</th><th>P&L</th><th>Bars</th><th>Score</th>
  </tr>
  </thead>
  <tbody>{trade_rows}</tbody>
  </table>
  </div>
</div>

</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_backtest(
    tickers:     list[str] | None = None,
    from_date:   date | None      = None,
    cfg:         dict             = CONFIG,
    capital:     float            = 100_000.0,
    min_score:   float | None     = None,
    open_report: bool             = False,
) -> dict:
    cache_dir = Path(cfg.get("ohlcv_cache_dir", "ohlcv_cache"))
    data      = _load_cache(cache_dir)

    if not data:
        log.error(f"No data in {cache_dir}/ — run the bot first to populate cache")
        return {}

    if tickers:
        upper = [t.upper() for t in tickers]
        data  = {k: v for k, v in data.items() if k.upper() in upper}

    # Load SPY for regime detection
    spy_close = None
    if "SPY" in data:
        spy_close = data["SPY"]["close"]

    trades, eq_df = run_portfolio_backtest(data, spy_close, cfg, capital, from_date, min_score)

    if not trades:
        log.warning("No trades generated — try lowering min_score in config")
        return {}

    trades.sort(key=lambda t: t.entry_date)

    stats = compute_stats(trades, capital, eq_df)
    stats["tickers_tested"] = len(data)
    stats["date_range"] = {
        "from": str(trades[0].entry_date)[:10],
        "to":   str(trades[-1].exit_date)[:10],
    }

    # Save outputs
    pd.DataFrame([t.to_dict() for t in trades]).to_csv(OUT_DIR / "trades.csv", index=False)
    eq_df.to_csv(OUT_DIR / "equity.csv", index=False)
    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(stats, f, indent=2, default=str)

    html = build_html_report(trades, eq_df, stats, cfg)
    report_path = OUT_DIR / "report.html"
    report_path.write_text(html)

    # Print summary
    print(f"\n{'='*56}")
    print(f"  BACKTEST COMPLETE  ({stats['date_range']['from']} → {stats['date_range']['to']})")
    print(f"  Tickers:       {stats['tickers_tested']}")
    print(f"  Trades:        {stats['total_trades']}")
    print(f"  Win rate:      {stats['win_rate_pct']}%")
    print(f"  Avg R:         {stats['avg_r']:+.3f}")
    print(f"  Total R:       {stats['total_r']:+.1f}")
    print(f"  Profit factor: {stats['profit_factor']:.2f}")
    print(f"  CAGR:          {stats['cagr_pct']:+.1f}%")
    print(f"  Max drawdown:  {stats['max_drawdown_pct']:.1f}%")
    print(f"  Total P&L:     ${stats['total_pnl_usd']:+,.0f}")
    print(f"\n  By pattern:")
    for pat, v in stats.get("by_pattern", {}).items():
        print(f"    {pat:<12} {v['trades']:>3}  WR={v['win_rate']}%  avgR={v['avg_r']:+.2f}  totalR={v['total_r']:+.1f}")
    print(f"\n  Report → {report_path.resolve()}")
    print(f"{'='*56}\n")

    if open_report:
        import webbrowser
        webbrowser.open(str(report_path.resolve()))

    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Portfolio walk-forward backtest")
    parser.add_argument("--tickers", nargs="*",     help="Tickers to test (default: all in cache)")
    parser.add_argument("--from",    dest="from_date", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--capital", type=float,    default=100_000, help="Starting capital")
    parser.add_argument("--score",   type=float,    default=None,    help="Override min_score_display")
    parser.add_argument("--report",  action="store_true",            help="Open report in browser")
    args = parser.parse_args()

    from_dt = date.fromisoformat(args.from_date) if args.from_date else None
    run_backtest(
        tickers    = args.tickers,
        from_date  = from_dt,
        cfg        = CONFIG,
        capital    = args.capital,
        min_score  = args.score,
        open_report= args.report,
    )