"""
reconcile.py — Startup order reconciliation for paper/live trading.

Problem: IB paper trading resets overnight, silently cancelling all open orders.
Result:  state.json still shows positions as "open" but there are no live orders.

This module runs once at bot startup and fixes the mismatch:
  1. Load open_positions from state.json
  2. Query IB for currently active orders
  3. For each position with no matching IB order:
       a. If status is "pending" (entry never filled) → re-submit bracket order
       b. If status is "open" (entry filled, managing TP/SL) → re-submit TP/SL bracket
  4. Re-register everything with PositionMonitor so fills are tracked normally

Design: completely additive — doesn't change StateManager or PositionMonitor,
just populates them correctly from persisted state before the main loop starts.
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from bot import PositionMonitor
    from ib_client import IBClient
    from order_logger import OrderLogger, Trade
    from state_manager import StateManager

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _active_ib_order_ids(client) -> set[int]:
    """Return set of currently active (open/submitted) order IDs from IB."""
    try:
        trades = client.ib.trades()
        active_statuses = {
            "Submitted", "PreSubmitted", "PendingSubmit",
            "PendingCancel", "ApiWaiting",
        }
        return {
            t.order.orderId
            for t in trades
            if t.orderStatus.status in active_statuses
        }
    except Exception as e:
        log.warning(f"Could not query IB active orders: {e}")
        return set()


def _build_trade_from_pos(pos: dict, order_id: int = 0) -> "Trade":
    """Reconstruct a Trade object from a persisted state position dict."""
    from order_logger import Trade
    return Trade(
        ticker       = pos["ticker"],
        pattern      = pos.get("pattern", "unknown"),
        order_id     = order_id,
        entry_price  = pos.get("fill_price", pos.get("entry", 0.0)),
        stop_price   = pos.get("stop",   0.0),
        target_price = pos.get("target", 0.0),
        shares       = int(pos.get("shares", 1)),
        score        = pos.get("score",  0.0),
        regime       = pos.get("regime", "unknown"),
        vix          = pos.get("vix",    0.0),
        rr           = pos.get("rr",     0.0),
        atr          = pos.get("atr",    0.0),
        swing_low    = pos.get("swing_low",  0.0),
        swing_high   = pos.get("swing_high", 0.0),
        extra        = pos.get("extra",  {}),
    )


async def _resubmit_pending(client, pos: dict, cfg: dict) -> tuple[int, int, int]:
    """
    Re-submit a full bracket order for a position whose entry was never filled.
    Returns (parent_id, tp_id, sl_id) or (0,0,0) on failure.
    """
    from bot import place_bracket_order
    trade = _build_trade_from_pos(pos)
    log.info(f"[{pos['ticker']}] Re-submitting pending entry bracket "
             f"@ ${trade.entry_price:.2f}  SL=${trade.stop_price:.2f}  "
             f"TP=${trade.target_price:.2f}")
    return await place_bracket_order(client, trade, cfg)


async def _resubmit_tp_sl(client, pos: dict, cfg: dict) -> tuple[int, int]:
    """
    Re-submit only TP + SL orders for a position already filled.
    Returns (tp_id, sl_id) or (0,0) on failure.
    """
    from ib_async import LimitOrder, StopOrder
    ticker  = pos["ticker"]
    fill_px = pos.get("fill_price", 0.0)
    stop    = pos.get("stop",   0.0)
    target  = pos.get("target", 0.0)
    shares  = int(pos.get("shares", 1))
    tif     = cfg.get("order_tif", "GTC")

    if not (fill_px > 0 and stop > 0 and target > 0):
        log.warning(f"[{ticker}] Missing levels for TP/SL resubmit — skipping")
        return 0, 0

    try:
        contract = client.make_stock(ticker)
        tp_order = LimitOrder("SELL", shares, target)
        tp_order.tif = tif
        tp_order.outsideRth = True

        sl_order = StopOrder("SELL", shares, stop)
        sl_order.tif = tif
        sl_order.outsideRth = True

        tp_trade = client.ib.placeOrder(contract, tp_order)
        sl_trade = client.ib.placeOrder(contract, sl_order)

        log.info(f"[{ticker}] Re-submitted TP @ ${target:.2f} (id={tp_trade.order.orderId})  "
                 f"SL @ ${stop:.2f} (id={sl_trade.order.orderId})")
        return tp_trade.order.orderId, sl_trade.order.orderId

    except Exception as e:
        log.error(f"[{ticker}] TP/SL resubmit failed: {e}")
        return 0, 0


# ── Main reconciliation entry point ──────────────────────────────────────────

async def reconcile_on_startup(
    client,
    monitor:    "PositionMonitor",
    state:      "StateManager",
    order_log:  "OrderLogger",
    data_cache: dict,
    cfg:        dict,
) -> int:
    """
    Called once at bot startup, after IB connection is established.

    Checks every position in state.json against live IB orders.
    Re-submits and re-registers anything that has gone missing.

    Returns number of positions reconciled (re-submitted).
    """
    if not cfg.get("order_transmit", False):
        log.info("Reconcile: dry-run mode — skipping (no live orders to check)")
        return 0

    open_positions = state.get_open_positions() if hasattr(state, "get_open_positions") \
                     else state._state.get("open_positions", [])

    if not open_positions:
        log.info("Reconcile: no open positions in state — nothing to do")
        return 0

    active_ids   = _active_ib_order_ids(client)
    reconciled   = 0

    log.info(f"Reconcile: {len(open_positions)} open positions in state, "
             f"{len(active_ids)} active IB orders")

    for pos in list(open_positions):
        ticker    = pos.get("ticker", "?")
        order_id  = int(pos.get("order_id",  0))
        tp_id     = int(pos.get("tp_id",     0))
        sl_id     = int(pos.get("sl_id",     0))
        fill_time = pos.get("fill_time")

        is_filled  = fill_time is not None
        has_entry  = order_id in active_ids
        has_tp     = tp_id    in active_ids
        has_sl     = sl_id    in active_ids

        if is_filled:
            # Position already filled — check TP/SL are still live
            if has_tp and has_sl:
                # Both exits live — just re-register so monitor tracks fills
                log.info(f"[{ticker}] Already filled, exits live — re-registering")
                trade = _build_trade_from_pos(pos, order_id)
                trade.fill_price = float(pos.get("fill_price", 0))
                trade.fill_time  = datetime.fromisoformat(fill_time)
                trade.status     = "open"
                monitor.register(trade, order_id, tp_id, sl_id)

            else:
                # Exits missing — re-submit TP/SL
                log.warning(f"[{ticker}] FILLED but TP/SL missing from IB — re-submitting exits")
                new_tp_id, new_sl_id = await _resubmit_tp_sl(client, pos, cfg)
                if new_tp_id and new_sl_id:
                    trade = _build_trade_from_pos(pos, order_id)
                    trade.fill_price = float(pos.get("fill_price", 0))
                    trade.fill_time  = datetime.fromisoformat(fill_time)
                    trade.status     = "open"
                    monitor.register(trade, order_id, new_tp_id, new_sl_id)
                    # Update persisted IDs so next restart is clean
                    pos["tp_id"] = new_tp_id
                    pos["sl_id"] = new_sl_id
                    state._save()
                    reconciled += 1
                else:
                    log.error(f"[{ticker}] Could not re-submit exits — manual intervention needed")

        else:
            # Entry not yet filled
            if has_entry:
                # Entry order still live — re-register
                log.info(f"[{ticker}] Pending entry still live — re-registering")
                trade = _build_trade_from_pos(pos, order_id)
                monitor.register(trade, order_id, tp_id, sl_id)
            else:
                # Entry order vanished — re-submit full bracket
                log.warning(f"[{ticker}] PENDING entry missing from IB — re-submitting bracket")
                df_daily = data_cache.get(ticker, pd.DataFrame())
                new_parent, new_tp, new_sl = await _resubmit_pending(client, pos, cfg)
                if new_parent:
                    trade = _build_trade_from_pos(pos, new_parent)
                    monitor.register(trade, new_parent, new_tp, new_sl)
                    pos["order_id"] = new_parent
                    pos["tp_id"]    = new_tp
                    pos["sl_id"]    = new_sl
                    state._save()
                    reconciled += 1
                else:
                    log.error(f"[{ticker}] Could not re-submit entry — removing from state")
                    state._state["open_positions"] = [
                        p for p in state._state["open_positions"]
                        if p.get("ticker") != ticker
                    ]
                    state._save()

    log.info(f"Reconcile complete — {reconciled} orders re-submitted, "
             f"{len(open_positions) - reconciled} already active")
    return reconciled