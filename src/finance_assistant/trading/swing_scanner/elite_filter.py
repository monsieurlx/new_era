"""
elite_filter.py — Stage 2: Reduce ~180 scanner outputs to 10-15 actionable candidates.

Applied AFTER the weekly scan. Takes the full scored DataFrame and applies
stricter filters + sector diversification to produce the final watchlist.

Why this stage?
  180 candidates is too many to monitor — even a bot cannot track that many with
  discipline. The elite filter enforces: higher bar for every signal, max 2
  candidates per sector (avoid sector clustering), and a hard cap on size.

Usage:
    from elite_filter import apply_elite_filter
    watchlist = apply_elite_filter(df_scanner_results, cfg)
    watchlist.to_csv("watchlist.csv", index=False)
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ─── GICS Sector mapping (ticker → sector) ────────────────────────────────────
# Covers S&P 500 components. Used to enforce sector diversification.
# Pulled from a static mapping — no API call needed.
SECTOR_MAP: dict[str, str] = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "AVGO": "Technology", "ORCL": "Technology", "CRM": "Technology",
    "ACN":  "Technology", "AMD":  "Technology", "ADBE": "Technology",
    "QCOM": "Technology", "TXN":  "Technology", "INTC": "Technology",
    "MU":   "Technology", "AMAT": "Technology", "LRCX": "Technology",
    # Communication
    "GOOGL":"Communication", "META": "Communication", "NFLX": "Communication",
    "DIS":  "Communication", "CMCSA":"Communication", "T":    "Communication",
    "VZ":   "Communication", "TMUS": "Communication",
    # Consumer Discretionary
    "AMZN": "ConsDisc", "TSLA": "ConsDisc", "HD":   "ConsDisc",
    "MCD":  "ConsDisc", "NKE":  "ConsDisc", "SBUX": "ConsDisc",
    "TGT":  "ConsDisc", "LOW":  "ConsDisc", "BKNG": "ConsDisc",
    # Consumer Staples
    "WMT":  "ConsStaples", "PG":   "ConsStaples", "KO":   "ConsStaples",
    "PEP":  "ConsStaples", "COST": "ConsStaples", "MDLZ": "ConsStaples",
    # Financials
    "JPM":  "Financials", "BAC":  "Financials", "WFC":  "Financials",
    "GS":   "Financials", "MS":   "Financials", "BLK":  "Financials",
    "AXP":  "Financials", "SPGI": "Financials", "CME":  "Financials",
    "BX":   "Financials", "SCHW": "Financials", "V":    "Financials",
    "MA":   "Financials",
    # Healthcare
    "UNH":  "Healthcare", "JNJ":  "Healthcare", "LLY":  "Healthcare",
    "ABBV": "Healthcare", "MRK":  "Healthcare", "TMO":  "Healthcare",
    "ABT":  "Healthcare", "DHR":  "Healthcare", "ISRG": "Healthcare",
    "SYK":  "Healthcare", "BSX":  "Healthcare", "ZTS":  "Healthcare",
    # Energy
    "XOM":  "Energy", "CVX":  "Energy", "COP":  "Energy",
    "EOG":  "Energy", "SLB":  "Energy", "PSX":  "Energy",
    # Industrials
    "CAT":  "Industrials", "HON":  "Industrials", "UPS":  "Industrials",
    "DE":   "Industrials", "GE":   "Industrials", "MMM":  "Industrials",
    "RTX":  "Industrials", "LMT":  "Industrials", "NOC":  "Industrials",
    # Utilities / RE / Materials (less common in swing trading)
    "NEE":  "Utilities", "DUK":  "Utilities",
    "AMT":  "RealEstate", "PLD":  "RealEstate",
    "LIN":  "Materials", "APD":  "Materials", "FCX":  "Materials",
}


def apply_elite_filter(
    df: pd.DataFrame,
    cfg: dict,
) -> pd.DataFrame:
    """
    Apply Stage 2 elite filters to scanner results.

    Filters applied in order:
      1. Minimum composite score
      2. Pattern required (not "none")
      3. Minimum ADX (stronger trend)
      4. Minimum RVOL (stronger volume)
      5. Minimum R:R
      6. Minimum RS windows outperformed
      7. Sector diversification (max N per sector)
      8. Hard cap on total candidates

    Args:
        df:  Full scanner output DataFrame (from swing_results.csv)
        cfg: CONFIG dict

    Returns:
        Filtered DataFrame — the final actionable watchlist.
    """
    original_count = len(df)
    df = df.copy().sort_values("score", ascending=False)
    log_steps = []

    # ── 1. Minimum score ─────────────────────────────────────────────────────
    df = df[df["score"] >= cfg["elite_min_score"]]
    log_steps.append(f"min_score>={cfg['elite_min_score']}: {len(df)} remain")

    # ── 2. Pattern required ───────────────────────────────────────────────────
    if cfg.get("elite_require_pattern", True) and "pattern" in df.columns:
        df = df[df["pattern"] != "none"]
        log_steps.append(f"pattern_required: {len(df)} remain")

    # ── 3. Minimum ADX ────────────────────────────────────────────────────────
    if "adx" in df.columns:
        df = df[df["adx"] >= cfg["elite_min_adx"]]
        log_steps.append(f"adx>={cfg['elite_min_adx']}: {len(df)} remain")

    # ── 4. Minimum RVOL ───────────────────────────────────────────────────────
    if "rvol" in df.columns:
        df = df[df["rvol"] >= cfg["elite_min_rvol"]]
        log_steps.append(f"rvol>={cfg['elite_min_rvol']}: {len(df)} remain")

    # ── 5. Minimum R:R ────────────────────────────────────────────────────────
    if "rr" in df.columns:
        df = df[df["rr"] >= cfg["elite_min_rr"]]
        log_steps.append(f"rr>={cfg['elite_min_rr']}: {len(df)} remain")

    # ── 6. RS windows ─────────────────────────────────────────────────────────
    # rs_avg_pct must be positive (outperforming benchmark)
    if "rs_avg_pct" in df.columns:
        df = df[df["rs_avg_pct"] > 0]
        log_steps.append(f"rs_positive: {len(df)} remain")

    # ── 7. Sector diversification ─────────────────────────────────────────────
    df = _apply_sector_limit(df, cfg.get("elite_max_per_sector", 2))
    log_steps.append(f"sector_limit={cfg.get('elite_max_per_sector',2)}: {len(df)} remain")

    # ── 8. Hard cap ───────────────────────────────────────────────────────────
    df = df.head(cfg["elite_max_candidates"])

    # Print filter funnel
    print(f"\n{'─'*55}")
    print(f"  ELITE FILTER: {original_count} → {len(df)} candidates")
    print(f"{'─'*55}")
    for step in log_steps:
        print(f"  {step}")
    print(f"{'─'*55}")

    if not df.empty:
        _print_watchlist(df)

    return df.reset_index(drop=True)


def _apply_sector_limit(df: pd.DataFrame, max_per_sector: int) -> pd.DataFrame:
    """Keep at most N candidates per sector (score-ranked, so best survive)."""
    if "ticker" not in df.columns:
        return df

    sector_counts: dict[str, int] = {}
    keep = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        sector = SECTOR_MAP.get(ticker, "Unknown")
        count  = sector_counts.get(sector, 0)
        if count < max_per_sector:
            sector_counts[sector] = count + 1
            keep.append(row)

    return pd.DataFrame(keep) if keep else pd.DataFrame(columns=df.columns)


def _print_watchlist(df: pd.DataFrame) -> None:
    """Pretty-print the final watchlist."""
    cols = [c for c in ["ticker", "score", "price", "pattern", "rsi",
                        "adx", "rvol", "rr", "entry", "stop", "target"]
            if c in df.columns]
    print("\n  FINAL WATCHLIST")
    print(df[cols].to_string(index=True))
    print()


def load_and_filter(csv_path: str = "swing_results.csv", cfg: dict = None) -> pd.DataFrame:
    """
    Convenience: load scanner CSV and apply elite filter.

    Usage:
        from elite_filter import load_and_filter
        from config import CONFIG
        watchlist = load_and_filter("swing_results.csv", CONFIG)
        watchlist.to_csv("watchlist.csv", index=False)
    """
    from config import CONFIG as _cfg
    cfg = cfg or _cfg

    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows from {csv_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {csv_path}. Run scanner first.")
        return pd.DataFrame()

    return apply_elite_filter(df, cfg)
