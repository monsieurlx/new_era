"""
config.py — Single source of truth for all scanner parameters.

HOW TO USE:
    from config import CONFIG
    cfg = CONFIG  # pass into every function

To run a different scenario, make a copy and override keys:
    from config import CONFIG
    import copy
    MY_CFG = copy.deepcopy(CONFIG)
    MY_CFG["rsi_min"] = 50  # override one value
"""

CONFIG: dict = {

    # ─── Account ─────────────────────────────────────────────────────────────
    "account_size":           1_000.0,   # USD — your total account
    "risk_per_trade_pct":     0.01,      # fraction at risk per trade (1%)
    "min_rr_ratio":           2.0,       # minimum acceptable reward:risk

    # ─── Universe ────────────────────────────────────────────────────────────
    "universe":               "sp500",   # "sp500" | "nasdaq100" | "custom"
    "custom_tickers":         [],        # list of tickers; used when universe="custom"

    # ─── Liquidity — hard filters ─────────────────────────────────────────────
    "min_price":              10.0,      # USD
    "max_price":              500.0,     # USD
    "min_avg_volume":         1_000_000, # shares/day (20-day rolling average)
    "min_dollar_volume":      10_000_000,# USD/day (price × volume, 20-day avg)

    # ─── Trend filters ───────────────────────────────────────────────────────
    "sma_periods":            [20, 50, 200],
    "ema_fast":               20,
    "adx_period":             14,
    "adx_min":                20.0,      # ADX must exceed this to confirm trend
    "slope_lookback":         10,        # bars to measure SMA50 slope direction
    "min_trend_conditions":   3,         # out of 5 conditions needed to pass

    # ─── Momentum ────────────────────────────────────────────────────────────
    "rsi_period":             14,
    "rsi_min":                45.0,      # minimum RSI for long candidates
    "rsi_max":                70.0,      # maximum RSI (avoid overbought)
    "rsi_ideal":              60.0,      # ideal RSI value for scoring

    # ─── Volatility ──────────────────────────────────────────────────────────
    "atr_period":             14,
    "atr_pct_min":            2.0,       # ATR% must exceed this (fuel)
    "atr_pct_max":            8.0,       # ATR% must not exceed this (risk)
    "atr_pct_ideal":          4.5,       # ideal ATR% for scoring

    # ─── Volume ──────────────────────────────────────────────────────────────
    "rvol_avg_period":        20,        # rolling average period for RVOL
    "rvol_threshold":         1.5,       # breakout trigger minimum RVOL
    "obv_slope_lookback":     10,        # bars to measure OBV direction

    # ─── Relative Strength ───────────────────────────────────────────────────
    "rs_windows":             [20, 60, 120],  # trading-day windows ~1M, 3M, 6M
    "benchmark":              "SPY",

    # ─── Pattern: Breakout ───────────────────────────────────────────────────
    "consolidation_days":     15,        # bars to look back for base
    "consolidation_tight":    0.12,      # max range: high/low - 1 <= 12%
    "breakout_buffer_pct":    0.005,     # close must be 0.5% above base_high

    # ─── Pattern: Pullback ───────────────────────────────────────────────────
    "pullback_min_pct":       0.03,      # min retracement from swing high
    "pullback_max_pct":       0.12,      # max retracement allowed
    "pullback_ema_touch":     0.025,     # must be within 2.5% of EMA20
    "pullback_rsi_min":       40.0,      # RSI floor for pullback (not breakdown)
    "pullback_rsi_max":       60.0,      # RSI ceiling for pullback (not overbought)
    "pullback_rsi_ideal":     52.0,      # ideal RSI for pullback scoring
    "pullback_depth_ideal":   0.07,      # ideal pullback depth (7%) for scoring

    # ─── Pattern: BB Squeeze ─────────────────────────────────────────────────
    "bb_period":              20,
    "bb_std":                 2.0,
    "squeeze_percentile":     0.25,      # bandwidth must be in bottom 25th pct
    "squeeze_lookback":       50,        # bars of history for percentile calc

    # ─── Scoring Weights (must sum to 1.0) ───────────────────────────────────
    "score_weights": {
        "trend":   0.20,
        "pattern": 0.20,
        "rs":      0.15,
        "rvol":    0.12,
        "rsi":     0.10,
        "rr":      0.10,
        "atr_fit": 0.08,
        "obv":     0.05,
    },

    # ─── Regime Multipliers ───────────────────────────────────────────────────
    "regime_multipliers": {
        "bull":    1.10,
        "neutral": 1.00,
        "bear":    0.60,
    },
    "vix_high_threshold":     30.0,      # VIX above this = apply extra penalty
    "vix_high_multiplier":    0.80,

    # ─── Output / Display ────────────────────────────────────────────────────
    "top_n":                  15,        # rows to display in console
    "min_score_display":      40.0,      # hide rows below this score

    # ─── Interactive Brokers ─────────────────────────────────────────────────
    "ib_host":                "127.0.0.1",
    "ib_port":                7497,      # 7497=TWS paper, 7496=TWS live, 4002=Gateway paper
    "ib_client_id":           1,         # must be unique per connected script
    "ib_timeout":             30,        # seconds to wait for connection
    "ib_request_delay":       0.6,       # seconds between historical data requests (pacing)

    # ─── IB Historical Data Settings ─────────────────────────────────────────
    "history_duration":       "1 Y",     # IB duration string
    "history_bar_size":       "1 day",   # IB bar size
    "history_what_to_show":   "TRADES",  # price data type
    "min_bars_required":      60,        # drop tickers with fewer bars

    # ─── Dashboard ───────────────────────────────────────────────────────────
    "dashboard_host":         "127.0.0.1",
    "dashboard_port":         8050,
}
