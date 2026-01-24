import yfinance as yf
import pandas as pd

def _get_ticker(ticker_or_obj):
    """Helper to accept either a ticker string or a yf.Ticker object."""
    if isinstance(ticker_or_obj, yf.Ticker):
        return ticker_or_obj
    return yf.Ticker(ticker_or_obj)


def stock_price(ticker_or_obj, period="1mo") -> pd.Series:
    """Get the closing prices for the last month for a given ticker symbol."""
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=period)
    return hist['Close']


def current_price(ticker_or_obj) -> float:
    """Get the current price for a given ticker symbol."""
    stock = _get_ticker(ticker_or_obj)
    return stock.info.get('regularMarketPrice')


def company_info(ticker_or_obj) -> dict:
    """Get company information for a given ticker symbol."""
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    return {
        'name': info.get('shortName', 'N/A'),
        'sector': info.get('sector', 'N/A'),
        'summary': info.get('longBusinessSummary', 'N/A')
    }


def historical_data(ticker_or_obj, period: str = "6mo") -> pd.DataFrame:
    """Get OHLCV historical data for a given ticker and period (e.g., '1mo', '6mo', '1y')."""
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=period)
    return hist[['Open', 'High', 'Low', 'Close', 'Volume']]


def simple_moving_average(ticker_or_obj, window: int = 20, period: str = "1mo") -> pd.Series:
    """Calculate the Simple Moving Average (SMA) for a given ticker and window size, using the same period as stock_price."""
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=period)
    return hist['Close'].rolling(window=window).mean().dropna()


def rsi(ticker_or_obj, period: int = 14, price_period: str = "1mo") -> pd.Series:
    """Calculate the Relative Strength Index (RSI) for a given ticker and period, using the same period as stock_price."""
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=price_period)
    close = hist['Close']
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.dropna()


def news_headlines(ticker_or_obj) -> list:
    """Get recent news headlines for a given ticker symbol."""
    stock = _get_ticker(ticker_or_obj)
    news = getattr(stock, 'news', None)
    if not news or not isinstance(news, list):
        return []
    return [
        {
            'title': item.get('title', 'No Title'),
            'publisher': item.get('publisher', 'Unknown')
        }
        for item in news[:5]
    ]


def pe_ratio(ticker_or_obj) -> float:
    """
    Price-to-Earnings Ratio: Current price divided by annual earnings per share (EPS).
    Returns float or None if data unavailable.
    """
    stock = _get_ticker(ticker_or_obj)
    price = stock.info.get('regularMarketPrice')
    eps = stock.info.get('trailingEps')
    if price is None or eps in (None, 0):
        return float('nan')
    return price / eps


def eps_growth(ticker_or_obj) -> float:
    """
    EPS Growth: Year-over-year growth in earnings per share.
    Returns percent growth as float, or nan if unavailable.
    """
    stock = _get_ticker(ticker_or_obj)
    eps_this_year = stock.info.get('trailingEps')
    eps_last_year = stock.info.get('forwardEps')
    if eps_this_year in (None, 0) or eps_last_year in (None, 0):
        return float('nan')
    return ((eps_last_year - eps_this_year) / abs(eps_this_year)) * 100


def profit_margin(ticker_or_obj) -> float:
    """
    Profit Margin: Net income divided by revenue.
    Returns percent as float, or nan if unavailable.
    """
    stock = _get_ticker(ticker_or_obj)
    margin = stock.info.get('profitMargins')
    if margin is None:
        return float('nan')
    return margin * 100


def debt_to_equity(ticker_or_obj) -> float:
    """
    Debt-to-Equity Ratio: Total debt divided by shareholder equity.
    Uses Yahoo's precomputed 'debtToEquity' if available, else computes manually.
    Returns float or nan if unavailable.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    # Prefer Yahoo's precomputed ratio (as percent, e.g., 120 means 1.2)
    dte = info.get('debtToEquity')
    if dte is not None:
        try:
            return float(dte) / 100  # Convert percent to ratio
        except Exception:
            pass
    # Fallback: compute manually
    total_debt = info.get('totalDebt')
    equity = info.get('totalStockholderEquity')
    if total_debt is None or equity in (None, 0):
        return float('nan')
    return total_debt / equity
