import yfinance as yf
from typing import Dict, Any

def get_company_metrics(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            'ticker': ticker,
            'pe_ratio': info.get('trailingPE'),
            'peg_ratio': info.get('pegRatio'),
            'profit_margin': info.get('profitMargins'),
            'roe': info.get('returnOnEquity'),
            'roa': info.get('returnOnAssets'),
            'debt_to_equity': info.get('debtToEquity'),
            'current_ratio': info.get('currentRatio'),
            'revenue': info.get('totalRevenue'),
            'market_cap': info.get('marketCap'),
            'dividend_yield': info.get('dividendYield'),
            'eps': info.get('trailingEps'),
            'ebitda': info.get('ebitda'),
            'free_cashflow': info.get('freeCashflow'),
            'debt': info.get('totalDebt'),
            'cash': info.get('totalCash'),
        }
    except Exception as e:
        print(f"⚠ Error getting {ticker}: {e}")
        return {'ticker': ticker}

def get_company_info(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        return stock.info
    except Exception:
        return {}

def get_sector_name(ticker: str) -> str:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get('sector', 'N/A')
    except Exception:
        return 'N/A'
