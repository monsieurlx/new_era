"""
run.py — Entry point for the complete swing trading system.

══════════════════════════════════════════════════════════════════
 QUICK START
══════════════════════════════════════════════════════════════════

  PAPER TRADING (recommended to start):
    python run.py --mode weekly   --paper    # Sunday evening
    python run.py --mode filter   --paper    # right after weekly
    python run.py --mode bot      --paper    # weekdays 9:25am → auto-exits 16:00
    python run.py --mode dashboard            # always-on, any time

  LIVE TRADING (only after weeks of paper testing):
    python run.py --mode bot --live --transmit

══════════════════════════════════════════════════════════════════
 AUTOMATION ON LOCAL MACHINE
══════════════════════════════════════════════════════════════════

  Windows Task Scheduler:
    Task 1 — "Weekly Scan"
      Trigger:  Every Sunday at 19:00
      Action:   python C:\\path\\run.py --mode weekly --paper
      Then:     python C:\\path\\run.py --mode filter --paper

    Task 2 — "Daily Scan"
      Trigger:  Mon-Fri at 09:00
      Action:   python C:\\path\\run.py --mode daily --paper

    Task 3 — "Bot"
      Trigger:  Mon-Fri at 09:25
      Action:   python C:\\path\\run.py --mode bot --paper
      Note:     Bot auto-exits at 16:00 ET

    Task 4 — "Dashboard" (optional, or just run manually)
      Trigger:  On startup
      Action:   python C:\\path\\run.py --mode dashboard

  Mac / Linux crontab (crontab -e):
    0  19 * * 0   cd /path && python run.py --mode weekly --paper
    5  19 * * 0   cd /path && python run.py --mode filter --paper
    0   9 * * 1-5 cd /path && python run.py --mode daily  --paper
    25  9 * * 1-5 cd /path && python run.py --mode bot    --paper

  Note: IB TWS or Gateway must be running before the bot starts.
  IB Gateway is lighter than TWS and better for automated use.
  Set it to auto-restart on logon in IB Gateway settings.

══════════════════════════════════════════════════════════════════
 PORTS
══════════════════════════════════════════════════════════════════
  Paper  TWS:     7497   (--paper,  default)
  Paper  Gateway: 4002   (--paper --gateway)
  Live   TWS:     7496   (--live)
  Live   Gateway: 4001   (--live --gateway)

══════════════════════════════════════════════════════════════════
 PAPER → LIVE CHECKLIST
══════════════════════════════════════════════════════════════════
  □ Run paper mode for at least 2-4 weeks
  □ Review order_history/ screenshots — do entries make sense?
  □ Run: python run.py --mode analyze — check win rate and R
  □ Verify bracket orders appear correctly in TWS paper account
  □ Set small position sizes in config.py first (risk_per_trade_pct)
  □ Only then: python run.py --mode bot --live --transmit
"""

import argparse
import asyncio
import copy
import logging
import os
import sys

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)-20s  %(message)s",
    datefmt="%H:%M:%S",
)
for lib in ("ib_async", "asyncio", "werkzeug"):
    logging.getLogger(lib).setLevel(
        logging.DEBUG if log_level == "DEBUG" else logging.WARNING
    )

logger = logging.getLogger("run")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Swing Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--mode", default="weekly",
                   choices=["weekly","daily","filter","bot","dashboard","test","analyze"],
                   help="Run mode (default: weekly)")

    # Paper / Live
    mode_grp = p.add_mutually_exclusive_group()
    mode_grp.add_argument("--paper", action="store_true", default=True,
                          help="Paper trading mode (default)")
    mode_grp.add_argument("--live",  action="store_true",
                          help="Live trading mode — real money")

    # Gateway vs TWS
    p.add_argument("--gateway", action="store_true",
                   help="Use IB Gateway instead of TWS (lighter, better for automation)")

    # Safety
    p.add_argument("--transmit", action="store_true",
                   help="Actually transmit orders (default: dry-run, stages in TWS only)")

    # Overrides
    p.add_argument("--port",      type=int, help="Override IB port")
    p.add_argument("--client-id", type=int, help="Override IB client ID")
    p.add_argument("--top-n",     type=int, help="Override top N results")
    p.add_argument("--tickers",   type=str, help="Comma-separated tickers for test mode")
    p.add_argument("--watchlist", default="watchlist.csv",
                   help="Watchlist CSV for bot mode")
    p.add_argument("--input",     default="scan_results",
                   help="Scanner output folder/file for filter mode")
    p.add_argument("--force", action="store_true",
                   help="Bypass market hours check — run bot anytime (paper testing)")

    return p.parse_args()


