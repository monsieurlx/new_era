"""
order_logger.py — Trade lifecycle logging, chart screenshots, and post-trade tracking.

FOLDER STRUCTURE:
    order_history/
    └── 20250222/                          ← one folder per trading day (entry date)
        ├── AAPL_breakout_1042/            ← one folder per trade
        │   ├── 01_entry.png              ← chart at moment of entry
        │   ├── 01_entry.json             ← full trade metadata
        │   ├── 02_exit_tp.png            ← chart at moment of exit
        │   ├── 02_exit_tp.json
        │   ├── 03_post_24h.png           ← what happened 24h AFTER exit
        │   ├── 03_post_24h.json          ← was the stop premature? did it continue?
        │   ├── 04_post_5d.png            ← what happened 5 days after exit
        │   └── 04_post_5d.json
        └── NVDA_pullback_1089/
            └── ...

    order_history/trade_log.csv            ← master log, one row per closed trade

CHART CONTENT (each screenshot shows):
    Panel 1 — Daily OHLCV candles (60 bars context)
        - SMA20 (blue), SMA50 (orange), EMA20 (green dashed)
        - Bollinger Bands (light fill)
        - Entry trigger level (the actual level that fired the signal)
        - Stop loss level  (as defined by pattern — base low / 1.5ATR / swing low)
        - Take profit level (prior swing high / measured move)
        - Risk zone shading (entry→stop, red alpha)
        - Reward zone shading (entry→target, green alpha)
        - Fibonacci retracement levels (0.236, 0.382, 0.5, 0.618, 0.786)
          drawn from the swing low/high that defined the setup
        - Event markers (vertical line + label at entry bar, exit bar)

    Panel 2 — RSI(14) with overbought/oversold bands
    Panel 3 — Volume bars (colored by day direction) + RVOL line
    Panel 4 — ADX (trend strength) — helps assess if trend was real

POST-TRADE TRACKING:
    After a trade closes (TP or SL), the bot schedules follow-up snapshots:
    - 24h later: did price continue in our direction? was the SL premature?
    - 5 days later: what was the full move after our exit?
    These are saved automatically and annotated with what happened vs. what we expected.
    This is your incremental backtesting dataset.

WHAT THIS ENABLES:
    Feed the trade_log.csv + screenshots to Claude for analysis:
    - "Why did my SL trades mostly recover?" → recalibrate stop distance
    - "Which patterns have best post-exit continuation?" → weight scorer
    - "What regime/VIX conditions correlate with wins?" → regime filter tuning
"""

import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.gridspec import GridSpec
    from matplotlib.lines import Line2D
    MPL_OK = True
except ImportError:
    MPL_OK = False
    log.warning("pip install matplotlib — screenshots disabled")


# ═══════════════════════════════════════════════════════════════════════════════
# TRADE OBJECT
# ═══════════════════════════════════════════════════════════════════════════════

