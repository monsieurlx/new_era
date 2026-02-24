"""
bot.py — Entry scanner and order execution bot.

Runs during market hours. On each scan cycle:
  1. For each watchlist ticker: fetch fresh intraday bars (5min)
  2. Check if daily entry trigger is still valid
  3. Check intraday confirmation (price > trigger level for N bars)
  4. If confirmed AND we have capacity: place bracket order (entry + TP + SL)
  5. Monitor open positions for fill events (entry fill, TP hit, SL hit)
  6. On any fill event: capture screenshot + log metadata

Safety controls:
  - order_transmit = False in config until you're ready for live orders
  - Max 5 concurrent positions
  - No new entries in final 15 min of session
  - No entries outside regular trading hours

Usage:
    python run.py --mode bot --watchlist watchlist.csv
"""

import asyncio
import logging
from datetime import datetime, time as dtime
from pathlib import Path

import pandas as pd

from config import CONFIG
from ib_client import get_client, normalize_ticker
from indicators import calc_all, calc_sma, calc_ema, calc_rsi, calc_atr
from order_logger import OrderLogger, Trade, PostTradeScheduler

logger = logging.getLogger(__name__)


# ─── Market hours helpers ─────────────────────────────────────────────────────

def _parse_time(t_str: str) -> dtime:
    h, m = map(int, t_str.split(":"))
    return dtime(h, m)


def is_market_open(cfg: dict) -> bool:
    """Return True if current ET time is within tradeable window."""
    now      = datetime.now().time()
    open_t   = _parse_time(cfg["bot_market_open"])
    close_t  = _parse_time(cfg["bot_market_close"])
    no_trade = _parse_time(
        f"{cfg['bot_market_close'].split(':')[0]}:"
        f"{int(cfg['bot_market_close'].split(':')[1]) - cfg['bot_no_trade_last_min']}"
    )
    pre_buf  = cfg.get("bot_pre_entry_buffer_min", 5)
    earliest = dtime(open_t.hour, open_t.minute + pre_buf)
    return earliest <= now <= no_trade


# ─── Intraday confirmation ────────────────────────────────────────────────────

def check_entry_confirmation(
    df_intraday: pd.DataFrame,
    trigger_price: float,
    cfg: dict,
) -> bool:
    """
    Returns True if the intraday chart confirms the daily entry signal.

    Logic:
    - The last N=bot_confirm_bars bars must have closed ABOVE the trigger price
    - This filters out false breakouts / whipsaws on the 5min chart
    """
    n = cfg.get("bot_confirm_bars", 1)
    if len(df_intraday) < n:
        return False

    recent_closes = df_intraday["close"].iloc[-n:]
    buffer        = 1 + cfg.get("bot_entry_trigger_buffer", 0.001)
    return all(c > trigger_price * buffer for c in recent_closes)


def compute_entry_trigger(watchlist_row: pd.Series, pattern: str) -> float:
    """
    Determine the trigger price for entry based on the pattern.
    This comes from the scanner output (the 'entry' column).
    """
    return float(watchlist_row.get("entry", 0.0))


# ─── IB Order Placement ───────────────────────────────────────────────────────