def build_config(args) -> dict:
    from config import CONFIG
    cfg = copy.deepcopy(CONFIG)

    # Trading mode
    is_live = getattr(args, "live", False)
    cfg["trading_mode"] = "live" if is_live else "paper"

    # Port selection
    if args.port:
        cfg["ib_port"] = args.port
    elif is_live:
        cfg["ib_port"] = 4001 if getattr(args, "gateway", False) else 7496
    else:
        cfg["ib_port"] = 4002 if getattr(args, "gateway", False) else 7497

    if getattr(args, "client_id", None):
        cfg["ib_client_id"] = args.client_id

    if args.top_n:
        cfg["top_n"] = args.top_n

    if args.transmit:
        if not is_live:
            # Paper transmit is safe — paper account
            cfg["order_transmit"] = True
            logger.info("Paper transmit enabled — orders sent to paper account")
        else:
            cfg["order_transmit"] = True
            logger.warning("⚠  LIVE TRANSMIT — real orders will be sent!")

    return cfg


# ── Mode handlers ─────────────────────────────────────────────────────────────

async def mode_weekly(cfg: dict) -> None:
    """Full S&P500 scan → saves swing_results_YYYYMMDD.csv in scan_results/"""
    from scanner import run_scanner
    df = await run_scanner(cfg)
    if not df.empty:
        print("\nNext: python run.py --mode filter --paper")