class Trade:
    """
    Complete lifecycle of one swing trade.

    Created when entry signal fires.
    Updated at fill, at exit, and at post-trade snapshots.
    All state is serializable to JSON for persistence.
    """

    def __init__(
        self,
        ticker:        str,
        pattern:       str,          # "breakout" | "pullback" | "squeeze"
        order_id:      int,
        entry_price:   float,        # planned entry (trigger level)
        stop_price:    float,        # stop loss level (from risk.py)
        target_price:  float,        # take profit level (from risk.py)
        shares:        int,
        score:         float,        # composite score at signal time
        regime:        str,          # "bull" | "neutral" | "bear"
        vix:           float,
        rr:            float,        # planned R:R
        atr:           float,        # ATR at signal time (for chart annotations)
        swing_low:     float,        # swing low used for fib / stop calculation
        swing_high:    float,        # swing high used for fib / target
        extra:         dict = None,  # any additional metadata (RS scores, ADX, etc.)
    ):
        self.ticker       = ticker
        self.pattern      = pattern
        self.order_id     = order_id
        self.entry_price  = entry_price
        self.stop_price   = stop_price
        self.target_price = target_price
        self.shares       = shares
        self.score        = score
        self.regime       = regime
        self.vix          = vix
        self.rr           = rr
        self.atr          = atr
        self.swing_low    = swing_low
        self.swing_high   = swing_high
        self.extra        = extra or {}

        # Filled at runtime
        self.fill_price:   float           = 0.0
        self.fill_time:    datetime | None = None
        self.exit_price:   float           = 0.0
        self.exit_time:    datetime | None = None
        self.exit_event:   str             = ""   # "tp" | "sl" | "cancel" | "manual"
        self.pnl_usd:      float           = 0.0
        self.pnl_pct:      float           = 0.0
        self.pnl_r:        float           = 0.0  # profit in R units (1R = risk_per_share)
        self.status:       str             = "pending"  # pending→open→closed

        # Post-trade observations (filled by follow-up snapshots)
        self.post_24h_price: float = 0.0
        self.post_5d_price:  float = 0.0
        self.post_24h_move:  float = 0.0   # % from exit price
        self.post_5d_move:   float = 0.0
        # Qualitative: did price continue in trade direction after our exit?
        self.post_verdict:   str   = ""    # "continued" | "reversed" | "sideways"

    # ── State transitions ────────────────────────────────────────────────────

    def on_fill(self, fill_price: float, fill_time: datetime) -> None:
        self.fill_price = fill_price
        self.fill_time  = fill_time
        self.status     = "open"

    def on_exit(self, exit_price: float, exit_time: datetime, event: str) -> None:
        self.exit_price  = exit_price
        self.exit_time   = exit_time
        self.exit_event  = event
        risk_per_share   = max(self.fill_price - self.stop_price, 0.01)
        self.pnl_usd     = (exit_price - self.fill_price) * self.shares
        self.pnl_pct     = (exit_price - self.fill_price) / self.fill_price * 100
        self.pnl_r       = (exit_price - self.fill_price) / risk_per_share
        self.status      = "closed"

    def on_post_snapshot(self, period: str, current_price: float) -> None:
        """Record post-exit price for retrospective analysis."""
        if self.exit_price == 0:
            return
        move = (current_price - self.exit_price) / self.exit_price * 100
        if period == "24h":
            self.post_24h_price = current_price
            self.post_24h_move  = move
        elif period == "5d":
            self.post_5d_price  = current_price
            self.post_5d_move   = move
            # Determine post-exit verdict
            threshold = 2.0   # 2% move = meaningful direction
            if self.exit_event == "sl":
                # Did price recover after our SL?
                if move > threshold:
                    self.post_verdict = "premature_sl"    # stopped out, then recovered
                elif move < -threshold:
                    self.post_verdict = "sl_correct"      # SL was right, kept falling
                else:
                    self.post_verdict = "sideways"
            elif self.exit_event == "tp":
                if move > threshold:
                    self.post_verdict = "left_on_table"   # TP too early
                elif move < -threshold:
                    self.post_verdict = "tp_correct"      # TP was perfect
                else:
                    self.post_verdict = "sideways"

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        def _fmt(dt):
            return dt.isoformat() if dt else None

        return {
            # Identity
            "ticker":         self.ticker,
            "pattern":        self.pattern,
            "order_id":       self.order_id,
            # Setup quality
            "score":          self.score,
            "regime":         self.regime,
            "vix":            self.vix,
            "rr_planned":     self.rr,
            "atr":            self.atr,
            "swing_low":      self.swing_low,
            "swing_high":     self.swing_high,
            # Planned levels
            "entry_planned":  self.entry_price,
            "stop_planned":   self.stop_price,
            "target_planned": self.target_price,
            "shares":         self.shares,
            # Execution
            "fill_price":     self.fill_price,
            "fill_time":      _fmt(self.fill_time),
            "exit_price":     self.exit_price,
            "exit_time":      _fmt(self.exit_time),
            "exit_event":     self.exit_event,
            # Result
            "pnl_usd":        round(self.pnl_usd, 2),
            "pnl_pct":        round(self.pnl_pct, 4),
            "pnl_r":          round(self.pnl_r, 3),
            "status":         self.status,
            # Post-trade
            "post_24h_price": self.post_24h_price,
            "post_24h_move":  round(self.post_24h_move, 3),
            "post_5d_price":  self.post_5d_price,
            "post_5d_move":   round(self.post_5d_move, 3),
            "post_verdict":   self.post_verdict,
            # Extra metadata from scanner
            **self.extra,
        }

    # ── Naming helpers ───────────────────────────────────────────────────────

    @property
    def day_str(self) -> str:
        """YYYYMMDD from fill time (or today)."""
        dt = self.fill_time or datetime.now()
        return dt.strftime("%Y%m%d")

    @property
    def trade_folder_name(self) -> str:
        """e.g. AAPL_breakout_1042"""
        return f"{self.ticker}_{self.pattern}_{self.order_id}"


