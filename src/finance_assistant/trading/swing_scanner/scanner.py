"""
scanner.py — Main orchestrator. Runs the full pipeline end to end.

PERFORMANCE OPTIMIZATIONS:
  - IB data fetch: concurrent async requests (semaphore + rate limiter)
    → 503 tickers in ~60-90s instead of ~5 minutes
  - Scoring: parallel across CPU cores via ProcessPoolExecutor
    → indicators + filters + pattern + risk computed simultaneously
    → 500 tickers scored in ~2-3s instead of ~15s sequentially

Pipeline:
  1. Load universe
  2. Connect to IB, download data concurrently
  3. Detect regime (SPY + VIX)
  4. Score all tickers in parallel (CPU-bound work → process pool)
  5. Sort, print, save CSV
"""

import asyncio
import logging
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import os
import pandas as pd

from config import CONFIG
from ib_client import get_client
from universe import get_tickers
from indicators import calc_all
from regime import detect_regime
from filters import apply_all_filters
from patterns import detect_best_pattern
from risk import compute_risk
from scorer import score_ticker

logger = logging.getLogger(__name__)

DISPLAY_COLS = [
    "ticker", "score", "price", "pattern", "rsi",
    "atr_pct", "rvol", "trend_count", "rr",
    "entry", "stop", "target", "shares", "position_value",
]


# ─── Per-ticker worker (runs in separate process) ─────────────────────────────

def _process_one_ticker(
    ticker: str,
    df: pd.DataFrame,
    spy_close: pd.Series,
    regime: dict,
    cfg: dict,
) -> tuple:
    """
    Complete pipeline for one ticker.
    Runs in a process pool worker — no async, no shared state.

    Returns: ("ok", row_dict) | ("reject", reason_str) | ("error", exc_str)
    """
    try:
        inds = calc_all(df, cfg)

        passes, reason = apply_all_filters(ticker, df, inds, cfg)
        if not passes:
            return ("reject", reason.split("_")[0])

        rs_scores = []
        for w in cfg["rs_windows"]:
            if len(df) >= w and len(spy_close) >= w:
                rs_scores.append(
                    float(df["close"].pct_change(w).iloc[-1]
                          - spy_close.pct_change(w).iloc[-1])
                )

        pattern = detect_best_pattern(df, inds, cfg)
        risk    = compute_risk(df, inds, pattern, cfg, regime["size_mult"])
        scores  = score_ticker(ticker, df, inds, pattern, rs_scores, regime, risk, cfg)
        row     = {**scores, **{k: v for k, v in risk.items() if k not in scores}}
        return ("ok", row)

    except Exception as e:
        return ("error", str(e))


async def _score_all_parallel(
    data: dict,
    spy_close: pd.Series,
    regime: dict,
    cfg: dict,
) -> tuple:
    """
    Score all tickers in parallel using a ProcessPoolExecutor.

    CPU-bound work (indicator math, numpy operations) is distributed across
    all available CPU cores. Typical speedup: 4-8x on a modern machine.
    """
    loop     = asyncio.get_event_loop()
    results  = []
    rejected = defaultdict(int)
    items    = list(data.items())

    with ProcessPoolExecutor() as pool:
        futures = {
            loop.run_in_executor(
                pool,
                _process_one_ticker,
                ticker, df, spy_close, regime, cfg,
            ): ticker
            for ticker, df in items
        }
        for fut in asyncio.as_completed(futures):
            try:
                status, payload = await fut
                if status == "ok":
                    results.append(payload)
                elif status == "reject":
                    rejected[payload] += 1
                else:
                    rejected["error"] += 1
            except Exception as e:
                rejected["error"] += 1
                logger.debug(f"Gather error: {e}")

    return results, rejected


# ─── Main Scanner ─────────────────────────────────────────────────────────────

