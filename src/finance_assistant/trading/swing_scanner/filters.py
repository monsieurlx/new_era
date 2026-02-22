"""
filters.py — Hard binary filters applied before scoring.

Fail any filter → ticker is dropped immediately.
These are not probabilistic — they are hard gates.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def passes_liquidity(df: pd.DataFrame, cfg: dict) -> tuple[bool, str]:
    """
    Check price, average volume, and dollar volume.

    Returns:
        (True, "ok") or (False, rejection_reason)
    """
    price   = df["close"].iloc[-1]
    avg_vol = df["volume"].rolling(cfg["rvol_avg_period"]).mean().iloc[-1]
    dol_vol = (df["close"] * df["volume"]).rolling(cfg["rvol_avg_period"]).mean().iloc[-1]

    if not (cfg["min_price"] <= price <= cfg["max_price"]):
        return False, f"price_{price:.2f}"
    if avg_vol < cfg["min_avg_volume"]:
        return False, f"low_volume_{avg_vol:.0f}"
    if dol_vol < cfg["min_dollar_volume"]:
        return False, f"low_dollar_vol_{dol_vol:.0f}"

    return True, "ok"


def passes_volatility(inds: dict, cfg: dict) -> tuple[bool, str]:
    """
    Check ATR% is within the desired swing volatility band.

    Returns:
        (True, "ok") or (False, rejection_reason)
    """
    atr_pct = inds["atr_pct"].iloc[-1]
    if atr_pct < cfg["atr_pct_min"]:
        return False, f"atr_too_low_{atr_pct:.2f}%"
    if atr_pct > cfg["atr_pct_max"]:
        return False, f"atr_too_high_{atr_pct:.2f}%"
    return True, "ok"


def passes_trend(inds: dict, cfg: dict) -> tuple[bool, int]:
    """
    Check trend alignment across 5 conditions.

    Returns:
        (passes: bool, conditions_met: int out of 5)
    """
    p    = inds["price"]
    s20  = inds["sma20"].iloc[-1]
    s50  = inds["sma50"].iloc[-1]
    s200 = inds["sma200"].iloc[-1]
    adx  = inds["adx"].iloc[-1]
    slope50 = inds["sma50_slope"]

    conditions = [
        p > s20,
        s20 > s50,
        s50 > s200,
        slope50 > 0,
        adx > cfg["adx_min"],
    ]
    met = sum(conditions)
    return met >= cfg["min_trend_conditions"], met


def apply_all_filters(
    ticker: str,
    df: pd.DataFrame,
    inds: dict,
    cfg: dict,
) -> tuple[bool, str]:
    """
    Run all hard filters in sequence. Short-circuit on first failure.

    Args:
        ticker: for logging only
        df:     OHLCV DataFrame
        inds:   output of indicators.calc_all()
        cfg:    CONFIG dict

    Returns:
        (passes: bool, reason: str)
        reason is "ok" if passes, otherwise a short description of why it failed.
    """
    # Minimum data check
    if len(df) < cfg["min_bars_required"]:
        return False, f"insufficient_bars_{len(df)}"

    # Liquidity
    ok, reason = passes_liquidity(df, cfg)
    if not ok:
        return False, reason

    # Volatility (ATR%)
    ok, reason = passes_volatility(inds, cfg)
    if not ok:
        return False, reason

    # Trend alignment
    trend_ok, trend_count = passes_trend(inds, cfg)
    if not trend_ok:
        return False, f"weak_trend_{trend_count}_of_5"

    return True, "ok"
