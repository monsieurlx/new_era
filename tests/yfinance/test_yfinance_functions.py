import yfinance as yf
import pandas as pd
from finance_assistant import stock_price, current_price, simple_moving_average, rsi, company_info, news_headlines, pe_ratio, debt_to_equity
from finance_assistant import return_on_ebit, return_on_capital, roic_greenblatt, magic_formula_score
from finance_assistant.fundamental.analytics.sector import calculate_sector_averages
from finance_assistant.data_providers.yfinance.yfinance_provider import YFinanceProvider

# Example ticker for testing
TICKER = 'AAPL'
provider = YFinanceProvider()

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

def test_calculate_sector_averages():
    print('Sector Averages:', calculate_sector_averages(TICKER, provider=provider))

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
    test_calculate_sector_averages()