async def run_scanner(cfg: dict = CONFIG) -> pd.DataFrame:
    """
    Run the full swing trading scanner pipeline.

    Returns:
        pd.DataFrame sorted by score descending. Also saves swing_results.csv.
    """
    t_start = time.monotonic()

    print("\n" + "=" * 65)
    print(f"  SWING TRADING SCANNER   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 65)

    # ── Step 1: Universe ──────────────────────────────────────────────────────
    tickers = get_tickers(cfg)
    print(f"\n[1/5] Universe: {len(tickers)} tickers ({cfg['universe']})")

    # ── Step 2: Concurrent data download ─────────────────────────────────────
    print(f"[2/5] Connecting to IB ({cfg['ib_host']}:{cfg['ib_port']})...")
    client = get_client(cfg)
    await client.connect()

    t_fetch = time.monotonic()
    print("      Fetching SPY, VIX and all tickers concurrently...")

    # SPY and VIX are launched simultaneously with the full ticker fetch
    spy_task = asyncio.create_task(client.fetch_historical_stock(cfg["benchmark"]))
    vix_task = asyncio.create_task(client.fetch_vix())
    all_task = asyncio.create_task(client.fetch_all_historical(tickers))

    spy_df, vix_series, data = await asyncio.gather(spy_task, vix_task, all_task)
    await client.disconnect()

    fetch_elapsed = time.monotonic() - t_fetch
    print(f"      Fetch complete: {len(data)} tickers in {fetch_elapsed:.1f}s")

    if spy_df.empty:
        logger.error("Failed to fetch SPY data. Check IB connection.")
        return pd.DataFrame()

    # ── Step 3: Regime ────────────────────────────────────────────────────────
    print("[3/5] Detecting market regime...")
    regime = detect_regime(spy_df, vix_series, cfg)

    # ── Step 4: Parallel scoring ──────────────────────────────────────────────
    t_score = time.monotonic()
    print(f"[4/5] Scoring {len(data)} tickers in parallel...")

    spy_close = spy_df["close"]
    results, rejected = await _score_all_parallel(data, spy_close, regime, cfg)

    score_elapsed = time.monotonic() - t_score
    print(f"      Done: {len(results)} passed / "
          f"{sum(rejected.values())} rejected in {score_elapsed:.1f}s")

    # ── Step 5: Sort, display, save ───────────────────────────────────────────
    print("[5/5] Sorting and saving...")

    if not results:
        print("\n[!] No tickers passed all filters.")
        print("    Tips: lower min_trend_conditions, widen atr_pct_max, lower adx_min")
        return pd.DataFrame()

    df_out = (
        pd.DataFrame(results)
        .sort_values("score", ascending=False)
        .reset_index(drop=True)
    )
    df_out.index += 1

    df_display = df_out[df_out["score"] >= cfg["min_score_display"]]
    _print_summary(df_display, regime, cfg, rejected, len(data))

    # Output CSV to scan_result folder with yyyymmdd metadata
    out_dir = "scan_result"
    os.makedirs(out_dir, exist_ok=True)
    date_str = datetime.now().strftime('%Y%m%d')
    out_name = f"swing_results_{date_str}.csv"
    out_path = os.path.join(out_dir, out_name)
    df_out.to_csv(out_path, index=True)

    # Apply elite filter and save watchlist
    try:
        from elite_filter import apply_elite_filter
        watchlist = apply_elite_filter(df_out, cfg)
        date_str = datetime.now().strftime('%Y%m%d')
        watchlist_name = f"watchlist_{date_str}.csv"
        watchlist_path = os.path.join("Scan_result", watchlist_name)
        watchlist.to_csv(watchlist_path, index=False)
        print(f"[Saved] {watchlist_path} ({len(watchlist)} rows)")
    except Exception as e:
        print(f"[Elite Filter Error] {e}")

    total_elapsed = time.monotonic() - t_start
    print(f"\n[Done] {total_elapsed:.1f}s total  "
          f"({fetch_elapsed:.1f}s fetch + {score_elapsed:.1f}s scoring)")
    print(f"[Saved] {out_path} ({len(df_out)} rows)")

    return df_out


# ─── Console Display ──────────────────────────────────────────────────────────

def _print_summary(df, regime, cfg, rejected, total_fetched):
    top     = df.head(cfg["top_n"])
    vix_str = f"{regime['vix']:.1f}" if regime.get("vix") else "N/A"

    print("\n" + "=" * 65)
    print(f"  TOP {cfg['top_n']} CANDIDATES   "
          f"Regime: {regime['trend'].upper()}   VIX: {vix_str}")
    print("=" * 65)

    cols = [c for c in DISPLAY_COLS if c in top.columns]
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 140)
    pd.set_option("display.float_format", "{:.2f}".format)
    print(top[cols].to_string())

    print("\n" + "─" * 65)
    print("  DETAILED BREAKDOWN — Top 5")
    print("─" * 65)
    for _, row in top.head(5).iterrows():
        _print_detail(row)

    total_rej = sum(rejected.values())
    print(f"\n  Passed: {len(df)}  |  Fetched: {total_fetched}  "
          f"|  Rejected: {total_rej}")
    for reason, count in sorted(rejected.items(), key=lambda x: -x[1]):
        print(f"    {reason:<25}: {count}")
    print("─" * 65)


def _print_detail(row):
    print(f"\n  [{row['ticker']}]  Score: {row['score']}  |  "
          f"Pattern: {row.get('pattern','?').upper()}")
    print(f"    Price: ${row.get('price',0):.2f}  "
          f"Trend: {row.get('trend_count','?')}/5  "
          f"RSI: {row.get('rsi',0):.1f}  "
          f"ATR%: {row.get('atr_pct',0):.2f}%  "
          f"RVOL: {row.get('rvol',0):.2f}x")
    print(f"    Entry: ${row.get('entry',0):.2f}  "
          f"Stop: ${row.get('stop',0):.2f}  "
          f"Target: ${row.get('target',0):.2f}  "
          f"R:R: {row.get('rr',0):.1f}:1")
    print(f"    Shares: {row.get('shares',0)}  "
          f"Position: ${row.get('position_value',0):.2f}  "
          f"RS vs SPY: {row.get('rs_avg_pct',0):+.2f}%")