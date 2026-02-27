"""
config.py — Single source of truth for all scanner and bot parameters.

HOW TO USE:
    from config import CONFIG
    cfg = CONFIG  # pass into every function

To run a different scenario:
    import copy
    MY_CFG = copy.deepcopy(CONFIG)
    MY_CFG["rsi_min"] = 50
"""

CONFIG: dict = {

    # ─── Account ─────────────────────────────────────────────────────────────
    "account_size":               1_000.0,  # USD — your total account
    "risk_per_trade_pct":         0.01,     # fraction at risk per trade (1%)
    "min_rr_ratio":               2.0,      # minimum acceptable reward:risk

    # ─── Universe ────────────────────────────────────────────────────────────
    "universe":                   "sp500",  # "sp500" | "nasdaq100" | "custom"
    "custom_tickers":             [],       # used when universe="custom"

    # ─── Liquidity — hard filters ─────────────────────────────────────────────
    "min_price":                  10.0,     # USD
    "max_price":                  500.0,    # USD
    "min_avg_volume":             1_000_000,# shares/day (20-day rolling average)
    "min_dollar_volume":          10_000_000,# USD/day

    # ─── Trend filters ───────────────────────────────────────────────────────
    "sma_periods":                [20, 50, 200],
    "ema_fast":                   20,
    "adx_period":                 14,
    "adx_min":                    20.0,
    "slope_lookback":             10,       # bars for SMA50 slope direction
    "min_trend_conditions":       3,        # out of 5 to pass

    # ─── Momentum ────────────────────────────────────────────────────────────
    "rsi_period":                 14,
    "rsi_min":                    45.0,
    "rsi_max":                    70.0,
    "rsi_ideal":                  60.0,

    # ─── Volatility ──────────────────────────────────────────────────────────
    "atr_period":                 14,
    "atr_pct_min":                2.0,
    "atr_pct_max":                8.0,
    "atr_pct_ideal":              4.5,

    # ─── Volume ──────────────────────────────────────────────────────────────
    "rvol_avg_period":            20,
    "rvol_threshold":             1.5,
    "obv_slope_lookback":         10,

    # ─── Relative Strength ───────────────────────────────────────────────────
    "rs_windows":                 [20, 60, 120],
    "benchmark":                  "SPY",

    # ─── Pattern: Breakout ───────────────────────────────────────────────────
    "consolidation_days":         15,
    "consolidation_tight":        0.12,
    "breakout_buffer_pct":        0.005,

    # ─── Pattern: Pullback ───────────────────────────────────────────────────
    "pullback_min_pct":           0.03,
    "pullback_max_pct":           0.12,
    "pullback_ema_touch":         0.025,
    "pullback_rsi_min":           40.0,
    "pullback_rsi_max":           60.0,
    "pullback_rsi_ideal":         52.0,
    "pullback_depth_ideal":       0.07,

    # ─── Pattern: BB Squeeze ─────────────────────────────────────────────────
    "bb_period":                  20,
    "bb_std":                     2.0,
    "squeeze_percentile":         0.25,
    "squeeze_lookback":           50,

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
    "vix_high_threshold":         30.0,
    "vix_high_multiplier":        0.80,

    # ─── Output / Display ────────────────────────────────────────────────────
    "top_n":                      15,
    "min_score_display":          40.0,

    # ─── Interactive Brokers — Scanner ────────────────────────────────────────
    "ib_host":                    "127.0.0.1",
    "ib_port":                    7497,     # 7497=TWS paper, 7496=TWS live, 4002=Gateway paper
    "ib_client_id":               1,        # scanner client
    "ib_timeout":                 30,

    # ─── IB Concurrency & Rate Limiting ──────────────────────────────────────
    # IB hard rule: max 50 historical requests per 10 seconds.
    # Lower ib_concurrent_requests to 15-20 if you see Error 162.
    "ib_concurrent_requests":     40,
    "ib_rate_limit_requests":     45,
    "ib_rate_limit_window":       10.0,

    # ─── IB Historical Data Settings ─────────────────────────────────────────
    "history_duration":           "1 Y",
    "history_bar_size":           "1 day",
    "history_what_to_show":       "TRADES",
    "min_bars_required":          60,

    # ─── Dashboard ───────────────────────────────────────────────────────────
    "dashboard_host":             "127.0.0.1",
    "dashboard_port":             8050,

    # =========================================================================
    # STAGE 2: ELITE FILTER
    # Reduces the ~180 scanner outputs to 10-15 actionable candidates.
    # Applied once per week after the full scan completes.
    # =========================================================================

    # ── Elite filter ──────────────────────────────────────────────────────────
    # These are BASE thresholds. The filter automatically relaxes them based on
    # current VIX and regime (see elite_filter.py REGIME_MULTIPLIERS).
    # At VIX=21 (current market), effective ADX threshold is ~18, RVOL ~1.35.
    "elite_min_score":            58.0,    # base minimum score (relaxed for choppy market)
    "elite_max_candidates":       15,      # max watchlist size
    "elite_min_adx":              22.0,    # base ADX (adaptive — auto-relaxed by regime)
    "elite_min_rvol":             1.5,     # base RVOL (adaptive — auto-relaxed by regime)
    "elite_min_rr":               2.0,     # minimum R:R (not adaptive — hard floor)
    "elite_require_pattern":      True,    # must have a detected pattern
    # NOTE: sector diversification removed — irrelevant at small account sizes.
    # You want the best 5 signals, not artificial balance across sectors.

    # =========================================================================
    # BOT: ENTRY SCANNER
    # Runs continuously during market hours, checking elite watchlist for
    # intraday confirmation of daily entry signals.
    # =========================================================================

    # IB connection (separate client_id from scanner to avoid conflicts)
    "bot_ib_client_id":           2,

    # Scan timing
    "bot_scan_interval_sec":      300,     # check watchlist every 5 minutes
    "bot_market_open":            "09:30", # ET — no entries before this
    "bot_market_close":           "16:00", # ET
    "bot_no_trade_last_min":      15,      # no new entries in final N minutes
    "bot_pre_entry_buffer_min":   5,       # wait N min after open before first scan

    # Intraday confirmation (5min bars to confirm daily signal)
    "bot_intraday_bar_size":      "5 mins",
    "bot_intraday_bars":          20,      # how many intraday bars to fetch
    "bot_confirm_above_trigger":  True,    # price must close above trigger level
    "bot_confirm_bars":           1,       # bars that must close above trigger

    # Entry trigger levels
    # breakout: price > base_high (already on daily, just confirm intraday)
    # pullback: price > yesterday's high on 5min bar (reversal candle)
    "bot_entry_trigger_buffer":   0.001,   # 0.1% buffer above trigger price

    # Position limits
    "bot_max_open_trades":        5,       # hard cap concurrent live positions

    # =========================================================================
    # ORDER EXECUTION
    # =========================================================================

    "order_transmit":             False,   # SAFETY: False = stage in TWS, don't send
                                           # Set True ONLY after paper testing
    "order_tif":                  "GTC",   # time-in-force: "DAY" | "GTC"

    # ── Backtest settings ──────────────────────────────────────────────────────
    "backtest_max_hold_bars":     40,      # max bars before timeout exit (~8 weeks daily)
    "backtest_slippage_pct":      0.05,    # % slippage on simulated fills
    "order_type":                 "LMT",   # "LMT" (preferred) | "MKT"
    "order_limit_slippage_pct":   0.001,   # LMT price = trigger × (1 + this)
    "use_bracket_orders":         True,    # bracket = entry + TP + SL in one shot

    # =========================================================================
    # ORDER HISTORY, SCREENSHOTS & TRADE LOGGING
    # =========================================================================

    "order_history_dir":          "order_history",
    "ohlcv_cache_dir":            "ohlcv_cache",
    # Filename pattern: {ticker}_{yyyymmdd}_{type}_{order_id}_{event}.png
    # Example: AAPL_20250222_breakout_1042_entry.png

    # Screenshot settings
    "screenshot_dpi":             150,
    "screenshot_lookback_bars":   60,      # bars before event
    "screenshot_lookahead_bars":  20,      # bars after event (for exit screenshots)
    "screenshot_intraday_bars":   48,      # 5min bars to show in intraday panel

    # What to capture
    "capture_on_entry":           True,    # screenshot when order fills
    "capture_on_exit":            True,    # screenshot when TP or SL triggers
    "capture_on_cancel":          True,    # screenshot if order cancelled/expired

    # Trade metadata logged to JSON alongside every screenshot
    "log_level":                  "INFO",  # "DEBUG" | "INFO" | "WARNING"
}