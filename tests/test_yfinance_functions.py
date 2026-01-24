import sys
import os
import yfinance as yf
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from finance_assistant.yfinance_functions import (
    stock_price,
    current_price,
    company_info,
    historical_data,
    simple_moving_average,
    rsi,
    news_headlines,
)

# Example ticker for testing
TICKER = 'AAPL'

def test_stock_price():
    print('Stock Price:', stock_price(TICKER))

def test_current_price():
    print('Current Price:', current_price(TICKER))

def test_company_info():
    print('Company Info:', company_info(TICKER))

def test_historical_data():
    print('Historical Data:', historical_data(TICKER))

def test_simple_moving_average():
    print('SMA:', simple_moving_average(TICKER))

def test_rsi():
    print('RSI:', rsi(TICKER))

def test_news_headlines():
    print('News Headlines:', news_headlines(TICKER))

if __name__ == '__main__':
    # test_stock_price()
    # test_current_price()
    # test_company_info()
    # test_historical_data()
    test_simple_moving_average()
    test_rsi()
    # test_news_headlines()