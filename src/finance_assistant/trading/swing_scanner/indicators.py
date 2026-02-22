"""
indicators.py — All technical indicator calculations.

Rules:
  - Pure functions only. No side effects.
  - Input: pd.Series or pd.DataFrame
  - Output: pd.Series (or scalar for current values)
  - No imports from other project modules.
"""

import numpy as np
import pandas as pd


# ─── Individual Indicators ────────────────────────────────────────────────────

def calc_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(period).mean()


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index using Wilder smoothing.
    Returns values in range [0, 100].
    """
    delta = series.diff()
    gain  = delta.clip(lower=0.0).rolling(period).mean()
    loss  = (-delta.clip(upper=0.0)).rolling(period).mean()
    rs    = gain / (loss + 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low  - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average Directional Index.
    Returns ADX series [0, 100]. Higher = stronger trend (direction-agnostic).
    """
    up_move   = high.diff()
    down_move = -low.diff()

    plus_dm  = np.where((up_move > down_move)  & (up_move > 0),   up_move,   0.0)
    minus_dm = np.where((down_move > up_move)  & (down_move > 0), down_move, 0.0)

    plus_dm_s  = pd.Series(plus_dm,  index=high.index).rolling(period).mean()
    minus_dm_s = pd.Series(minus_dm, index=high.index).rolling(period).mean()

    atr_s   = calc_atr(high, low, close, period)
    plus_di  = 100.0 * plus_dm_s  / (atr_s + 1e-10)
    minus_di = 100.0 * minus_dm_s / (atr_s + 1e-10)

    dx  = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx = dx.rolling(period).mean()
    return adx


def calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On Balance Volume — cumulative volume with direction from price."""
    direction = np.sign(close.diff()).fillna(0.0)
    return (direction * volume).cumsum()


def calc_bb_bandwidth(
    close: pd.Series,
    period: int = 20,
    std_mult: float = 2.0,
) -> pd.Series:
    """
    Bollinger Band Bandwidth = (upper - lower) / midline.
    Low value = squeeze (low volatility, potential expansion ahead).
    """
    sma   = calc_sma(close, period)
    std   = close.rolling(period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    return (upper - lower) / (sma + 1e-10)


def calc_bb_bands(
    close: pd.Series,
    period: int = 20,
    std_mult: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (upper, midline, lower) Bollinger Bands."""
    sma   = calc_sma(close, period)
    std   = close.rolling(period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    return upper, sma, lower


# ─── Batch Calculator ────────────────────────────────────────────────────────

def calc_all(df: pd.DataFrame, cfg: dict) -> dict:
    """
    Compute all indicators for one ticker.

    Args:
        df:  OHLCV DataFrame with columns [open, high, low, close, volume]
        cfg: CONFIG dict

    Returns:
        dict of named pd.Series + convenience scalar fields.
    """
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"]

    sma20  = calc_sma(close, 20)
    sma50  = calc_sma(close, 50)
    sma200 = calc_sma(close, 200)
    ema20  = calc_ema(close, cfg["ema_fast"])
    rsi    = calc_rsi(close, cfg["rsi_period"])
    atr    = calc_atr(high, low, close, cfg["atr_period"])
    atr_pct = atr / (close + 1e-10) * 100.0
    adx    = calc_adx(high, low, close, cfg["adx_period"])
    obv    = calc_obv(close, volume)
    bb_bw  = calc_bb_bandwidth(close, cfg["bb_period"], cfg["bb_std"])
    bb_upper, bb_mid, bb_lower = calc_bb_bands(close, cfg["bb_period"], cfg["bb_std"])

    # Convenience scalars for current bar
    price       = close.iloc[-1]
    avg_vol_20  = volume.rolling(cfg["rvol_avg_period"]).mean().iloc[-1]
    rvol        = volume.iloc[-1] / (avg_vol_20 + 1e-1)
    obv_slope   = (
        (obv.iloc[-1] - obv.iloc[-cfg["obv_slope_lookback"]])
        / (abs(obv.iloc[-cfg["obv_slope_lookback"]]) + 1e-10)
        * 100.0
    )
    sma50_slope = (
        (sma50.iloc[-1] / sma50.iloc[-cfg["slope_lookback"]] - 1.0) * 100.0
        if len(sma50.dropna()) >= cfg["slope_lookback"] else 0.0
    )

    return {
        # Full series
        "sma20":    sma20,
        "sma50":    sma50,
        "sma200":   sma200,
        "ema20":    ema20,
        "rsi":      rsi,
        "atr":      atr,
        "atr_pct":  atr_pct,
        "adx":      adx,
        "obv":      obv,
        "bb_bw":    bb_bw,
        "bb_upper": bb_upper,
        "bb_mid":   bb_mid,
        "bb_lower": bb_lower,

        # Current-bar scalars
        "price":        price,
        "avg_vol_20":   avg_vol_20,
        "rvol":         rvol,
        "obv_slope":    obv_slope,
        "sma50_slope":  sma50_slope,
    }
