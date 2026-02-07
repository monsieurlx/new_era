from .data import _get_ticker
from .fundamentals import profit_margin
from .valuation import pe_ratio, peg_ratio
from .health import debt_to_equity, current_ratio
import pandas as pd
import yfinance as yf

def fundamental_score(ticker_or_obj) -> dict:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    def safe_get(key, multiplier=1, default=None):
        val = info.get(key)
        if val is not None and val != float('nan'):
            try:
                return round(float(val) * multiplier, 2)
            except (ValueError, TypeError):
                return default
        return default
    return {
        'ticker': info.get('symbol', 'Unknown'),
        'profit_margin': safe_get('profitMargins', 100),
        'roe': safe_get('returnOnEquity', 100),
        'roa': safe_get('returnOnAssets', 100),
        'pe_ratio': safe_get('trailingPE', 1),
        'peg_ratio': safe_get('pegRatio', 1),
        'debt_to_equity': safe_get('debtToEquity', 1),
        'current_ratio': safe_get('currentRatio', 1),
        'revenue_growth': safe_get('revenueGrowth', 100),
    }
