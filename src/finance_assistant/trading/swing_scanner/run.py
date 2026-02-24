"""
run.py — Entry point for the swing trading scanner.

USAGE:
    python run.py                     # default: weekly scan
    python run.py --mode weekly       # full scan (IB fetch + score + save CSV)
    python run.py --mode daily        # same but with a smaller universe refresh note
    python run.py --mode dashboard    # start the Dash visualization server
    python run.py --mode test         # scan 10 tickers only (fast dev check)
    python run.py --mode test --tickers AAPL,MSFT,NVDA

PREREQUISITES:
    pip install ib_async pandas numpy dash plotly requests
    Start TWS or IB Gateway before running weekly/daily/test modes.

DEBUGGING:
    Set LOG_LEVEL=DEBUG for verbose output:
        LOG_LEVEL=DEBUG python run.py --mode test
"""

import argparse
import asyncio
import copy
import logging
import os
import sys

# ── Logging setup ─────────────────────────────────────────────────────────────
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Swing Trading Scanner — Interactive Brokers Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["weekly", "daily", "dashboard", "test"],
        default="weekly",
        help="Run mode (default: weekly)",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated ticker list (used in --mode test)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override IB port (e.g. 7497 for paper, 7496 for live)",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=None,
        help="Override IB client ID",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Override number of top results to display",
    )
    return parser.parse_args()


def build_config(args) -> dict:
    """Build a config dict, applying any CLI overrides."""
    from config import CONFIG
    cfg = copy.deepcopy(CONFIG)

    if args.port:
        cfg["ib_port"] = args.port
        logger.info(f"IB port overridden: {args.port}")

    if args.client_id:
        cfg["ib_client_id"] = args.client_id

    if args.top_n:
        cfg["top_n"] = args.top_n

    return cfg


async def run_weekly(cfg: dict):
    """Full scan: fetch data from IB, score all tickers, save results."""
    from scanner import run_scanner
    df = await run_scanner(cfg)
    return df


async def run_test(cfg: dict, tickers: list[str] = None):
    """
    Fast development scan on a tiny universe.
    Use this to verify the pipeline works before running the full scan.
    """
    if not tickers:
        tickers = [
            "AAPL", "MSFT", "NVDA", "GOOGL", "META",
            "AMZN", "JPM", "V", "XOM", "LLY",
        ]
    logger.info(f"TEST MODE: scanning {len(tickers)} tickers: {tickers}")
    test_cfg = copy.deepcopy(cfg)
    test_cfg["universe"]        = "custom"
    test_cfg["custom_tickers"]  = tickers
    test_cfg["min_trend_conditions"] = 2   # relax slightly for fast test
    test_cfg["ib_request_delay"]     = 0.3  # faster in test

    from scanner import run_scanner
    df = await run_scanner(test_cfg)
    return df


def run_dashboard(cfg: dict, data_store: dict = None):
    """Start the Dash visualization server."""
    from dashboard import build_app, DASH_AVAILABLE
    if not DASH_AVAILABLE:
        print("ERROR: Install dash and plotly first:")
        print("       pip install dash plotly")
        sys.exit(1)

    print(f"\nStarting dashboard at http://{cfg['dashboard_host']}:{cfg['dashboard_port']}")
    print("Run the scanner first (--mode weekly) to generate swing_results.csv")
    print("Press Ctrl+C to stop.\n")

    # Find latest watchlist file in Scan_result
    import glob
    import os
    scan_dir = "Scan_result"
    files = glob.glob(os.path.join(scan_dir, "watchlist_*.csv"))
    if files:
        latest = max(files, key=os.path.getmtime)
        print(f"Loading dashboard from: {latest}")
        results_csv = latest
    else:
        results_csv = os.path.join(scan_dir, "watchlist.csv")
    app = build_app(cfg, results_csv=results_csv, data_store=data_store)
    app.run(
        host=cfg["dashboard_host"],
        port=cfg["dashboard_port"],
        debug=False,
    )


def main():
    args   = parse_args()
    cfg    = build_config(args)
    mode   = args.mode

    print(f"\n  Mode: {mode.upper()}")
    print(f"  IB:   {cfg['ib_host']}:{cfg['ib_port']}  (client_id={cfg['ib_client_id']})")
    print(f"  Universe: {cfg['universe']}\n")

    if mode in ("weekly", "daily"):
        asyncio.run(run_weekly(cfg))

    elif mode == "test":
        tickers = args.tickers.split(",") if args.tickers else None
        asyncio.run(run_test(cfg, tickers))

    elif mode == "dashboard":
        run_dashboard(cfg)


if __name__ == "__main__":
    main()
