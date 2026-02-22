"""
scorer.py — Composite scoring engine.

Combines 8 signal components into a single 0–100 score.
Applies regime multiplier after base score is computed.
"""

import logging

import pandas as pd

from filters import passes_trend

logger = logging.getLogger(__name__)


def score_ticker(
    ticker: str,
    df: pd.DataFrame,
    inds: dict,
    pattern: dict,
    rs_scores: list[float],
    regime: dict,
    risk: dict,
    cfg: dict,
) -> dict:
    """
    Compute composite score for a single ticker.

    Args:
        ticker:    ticker string (for output only)
        df:        OHLCV DataFrame
        inds:      indicators dict from calc_all()
        pattern:   pattern dict from detect_best_pattern()
        rs_scores: list of floats — outperformance vs SPY per window
        regime:    dict from detect_regime()
        risk:      dict from compute_risk()
        cfg:       CONFIG dict

    Returns:
        dict with score and all component scores for transparency.
    """
    w = cfg["score_weights"]

    # ── Component: Trend ─────────────────────────────────────────────────────
    _, trend_count = passes_trend(inds, cfg)
    c_trend = trend_count / 5.0

    # ── Component: RSI alignment ─────────────────────────────────────────────
    rsi_val = inds["rsi"].iloc[-1]
    ideal   = cfg.get("rsi_ideal", 60.0)
    if 40.0 < rsi_val < 80.0:
        c_rsi = max(1.0 - abs(rsi_val - ideal) / 30.0, 0.0)
    else:
        c_rsi = 0.1   # out of ideal zone

    # ── Component: ATR% fit ───────────────────────────────────────────────────
    atr_pct = inds["atr_pct"].iloc[-1]
    c_atr   = max(1.0 - abs(atr_pct - cfg["atr_pct_ideal"]) / 3.0, 0.0)

    # ── Component: Relative Volume ────────────────────────────────────────────
    rvol   = inds["rvol"]
    c_rvol = min(max((rvol - 1.0) / 2.0, 0.0), 1.0)

    # ── Component: Relative Strength vs benchmark ─────────────────────────────
    rs_avg  = sum(rs_scores) / len(rs_scores) if rs_scores else 0.0
    c_rs    = min(max(rs_avg * 10.0 + 0.5, 0.0), 1.0)

    # ── Component: Pattern quality ────────────────────────────────────────────
    c_pattern = pattern.get("score", 0.0)

    # ── Component: OBV slope ──────────────────────────────────────────────────
    c_obv = 1.0 if inds["obv_slope"] > 0 else 0.0

    # ── Component: Risk:Reward ────────────────────────────────────────────────
    rr = risk.get("rr", 0.0)
    if risk.get("valid", False) and rr >= cfg["min_rr_ratio"]:
        c_rr = min((rr - 2.0) / 3.0, 1.0)   # 2:1 → 0, 5:1 → 1.0
    else:
        c_rr = 0.0

    # ── Weighted composite ────────────────────────────────────────────────────
    composite = (
        w["trend"]   * c_trend   +
        w["rsi"]     * c_rsi     +
        w["atr_fit"] * c_atr     +
        w["rvol"]    * c_rvol    +
        w["rs"]      * c_rs      +
        w["pattern"] * c_pattern +
        w["rr"]      * c_rr      +
        w["obv"]     * c_obv
    ) * 100.0

    # ── Regime multiplier ─────────────────────────────────────────────────────
    trend     = regime.get("trend", "neutral")
    regime_m  = cfg["regime_multipliers"].get(trend, 1.0)
    vix       = regime.get("vix")
    vix_m     = cfg.get("vix_high_multiplier", 0.80) if (
        vix and vix > cfg.get("vix_high_threshold", 30.0)
    ) else 1.0

    composite *= regime_m * vix_m

    # ── Collect readable metrics for output ───────────────────────────────────
    return {
        "ticker":         ticker,
        "score":          round(composite, 1),
        # Component scores (for radar chart and debugging)
        "c_trend":        round(c_trend,   3),
        "c_rsi":          round(c_rsi,     3),
        "c_atr":          round(c_atr,     3),
        "c_rvol":         round(c_rvol,    3),
        "c_rs":           round(c_rs,      3),
        "c_pattern":      round(c_pattern, 3),
        "c_obv":          round(c_obv,     3),
        "c_rr":           round(c_rr,      3),
        # Human-readable indicators
        "price":          round(inds["price"], 2),
        "rsi":            round(rsi_val, 1),
        "atr_pct":        round(atr_pct, 2),
        "rvol":           round(rvol, 2),
        "trend_count":    trend_count,
        "rs_avg_pct":     round(rs_avg * 100.0, 2),
        "obv_slope":      round(inds["obv_slope"], 2),
        "adx":            round(inds["adx"].iloc[-1], 1),
        "pattern":        pattern.get("type", "none"),
        "pattern_score":  pattern.get("score", 0.0),
    }
