"""
risk.py — Stop / target / position size / R:R calculations.

Every trade candidate must pass R:R >= cfg["min_rr_ratio"].
Position size is always derived from account risk, never from conviction.
"""

import math
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_risk(
    df: pd.DataFrame,
    inds: dict,
    pattern: dict,
    cfg: dict,
    regime_size_mult: float = 1.0,
) -> dict:
    """
    Compute stop, target, R:R, and position size for a candidate.

    Args:
        df:               OHLCV DataFrame
        inds:             indicators dict from calc_all()
        pattern:          pattern dict from detect_best_pattern()
        cfg:              CONFIG dict
        regime_size_mult: size multiplier from regime detection (e.g. 0.7 for neutral)

    Returns:
        dict with keys: valid, entry, stop, target, risk_per_share,
                        rr, shares, position_value, dollar_risk, risk_pct
        valid=False if R:R < min_rr_ratio or shares < 1.
    """
    close   = df["close"].iloc[-1]
    atr     = inds["atr"].iloc[-1]
    low_20  = df["low"].iloc[-20:].min()
    high_20 = df["high"].iloc[-20:].max()

    ptype = pattern.get("type", "none")

    # Stop and target by pattern type
    if ptype == "breakout":
        stop   = low_20                           # below the base low
        target = max(high_20, close + 2.0 * atr) # prior high or measured move

    elif ptype == "pullback":
        stop   = close - 1.5 * atr               # 1.5 ATR below entry
        target = high_20                          # prior swing high

    elif ptype == "squeeze":
        stop   = close - 1.0 * atr               # 1 ATR below entry
        target = close + 2.0 * atr               # 2 ATR target

    else:  # no pattern — use generic 1 ATR stop, 2 ATR target
        stop   = close - atr
        target = close + 2.0 * atr

    stop = max(stop, 0.01)

    risk   = close - stop
    reward = target - close

    if risk <= 0 or reward <= 0:
        return _invalid_risk()

    rr = reward / risk

    # Position sizing: dollar_risk / risk_per_share × regime size scaling
    dollar_risk  = cfg["account_size"] * cfg["risk_per_trade_pct"] * regime_size_mult
    shares       = math.floor(dollar_risk / risk)
    position_val = shares * close

    valid = rr >= cfg["min_rr_ratio"] and shares >= 1

    return {
        "valid":          valid,
        "entry":          round(close, 2),
        "stop":           round(stop, 2),
        "target":         round(target, 2),
        "risk_per_share": round(risk, 2),
        "rr":             round(rr, 2),
        "shares":         shares,
        "position_value": round(position_val, 2),
        "dollar_risk":    round(dollar_risk, 2),
        "risk_pct":       round(risk / close * 100.0, 2),
    }


def _invalid_risk() -> dict:
    return {
        "valid":          False,
        "entry":          0.0,
        "stop":           0.0,
        "target":         0.0,
        "risk_per_share": 0.0,
        "rr":             0.0,
        "shares":         0,
        "position_value": 0.0,
        "dollar_risk":    0.0,
        "risk_pct":       0.0,
    }