# ═══════════════════════════════════════════════════════════════════════════════
# ORDER LOGGER
# ═══════════════════════════════════════════════════════════════════════════════

class OrderLogger:
    """
    Manages the order_history directory tree.

    Each trade gets its own dated subfolder.
    Every event within that trade is a numbered PNG + JSON file.
    A master trade_log.csv is updated on every trade close.
    """

    EVENT_PREFIX = {
        "entry":    "01_entry",
        "tp":       "02_exit_tp",
        "sl":       "02_exit_sl",
        "cancel":   "02_exit_cancel",
        "manual":   "02_exit_manual",
        "post_24h": "03_post_24h",
        "post_5d":  "04_post_5d",
    }

    def __init__(self, cfg: dict):
        self.cfg      = cfg
        self.root     = Path(cfg["order_history_dir"])
        self.root.mkdir(parents=True, exist_ok=True)
        self.master   = self.root / "trade_log.csv"

    # ── Public API ───────────────────────────────────────────────────────────

    def log_event(
        self,
        trade:       Trade,
        event:       str,
        df_daily:    pd.DataFrame,
        df_intraday: pd.DataFrame | None = None,
        notes:       str = "",
    ) -> Path | None:
        """
        Save a screenshot + JSON for a trade event.

        Args:
            trade:       Trade object
            event:       "entry" | "tp" | "sl" | "cancel" | "manual"
                         | "post_24h" | "post_5d"
            df_daily:    OHLCV daily DataFrame for the ticker
            df_intraday: 5min OHLCV DataFrame (optional)
            notes:       free text appended to the JSON

        Returns:
            Path to the saved PNG, or None if screenshot failed.
        """
        folder   = self._trade_folder(trade)
        prefix   = self.EVENT_PREFIX.get(event, f"99_{event}")
        png_path = folder / f"{prefix}.png"
        json_path= folder / f"{prefix}.json"

        # Screenshot
        png_saved = None
        if MPL_OK and not df_daily.empty:
            try:
                self._save_chart(trade, event, df_daily, df_intraday, png_path, notes)
                png_saved = png_path
                log.info(f"[{trade.ticker}] Chart saved → {png_path.relative_to(self.root)}")
            except Exception as e:
                log.warning(f"Chart failed for {trade.ticker}/{event}: {e}")

        # JSON metadata
        meta = {
            **trade.to_dict(),
            "event":      event,
            "event_time": datetime.now().isoformat(),
            "notes":      notes,
            "screenshot": str(png_path.name) if png_saved else None,
        }
        json_path.write_text(json.dumps(meta, indent=2, default=str))

        # Update master CSV on close events
        if event in ("tp", "sl", "cancel", "manual"):
            self._append_master(trade.to_dict() | {"event": event})

        return png_saved

    def load_trade_log(self) -> pd.DataFrame:
        if self.master.exists():
            return pd.read_csv(self.master)
        return pd.DataFrame()

    def get_trade_folder(self, trade: Trade) -> Path:
        return self._trade_folder(trade)

    # ── Folder management ────────────────────────────────────────────────────

    def _trade_folder(self, trade: Trade) -> Path:
        """
        Returns (and creates) the folder for this trade:
        order_history/20250222/AAPL_breakout_1042/
        """
        folder = self.root / trade.day_str / trade.trade_folder_name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _append_master(self, row: dict) -> None:
        df = pd.DataFrame([row])
        if self.master.exists():
            df.to_csv(self.master, mode="a", header=False, index=False)
        else:
            df.to_csv(self.master, mode="w", header=True,  index=False)

    # ═══════════════════════════════════════════════════════════════════════════
    # CHART RENDERING
    # ═══════════════════════════════════════════════════════════════════════════

    def _save_chart(
        self,
        trade:       Trade,
        event:       str,
        df_daily:    pd.DataFrame,
        df_intraday: pd.DataFrame | None,
        path:        Path,
        notes:       str,
    ) -> None:
        """
        Multi-panel chart saved to PNG.

        Layout:
            Row 0 (tall)  — Daily candlesticks + all overlays
            Row 1 (short) — RSI panel
            Row 2 (short) — Volume + RVOL
            Row 3 (short) — ADX
            [Row 4]       — Intraday 5min candles (if available)
        """
        cfg = self.cfg
        has_intra = df_intraday is not None and not df_intraday.empty

        n_rows    = 5 if has_intra else 4
        h_ratios  = [5, 1.2, 1.2, 1.2, 2.5] if has_intra else [5, 1.2, 1.2, 1.2]
        fig_h     = 18 if has_intra else 14

        fig = plt.figure(figsize=(20, fig_h), facecolor=C["bg"])
        gs  = GridSpec(n_rows, 1, figure=fig,
                       height_ratios=h_ratios, hspace=0.06)

        ax_price = fig.add_subplot(gs[0])
        ax_rsi   = fig.add_subplot(gs[1], sharex=ax_price)
        ax_vol   = fig.add_subplot(gs[2], sharex=ax_price)
        ax_adx   = fig.add_subplot(gs[3], sharex=ax_price)

        # Slice daily data
        lb = cfg.get("screenshot_lookback_bars", 60)
        la = cfg.get("screenshot_lookahead_bars", 20) if event != "entry" else 5
        df = df_daily.iloc[-(lb + la):].copy().reset_index()
        n  = len(df)

        # ── Indicators on price panel ──────────────────────────────────────
        close = df["close"].values
        high  = df["high"].values
        low   = df["low"].values

        sma20  = _rolling_mean(close, 20)
        sma50  = _rolling_mean(close, 50)
        ema20  = _ema(close, 20)
        bb_mid, bb_up, bb_lo = _bollinger(close, 20, 2.0)

        # ── Fibonacci levels ───────────────────────────────────────────────
        fib_levels = _fibonacci(trade.swing_low, trade.swing_high)

        # ── Draw everything ────────────────────────────────────────────────
        _draw_candles(ax_price, df)
        _draw_bb(ax_price, n, bb_mid, bb_up, bb_lo)
        _draw_ma(ax_price, n, sma20, sma50, ema20)
        _draw_trade_levels(ax_price, n, trade)
        _draw_fibonacci(ax_price, n, fib_levels)
        _draw_zones(ax_price, n, trade)
        _draw_event_marker(ax_price, df, trade, event)

        # ── Sub-panels ────────────────────────────────────────────────────
        rsi = _rsi(close, 14)
        _draw_rsi(ax_rsi, n, rsi)

        volume = df["volume"].values
        avg_vol = _rolling_mean(volume.astype(float), 20)
        _draw_volume(ax_vol, df, volume, avg_vol)

        adx = _adx(df["high"].values, df["low"].values, close, 14)
        _draw_adx(ax_adx, n, adx)

        # ── Intraday panel ────────────────────────────────────────────────
        if has_intra:
            ax_intra = fig.add_subplot(gs[4])
            n_bars   = cfg.get("screenshot_intraday_bars", 78)  # ~1 full session
            df5 = df_intraday.iloc[-n_bars:].copy().reset_index()
            _draw_candles(ax_intra, df5, bar_width=0.4)
            _draw_trade_levels(ax_intra, len(df5), trade, alpha=0.6, label=False)
            _style_ax(ax_intra, title="Intraday (5 min)", xlabel=True)

        # ── Title and labels ──────────────────────────────────────────────
        event_label = {
            "entry":    "ENTRY",
            "tp":       "EXIT — TAKE PROFIT ✓",
            "sl":       "EXIT — STOP LOSS ✗",
            "cancel":   "CANCELLED",
            "manual":   "MANUAL EXIT",
            "post_24h": "POST-TRADE +24h",
            "post_5d":  "POST-TRADE +5 days",
        }.get(event, event.upper())

        pnl_str = ""
        if trade.status == "closed":
            sign = "+" if trade.pnl_usd >= 0 else ""
            pnl_str = (f"   PnL: {sign}${trade.pnl_usd:.2f} "
                       f"({sign}{trade.pnl_pct:.2f}%)  "
                       f"{sign}{trade.pnl_r:.2f}R")

        post_str = ""
        if event == "post_5d" and trade.post_verdict:
            post_str = f"   Verdict: {trade.post_verdict.upper().replace('_',' ')}"

        title = (f"{trade.ticker}  ·  {event_label}  ·  "
                 f"{trade.pattern.upper()}  ·  Score {trade.score:.0f}  ·  "
                 f"Regime {trade.regime.upper()}  ·  VIX {trade.vix:.1f}"
                 f"{pnl_str}{post_str}")

        ax_price.set_title(title, color=C["text"], fontsize=13,
                           pad=12, fontweight="bold")

        if notes:
            fig.text(0.01, 0.005, f"Notes: {notes}",
                     color=C["muted"], fontsize=8, ha="left")

        # ── Shared x-axis labels only on bottom panel ─────────────────────
        for ax in [ax_price, ax_rsi, ax_vol]:
            plt.setp(ax.get_xticklabels(), visible=False)
        _style_ax(ax_price)
        _style_ax(ax_rsi,  title="RSI (14)")
        _style_ax(ax_vol,  title="Volume")
        _style_ax(ax_adx,  title="ADX (14)", xlabel=not has_intra)

        # x-axis date labels on bottom-most visible panel
        _set_xticklabels(ax_adx if not has_intra else ax_intra, df if not has_intra else df5)

        fig.savefig(path, dpi=cfg.get("screenshot_dpi", 150),
                    bbox_inches="tight", facecolor=C["bg"])
        plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# COLOR PALETTE — dark TradingView-like theme
