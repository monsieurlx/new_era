import yfinance as yf
import pandas as pd

def _get_ticker(ticker_or_obj):
    """Helper to accept either a ticker string or a yf.Ticker object."""
    if isinstance(ticker_or_obj, yf.Ticker):
        return ticker_or_obj
    return yf.Ticker(ticker_or_obj)
