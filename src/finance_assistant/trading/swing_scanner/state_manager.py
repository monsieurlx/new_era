"""
state_manager.py — Shared state between bot process and dashboard process.

The bot writes to state.json continuously.
The dashboard reads it every 30 seconds.
No shared memory, no WebSocket server, no race conditions.

STATE SCHEMA:
{
  "last_updated":    "2025-02-22T10:34:12",
  "mode":            "paper" | "live",
  "market_status":   "pre_market" | "open_entry" | "open_monitor" | "closed",
  "trading_window":  true | false,   # whether bot is actively looking for entries
  "regime": {
    "trend":         "bull" | "neutral" | "bear",
    "vix":           18.4,
    "size_mult":     1.1,
    "spy_price":     512.3,
    "sma50":         498.1,
    "sma200":        481.2,
  },
  "last_scan": {
    "weekly":        "2025-02-16T20:14:00",
    "daily":         "2025-02-22T09:05:00",
    "candidates":    180,
    "watchlist":     15,
  },
  "watchlist": [
    {
      "ticker":      "NVDA",
      "score":       74.2,
      "pattern":     "breakout",
      "entry":       142.50,
      "stop":        136.80,
      "target":      157.20,
      "rr":          2.7,
      "rsi":         61.2,
      "adx":         28.4,
      "rvol":        2.1,
      "status":      "watching" | "triggered" | "filled" | "closed",
    },
    ...
  ],
  "open_positions": [
    {
      "ticker":      "AAPL",
      "pattern":     "pullback",
      "order_id":    1042,
      "fill_price":  183.20,
      "fill_time":   "2025-02-22T10:12:44",
      "stop":        178.40,
      "target":      192.60,
      "shares":      5,
      "current_price": 185.10,
      "unrealized_pnl": 9.50,
      "unrealized_pct": 0.52,
      "unrealized_r":   0.34,
    },
    ...
  ],
  "recent_fills": [        # last 20 fill events for the activity feed
    {
      "time":        "2025-02-22T10:12:44",
      "ticker":      "AAPL",
      "event":       "entry" | "tp" | "sl" | "cancel",
      "price":       183.20,
      "pnl_usd":     null | 44.20,
    },
    ...
  ],
  "session_stats": {
    "trades_today":   2,
    "wins_today":     1,
    "losses_today":   0,
    "open_today":     1,
    "pnl_today":      44.20,
    "total_trades":   18,
    "total_wins":     11,
    "total_pnl":      312.40,
    "win_rate":       61.1,
  },
  "errors": [],            # list of recent error strings for dashboard display
}
"""

import json
import logging
import os
import threading
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STATE_FILE = "state.json"
_lock      = threading.Lock()          # safe for multi-threaded access


# ─── Market session classifier ────────────────────────────────────────────────

SESSIONS = {
    # (start, end, label, entry_allowed)
    "pre_market":    (dtime(9,  0),  dtime(9, 30),  "PRE-MARKET",    False),
    "avoid_open":    (dtime(9, 30),  dtime(10,  0), "AVOID (OPEN)",  False),
    "entry_morning": (dtime(10,  0), dtime(11, 30), "ENTRY WINDOW ✓",True),
    "midday":        (dtime(11, 30), dtime(13, 30), "MIDDAY",        False),
    "entry_afternoon":(dtime(13,30), dtime(15,  0), "ENTRY WINDOW ✓",True),
    "avoid_close":   (dtime(15,  0), dtime(15, 45), "AVOID (CLOSE)", False),
    "market_close":  (dtime(15, 45), dtime(16,  0), "CLOSING",       False),
    "closed":        (dtime(16,  0), dtime(23, 59), "CLOSED",        False),
}


def get_market_session() -> tuple[str, str, bool]:
    """
    Returns (session_key, label, entry_allowed) for current ET time.
    Note: assumes system clock is ET. Adjust if running on UTC server.
    """
    now = datetime.now().time()
    for key, (start, end, label, allowed) in SESSIONS.items():
        if start <= now < end:
            return key, label, allowed
    return "closed", "CLOSED", False