# ═══════════════════════════════════════════════════════════════════════════════

C = {
    "bg":       "#0d1117",
    "panel":    "#161b22",
    "border":   "#30363d",
    "text":     "#e6edf3",
    "muted":    "#8b949e",
    "bull":     "#26a69a",    # teal green (TradingView style)
    "bear":     "#ef5350",    # red
    "sma20":    "#2196f3",    # blue
    "sma50":    "#ff9800",    # orange
    "ema20":    "#4caf50",    # green
    "bb":       "#9c27b0",    # purple
    "entry":    "#26a69a",    # same as bull
    "stop":     "#ef5350",    # same as bear
    "target":   "#2196f3",    # blue
    "fib":      "#ffd700",    # gold
    "risk_bg":  "#ef535022",  # transparent red
    "reward_bg":"#26a69a22",  # transparent green
    "rsi":      "#e040fb",
    "adx":      "#40c4ff",
    "vol_bull": "#26a69a55",
    "vol_bear": "#ef535055",
    "rvol":     "#ffeb3b",
}


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATOR MATH (local — no import from indicators.py to keep this self-contained)
# ═══════════════════════════════════════════════════════════════════════════════

def _rolling_mean(arr: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(arr), np.nan)
    for i in range(n - 1, len(arr)):
        out[i] = arr[i - n + 1 : i + 1].mean()
    return out


