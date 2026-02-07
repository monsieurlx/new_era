import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from io import StringIO

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
        print(f"Fetched {len(tickers)} tickers for {index.upper()} from Wikipedia.")
        return tickers
    except Exception as e:
        print(f"Error fetching {index.upper()} tickers: {e}")
        return []

def get_global_index_tickers(indices=None):
    if indices is None:
        indices = ['sp500', 'nasdaq100', 'dowjones']
    all_tickers = set()
    for idx in indices:
        all_tickers.update(get_index_tickers(idx))
    print(f"Total unique tickers fetched: {len(all_tickers)}")
    return list(all_tickers)
