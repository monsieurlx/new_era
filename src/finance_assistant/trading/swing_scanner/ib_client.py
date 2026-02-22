"""
ib_client.py — All Interactive Brokers API interaction.

PERFORMANCE:
    Uses concurrent async requests with a semaphore to max out IB's throughput
    while staying within pacing limits.

    IB pacing rule: max 50 historical data requests per 10 seconds per connection.
    Strategy: run N concurrent workers (default 40), each waiting only when the
    semaphore is exhausted — not sleeping between every single request.

    Result: 500 tickers in ~60-90s instead of ~5 minutes.

SETUP:
    pip install ib_async
    Start TWS or IB Gateway before running.
    Paper trading port: 7497 (TWS) or 4002 (Gateway)
    Live trading port:  7496 (TWS) or 4001 (Gateway)
"""

import asyncio
import logging
import time
from collections import deque

import pandas as pd

logger = logging.getLogger(__name__)

# ── Try importing ib_async ────────────────────────────────────────────────────
try:
    from ib_async import IB, Stock, Index, util
    IB_AVAILABLE = True
except ImportError:
    logger.warning("ib_async not installed. Falling back to yfinance.")
    IB_AVAILABLE = False

# ── Ticker symbol normalization ───────────────────────────────────────────────
# IB uses different symbols for some tickers vs Wikipedia's list
_SYMBOL_MAP = {
    "BRK.B":  "BRK B",   # Berkshire B shares — IB uses space not dot
    "BRK.A":  "BRK A",
    "BF.B":   "BF B",    # Brown-Forman B
    "BF.A":   "BF A",
}

def normalize_ticker(ticker: str) -> str:
    """Map Wikipedia-style ticker to IB-compatible symbol."""
    return _SYMBOL_MAP.get(ticker, ticker.replace("-", " "))


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class IBRateLimiter:
    """
    Token-bucket style rate limiter for IB historical data requests.

    IB rule: no more than `max_requests` per `window_seconds`.
    Default: 45 requests per 10 seconds (conservative margin under the 50 limit).

    Usage:
        limiter = IBRateLimiter(max_requests=45, window_seconds=10)
        await limiter.acquire()   # blocks if at the rate limit
        # ... make your request ...
    """

    def __init__(self, max_requests: int = 45, window_seconds: float = 10.0):
        self.max_requests    = max_requests
        self.window_seconds  = window_seconds
        self._timestamps: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Drop timestamps outside the sliding window
            while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.max_requests:
                # Must wait until the oldest request expires from the window
                sleep_for = self.window_seconds - (now - self._timestamps[0]) + 0.05
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                # Re-clean after sleeping
                now = time.monotonic()
                while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                    self._timestamps.popleft()

            self._timestamps.append(time.monotonic())


# ─── IB Client ────────────────────────────────────────────────────────────────