async def place_bracket_order(
    ib_client,
    trade: Trade,
    cfg: dict,
) -> tuple[int, int, int]:
    """
    Place a bracket order (parent limit entry + TP limit + SL stop).

    Returns:
        (parent_order_id, tp_order_id, sl_order_id)
        Returns (0, 0, 0) if transmit=False (dry run) or on failure.

    Bracket order structure in IB:
        Parent:  LMT BUY  at entry_price (or slightly above for fills)
        Child 1: LMT SELL at target_price (take profit)
        Child 2: STP SELL at stop_price   (stop loss)
    Both children have parentId = parent order id and transmit = True.
    """
    from ib_async import LimitOrder, StopOrder, BracketOrder

    ticker       = trade.ticker
    shares       = trade.shares
    entry        = trade.entry_price
    tp           = trade.target_price
    sl           = trade.stop_price
    transmit     = cfg.get("order_transmit", False)
    tif          = cfg.get("order_tif", "DAY")

    # Limit price with small slippage buffer (ensure we get filled)
    slip     = cfg.get("order_limit_slippage_pct", 0.001)
    lmt_buy  = round(entry * (1 + slip), 2)

    contract = ib_client.make_stock(ticker)

    if not transmit:
        logger.info(
            f"[DRY RUN] Would place bracket: {ticker} "
            f"BUY {shares} @ ${lmt_buy:.2f}  TP=${tp:.2f}  SL=${sl:.2f}  "
            f"(transmit=False in config)"
        )
        return 0, 0, 0

    try:
        bracket = ib_client.ib.bracketOrder(
            action="BUY",
            quantity=shares,
            limitPrice=lmt_buy,
            takeProfitPrice=tp,
            stopLossPrice=sl,
        )
        # Set TIF on all legs
        for order in bracket:
            order.tif = tif

        # Place each leg
        parent_trade = ib_client.ib.placeOrder(contract, bracket.parent)
        tp_trade     = ib_client.ib.placeOrder(contract, bracket.takeProfit)
        sl_trade     = ib_client.ib.placeOrder(contract, bracket.stopLoss)

        logger.info(
            f"Bracket placed: {ticker} BUY {shares}  "
            f"Entry=${lmt_buy:.2f} TP=${tp:.2f} SL=${sl:.2f}  "
            f"IDs: {parent_trade.order.orderId}/"
            f"{tp_trade.order.orderId}/{sl_trade.order.orderId}"
        )
        return (parent_trade.order.orderId,
                tp_trade.order.orderId,
                sl_trade.order.orderId)

    except Exception as e:
        logger.error(f"Order placement failed for {ticker}: {e}")
        return 0, 0, 0


# ─── Position Monitor ─────────────────────────────────────────────────────────

