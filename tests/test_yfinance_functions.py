import sys
import os
import yfinance as yf
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from finance_assistant.price import stock_price, current_price, simple_moving_average, rsi
from finance_assistant.info import company_info
from finance_assistant.news import news_headlines
from finance_assistant.valuation import pe_ratio
from finance_assistant.health import debt_to_equity
from finance_assistant.scoring import return_on_ebit, return_on_capital, roic_greenblatt, magic_formula_score

# Example ticker for testing
TICKER = 'AAPL'

def test_stock_price():
    print('Stock Price:', stock_price(TICKER))

def test_current_price():
    print('Current Price:', current_price(TICKER))

def test_company_info():
    print('Company Info:', company_info(TICKER))

def test_simple_moving_average():
    print('SMA:', simple_moving_average(TICKER))

def test_rsi():
    print('RSI:', rsi(TICKER))

def test_news_headlines():
    print('News Headlines:', news_headlines(TICKER))

def test_debt_to_equity():
    stock = yf.Ticker(TICKER)
    print('Raw info:', stock.info)
    dte = debt_to_equity(stock)
    print('Debt/Equity:', dte)

def test_return_on_ebit():
    print('Return on EBIT:', return_on_ebit(TICKER))

def test_return_on_capital():
    print('Return on Capital:', return_on_capital(TICKER))

def test_roic_greenblatt():
    print('ROIC (Greenblatt):', roic_greenblatt(TICKER))

def test_magic_formula_score():
    print('Magic Formula Score:', magic_formula_score(TICKER))

if __name__ == '__main__':
    # test_stock_price()
    # test_current_price()
    # test_company_info()
    # test_simple_moving_average()
    # test_rsi()
    # test_debt_to_equity()
    # test_news_headlines()
    test_return_on_ebit()
    test_return_on_capital()
    test_roic_greenblatt()
    test_magic_formula_score()