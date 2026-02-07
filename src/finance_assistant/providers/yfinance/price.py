from ..fundamental.analytics.data import _get_ticker
import pandas as pd

def stock_price(ticker_or_obj, period="1mo") -> pd.Series:
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=period)
    return hist['Close']

def current_price(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    return stock.info.get('regularMarketPrice')

def historical_data(ticker_or_obj, period: str = "6mo") -> pd.DataFrame:
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=period)
    return hist[['Open', 'High', 'Low', 'Close', 'Volume']]

def simple_moving_average(ticker_or_obj, window: int = 20, period: str = "1mo") -> pd.Series:
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=period)
    return hist['Close'].rolling(window=window).mean().dropna()

def rsi(ticker_or_obj, period: int = 14, price_period: str = "1mo") -> pd.Series:
    stock = _get_ticker(ticker_or_obj)
    hist = stock.history(period=price_period)
    close = hist['Close']
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.dropna()
