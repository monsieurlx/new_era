"""
regime.py — Market regime classification using SPY + VIX.

Run this BEFORE scanning individual tickers.
The regime determines position sizing multiplier for the whole session.
"""

import logging

import pandas as pd

from indicators import calc_sma

logger = logging.getLogger(__name__)


def detect_regime(
    spy_df: pd.DataFrame,
    vix_series: pd.Series,
    cfg: dict,
) -> dict:
    """
    Classify the current market regime.

    Args:
        spy_df:     Daily OHLCV DataFrame for SPY.
        vix_series: Daily close Series for VIX. Empty Series if unavailable.
        cfg:        CONFIG dict.

    Returns:
        dict with keys:
            trend       : "bull" | "bear" | "neutral"
            vix         : float or None
            vix_regime  : "low" | "normal" | "elevated" | "high" | "unknown"
            size_mult   : float — multiply normal position size by this
            spy_price   : float
            sma50       : float
            sma200      : float
            slope50_pct : float — SMA50 slope over last 10 bars (%)
    """
    close    = spy_df["close"]
    sma50_s  = calc_sma(close, 50)
    sma200_s = calc_sma(close, 200)

    sma50   = sma50_s.iloc[-1]
    sma200  = sma200_s.iloc[-1]
    price   = close.iloc[-1]

    # SMA50 slope — positive means trend is rising
    lookback = min(cfg.get("slope_lookback", 10), len(sma50_s.dropna()) - 1)
    sma50_prev  = sma50_s.iloc[-(lookback + 1)]
    slope50_pct = (sma50 / sma50_prev - 1.0) * 100.0 if sma50_prev else 0.0

    # ── Trend classification ──────────────────────────────────────────────────
    if price > sma200 and sma50 > sma200 and slope50_pct > 0:
        trend = "bull"
    elif price < sma200 and sma50 < sma200:
        trend = "bear"
    else:
        trend = "neutral"

    # ── VIX overlay ───────────────────────────────────────────────────────────
    vix = float(vix_series.iloc[-1]) if len(vix_series) > 0 else None

    base_mult = cfg["regime_multipliers"].get(trend, 1.0)

    if vix is None:
        vix_regime  = "unknown"
        vix_adj     = 1.0
    elif vix < 18.0:
        vix_regime  = "low"
        vix_adj     = 1.0
    elif vix < 25.0:
        vix_regime  = "normal"
        vix_adj     = 1.0
    elif vix < 30.0:
        vix_regime  = "elevated"
        vix_adj     = 0.75
    elif vix < cfg.get("vix_high_threshold", 30.0):
        vix_regime  = "high"
        vix_adj     = cfg.get("vix_high_multiplier", 0.80)
    else:
        vix_regime  = "high"
        vix_adj     = cfg.get("vix_high_multiplier", 0.80)

    size_mult = base_mult * vix_adj

    result = {
        "trend":       trend,
        "vix":         vix,
        "vix_regime":  vix_regime,
        "size_mult":   round(size_mult, 3),
        "spy_price":   round(price, 2),
        "sma50":       round(sma50, 2),
        "sma200":      round(sma200, 2),
        "slope50_pct": round(slope50_pct, 3),
    }

    _log_regime(result)
    return result


def _log_regime(r: dict) -> None:
    """Pretty-print regime to console/log."""
    vix_str = f"{r['vix']:.1f} ({r['vix_regime']})" if r["vix"] else "N/A"
    bias_map = {"bull": "LONG", "bear": "AVOID LONGS", "neutral": "LONG-LIGHT"}
    bias = bias_map.get(r["trend"], "?")

    print("\n" + "─" * 55)
    print(f"  MARKET REGIME : {r['trend'].upper():<10}  Bias: {bias}")
    print(f"  SPY Price     : ${r['spy_price']:.2f}")
    print(f"  SMA50 / SMA200: ${r['sma50']:.2f} / ${r['sma200']:.2f}")
    print(f"  SMA50 Slope   : {r['slope50_pct']:+.2f}%")
    print(f"  VIX           : {vix_str}")
    print(f"  Size Mult     : {r['size_mult']:.2f}x  ({int(r['size_mult'] * 100)}% of normal)")
    print("─" * 55 + "\n")
