"""
elite_filter.py — Stage 2: Reduce scanner output to 10-15 actionable candidates.

KEY DESIGN DECISIONS:
  - No sector diversification filter. At a small account (< $10k, max 5 positions)
    you want the BEST signals, not artificial sector balance. Sector diversification
    is for large funds managing hundreds of positions.

  - Regime-adaptive thresholds. The same ADX/RVOL thresholds that work in a clean
    bull market will give zero results in a choppy/rotating market. This filter
    automatically relaxes thresholds based on current VIX and regime so you always
    get candidates when there are genuine setups, and zero when there truly aren't.

  - Transparent funnel. Every filter step is logged with the count before/after so
    you can see exactly which gate is killing your candidates and tune accordingly.

THRESHOLD GUIDE:
    Bull market (VIX < 15, clear uptrend):
        Use strict thresholds — you want only the very best setups
    Neutral/choppy (VIX 15-25):
        Relax ADX and RVOL — trends are less clean but setups still exist
    Bear/high vol (VIX > 25):
        Only trade the highest-conviction setups, smaller size, wider stops
        Consider reducing elite_max_candidates to 5
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


# ─── Regime-adaptive threshold multipliers ────────────────────────────────────
# Applied on top of base thresholds from config.
# Effectively relaxes filters when the market is not clean.

REGIME_MULTIPLIERS = {
    #                adx_mult  rvol_mult  score_mult
    "bull":         (1.00,     1.00,      1.00),   # full strictness
    "neutral":      (0.85,     0.85,      0.95),   # slightly relaxed
    "bear":         (0.75,     0.75,      0.90),   # more relaxed — fewer but real setups
}

VIX_MULTIPLIERS = {
    # VIX range        adx_mult  rvol_mult
    "low":    (0, 15,   1.00,     1.00),
    "normal": (15, 20,  0.92,     0.90),
    "high":   (20, 25,  0.85,     0.82),
    "vhigh":  (25, 999, 0.75,     0.75),
}


def _get_vix_mult(vix: float) -> tuple[float, float]:
    for key, (lo, hi, am, rm) in VIX_MULTIPLIERS.items():
        if lo <= vix < hi:
            return am, rm
    return 0.75, 0.75


def apply_elite_filter(
    df:      pd.DataFrame,
    cfg:     dict,
    regime:  dict | None = None,
) -> pd.DataFrame:
    """
    Apply Stage 2 elite filters to scanner results.

    Args:
        df:      Full scanner output DataFrame (swing_results_YYYYMMDD.csv)
        cfg:     CONFIG dict
        regime:  Optional dict with keys 'trend' and 'vix' for adaptive thresholds.
                 If None, reads from state.json automatically.

    Returns:
        Filtered DataFrame — the final actionable watchlist.
    """
    if df.empty:
        log.error("Empty DataFrame passed to elite filter")
        return df

    # Normalise column names
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    original = len(df)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)

    # ── Resolve regime ────────────────────────────────────────────────────────
    if regime is None:
        regime = _read_regime_from_state()
    trend = regime.get("trend", "neutral")
    vix   = float(regime.get("vix", 18.0))

    # Compute adaptive thresholds
    reg_adx_m, reg_rvol_m, reg_score_m = REGIME_MULTIPLIERS.get(trend, (0.85, 0.85, 0.95))
    vix_adx_m, vix_rvol_m              = _get_vix_mult(vix)

    adx_thresh   = cfg["elite_min_adx"]   * reg_adx_m  * vix_adx_m
    rvol_thresh  = cfg["elite_min_rvol"]  * reg_rvol_m * vix_rvol_m
    score_thresh = cfg["elite_min_score"] * reg_score_m
    rr_thresh    = cfg["elite_min_rr"]

    # Print header
    print(f"\n{'─'*60}")
    print(f"  ELITE FILTER")
    print(f"  Regime: {trend.upper()}  VIX: {vix:.1f}")
    print(f"  Adaptive thresholds:")
    print(f"    Score  ≥ {score_thresh:.1f}  (base {cfg['elite_min_score']})")
    print(f"    ADX    ≥ {adx_thresh:.1f}  (base {cfg['elite_min_adx']})")
    print(f"    RVOL   ≥ {rvol_thresh:.2f}  (base {cfg['elite_min_rvol']})")
    print(f"    R:R    ≥ {rr_thresh:.1f}")
    print(f"{'─'*60}")

    steps = []

    def _step(label: str, mask=None):
        nonlocal df
        before = len(df)
        if mask is not None:
            df = df[mask].reset_index(drop=True)
        after = len(df)
        dropped = before - after
        marker = "  " if dropped == 0 else f"-{dropped}"
        steps.append(f"  {marker:>4}  {label:<35} → {after} remain")

    # ── 1. Minimum score ──────────────────────────────────────────────────────
    if "score" in df.columns:
        _step(f"score ≥ {score_thresh:.1f}",
              df["score"] >= score_thresh)
    else:
        _step("score (column missing — skipped)")

    # ── 2. Pattern required ───────────────────────────────────────────────────
    if cfg.get("elite_require_pattern", True) and "pattern" in df.columns:
        _step("pattern ≠ none",
              df["pattern"].str.lower().isin(["breakout", "pullback", "squeeze"]))

    # ── 3. ADX — adaptive ────────────────────────────────────────────────────
    if "adx" in df.columns:
        _step(f"adx ≥ {adx_thresh:.1f} (adaptive)",
              df["adx"] >= adx_thresh)

    # ── 4. RVOL — adaptive ────────────────────────────────────────────────────
    if "rvol" in df.columns:
        _step(f"rvol ≥ {rvol_thresh:.2f} (adaptive)",
              df["rvol"] >= rvol_thresh)

    # ── 5. R:R ────────────────────────────────────────────────────────────────
    if "rr" in df.columns:
        _step(f"r:r ≥ {rr_thresh:.1f}",
              df["rr"] >= rr_thresh)

    # ── 6. Positive RS vs SPY ─────────────────────────────────────────────────
    if "rs_avg_pct" in df.columns:
        _step("rs_avg_pct > 0 (outperforming SPY)",
              df["rs_avg_pct"] > 0)

    # ── 7. Valid entry/stop/target prices ─────────────────────────────────────
    price_cols = [c for c in ["entry", "stop", "target"] if c in df.columns]
    if price_cols:
        mask = pd.Series([True] * len(df))
        for col in price_cols:
            mask = mask & (df[col] > 0)
        _step("entry/stop/target > 0", mask)

    # ── 8. Hard cap ───────────────────────────────────────────────────────────
    max_c = cfg.get("elite_max_candidates", 15)
    if len(df) > max_c:
        df = df.head(max_c)
        steps.append(f"  {'':>4}  {'hard cap → top ' + str(max_c):<35} → {len(df)} remain")

    # Print funnel
    print(f"  Input: {original} tickers")
    for s in steps:
        print(s)
    print(f"{'─'*60}")
    print(f"  RESULT: {len(df)} candidates\n")

    if df.empty:
        _print_empty_advice(trend, vix, cfg,
                            adx_thresh, rvol_thresh, score_thresh)
        return df

    _print_watchlist(df)
    return df.reset_index(drop=True)


def _print_empty_advice(trend, vix, cfg,
                        adx_thresh, rvol_thresh, score_thresh):
    """Give actionable advice when 0 candidates pass."""
    print("  ⚠  ZERO CANDIDATES — possible causes:\n")

    if vix > 20:
        print(f"  • VIX={vix:.1f} is elevated. Market is choppy/uncertain.")
        print(f"    This is normal — the filter is working correctly.")
        print(f"    Consider waiting for VIX to settle below 18.")
    if trend == "bear":
        print(f"  • Regime is BEAR. Scanner is applying 0.60× multiplier to scores.")
        print(f"    Most stocks won't meet the minimum score threshold.")

    print(f"\n  Tune these config values if you want to see more candidates:")
    print(f"    elite_min_score:  currently {cfg['elite_min_score']} "
          f"(effective {score_thresh:.1f})  → try {cfg['elite_min_score'] - 5}")
    print(f"    elite_min_adx:    currently {cfg['elite_min_adx']} "
          f"(effective {adx_thresh:.1f})  → try {cfg['elite_min_adx'] - 3}")
    print(f"    elite_min_rvol:   currently {cfg['elite_min_rvol']} "
          f"(effective {rvol_thresh:.2f})  → try {cfg['elite_min_rvol'] - 0.2}")
    print(f"\n  Or share your swing_results CSV and ask Claude to analyze it.\n")


def _print_watchlist(df: pd.DataFrame) -> None:
    cols = [c for c in ["ticker", "score", "pattern", "rsi", "adx",
                        "rvol", "rr", "entry", "stop", "target"]
            if c in df.columns]
    pd.set_option("display.float_format", "{:.2f}".format)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print("  FINAL WATCHLIST")
    print(df[cols].to_string(index=True))
    print()


def _read_regime_from_state() -> dict:
    """Try to read current regime from state.json written by the bot."""
    try:
        import json
        p = Path("state.json")
        if p.exists():
            state = json.loads(p.read_text())
            return state.get("regime", {})
    except Exception:
        pass
    return {}


# ─── Convenience loaders ──────────────────────────────────────────────────────

def load_and_filter(
    csv_path: str = "swing_results.csv",
    cfg: dict = None,
    regime: dict | None = None,
) -> pd.DataFrame:
    """
    Load a scanner CSV and apply the elite filter.

    Usage:
        from elite_filter import load_and_filter
        from config import CONFIG
        watchlist = load_and_filter("scan_results/swing_results_20260224.csv", CONFIG)
        watchlist.to_csv("Scan_result/watchlist_20260224.csv", index=False)
    """
    from config import CONFIG as _cfg
    cfg = cfg or _cfg

    try:
        df = pd.read_csv(csv_path)
        log.info(f"Loaded {len(df)} rows from {csv_path}")
    except FileNotFoundError:
        log.error(f"File not found: {csv_path}")
        return pd.DataFrame()

    return apply_elite_filter(df, cfg, regime)


def load_latest_and_filter(
    scan_dir: str = "Scan_result",
    cfg: dict = None,
    regime: dict | None = None,
) -> pd.DataFrame:
    """
    Auto-find the latest swing_results_*.csv and filter it.
    Saves watchlist_YYYYMMDD.csv to the same folder.

    Usage:
        from elite_filter import load_latest_and_filter
        from config import CONFIG
        watchlist = load_latest_and_filter(cfg=CONFIG)
    """
    from config import CONFIG as _cfg
    cfg = cfg or _cfg

    scan_path = Path(scan_dir)
    csvs = sorted(scan_path.glob("swing_results_*.csv"),
                  key=lambda f: f.stat().st_mtime, reverse=True)
    if not csvs:
        log.error(f"No swing_results_*.csv found in {scan_dir}/")
        return pd.DataFrame()

    latest = csvs[0]
    log.info(f"Using: {latest.name}")

    watchlist = load_and_filter(str(latest), cfg, regime)

    if not watchlist.empty:
        date_str  = datetime.now().strftime("%Y%m%d")
        out_path  = scan_path / f"watchlist_{date_str}.csv"
        watchlist.to_csv(out_path, index=False)
        print(f"[Saved] {out_path}  ({len(watchlist)} tickers)")

    return watchlist