def _ema(arr: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(arr), np.nan)
    k   = 2 / (n + 1)
    for i in range(len(arr)):
        if np.isnan(arr[i]):
            continue
        if np.isnan(out[i - 1]) if i > 0 else True:
            out[i] = arr[i]
        else:
            out[i] = arr[i] * k + out[i - 1] * (1 - k)
    return out


def _bollinger(arr: np.ndarray, n: int, mult: float):
    mid = _rolling_mean(arr, n)
    std = np.full(len(arr), np.nan)
    for i in range(n - 1, len(arr)):
        std[i] = arr[i - n + 1 : i + 1].std()
    return mid, mid + mult * std, mid - mult * std


def _rsi(arr: np.ndarray, n: int) -> np.ndarray:
    delta = np.diff(arr, prepend=arr[0])
    gain  = np.where(delta > 0, delta, 0.0)
    loss  = np.where(delta < 0, -delta, 0.0)
    avg_g = _rolling_mean(gain, n)
    avg_l = _rolling_mean(loss, n)
    rs    = np.where(avg_l == 0, 100, avg_g / (avg_l + 1e-10))
    return 100 - (100 / (1 + rs))


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    up   = np.diff(high, prepend=high[0])
    dn   = -np.diff(low,  prepend=low[0])
    pdm  = np.where((up > dn) & (up > 0), up, 0.0)
    mdm  = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr1  = high - low
    tr2  = np.abs(high - np.roll(close, 1))
    tr3  = np.abs(low  - np.roll(close, 1))
    tr   = np.maximum(tr1, np.maximum(tr2, tr3))
    atr  = _rolling_mean(tr, n)
    pdi  = 100 * _rolling_mean(pdm, n) / (atr + 1e-10)
    mdi  = 100 * _rolling_mean(mdm, n) / (atr + 1e-10)
    dx   = 100 * np.abs(pdi - mdi) / (pdi + mdi + 1e-10)
    return _rolling_mean(dx, n)


