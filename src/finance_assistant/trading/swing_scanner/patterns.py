"""
patterns.py — Entry pattern detection.

Three patterns:
  1. Breakout from tight consolidation base
  2. Pullback to moving average in an uptrend
  3. Bollinger Band squeeze (volatility compression)

Each function returns:
    {"flag": bool, "score": float 0–1, "type": str, ...extra_stats}
"""

import logging
from statistics import mean

import pandas as pd

logger = logging.getLogger(__name__)


def detect_breakout(df: pd.DataFrame, inds: dict, cfg: dict) -> dict:
    """
    Detect a breakout from a tight consolidation base.

    Quality is higher when:
    - Base is longer (more accumulation time)
    - Base is tighter (price coiling)
    - Volume during base is quiet (no distribution)
    - Breakout volume is strong (institutional participation)
    """
    _base_result = {"flag": False, "score": 0.0, "type": "breakout"}
    n = cfg["consolidation_days"]

    if len(df) < n + 5:
        return _base_result

    base  = df.iloc[-(n + 1):-1]  # exclude today
    today = df.iloc[-1]

    base_high  = base["high"].max()
    base_low   = base["low"].min()
    base_range = base_high / (base_low + 1e-10) - 1.0

    # Hard check: base must be tight
    if base_range > cfg["consolidation_tight"]:
        return _base_result

    avg_vol_20    = df["volume"].rolling(20).mean().iloc[-1]
    base_avg_vol  = base["volume"].mean()
    base_vol_ratio = base_avg_vol / (avg_vol_20 + 1e-1)

    # Breakout: close above base high with buffer
    entry_trigger = today["close"] > base_high * (1.0 + cfg["breakout_buffer_pct"])
    rvol          = today["volume"] / (base_avg_vol + 1e-1)

    if not entry_trigger or rvol < cfg["rvol_threshold"]:
        return _base_result

    # Quality components (each 0–1)
    tightness_score = max(1.0 - (base_range / cfg["consolidation_tight"]), 0.0)
    length_score    = min(n / 30.0, 1.0)
    volume_score    = min((rvol - 1.0) / 2.0, 1.0)
    quiet_score     = max(1.0 - base_vol_ratio, 0.0)
    quality         = mean([tightness_score, length_score, volume_score, quiet_score])

    return {
        "flag":           True,
        "score":          round(quality, 3),
        "type":           "breakout",
        "base_range_pct": round(base_range * 100.0, 2),
        "base_length":    n,
        "rvol":           round(rvol, 2),
        "base_high":      round(base_high, 2),
    }


def detect_pullback(df: pd.DataFrame, inds: dict, cfg: dict) -> dict:
    """
    Detect a pullback-to-EMA setup within an established uptrend.

    Ideal setup:
    - Price is above SMA50 with positive slope (uptrend intact)
    - Price pulled back 3–12% from recent swing high
    - Price touched or came near EMA20 (the dynamic support)
    - RSI reset to 45–55 (healthy, not oversold)
    - Today shows a reversal candle (close > yesterday's high)
    - Volume was quiet on the pullback, stronger on reversal
    """
    _base_result = {"flag": False, "score": 0.0, "type": "pullback"}

    close   = df["close"]
    sma50   = inds["sma50"]
    ema20   = inds["ema20"]
    rsi     = inds["rsi"]

    # Trend pre-condition
    if close.iloc[-1] <= sma50.iloc[-1] or inds["sma50_slope"] <= 0:
        return _base_result

    # Pullback depth from 20-bar swing high
    recent_high  = df["high"].iloc[-20:].max()
    pullback_pct = (recent_high - close.iloc[-1]) / (recent_high + 1e-10)

    if not (cfg["pullback_min_pct"] <= pullback_pct <= cfg["pullback_max_pct"]):
        return _base_result

    # EMA proximity check
    ema_dist = abs(close.iloc[-1] - ema20.iloc[-1]) / (ema20.iloc[-1] + 1e-10)
    if ema_dist > cfg["pullback_ema_touch"]:
        return _base_result

    # RSI reset check
    rsi_val = rsi.iloc[-1]
    if not (cfg["pullback_rsi_min"] < rsi_val < cfg["pullback_rsi_max"]):
        return _base_result

    # Volume and candle quality
    avg_vol     = df["volume"].rolling(20).mean().iloc[-1]
    pull_rvol   = df["volume"].iloc[-3:].mean() / (avg_vol + 1e-1)
    reversal    = close.iloc[-1] > df["high"].iloc[-2]   # today's close > yesterday's high

    # Quality components (each 0–1)
    ideal_depth    = cfg.get("pullback_depth_ideal", 0.07)
    depth_score    = max(1.0 - abs(pullback_pct - ideal_depth) / 0.05, 0.0)
    ema_score      = max(1.0 - ema_dist / (cfg["pullback_ema_touch"] + 1e-10), 0.0)
    ideal_rsi      = cfg.get("pullback_rsi_ideal", 52.0)
    rsi_score      = max(1.0 - abs(rsi_val - ideal_rsi) / 12.0, 0.0)
    reversal_score = 1.0 if reversal else 0.5
    quiet_score    = 1.0 if pull_rvol < 1.0 else 0.3

    quality = mean([depth_score, ema_score, rsi_score, reversal_score, quiet_score])

    return {
        "flag":          True,
        "score":         round(quality, 3),
        "type":          "pullback",
        "pullback_pct":  round(pullback_pct * 100.0, 2),
        "rsi":           round(rsi_val, 1),
        "ema_dist_pct":  round(ema_dist * 100.0, 2),
        "reversal":      reversal,
        "pull_rvol":     round(pull_rvol, 2),
    }


def detect_squeeze(df: pd.DataFrame, inds: dict, cfg: dict) -> dict:
    """
    Detect a Bollinger Band squeeze: volatility compression before expansion.

    Signal fires when BB bandwidth is in the bottom 25th percentile of recent history.
    Score is proportional to how extreme the compression is.
    """
    _base_result = {"flag": False, "score": 0.0, "type": "squeeze"}

    bb_bw    = inds["bb_bw"]
    lookback = cfg["squeeze_lookback"]
    pct      = cfg["squeeze_percentile"]

    valid_bw = bb_bw.dropna()
    if len(valid_bw) < lookback:
        return _base_result

    threshold  = bb_bw.rolling(lookback).quantile(pct).iloc[-1]
    current_bw = bb_bw.iloc[-1]
    squeeze    = current_bw <= threshold

    if not squeeze:
        return _base_result

    # Score: deeper squeeze = closer to zero bandwidth = higher score
    score = max(1.0 - (current_bw / (threshold + 1e-10)), 0.0)
    score = min(score, 1.0)

    return {
        "flag":          True,
        "score":         round(score, 3),
        "type":          "squeeze",
        "bb_bw_current": round(current_bw, 4),
        "bb_bw_thresh":  round(threshold, 4),
    }


def detect_best_pattern(df: pd.DataFrame, inds: dict, cfg: dict) -> dict:
    """
    Run all three pattern detectors and return the one with the highest score.

    If no pattern fires, returns {"flag": False, "score": 0.0, "type": "none"}.
    """
    bo = detect_breakout(df, inds, cfg)
    pb = detect_pullback(df, inds, cfg)
    sq = detect_squeeze(df, inds, cfg)

    best = max([bo, pb, sq], key=lambda x: x["score"])

    if best["score"] == 0.0:
        return {"flag": False, "score": 0.0, "type": "none"}

    return best
