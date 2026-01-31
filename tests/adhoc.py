import sys
import os
import yfinance as yf
import pandas as pd
import requests
from io import StringIO

from finance_assistant.fundamental.analytics.data import _get_ticker
from finance_assistant.fundamental.analytics.ticker import *
from finance_assistant.fundamental.analytics.sector import calculate_sector_averages


def get_index_tickers(index):
    """
    Fetch tickers for a given major index using pandas.read_html and a user-agent header.
    Supported indices: 'sp500', 'nasdaq100', 'dowjones', 'ftse100', 'nikkei225', 'cac40', 'dax', 'asx200'
    Returns a list of tickers (with correct suffixes for non-US indices).
    """
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
    url = "https://fr.wikipedia.org/wiki/CAC_40"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        # print(response.text)
        tables = pd.read_html(StringIO(response.text))
        print(tables)
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

print(get_index_tickers('cac40'))


# Get average metrics for Technology sector
tech = calculate_sector_averages('technology', n=20)

# Access any metric
print(f"Tech avg P/E: {tech['pe_ratio']['average']:.1f}")
print(f"Tech avg ROE: {tech['roe']['average']*100:.1f}%")
print(f"Tech avg EBITDA: {tech['ebitda']['average']:,.0f}")
print(f"Tech avg D/E: {tech['debt_to_equity']['average']:.2f}x")
print(f"Tech avg margins: {tech['profit_margin']['average']*100:.1f}%")

# Also get median, min, max for each
print(f"Tech median P/E: {tech['pe_ratio']['median']:.1f}")
print(f"Tech max P/E: {tech['pe_ratio']['max']:.1f}")