def _fibonacci(low: float, high: float) -> dict[str, float]:
    """Return standard Fibonacci retracement levels from swing low to swing high."""
    diff = high - low
    return {
        "0.0":   high,
        "0.236": high - 0.236 * diff,
        "0.382": high - 0.382 * diff,
        "0.500": high - 0.500 * diff,
        "0.618": high - 0.618 * diff,
        "0.786": high - 0.786 * diff,
        "1.0":   low,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DRAWING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_candles(ax, df: pd.DataFrame, bar_width: float = 0.6) -> None:
    for i, row in df.iterrows():
        is_bull = row["close"] >= row["open"]
        color   = C["bull"] if is_bull else C["bear"]
        body_lo = min(row["open"], row["close"])
        body_hi = max(row["open"], row["close"])
        # Wick
        ax.plot([i, i], [row["low"], row["high"]], color=color, lw=0.8, zorder=2)
        # Body
        ax.bar(i, body_hi - body_lo, bottom=body_lo,
               color=color, width=bar_width, linewidth=0, zorder=3)


def _draw_bb(ax, n, mid, upper, lower) -> None:
    x = range(n)
    ax.plot(x, mid,   color=C["bb"], lw=0.8, alpha=0.5, ls="--", label="BB mid")
    ax.plot(x, upper, color=C["bb"], lw=0.8, alpha=0.4, label="BB upper")
    ax.plot(x, lower, color=C["bb"], lw=0.8, alpha=0.4, label="BB lower")
    ax.fill_between(x, upper, lower, color=C["bb"], alpha=0.04)


def _draw_ma(ax, n, sma20, sma50, ema20) -> None:
    x = range(n)
    ax.plot(x, sma20, color=C["sma20"], lw=1.3, alpha=0.9, label="SMA 20")
    ax.plot(x, sma50, color=C["sma50"], lw=1.3, alpha=0.9, label="SMA 50")
    ax.plot(x, ema20, color=C["ema20"], lw=1.0, alpha=0.8, ls="--", label="EMA 20")
    ax.legend(fontsize=8, loc="upper left",
              facecolor=C["panel"], edgecolor=C["border"],
              labelcolor=C["text"], framealpha=0.8)


def _draw_trade_levels(
    ax, n: int, trade: Trade, alpha: float = 1.0, label: bool = True
) -> None:
    """Draw entry, stop, and target as horizontal dashed lines."""
    levels = [
        (trade.entry_price,  C["entry"],  "Entry",  ":"),
        (trade.stop_price,   C["stop"],   "Stop",   "--"),
        (trade.target_price, C["target"], "Target", "--"),
    ]
    for price, color, name, ls in levels:
        if price <= 0:
            continue
        ax.axhline(price, color=color, lw=1.3, ls=ls, alpha=alpha, zorder=4)
        if label:
            ax.text(n - 1, price, f"  {name} ${price:.2f}",
                    color=color, fontsize=8, va="center",
                    ha="left", zorder=5)


def _draw_fibonacci(ax, n: int, levels: dict[str, float]) -> None:
    """Draw Fibonacci retracement levels as thin horizontal lines."""
    x = range(n)
    for label, price in levels.items():
        ax.axhline(price, color=C["fib"], lw=0.7, ls=":", alpha=0.6, zorder=3)
        ax.text(1, price, f" Fib {label}  ${price:.2f}",
                color=C["fib"], fontsize=7, va="bottom", alpha=0.8)


def _draw_zones(ax, n: int, trade: Trade) -> None:
    """Shade the risk zone (red) and reward zone (green)."""
    if trade.entry_price <= 0:
        return
    # Risk zone: entry → stop
    if trade.stop_price > 0:
        ax.axhspan(trade.stop_price, trade.entry_price,
                   color=C["stop"], alpha=0.08, zorder=1)
    # Reward zone: entry → target
    if trade.target_price > 0:
        ax.axhspan(trade.entry_price, trade.target_price,
                   color=C["entry"], alpha=0.06, zorder=1)


def _draw_event_marker(
    ax, df: pd.DataFrame, trade: Trade, event: str
) -> None:
    """Vertical dashed line and annotation at the event bar (last bar in view)."""
    colors = {
        "entry":    C["entry"],
        "tp":       C["target"],
        "sl":       C["stop"],
        "post_24h": C["muted"],
        "post_5d":  C["muted"],
    }
    labels = {
        "entry":    "▲ ENTRY",
        "tp":       "✓ TP",
        "sl":       "✗ SL",
        "post_24h": "→ +24h",
        "post_5d":  "→ +5d",
    }
    color = colors.get(event, C["muted"])
    label = labels.get(event, event.upper())
    x     = len(df) - 1

    ax.axvline(x, color=color, lw=1.5, ls="--", alpha=0.8, zorder=5)

    # Get price for annotation
    if event == "entry":
        price = trade.fill_price or trade.entry_price
    elif event in ("tp", "sl"):
        price = trade.exit_price
    else:
        price = df["close"].iloc[-1] if not df.empty else 0

    if price > 0:
        ax.annotate(
            label,
            xy=(x, price),
            xytext=(max(x - 8, 0), price * 1.015),
            color=color,
            fontsize=10,
            fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
            zorder=6,
        )


def _draw_rsi(ax, n: int, rsi: np.ndarray) -> None:
    x = range(n)
    ax.plot(x, rsi, color=C["rsi"], lw=1.1, label="RSI 14")
    ax.axhline(70, color=C["bear"],  lw=0.7, ls=":", alpha=0.6)
    ax.axhline(50, color=C["muted"], lw=0.7, ls=":", alpha=0.4)
    ax.axhline(30, color=C["entry"], lw=0.7, ls=":", alpha=0.6)
    ax.fill_between(x, rsi, 70, where=(rsi >= 70), color=C["bear"],  alpha=0.15)
    ax.fill_between(x, rsi, 30, where=(rsi <= 30), color=C["entry"], alpha=0.15)
    ax.set_ylim(0, 100)
    ax.set_yticks([30, 50, 70])


def _draw_volume(ax, df: pd.DataFrame, volume: np.ndarray, avg_vol: np.ndarray) -> None:
    colors = [C["vol_bull"] if c >= o else C["vol_bear"]
              for c, o in zip(df["close"], df["open"])]
    ax.bar(range(len(df)), volume, color=colors, linewidth=0)
    ax.plot(range(len(df)), avg_vol, color=C["rvol"], lw=1.0,
            alpha=0.8, label="Avg Vol 20")


def _draw_adx(ax, n: int, adx: np.ndarray) -> None:
    x = range(n)
    ax.plot(x, adx, color=C["adx"], lw=1.1, label="ADX 14")
    ax.axhline(20, color=C["muted"], lw=0.7, ls=":", alpha=0.5)
    ax.axhline(25, color=C["sma20"], lw=0.7, ls=":", alpha=0.4)
    ax.set_ylim(0, min(60, np.nanmax(adx) * 1.2) if not np.all(np.isnan(adx)) else 60)


def _style_ax(ax, title: str = "", xlabel: bool = False) -> None:
    ax.set_facecolor(C["panel"])
    ax.tick_params(colors=C["muted"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(C["border"])
    ax.grid(True, color=C["border"], lw=0.4, alpha=0.6)
    if title:
        ax.set_ylabel(title, color=C["muted"], fontsize=8)
    if not xlabel:
        plt.setp(ax.get_xticklabels(), visible=False)


def _set_xticklabels(ax, df: pd.DataFrame) -> None:
    """Set readable date labels on the x-axis."""
    n      = len(df)
    step   = max(1, n // 8)
    ticks  = list(range(0, n, step))
    date_col = "date" if "date" in df.columns else df.columns[0]
    labels = []
    for t in ticks:
        try:
            labels.append(str(df[date_col].iloc[t])[:10])
        except Exception:
            labels.append(str(t))
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, color=C["muted"], fontsize=8, rotation=25, ha="right")


# ═══════════════════════════════════════════════════════════════════════════════
# POST-TRADE SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════

class PostTradeScheduler:
    """
    After a trade closes, schedules +24h and +5d follow-up snapshots.

    These snapshots show what price did AFTER our exit, answering:
    - "Was my stop loss premature?" (price recovered after SL)
    - "Did I exit TP too early?" (price kept running)
    - "Which patterns have strongest post-exit continuation?"

    Usage:
        scheduler = PostTradeScheduler(order_logger, cfg)
        scheduler.register(trade)          # call at trade close

        # In your bot loop:
        await scheduler.check_pending(client, data_fetcher)
    """

    def __init__(self, order_logger: OrderLogger, cfg: dict):
        self.ol  = order_logger
        self.cfg = cfg
        # List of (trade, period_str, due_datetime)
        self._pending: list[tuple[Trade, str, datetime]] = []

    def register(self, trade: Trade) -> None:
        """Schedule +24h and +5d snapshots for a just-closed trade."""
        if not trade.exit_time:
            return
        self._pending.append((trade, "post_24h", trade.exit_time + timedelta(hours=24)))
        self._pending.append((trade, "post_5d",  trade.exit_time + timedelta(days=5)))
        log.info(f"Post-trade snapshots scheduled for {trade.ticker} "
                 f"(24h + 5d after {trade.exit_time.strftime('%Y-%m-%d %H:%M')})")

    async def check_pending(self, fetch_fn) -> None:
        """
        Called from the bot loop. Checks if any scheduled snapshots are due.

        Args:
            fetch_fn: async callable(ticker) → pd.DataFrame (daily OHLCV)
        """
        now  = datetime.now()
        done = []

        for item in self._pending:
            trade, period, due_at = item
            if now < due_at:
                continue

            log.info(f"[{trade.ticker}] Post-trade snapshot: {period}")
            try:
                df = await fetch_fn(trade.ticker)
                if df.empty:
                    continue

                current_price = float(df["close"].iloc[-1])
                trade.on_post_snapshot(period, current_price)

                self.ol.log_event(
                    trade=trade,
                    event=period,
                    df_daily=df,
                    notes=(
                        f"Price at snapshot: ${current_price:.2f}  |  "
                        f"Move from exit: {trade.post_24h_move if period == 'post_24h' else trade.post_5d_move:+.2f}%"
                    ),
                )
                done.append(item)

            except Exception as e:
                log.warning(f"Post-trade snapshot failed {trade.ticker}/{period}: {e}")
                done.append(item)   # remove even on failure to avoid endless retries

        for item in done:
            self._pending.remove(item)

    @property
    def pending_count(self) -> int:
        return len(self._pending)