class PositionMonitor:
    """
    Monitors open positions for fill events.

    On each cycle:
    - Check IB executions for parent order fills (entry confirmed)
    - Check IB executions for TP or SL child fills (trade closed)
    - On any close event: fetch daily + intraday data, log screenshot + JSON
    """

    def __init__(self, ib_client, order_logger: OrderLogger, cfg: dict):
        self.client    = ib_client
        self.logger    = order_logger
        self.cfg       = cfg
        self._open:    dict[int, Trade] = {}   # order_id → Trade
        self._tp_map:  dict[int, int]   = {}   # tp_order_id → parent_order_id
        self._sl_map:  dict[int, int]   = {}   # sl_order_id → parent_order_id

    def register(self, trade: Trade, parent_id: int, tp_id: int, sl_id: int) -> None:
        """Register a new pending trade for monitoring."""
        self._open[parent_id]  = trade
        self._tp_map[tp_id]    = parent_id
        self._sl_map[sl_id]    = parent_id
        logger.info(f"Registered: {trade.ticker} order#{parent_id}")

    async def check_fills(self, data_cache: dict[str, pd.DataFrame]) -> None:
        """
        Poll IB executions and handle any new fills.
        Called on every scan cycle.
        """
        if not self._open:
            return

        try:
            executions = self.client.ib.executions()
        except Exception as e:
            logger.warning(f"Could not fetch executions: {e}")
            return

        for exec_obj in executions:
            oid  = exec_obj.orderId
            side = exec_obj.side   # "BOT" | "SLD"
            px   = exec_obj.price
            ts   = datetime.now()

            # Entry fill
            if oid in self._open and self._open[oid].entry_time is None:
                trade = self._open[oid]
                trade.on_fill(px, ts)
                logger.info(f"ENTRY FILL: {trade.ticker} @ ${px:.2f}")
                await self._capture(trade, "entry", data_cache)

            # TP fill
            elif oid in self._tp_map:
                parent_id = self._tp_map.pop(oid)
                trade     = self._open.pop(parent_id, None)
                if trade:
                    trade.on_exit(px, ts, "tp")
                    logger.info(f"TAKE PROFIT: {trade.ticker} @ ${px:.2f}  "
                                f"PnL=${trade.pnl_usd:+.2f}")
                    await self._capture(trade, "tp", data_cache)
                    self._sl_map = {k: v for k, v in self._sl_map.items()
                                    if v != parent_id}

            # SL fill
            elif oid in self._sl_map:
                parent_id = self._sl_map.pop(oid)
                trade     = self._open.pop(parent_id, None)
                if trade:
                    trade.on_exit(px, ts, "sl")
                    logger.warning(f"STOP LOSS: {trade.ticker} @ ${px:.2f}  "
                                   f"PnL=${trade.pnl_usd:+.2f}")
                    await self._capture(trade, "sl", data_cache)
                    self._tp_map = {k: v for k, v in self._tp_map.items()
                                    if v != parent_id}

    async def _capture(
        self,
        trade:      Trade,
        event:      str,
        data_cache: dict[str, pd.DataFrame],
    ) -> None:
        """Fetch fresh daily + intraday data, then log screenshot."""
        ticker = trade.ticker

        df_daily    = data_cache.get(ticker, pd.DataFrame())
        df_intraday = await self._fetch_intraday(ticker)

        self.logger.log_event(
            trade=trade,
            event=event,
            df_daily=df_daily,
            df_intraday=df_intraday,
            extra_notes=f"Regime={trade.regime}  Score={trade.score:.1f}",
        )

    async def _fetch_intraday(self, ticker: str) -> pd.DataFrame:
        """Fetch recent 5min bars for the ticker."""
        try:
            return await self.client.fetch_historical(
                self.client.make_stock(ticker),
                duration="2 D",
                bar_size=self.cfg["bot_intraday_bar_size"],
            )
        except Exception as e:
            logger.debug(f"Intraday fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    @property
    def open_count(self) -> int:
        return len(self._open)


# ─── Main Bot Loop ────────────────────────────────────────────────────────────

async def run_bot(cfg: dict = CONFIG, watchlist_csv: str = "watchlist.csv") -> None:
    """
    Main bot loop. Runs indefinitely during market hours.

    Args:
        cfg:           CONFIG dict
        watchlist_csv: path to the elite watchlist from elite_filter.py
    """
    # Load watchlist
    try:
        watchlist = pd.read_csv(watchlist_csv)
        logger.info(f"Watchlist loaded: {len(watchlist)} tickers from {watchlist_csv}")
    except FileNotFoundError:
        logger.error(f"Watchlist not found: {watchlist_csv}. Run scanner + elite filter first.")
        return

    # Connect to IB (separate client_id from scanner)
    bot_cfg              = {**cfg, "ib_client_id": cfg["bot_ib_client_id"]}
    client               = get_client(bot_cfg)
    await client.connect()

    order_log = OrderLogger(cfg)
    monitor   = PositionMonitor(client, order_log, cfg)
    scheduler = PostTradeScheduler(order_log, cfg)

    # Pre-load daily data cache
    tickers    = watchlist["ticker"].tolist()
    data_cache = await client.fetch_all_historical(tickers)
    logger.info(f"Daily data cache: {len(data_cache)} tickers")

    interval = cfg["bot_scan_interval_sec"]
    logger.info(f"Bot started. Scanning every {interval}s. "
                f"transmit={'LIVE' if cfg['order_transmit'] else 'DRY RUN'}")

    try:
        while True:
            cycle_start = datetime.now()

            if not is_market_open(cfg):
                logger.info(f"Market closed / outside trading window — sleeping {interval}s")
                await asyncio.sleep(interval)
                continue

            logger.info(f"─── Scan cycle {cycle_start.strftime('%H:%M:%S')} "
                        f"| Open positions: {monitor.open_count}/{cfg['bot_max_open_trades']}")

            # Check fills first
            await monitor.check_fills(data_cache)

            # Post-trade follow-up snapshots (+24h, +5d)
            await scheduler.check_pending(client.fetch_historical_stock)

            # Scan for new entries
            capacity = cfg["bot_max_open_trades"] - monitor.open_count
            if capacity > 0:
                await _scan_entries(
                    watchlist, client, monitor, order_log,
                    data_cache, cfg, capacity,
                )
            else:
                logger.info("At max positions — skipping entry scan")

            # Refresh daily data cache periodically (every 10 cycles)
            # (lightweight: only refresh already-loaded tickers)

            elapsed  = (datetime.now() - cycle_start).total_seconds()
            sleep_for = max(0, interval - elapsed)
            await asyncio.sleep(sleep_for)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await client.disconnect()


async def _scan_entries(
    watchlist:  pd.DataFrame,
    client,
    monitor:    PositionMonitor,
    order_log:  OrderLogger,
    data_cache: dict,
    cfg:        dict,
    capacity:   int,
) -> None:
    """Check each watchlist ticker for an intraday entry confirmation."""
    entered  = 0
    active_tickers = set(t.ticker for t in monitor._open.values())

    for _, row in watchlist.iterrows():
        if entered >= capacity:
            break

        ticker  = row["ticker"]
        pattern = row.get("pattern", "none")

        if ticker in active_tickers:
            continue   # already have a position in this ticker

        # Fetch intraday bars for this ticker
        try:
            df_intra = await client.fetch_historical(
                client.make_stock(ticker),
                duration="2 D",
                bar_size=cfg["bot_intraday_bar_size"],
            )
        except Exception as e:
            logger.debug(f"[{ticker}] intraday fetch error: {e}")
            continue

        if df_intra.empty:
            logger.debug(f"[{ticker}] no intraday data")
            continue

        trigger_price = compute_entry_trigger(row, pattern)
        if trigger_price <= 0:
            continue

        confirmed = check_entry_confirmation(df_intra, trigger_price, cfg)

        if not confirmed:
            logger.debug(f"[{ticker}] not confirmed at ${trigger_price:.2f}")
            continue

        logger.info(f"[{ticker}] ENTRY CONFIRMED — {pattern.upper()} @ ${trigger_price:.2f}")

        # Build Trade object
        # Derive swing levels from daily data for chart annotations
        df_daily  = data_cache.get(ticker, pd.DataFrame())
        sw_low    = float(df_daily["low"].iloc[-20:].min())  if not df_daily.empty else 0.0
        sw_high   = float(df_daily["high"].iloc[-20:].max()) if not df_daily.empty else 0.0
        atr_val   = float(row.get("atr_pct", 2.0)) / 100 * float(row.get("price", 1.0))

        trade = Trade(
            ticker       = ticker,
            pattern      = pattern,
            order_id     = 0,
            entry_price  = float(row.get("entry",  trigger_price)),
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
            extra        = {
                "adx":        float(row.get("adx",        0)),
                "rsi":        float(row.get("rsi",        0)),
                "rvol":       float(row.get("rvol",       0)),
                "rs_avg_pct": float(row.get("rs_avg_pct", 0)),
            },
        )

        # Place bracket order
        parent_id, tp_id, sl_id = await place_bracket_order(client, trade, cfg)

        if not cfg.get("order_transmit", False):
            # Dry run — simulate a fill for logging purposes
            trade.order_id = 9000 + entered
            trade.on_fill(trigger_price, datetime.now())
            order_log.log_event(trade, "entry", df_daily, df_intra,
                                extra_notes="[DRY RUN]")
        else:
            trade.order_id = parent_id
            monitor.register(trade, parent_id, tp_id, sl_id)

        active_tickers.add(ticker)
        entered += 1