async def mode_daily(cfg: dict) -> None:
    """Re-score watchlist tickers with fresh data. Faster than weekly."""
    import pandas as pd
    from pathlib import Path
    scan_dir = Path(__file__).parent / "Scan_result"
    csv_files = sorted(scan_dir.glob("watchlist_*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not csv_files:
        logger.error("No watchlist_*.csv found in Scan_result — run weekly + filter first")
        return

    wl = pd.read_csv(csv_files[0])
    wl.columns = [c.strip().lower() for c in wl.columns]
    logger.info(f"Daily rescore: {len(wl)} watchlist tickers (from {csv_files[0].name})")
    # Override universe to just the watchlist tickers
    daily_cfg = copy.deepcopy(cfg)
    daily_cfg["universe"]       = "custom"
    daily_cfg["custom_tickers"] = wl["ticker"].tolist()

    from scanner import run_scanner
    from state_manager import StateManager
    df = await run_scanner(daily_cfg)

    if not df.empty:
        # Update state with new scores
        state = StateManager(cfg)
        state.update_scan_meta("daily", len(df), len(df))
        state.update_watchlist(df.to_dict("records"))
        logger.info("State updated with daily scores")


async def mode_filter(cfg: dict, input_src: str) -> None:
    """Apply elite filter to latest scan result → Scan_result/watchlist_YYYYMMDD.csv"""
    from elite_filter import load_latest_and_filter
    from state_manager import StateManager

    watchlist = load_latest_and_filter(scan_dir=input_src, cfg=cfg)

    if not watchlist.empty:
        print("Next: python run.py --mode bot --paper")
        state = StateManager(cfg)
        state.update_watchlist(watchlist.to_dict("records"))
        state.update_scan_meta("filter", len(watchlist), len(watchlist))
    else:
        print("\n[!] Zero candidates — see advice above for tuning thresholds.")
        print("    Or share your swing_results CSV for analysis.")


async def mode_bot(cfg: dict, watchlist_csv: str, force: bool = False) -> None:
    """Entry scanning + order execution bot. Auto-exits at 16:00."""
    from bot import run_bot
    await run_bot(cfg, watchlist_csv, force=force)


async def mode_test(cfg: dict, tickers: list | None) -> None:
    """Fast pipeline test on a few tickers."""
    tickers = tickers or [
        "AAPL","MSFT","NVDA","GOOGL","META","AMZN","JPM","V","XOM","LLY"
    ]
    logger.info(f"TEST: {tickers}")
    test_cfg = copy.deepcopy(cfg)
    test_cfg.update({
        "universe":               "custom",
        "custom_tickers":         tickers,
        "min_trend_conditions":   2,
        "ib_concurrent_requests": 10,
    })
    from scanner import run_scanner
    await run_scanner(test_cfg)


def mode_dashboard(cfg: dict, data_store: dict = None) -> None:
    """Start the always-on dashboard."""
    from dashboard import build_app, DASH_OK
    if not DASH_OK:
        print("Install: pip install dash plotly")
        sys.exit(1)
    host = cfg.get("dashboard_host", "127.0.0.1")
    port = cfg.get("dashboard_port", 8050)
    print(f"\n  Dashboard → http://{host}:{port}")
    print("  Reads state.json every 30s (written by bot)")
    print("  Keep this open in your browser all day\n")

    # Load OHLCV data for all watchlist tickers so charts render immediately.
    # Tries yfinance first (no IB connection needed), falls back to IB if available.
    if data_store is None:
        data_store = _load_ohlcv_for_dashboard(cfg)

    app = build_app(cfg, data_store)
    app.run(host=host, port=port, debug=False)


def _load_ohlcv_for_dashboard(cfg: dict) -> dict:
    """
    Load OHLCV data for the dashboard.

    Priority:
      1. ohlcv_cache/ folder — written by bot from IB data (best, no connection needed)
      2. IB live fetch — if cache is empty and IB is reachable
      3. Nothing — dashboard will fetch on-demand per ticker when clicked

    The bot writes ohlcv_cache/{TICKER}.csv every time it fetches from IB.
    So as long as the bot has run at least once, the cache will be populated.
    """
    import pandas as pd
    from pathlib import Path
    from bot import _load_ohlcv_cache

    # Try cache first (written by bot process from IB data)
    data_store = _load_ohlcv_cache(cfg)

    if data_store:
        logger.info(f"OHLCV loaded from IB cache: {len(data_store)} tickers "
                    f"(ohlcv_cache/)")
        return data_store

    # Cache is empty — bot hasn't run yet or cache dir doesn't exist.
    # Try a direct IB fetch for watchlist tickers.
    logger.info("ohlcv_cache/ is empty — attempting live IB fetch...")
    tickers = _get_watchlist_tickers(cfg)

    if not tickers:
        logger.warning(
            "No watchlist tickers found and no cache. "
            "Run the bot first (python run.py --mode bot --paper) "
            "to populate ohlcv_cache/. Charts will load on-demand when clicked."
        )
        return {}

    try:
        import asyncio
        from ib_client import get_client
        async def _fetch():
            client = get_client(cfg)
            await client.connect()
            data   = await client.fetch_all_historical(tickers)
            await client.disconnect()
            return data

        data_store = asyncio.run(_fetch())
        from bot import _save_ohlcv_cache
        _save_ohlcv_cache(data_store, cfg)
        logger.info(f"IB fetch complete: {len(data_store)} tickers cached")
    except Exception as e:
        logger.warning(
            f"IB fetch failed ({e}). "
            "Charts will load on-demand when you click each ticker."
        )

    return data_store


def _get_watchlist_tickers(cfg: dict) -> list:
    """Get tickers from state.json or latest watchlist CSV."""
    import pandas as pd
    from pathlib import Path
    from state_manager import StateManager

    state = StateManager.read()
    if state.get("watchlist"):
        return [r["ticker"] for r in state["watchlist"] if r.get("ticker")]

    scan_dir  = Path(__file__).parent / "Scan_result"
    csv_files = sorted(scan_dir.glob("watchlist_*.csv"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
    if csv_files:
        try:
            wl = pd.read_csv(csv_files[0])
            wl.columns = [c.strip().lower() for c in wl.columns]
            return wl["ticker"].dropna().tolist()
        except Exception:
            pass
    return []


def mode_analyze(cfg: dict) -> None:
    """Print trade log summary for review and send to Claude for analysis."""
    from order_logger import OrderLogger
    import pandas as pd

    ol  = OrderLogger(cfg)
    df  = ol.load_trade_log()

    if df.empty:
        print("No closed trades yet. Keep the bot running.")
        return

    print(f"\n{'='*60}")
    print(f"  TRADE HISTORY — {len(df)} closed trades")
    print(f"{'='*60}")

    if "exit_event" in df.columns:
        wins  = df[df["exit_event"] == "tp"]
        loses = df[df["exit_event"] == "sl"]
        wr    = len(wins)/len(df)*100 if len(df) else 0
        print(f"  Take Profits : {len(wins)}")
        print(f"  Stop Losses  : {len(loses)}")
        print(f"  Win Rate     : {wr:.1f}%")

    if "pnl_usd" in df.columns:
        total  = df["pnl_usd"].sum()
        avg_w  = df[df["pnl_usd"]>0]["pnl_usd"].mean() if len(wins)>0 else 0
        avg_l  = df[df["pnl_usd"]<0]["pnl_usd"].mean() if len(loses)>0 else 0
        avg_r  = df["pnl_r"].mean() if "pnl_r" in df.columns else 0
        print(f"  Total P&L    : ${total:+.2f}")
        print(f"  Avg Win      : ${avg_w:+.2f}")
        print(f"  Avg Loss     : ${avg_l:+.2f}")
        print(f"  Avg R        : {avg_r:+.2f}R")
        if avg_l != 0:
            print(f"  Actual R:R   : {abs(avg_w/avg_l):.2f}:1")

    if "post_verdict" in df.columns:
        print(f"\n  Post-trade verdicts:")
        for v, g in df.groupby("post_verdict"):
            print(f"    {v:<22}: {len(g)}")

    if "pattern" in df.columns:
        print(f"\n  By Pattern:")
        for pat, g in df.groupby("pattern"):
            pnl = g["pnl_usd"].sum() if "pnl_usd" in g.columns else 0
            w   = len(g[g.get("exit_event","")=="tp"]) if "exit_event" in g.columns else 0
            print(f"    {pat:<12}: {len(g)} trades  wins={w}  pnl=${pnl:+.2f}")

    if "regime" in df.columns:
        print(f"\n  By Regime:")
        for reg, g in df.groupby("regime"):
            pnl = g["pnl_usd"].sum() if "pnl_usd" in g.columns else 0
            print(f"    {reg:<10}: {len(g)} trades  pnl=${pnl:+.2f}")

    print(f"\n{'='*60}")
    from pathlib import Path
    hist = Path(cfg.get("order_history_dir","order_history"))
    print(f"  Screenshots: {hist.resolve()}")
    print(f"  To analyze: share trade_log.csv with Claude")
    print(f"{'='*60}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    cfg  = build_config(args)
    mode = args.mode
    is_live = getattr(args, "live", False)

    print(f"\n  {'='*52}")
    print(f"  Swing Trading System")
    print(f"  Mode:      {mode.upper()}")
    print(f"  Trading:   {'LIVE ⚠' if is_live else 'PAPER ✓'}")
    print(f"  IB:        {cfg['ib_host']}:{cfg['ib_port']}")
    print(f"  Transmit:  {'YES ⚠' if cfg.get('order_transmit') else 'NO (dry-run)'}")
    print(f"  {'='*52}\n")

    if mode == "dashboard":
        mode_dashboard(cfg)
    elif mode == "analyze":
        mode_analyze(cfg)
    else:
        fns = {
            "weekly":  lambda: mode_weekly(cfg),
            "daily":   lambda: mode_daily(cfg),
            "filter":  lambda: mode_filter(cfg, args.input),
            "bot":     lambda: mode_bot(cfg, args.watchlist,
                                        force=getattr(args, "force", False)),
            "test":    lambda: mode_test(
                cfg, args.tickers.split(",") if args.tickers else None),
        }
        asyncio.run(fns[mode]())


if __name__ == "__main__":
    main()