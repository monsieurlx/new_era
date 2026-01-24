import yfinance as yf
import pandas as pd

def stock_price(ticker: str, period="1mo") -> pd.Series:
    """Get the closing prices for the last month for a given ticker symbol."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    return hist['Close']


def current_price(ticker: str) -> float:
    """Get the current price for a given ticker symbol."""
    stock = yf.Ticker(ticker)
    return stock.info.get('regularMarketPrice')


def company_info(ticker: str) -> dict:
    """Get company information for a given ticker symbol."""
    stock = yf.Ticker(ticker)
    info = stock.info
    return {
        'name': info.get('shortName', 'N/A'),
        'sector': info.get('sector', 'N/A'),
        'summary': info.get('longBusinessSummary', 'N/A')
    }


def historical_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Get OHLCV historical data for a given ticker and period (e.g., '1mo', '6mo', '1y')."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    return hist[['Open', 'High', 'Low', 'Close', 'Volume']]


def simple_moving_average(ticker: str, window: int = 20, period: str = "1mo") -> pd.Series:
    """Calculate the Simple Moving Average (SMA) for a given ticker and window size, using the same period as stock_price."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    return hist['Close'].rolling(window=window).mean().dropna()


def rsi(ticker: str, period: int = 14, price_period: str = "1mo") -> pd.Series:
    """Calculate the Relative Strength Index (RSI) for a given ticker and period, using the same period as stock_price."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=price_period)
    close = hist['Close']
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.dropna()


def news_headlines(ticker: str) -> list:
    """Get recent news headlines for a given ticker symbol."""
    stock = yf.Ticker(ticker)
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
