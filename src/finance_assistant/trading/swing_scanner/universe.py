"""
universe.py — Provides the list of tickers to scan.

Supports: S&P 500, Nasdaq 100, or a custom list.
Falls back to a hardcoded list of large-caps if network fails.
"""


import logging
import pandas as pd
import requests
from io import StringIO

logger = logging.getLogger(__name__)


# ── Robust fallback: fetch S&P 500, CAC40, etc. from Wikipedia if possible ──
def get_index_tickers(index):
    url_map = {
        'sp500': ('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', 'Symbol', 0, None),
        'nasdaq100': ('https://en.wikipedia.org/wiki/NASDAQ-100', 'Ticker', 4, None),
        'dowjones': ('https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average', 'Symbol', 1, None),
        'ftse100': ('https://en.wikipedia.org/wiki/FTSE_100_Index', 'EPIC', 3, '.L'),
        'nikkei225': ('https://en.wikipedia.org/wiki/Nikkei_225', 'Ticker', 3, '.T'),
        'cac40': ('https://en.wikipedia.org/wiki/CAC_40', 'Ticker', 1, '.PA'),
        'dax': ('https://en.wikipedia.org/wiki/DAX', 'Ticker symbol', 1, '.DE'),
        'asx200': ('https://en.wikipedia.org/wiki/S%26P/ASX_200', 'ASX code', 0, '.AX'),
    }
    if index not in url_map:
        raise ValueError(f"Index '{index}' not supported.")
    url, col, table_idx, suffix = url_map[index]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        tables = pd.read_html(StringIO(response.text))
        df = tables[table_idx]
        tickers = df[col].tolist()
        if suffix:
            tickers = [t.strip() + suffix for t in tickers]
        else:
            tickers = [t.strip() for t in tickers]
        logger.info(f"Fetched {len(tickers)} tickers for {index.upper()} from Wikipedia.")
        return tickers
    except Exception as e:
        logger.warning(f"Error fetching {index.upper()} tickers: {e}")
        return []

def get_fallback_tickers():
    # Try to fetch S&P 500 and NASDAQ 100, else use static subset
    sp500 = get_index_tickers('sp500')
    nasdaq100 = get_index_tickers('nasdaq100')
    if sp500 or nasdaq100:
        return list(set(sp500 + nasdaq100))
    # If all fetches fail, use a static minimal fallback
    return [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
        "AIR.PA", "BNP.PA", "OR.PA", "MC.PA"
    ]



def get_tickers(cfg: dict) -> list[str]:
    """
    Return the list of tickers based on cfg["universe"].
    Args:
        cfg: CONFIG dict. Reads keys: "universe", "custom_tickers".
    Returns:
        List of ticker strings.
    """
    universe = cfg.get("universe", "sp500")
    if universe == "custom":
        tickers = cfg.get("custom_tickers", [])
        logger.info(f"Custom universe: {len(tickers)} tickers")
        return tickers
    if universe in ("sp500", "nasdaq100", "dowjones", "ftse100", "nikkei225", "cac40", "dax", "asx200"):
        tickers = get_index_tickers(universe)
        if tickers:
            return tickers
        logger.warning(f"Falling back to combined S&P 500 + CAC40 tickers.")
        return get_fallback_tickers()
    logger.warning(f"Unknown universe '{universe}', using fallback tickers.")
    return get_fallback_tickers()

