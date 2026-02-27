"""
bot.py — Market-hours bot: entry scanner + order execution + position monitor.

WHEN TO RUN:
    The bot runs from market open (9:30) to close (16:00).
    It does NOT need to watch every tick — swing trading uses daily signals.
    
    Trading windows (when new entries are allowed):
        10:00 - 11:30  Morning window   (confirmed breakouts, real volume)
        13:30 - 15:00  Afternoon window (institutional flow resumes)
    
    Outside windows: bot still monitors open positions for TP/SL fills,
    updates P&L in the dashboard, and runs post-trade snapshots.
    It just won't place NEW entries.

PAPER vs LIVE:
    Paper: IB port 7497 (TWS) or 4002 (Gateway). order_transmit can be True.
    Live:  IB port 7496 (TWS) or 4001 (Gateway). order_transmit MUST be True.
    
    Use --paper or --live flag in run.py. Never mix client_ids between modes.

ARCHITECTURE:
    bot.py writes all state to state.json via StateManager.
    dashboard.py reads state.json every 30s — completely decoupled.
    order_logger.py handles all file I/O for screenshots and trade history.

AUTOMATION ON LOCAL MACHINE:
    Windows: Task Scheduler → trigger at 9:25am weekdays
             Action: python C:\\path\\run.py --mode bot --paper
    Mac/Linux: crontab -e
             25 9 * * 1-5 cd /path && python run.py --mode bot --paper
    
    The bot exits automatically at market close (16:00).
    Run dashboard separately — it stays open all day.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config import CONFIG
from ib_client import get_client
from state_manager import StateManager, get_market_session
from order_logger import OrderLogger, Trade, PostTradeScheduler

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# OHLCV DISK CACHE
# Writes IB data to ohlcv_cache/ so the dashboard can read it without
# needing its own IB connection. One parquet file per ticker.
# ═══════════════════════════════════════════════════════════════════════════════

def _save_ohlcv_cache(
    data: dict,
    cfg: dict,
    append: bool = False,
) -> None:
    """
    Save OHLCV DataFrames to disk as CSV files.
    Called by bot after every IB fetch so dashboard always has fresh data.

    Structure:
        ohlcv_cache/
            AAPL.csv
            NVDA.csv
            ...
    """
    from pathlib import Path
    cache_dir = Path(cfg.get("ohlcv_cache_dir", "ohlcv_cache"))
    cache_dir.mkdir(exist_ok=True)
    for ticker, df in data.items():
        if df is None or df.empty:
            continue
        try:
            path = cache_dir / f"{ticker}.csv"
            if append and path.exists():
                # Merge new rows with existing file, drop duplicates
                existing = pd.read_csv(path, index_col=0, parse_dates=True)
                merged   = pd.concat([existing, df]).loc[
                    ~pd.concat([existing, df]).index.duplicated(keep="last")
                ].sort_index()
                merged.to_csv(path)
            else:
                df.to_csv(path)
        except Exception as e:
            log.debug(f"Cache write failed for {ticker}: {e}")


def _load_ohlcv_cache(cfg: dict) -> dict:
    """
    Load all cached OHLCV CSVs from disk.
    Called by dashboard on startup.
    Returns dict: {ticker: pd.DataFrame}
    """
    from pathlib import Path
    cache_dir = Path(cfg.get("ohlcv_cache_dir", "ohlcv_cache"))
    data = {}
    if not cache_dir.exists():
        return data
    for csv_path in cache_dir.glob("*.csv"):
        try:
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            if {"open","high","low","close","volume"}.issubset(df.columns):
                data[csv_path.stem] = df
        except Exception as e:
            log.debug(f"Cache read failed for {csv_path.stem}: {e}")
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# INTRADAY ENTRY CONFIRMATION
# ═══════════════════════════════════════════════════════════════════════════════

def check_entry_confirmation(
    df_intraday: pd.DataFrame,
    trigger_price: float,
    cfg: dict,
) -> bool:
    """
    Confirm daily entry signal on intraday (5min) chart.
    
    Rule: last N bars must close ABOVE trigger price with buffer.
    This filters whipsaws — price must sustain above the level, not just touch it.
    """
    n = cfg.get("bot_confirm_bars", 1)
    if len(df_intraday) < n:
        return False
    buf    = 1 + cfg.get("bot_entry_trigger_buffer", 0.001)
    recent = df_intraday["close"].iloc[-n:]
    return all(c > trigger_price * buf for c in recent)


# ═══════════════════════════════════════════════════════════════════════════════
# BRACKET ORDER PLACEMENT
# ═══════════════════════════════════════════════════════════════════════════════

async def place_bracket_order(
    client,
    trade: Trade,
    cfg: dict,
) -> tuple[int, int, int]:
    """
    Place bracket order on IB: entry LMT + TP LMT + SL STP.
    
    In paper mode:  transmit=True is safe — use paper account.
    In live mode:   transmit must be True and you accept real fills.
    In dry-run:     transmit=False, order staged in TWS but not sent.
    
    Returns (parent_id, tp_id, sl_id). Returns (0,0,0) on failure or dry-run.
    """
    transmit = cfg.get("order_transmit", False)
    mode     = cfg.get("trading_mode",   "paper")
    slip     = cfg.get("order_limit_slippage_pct", 0.001)
    lmt_buy  = round(trade.entry_price * (1 + slip), 2)

    log.info(
        f"[{trade.ticker}] Bracket order: "
        f"BUY {trade.shares} @ ${lmt_buy:.2f}  "
        f"TP=${trade.target_price:.2f}  SL=${trade.stop_price:.2f}  "
        f"mode={mode.upper()}  transmit={transmit}"
    )

    if not transmit:
        log.info(f"[{trade.ticker}] DRY RUN — not transmitted")
        return 0, 0, 0

    try:
        from ib_async import LimitOrder, StopOrder
        contract = client.make_stock(trade.ticker)
        bracket  = client.ib.bracketOrder(
            action="BUY",
            quantity=trade.shares,
            limitPrice=lmt_buy,
            takeProfitPrice=trade.target_price,
            stopLossPrice=trade.stop_price,
        )
        tif = cfg.get("order_tif", "DAY")
        for o in bracket:
            o.tif = tif

        p  = client.ib.placeOrder(contract, bracket.parent)
        tp = client.ib.placeOrder(contract, bracket.takeProfit)
        sl = client.ib.placeOrder(contract, bracket.stopLoss)
        return p.order.orderId, tp.order.orderId, sl.order.orderId

    except Exception as e:
        log.error(f"[{trade.ticker}] Order placement failed: {e}")
        return 0, 0, 0


# ═══════════════════════════════════════════════════════════════════════════════
# POSITION MONITOR
# ═══════════════════════════════════════════════════════════════════════════════

class PositionMonitor:
    """
    Monitors open positions by polling IB executions every scan cycle.
    
    On entry fill  → logs screenshot, updates state (open position)
    On TP/SL fill  → logs screenshot, updates state (closed), triggers post-trade
    On position    → polls current price, updates unrealized P&L in state
    """

    def __init__(self, client, order_logger: OrderLogger,
                 scheduler: PostTradeScheduler,
                 state: StateManager, cfg: dict):
        self.client    = client
        self.ol        = order_logger
        self.scheduler = scheduler
        self.state     = state
        self.cfg       = cfg

        # order_id → Trade
        self._open:   dict[int, Trade] = {}
        # child order_id → parent order_id
        self._tp_map: dict[int, int]   = {}
        self._sl_map: dict[int, int]   = {}
        # seen execution ids (avoid processing twice)
        self._seen_execs: set[str]     = set()

    def register(self, trade: Trade,
                 parent_id: int, tp_id: int, sl_id: int) -> None:
        self._open[parent_id]  = trade
        self._tp_map[tp_id]    = parent_id
        self._sl_map[sl_id]    = parent_id
        log.info(f"Registered: {trade.ticker} parent={parent_id}")

    async def check_fills(self, data_cache: dict[str, pd.DataFrame]) -> None:
        """Poll IB executions and handle new fills."""
        if not self._open and not self._tp_map and not self._sl_map:
            return
        try:
            executions = self.client.ib.executions()
        except Exception as e:
            log.warning(f"Could not fetch executions: {e}")
            return

        for ex in executions:
            exec_id = getattr(ex, "execId", str(ex.orderId))
            if exec_id in self._seen_execs:
                continue
            self._seen_execs.add(exec_id)

            oid = ex.orderId
            px  = ex.price
            ts  = datetime.now()

            # Entry fill
            if oid in self._open and self._open[oid].fill_time is None:
                trade = self._open[oid]
                trade.on_fill(px, ts)
                log.info(f"ENTRY FILL: {trade.ticker} @ ${px:.2f}")

                self.state.add_open_position({
                    "ticker":      trade.ticker,
                    "pattern":     trade.pattern,
                    "order_id":    oid,
                    "tp_id":       next((k for k,v in self._tp_map.items() if v==oid), 0),
                    "sl_id":       next((k for k,v in self._sl_map.items() if v==oid), 0),
                    "fill_price":  px,
                    "fill_time":   ts.isoformat(timespec="seconds"),
                    "stop":        trade.stop_price,
                    "target":      trade.target_price,
                    "shares":      trade.shares,
                    "current_price": px,
                    "unrealized_pnl": 0.0,
                    "unrealized_pct": 0.0,
                    "unrealized_r":   0.0,
                })
                await self._capture(trade, "entry", data_cache)

            # TP fill
            elif oid in self._tp_map:
                pid   = self._tp_map.pop(oid)
                trade = self._open.pop(pid, None)
                if trade:
                    trade.on_exit(px, ts, "tp")
                    log.info(f"TP: {trade.ticker} @ ${px:.2f}  "
                             f"PnL=${trade.pnl_usd:+.2f} ({trade.pnl_r:+.2f}R)")
                    self.state.close_position(trade.ticker, px, "tp", trade.pnl_usd)
                    await self._capture(trade, "tp", data_cache)
                    self.scheduler.register(trade)
                    self._sl_map = {k: v for k,v in self._sl_map.items() if v != pid}

            # SL fill
            elif oid in self._sl_map:
                pid   = self._sl_map.pop(oid)
                trade = self._open.pop(pid, None)
                if trade:
                    trade.on_exit(px, ts, "sl")
                    log.warning(f"SL: {trade.ticker} @ ${px:.2f}  "
                                f"PnL=${trade.pnl_usd:+.2f} ({trade.pnl_r:+.2f}R)")
                    self.state.close_position(trade.ticker, px, "sl", trade.pnl_usd)
                    await self._capture(trade, "sl", data_cache)
                    self.scheduler.register(trade)
                    self._tp_map = {k: v for k,v in self._tp_map.items() if v != pid}

    async def update_prices(self) -> None:
        """Poll current price for each open position and update state P&L."""
        for oid, trade in self._open.items():
            if trade.fill_time is None:
                continue   # not filled yet
            try:
                ticker = trade.ticker
                # Use IB snapshot if connected, else skip
                contract = self.client.make_stock(ticker)
                [ticker_data] = self.client.ib.reqTickers(contract)
                price = ticker_data.marketPrice()
                if price and price > 0:
                    self.state.update_position_price(ticker, float(price))
            except Exception as e:
                log.debug(f"Price update failed for {trade.ticker}: {e}")

    async def _capture(self, trade: Trade, event: str,
                       data_cache: dict[str, pd.DataFrame]) -> None:
        """Fetch latest data and save both strategy chart and pattern chart."""
        ticker   = trade.ticker
        df_daily = data_cache.get(ticker, pd.DataFrame())

        # Refresh daily data to include today
        try:
            fresh = await self.client.fetch_historical_stock(ticker)
            if not fresh.empty:
                df_daily = fresh
                data_cache[ticker] = fresh
                _save_ohlcv_cache({ticker: fresh}, cfg, append=True)
        except Exception:
            pass

        # Fetch intraday for the entry/exit panel
        df_intra = pd.DataFrame()
        try:
            df_intra = await self.client.fetch_historical(
                self.client.make_stock(ticker),
                duration="2 D",
                bar_size=self.cfg.get("bot_intraday_bar_size", "5 mins"),
            )
        except Exception:
            pass

        # Strategy chart (Chart 1)
        self.ol.log_event(trade, event, df_daily, df_intra,
                          notes=f"mode={self.cfg.get('trading_mode','paper')}")

        # Pattern chart (Chart 2) — only on entry
        if event == "entry":
            self.ol.log_pattern_chart(trade, df_daily)

    @property
    def open_count(self) -> int:
        return len(self._open)

    @property
    def active_tickers(self) -> set[str]:
        return {t.ticker for t in self._open.values()}


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

async def scan_entries(
    watchlist:  pd.DataFrame,
    client,
    monitor:    PositionMonitor,
    order_log:  OrderLogger,
    data_cache: dict[str, pd.DataFrame],
    state:      StateManager,
    cfg:        dict,
) -> None:
    """
    Check each watchlist ticker for intraday entry confirmation.
    Only called during active trading windows.
    """
    capacity = cfg["bot_max_open_trades"] - monitor.open_count
    if capacity <= 0:
        return

    entered = 0
    for _, row in watchlist.iterrows():
        if entered >= capacity:
            break

        ticker  = str(row["ticker"])
        pattern = str(row.get("pattern", "none"))

        if ticker in monitor.active_tickers:
            continue

        # Fetch fresh intraday bars
        try:
            df_intra = await client.fetch_historical(
                client.make_stock(ticker),
                duration="2 D",
                bar_size=cfg.get("bot_intraday_bar_size", "5 mins"),
            )
        except Exception as e:
            log.debug(f"[{ticker}] intraday fetch error: {e}")
            continue

        if df_intra.empty:
            continue

        trigger = float(row.get("entry", 0.0))
        if trigger <= 0:
            continue

        if not check_entry_confirmation(df_intra, trigger, cfg):
            log.debug(f"[{ticker}] not confirmed @ ${trigger:.2f}")
            continue

        log.info(f"[{ticker}] ENTRY CONFIRMED — {pattern.upper()} @ ${trigger:.2f}")
        state.mark_watchlist_triggered(ticker)

        # Derive swing levels for chart annotations
        df_daily  = data_cache.get(ticker, pd.DataFrame())
        sw_low    = float(df_daily["low"].iloc[-20:].min())  if not df_daily.empty else 0.0
        sw_high   = float(df_daily["high"].iloc[-20:].max()) if not df_daily.empty else 0.0
        atr_val   = (float(row.get("atr_pct", 2.0)) / 100
                     * float(row.get("price", trigger)))

        trade = Trade(
            ticker       = ticker,
            pattern      = pattern,
            order_id     = 0,
            entry_price  = float(row.get("entry",  trigger)),
            stop_price   = float(row.get("stop",   0.0)),
            target_price = float(row.get("target", 0.0)),
            shares       = int(row.get("shares",   1)),
            score        = float(row.get("score",  0.0)),
            regime       = str(row.get("regime",   "unknown")),
            vix          = float(row.get("vix",    0.0)),
            rr           = float(row.get("rr",     0.0)),
            atr          = atr_val,
            swing_low    = sw_low,
            swing_high   = sw_high,
            extra={
                "adx":        float(row.get("adx",        0)),
                "rsi":        float(row.get("rsi",        0)),
                "rvol":       float(row.get("rvol",       0)),
                "rs_avg_pct": float(row.get("rs_avg_pct", 0)),
                "mode":       cfg.get("trading_mode", "paper"),
            },
        )

        parent_id, tp_id, sl_id = await place_bracket_order(client, trade, cfg)

        if not cfg.get("order_transmit", False):
            # Dry run: simulate fill immediately for logging/dashboard
            trade.order_id = 9000 + entered
            trade.on_fill(trigger, datetime.now())
            state.add_open_position({
                "ticker":       ticker, "pattern": pattern,
                "order_id":     trade.order_id,
                "fill_price":   trigger,
                "fill_time":    datetime.now().isoformat(timespec="seconds"),
                "stop":         trade.stop_price,
                "target":       trade.target_price,
                "shares":       trade.shares,
                "current_price":trigger,
                "unrealized_pnl": 0.0, "unrealized_pct": 0.0, "unrealized_r": 0.0,
            })
            order_log.log_event(trade, "entry", df_daily, df_intra,
                                notes="[DRY RUN]")
            order_log.log_pattern_chart(trade, df_daily)
        else:
            trade.order_id = parent_id
            monitor.register(trade, parent_id, tp_id, sl_id)

        entered += 1


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BOT LOOP
# ═══════════════════════════════════════════════════════════════════════════════

async def run_bot(cfg: dict = CONFIG, watchlist_csv: str = "watchlist.csv", force: bool = False) -> None:
    """
    Main bot loop. Runs until market close or KeyboardInterrupt.

    Cycle (every bot_scan_interval_sec seconds):
      1. Update market session status
      2. Check IB execution fills (always)
      3. Update open position prices (always)
      4. Check post-trade snapshots (always)
      5. Scan for new entries (only during trading windows)
      6. Heartbeat state.json

    Exits automatically at 16:00 ET.
    """
    mode  = cfg.get("trading_mode", "paper")
    force = force or cfg.get("bot_force", False)
    log.info(f"Bot starting — mode={mode.upper()}  "
             f"transmit={cfg.get('order_transmit', False)}  "
             f"force={'YES (ignore market hours)' if force else 'NO'}")

    # Auto-detect latest watchlist from Scan_result/ folder
    from pathlib import Path
    scan_dir  = Path(__file__).parent / "Scan_result"
    csv_files = sorted(
        scan_dir.glob("watchlist_*.csv"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    resolved_csv = str(csv_files[0]) if csv_files else watchlist_csv
    if csv_files:
        log.info(f"Auto-detected latest watchlist: {resolved_csv}")
    else:
        log.warning(f"No watchlist_*.csv in Scan_result/ — using {watchlist_csv}")

    try:
        watchlist = pd.read_csv(resolved_csv)
        log.info(f"Loaded {len(watchlist)} rows, columns: {list(watchlist.columns)}")
        # Normalise column names (strip whitespace, lowercase)
        watchlist.columns = [c.strip().lower() for c in watchlist.columns]
        if "ticker" not in watchlist.columns:
            # Try common alternatives
            for alt in ["symbol", "stock", "asset"]:
                if alt in watchlist.columns:
                    watchlist = watchlist.rename(columns={alt: "ticker"})
                    log.info(f"Renamed column '{alt}' → 'ticker'")
                    break
            else:
                log.error(
                    f"No 'ticker' column found in {resolved_csv}. "
                    f"Columns present: {list(watchlist.columns)}"
                )
                return
        watchlist = watchlist.dropna(subset=["ticker"])
        watchlist = watchlist[watchlist["ticker"].astype(str).str.strip() != ""]
        log.info(f"Watchlist: {len(watchlist)} tickers from {resolved_csv}")
        if len(watchlist) == 0:
            log.error(f"Watchlist CSV exists but contains 0 valid tickers. "
                      f"Check {resolved_csv} — run weekly + filter again.")
            return
    except FileNotFoundError:
        log.error(
            f"Watchlist not found: {resolved_csv}. "
            f"Run: python run.py --mode weekly && python run.py --mode filter"
        )
        return

    # Connect IB (separate client_id from scanner, falls back to client_id + 1)
    bot_client_id = cfg.get("bot_ib_client_id", cfg.get("ib_client_id", 1) + 1)
    bot_cfg = {**cfg, "ib_client_id": bot_client_id}
    client  = get_client(bot_cfg)
    await client.connect()

    # Initialise shared services
    state      = StateManager(cfg)
    state.set_mode(mode)
    order_log  = OrderLogger(cfg)
    scheduler  = PostTradeScheduler(order_log, cfg)
    monitor    = PositionMonitor(client, order_log, scheduler, state, cfg)

    # Pre-load daily data cache for all watchlist tickers
    tickers    = watchlist["ticker"].tolist()
    data_cache = await client.fetch_all_historical(tickers)
    log.info(f"Daily cache ready: {len(data_cache)} tickers")

    # Write OHLCV cache to disk so dashboard can read it without IB connection
    _save_ohlcv_cache(data_cache, cfg)

    # Update watchlist in state
    wl_rows = watchlist.to_dict("records")
    for r in wl_rows:
        r.setdefault("status", "watching")
    state.update_watchlist(wl_rows)

    # ── Startup reconciliation ─────────────────────────────────────────────────
    # Re-submit any bracket orders that disappeared (IB paper reset, disconnect, etc.)
    from reconcile import reconcile_on_startup
    n_reconciled = await reconcile_on_startup(
        client, monitor, state, order_log, data_cache, cfg
    )
    if n_reconciled:
        log.info(f"Reconcile: {n_reconciled} order(s) re-submitted to IB")

    interval = cfg["bot_scan_interval_sec"]

    print(f"\n{'='*55}")
    print(f"  BOT RUNNING — {mode.upper()} MODE")
    print(f"  Watchlist: {len(watchlist)} tickers")
    print(f"  Max positions: {cfg['bot_max_open_trades']}")
    print(f"  Order transmit: {cfg.get('order_transmit', False)}")
    print(f"  Scan interval: {interval}s")
    print(f"  Entry windows: 10:00-11:30 and 13:30-15:00 ET")
    print(f"  Auto-exit at: 16:00 ET")
    if force:
        print(f"  ⚠  FORCE MODE — market hours bypassed (test/paper only)")
    print(f"{'='*55}\n")

    try:
        while True:
            now              = datetime.now()
            session, label, entry_allowed = get_market_session()
            _, _             = state.update_market_status()

            # Auto-exit at close (unless --force bypasses market hours)
            if not force and session in ("closed",) and now.hour >= 16:
                log.info("Market closed — bot exiting for today")
                break

            log.info(
                f"─── {now.strftime('%H:%M:%S')}  "
                f"Session: {label}  "
                f"Positions: {monitor.open_count}/{cfg['bot_max_open_trades']}  "
                f"PostTrade pending: {scheduler.pending_count}"
            )

            # Always: check fills
            await monitor.check_fills(data_cache)

            # Always: update P&L for open positions
            await monitor.update_prices()

            # Always: post-trade follow-up snapshots
            await scheduler.check_pending(client.fetch_historical_stock)

            # Only during entry windows: scan for new entries
            # --force bypasses window restriction for testing
            if entry_allowed or force:
                if force and not entry_allowed:
                    log.info("  FORCE: scanning outside normal entry window")
                await scan_entries(
                    watchlist, client, monitor, order_log,
                    data_cache, state, cfg,
                )
            else:
                log.info(f"  Outside entry window — monitoring only")

            state.heartbeat()

            # Sleep until next cycle
            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    except Exception as e:
        log.error(f"Bot crashed: {e}", exc_info=True)
        state.add_error(str(e))
    finally:
        await client.disconnect()
        log.info("Disconnected from IB")