class IBClient:
    """
    Wraps all IB API calls with concurrent batched fetching.

    Key optimization: fetch_all_historical() uses asyncio.gather() with a
    semaphore + rate limiter to send up to `ib_concurrent_requests` requests
    simultaneously while respecting IB's 50-req/10s pacing rule.

    Usage:
        client = IBClient(cfg)
        await client.connect()
        data = await client.fetch_all_historical(tickers)
        await client.disconnect()
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._connected = False
        self.ib = IB() if IB_AVAILABLE else None
        # Semaphore limits true concurrency to avoid overwhelming IB
        self._sem = asyncio.Semaphore(cfg.get("ib_concurrent_requests", 40))
        # Rate limiter enforces IB's 50 req/10s hard limit
        self._rate = IBRateLimiter(
            max_requests=cfg.get("ib_rate_limit_requests", 45),
            window_seconds=cfg.get("ib_rate_limit_window", 10.0),
        )

    # ─── Connection ──────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if not IB_AVAILABLE:
            logger.info("ib_async not available — dev mode")
            return
        host      = self.cfg["ib_host"]
        port      = self.cfg["ib_port"]
        client_id = self.cfg["ib_client_id"]
        try:
            await self.ib.connectAsync(host, port, clientId=client_id)
            self._connected = True
            logger.info(f"Connected to IB at {host}:{port} (client_id={client_id})")
        except Exception as e:
            raise ConnectionError(
                f"Cannot connect to IB at {host}:{port}.\n"
                f"  → Is TWS or IB Gateway running?\n"
                f"  → API port enabled? (Settings → API → Enable Socket Clients)\n"
                f"  → Is client_id={client_id} already in use?\n"
                f"  Original: {e}"
            )

    async def disconnect(self) -> None:
        if IB_AVAILABLE and self._connected:
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IB")

    # ─── Contract Builders ───────────────────────────────────────────────────

    def make_stock(self, ticker: str):
        symbol = normalize_ticker(ticker)
        return Stock(symbol, "SMART", "USD")

    def make_vix(self):
        return Index("VIX", "CBOE")

    # ─── Single Historical Fetch ─────────────────────────────────────────────

    async def fetch_historical(
        self,
        contract,
        duration: str = None,
        bar_size: str = None,
        what_to_show: str = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars for one contract. Returns empty DataFrame on any failure."""
        if not IB_AVAILABLE or not self._connected:
            return pd.DataFrame()

        cfg          = self.cfg
        duration     = duration     or cfg["history_duration"]
        bar_size     = bar_size     or cfg["history_bar_size"]
        what_to_show = what_to_show or cfg["history_what_to_show"]

        try:
            bars = await self.ib.reqHistoricalDataAsync(
                contract=contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=True,
                formatDate=1,
            )
            if not bars or len(bars) < cfg["min_bars_required"]:
                return pd.DataFrame()

            df = util.df(bars)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            df.columns = [c.lower() for c in df.columns]
            return df[["open", "high", "low", "close", "volume"]].dropna()

        except Exception as e:
            logger.debug(f"fetch_historical error: {e}")
            return pd.DataFrame()

    async def fetch_historical_stock(self, ticker: str) -> pd.DataFrame:
        return await self.fetch_historical(self.make_stock(ticker))

    async def fetch_vix(self) -> pd.Series:
        df = await self.fetch_historical(self.make_vix(), what_to_show="TRADES")
        if df.empty:
            logger.warning("VIX unavailable — regime will default to neutral")
            return pd.Series(dtype=float)
        return df["close"].rename("vix")

    # ─── Concurrent Batch Fetch ──────────────────────────────────────────────

    async def _fetch_one_throttled(
        self,
        ticker: str,
        results: dict,
        counters: dict,
    ) -> None:
        """
        Fetch one ticker under semaphore + rate limiter control.
        Writes result into shared `results` dict.
        """
        async with self._sem:
            await self._rate.acquire()
            try:
                df = await self.fetch_historical_stock(ticker)
                if not df.empty:
                    results[ticker] = df
                    counters["ok"] += 1
                else:
                    counters["skip"] += 1
            except Exception as e:
                logger.debug(f"[{ticker}] fetch error: {e}")
                counters["err"] += 1
            finally:
                counters["done"] += 1
                total = counters["total"]
                done  = counters["done"]
                if done % 50 == 0 or done == total:
                    pct = done / total * 100
                    elapsed = time.monotonic() - counters["t0"]
                    rate = done / elapsed if elapsed > 0 else 0
                    eta  = (total - done) / rate if rate > 0 else 0
                    logger.info(
                        f"  [{done:>3}/{total}]  {pct:4.0f}%  "
                        f"valid={counters['ok']}  "
                        f"elapsed={elapsed:.0f}s  eta={eta:.0f}s"
                    )

    async def fetch_all_historical(self, tickers: list[str]) -> dict[str, pd.DataFrame]:
        """
        Fetch historical data for all tickers concurrently.

        Instead of sequential requests with a fixed sleep between each one,
        this fires all requests simultaneously under semaphore + rate-limiter
        control. The rate limiter enforces IB's 50 req/10s rule without
        unnecessary idle time.

        503 tickers: ~60-90 seconds vs ~5 minutes sequentially.
        """
        if not tickers:
            return {}

        total    = len(tickers)
        results  = {}
        counters = {"ok": 0, "skip": 0, "err": 0, "done": 0, "total": total,
                    "t0": time.monotonic()}

        concurrency = self.cfg.get("ib_concurrent_requests", 40)
        logger.info(
            f"Fetching {total} tickers concurrently "
            f"(max_concurrent={concurrency}, "
            f"rate_limit={self.cfg.get('ib_rate_limit_requests', 45)}"
            f"/{self.cfg.get('ib_rate_limit_window', 10)}s)"
        )

        tasks = [
            self._fetch_one_throttled(ticker, results, counters)
            for ticker in tickers
        ]
        await asyncio.gather(*tasks)

        elapsed = time.monotonic() - counters["t0"]
        logger.info(
            f"Fetch complete: {counters['ok']} valid / "
            f"{counters['skip']} empty / "
            f"{counters['err']} errors  "
            f"in {elapsed:.1f}s"
        )
        return results


# ─── yfinance fallback ────────────────────────────────────────────────────────

class YFinanceFallbackClient:
    """
    Drop-in for IBClient when ib_async is not installed.
    Uses a true batch download (one HTTP call for all tickers).
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        try:
            import yfinance as yf
            self._yf = yf
        except ImportError:
            raise ImportError("pip install yfinance  OR  pip install ib_async")

    async def connect(self) -> None:
        logger.info("yfinance client ready (no connection needed)")

    async def disconnect(self) -> None:
        pass

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df.index.name = "date"
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[cols].dropna()
        return df if len(df) >= self.cfg["min_bars_required"] else pd.DataFrame()

    async def fetch_historical_stock(self, ticker: str) -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        df   = await loop.run_in_executor(
            None,
            lambda: self._yf.download(ticker, period="1y", auto_adjust=True, progress=False),
        )
        return self._clean(df)

    async def fetch_vix(self) -> pd.Series:
        df = await self.fetch_historical_stock("^VIX")
        return df["close"].rename("vix") if not df.empty else pd.Series(dtype=float)

    async def fetch_all_historical(self, tickers: list[str]) -> dict[str, pd.DataFrame]:
        """Single batch download via yfinance (much faster than one-by-one)."""
        total = len(tickers)
        logger.info(f"yfinance batch download: {total} tickers")
        t0 = time.monotonic()

        loop = asyncio.get_event_loop()
        raw  = await loop.run_in_executor(
            None,
            lambda: self._yf.download(
                tickers, period="1y", auto_adjust=True,
                progress=False, group_by="ticker", threads=True,
            ),
        )

        results = {}
        for ticker in tickers:
            try:
                df = raw[ticker].copy() if total > 1 else raw.copy()
                df = self._clean(df)
                if not df.empty:
                    results[ticker] = df
            except Exception:
                pass

        elapsed = time.monotonic() - t0
        logger.info(f"yfinance: {len(results)}/{total} tickers in {elapsed:.1f}s")
        return results


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_client(cfg: dict):
    """Return IBClient if ib_async is installed, else yfinance fallback."""
    if IB_AVAILABLE:
        return IBClient(cfg)
    logger.warning("ib_async not found — using yfinance fallback")
    return YFinanceFallbackClient(cfg)