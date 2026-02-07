from ..fundamental.analytics.data import _get_ticker
import pandas as pd

def pe_ratio(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    pe = info.get('trailingPE')
    if pe is not None and not pd.isna(pe):
        try:
            return float(pe)
        except:
            pass
    return float('nan')

def peg_ratio(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    peg = info.get('pegRatio')
    if peg is not None and not pd.isna(peg):
        try:
            return float(peg)
        except:
            pass
    return float('nan')

def price_to_book(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    pb = info.get('priceToBook')
    if pb is not None and not pd.isna(pb):
        try:
            return float(pb)
        except:
            pass
    return float('nan')

def eps_earnings_per_share(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    eps = info.get('trailingEps')
    if eps is not None and not pd.isna(eps):
        try:
            return float(eps)
        except:
            pass
    return float('nan')