# ─── StateManager ─────────────────────────────────────────────────────────────

class StateManager:
    """
    Manages the shared state.json file.

    The bot calls update_*() methods continuously.
    The dashboard calls read() every 30 seconds.

    Thread-safe: uses a file lock for writes.
    """

    def __init__(self, cfg: dict, path: str = STATE_FILE):
        self.cfg  = cfg
        self.path = Path(path)
        self._state = self._blank_state()

        # Load existing state if present (bot restart resilience)
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text())
                log.info(f"Resumed state from {self.path}")
            except Exception:
                log.warning("Could not read existing state.json — starting fresh")

    # ── Read (called by dashboard) ───────────────────────────────────────────

    @staticmethod
    def read(path: str = STATE_FILE) -> dict:
        """Read current state. Returns empty dict if file missing."""
        p = Path(path)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}

    # ── Write helpers (called by bot) ────────────────────────────────────────

    def _save(self) -> None:
        """Write state to disk atomically."""
        self._state["last_updated"] = datetime.now().isoformat(timespec="seconds")
        tmp = self.path.with_suffix(".tmp")
        with _lock:
            tmp.write_text(json.dumps(self._state, indent=2, default=str))
            tmp.replace(self.path)

    # ── Public update methods ─────────────────────────────────────────────────

    def set_mode(self, mode: str) -> None:
        """Set trading mode: 'paper' or 'live'."""
        self._state["mode"] = mode
        self._save()

    def update_market_status(self) -> tuple[str, bool]:
        """Refresh market session status. Returns (label, entry_allowed)."""
        key, label, allowed = get_market_session()
        self._state["market_status"]  = key
        self._state["trading_window"] = allowed
        self._save()
        return label, allowed

    def update_regime(self, regime: dict) -> None:
        self._state["regime"] = {
            "trend":    regime.get("trend",     "neutral"),
            "vix":      regime.get("vix",       0.0),
            "size_mult":regime.get("size_mult", 1.0),
            "spy_price":regime.get("spy_price", 0.0),
            "sma50":    regime.get("sma50",     0.0),
            "sma200":   regime.get("sma200",    0.0),
        }
        self._save()

    def update_scan_meta(self, scan_type: str, candidates: int = 0,
                         watchlist: int = 0) -> None:
        """Record when a scan ran and how many candidates it found."""
        if "last_scan" not in self._state:
            self._state["last_scan"] = {}
        self._state["last_scan"][scan_type]   = datetime.now().isoformat(timespec="seconds")
        self._state["last_scan"]["candidates"] = candidates
        self._state["last_scan"]["watchlist"]  = watchlist
        self._save()

    def update_watchlist(self, rows: list[dict]) -> None:
        """Replace full watchlist."""
        self._state["watchlist"] = rows
        self._save()

    def mark_watchlist_triggered(self, ticker: str) -> None:
        """Mark a watchlist entry as entry-triggered."""
        for row in self._state.get("watchlist", []):
            if row["ticker"] == ticker:
                row["status"] = "triggered"
        self._save()

    def add_open_position(self, position: dict) -> None:
        """Add a newly filled position."""
        positions = self._state.setdefault("open_positions", [])
        # Remove existing entry for same ticker if any
        positions[:] = [p for p in positions if p["ticker"] != position["ticker"]]
        positions.append(position)
        self._state["open_positions"] = positions
        self._add_fill_event(position["ticker"], "entry",
                             position["fill_price"], None)
        self._update_session_stats("entry")
        # Mark watchlist status
        for row in self._state.get("watchlist", []):
            if row["ticker"] == position["ticker"]:
                row["status"] = "filled"
        self._save()

    def update_position_price(self, ticker: str, current_price: float) -> None:
        """Update unrealized P&L for an open position."""
        for pos in self._state.get("open_positions", []):
            if pos["ticker"] == ticker:
                fp  = pos.get("fill_price", current_price)
                sh  = pos.get("shares", 1)
                sl  = pos.get("stop", fp)
                risk = max(fp - sl, 0.01)
                pos["current_price"]   = current_price
                pos["unrealized_pnl"]  = round((current_price - fp) * sh, 2)
                pos["unrealized_pct"]  = round((current_price - fp) / fp * 100, 3)
                pos["unrealized_r"]    = round((current_price - fp) / risk, 3)
        self._save()

    def close_position(self, ticker: str, exit_price: float,
                       event: str, pnl_usd: float) -> None:
        """Remove position from open, update stats, log fill event."""
        positions = self._state.get("open_positions", [])
        self._state["open_positions"] = [
            p for p in positions if p["ticker"] != ticker
        ]
        self._add_fill_event(ticker, event, exit_price, pnl_usd)
        self._update_session_stats(event, pnl_usd)
        for row in self._state.get("watchlist", []):
            if row["ticker"] == ticker:
                row["status"] = "closed"
        self._save()

    def add_error(self, msg: str) -> None:
        """Add an error message visible in the dashboard."""
        errors = self._state.setdefault("errors", [])
        errors.insert(0, {"time": datetime.now().isoformat(timespec="seconds"),
                          "msg": msg})
        self._state["errors"] = errors[:20]   # keep last 20
        self._save()

    def heartbeat(self) -> None:
        """Called every scan cycle to keep last_updated fresh."""
        self._save()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _add_fill_event(self, ticker: str, event: str,
                        price: float, pnl: float | None) -> None:
        feeds = self._state.setdefault("recent_fills", [])
        feeds.insert(0, {
            "time":    datetime.now().isoformat(timespec="seconds"),
            "ticker":  ticker,
            "event":   event,
            "price":   price,
            "pnl_usd": pnl,
        })
        self._state["recent_fills"] = feeds[:20]

    def _update_session_stats(self, event: str, pnl: float = 0.0) -> None:
        s = self._state.setdefault("session_stats", {
            "trades_today": 0, "wins_today": 0, "losses_today": 0,
            "open_today": 0,   "pnl_today":  0.0,
            "total_trades": 0, "total_wins": 0,  "total_pnl": 0.0,
            "win_rate": 0.0,
        })
        if event == "entry":
            s["open_today"]    = s.get("open_today", 0) + 1
        elif event in ("tp", "sl", "manual", "cancel"):
            s["trades_today"]  = s.get("trades_today", 0) + 1
            s["total_trades"]  = s.get("total_trades", 0) + 1
            s["open_today"]    = max(0, s.get("open_today", 1) - 1)
            s["pnl_today"]     = round(s.get("pnl_today",  0) + pnl, 2)
            s["total_pnl"]     = round(s.get("total_pnl",  0) + pnl, 2)
            if pnl > 0:
                s["wins_today"] = s.get("wins_today", 0) + 1
                s["total_wins"] = s.get("total_wins", 0) + 1
            elif pnl < 0:
                s["losses_today"] = s.get("losses_today", 0) + 1
            total = s["total_trades"]
            s["win_rate"] = round(s["total_wins"] / total * 100, 1) if total else 0.0

    @staticmethod
    def _blank_state() -> dict:
        return {
            "last_updated":   "",
            "mode":           "paper",
            "market_status":  "closed",
            "trading_window": False,
            "regime":         {},
            "last_scan":      {},
            "watchlist":      [],
            "open_positions": [],
            "recent_fills":   [],
            "session_stats":  {
                "trades_today": 0, "wins_today": 0, "losses_today": 0,
                "open_today": 0,   "pnl_today":  0.0,
                "total_trades": 0, "total_wins": 0,  "total_pnl": 0.0,
                "win_rate": 0.0,
            },
            "errors": [],
        }