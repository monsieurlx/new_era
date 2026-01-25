import pytest
import yfinance as yf
import sys
import os 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from finance_assistant.price import stock_price, current_price, simple_moving_average, rsi
from finance_assistant.info import company_info, get_sector
from finance_assistant.news import news_headlines
from finance_assistant.valuation import pe_ratio, peg_ratio, price_to_book, eps_earnings_per_share
from finance_assistant.fundamentals import profit_margin, operating_margin, roe_return_on_equity, roa_return_on_assets, revenue_growth, earnings_growth, eps_growth
from finance_assistant.health import debt_to_equity, current_ratio, quick_ratio, debt_to_assets

TICKER = 'AAPL'

@pytest.mark.parametrize("ticker", [TICKER])
def test_stock_price(ticker):
    prices = stock_price(ticker)
    assert hasattr(prices, 'iloc')
    assert len(prices) > 0

@pytest.mark.parametrize("ticker", [TICKER])
def test_current_price(ticker):
    price = current_price(ticker)
    assert isinstance(price, (float, int))
    assert price > 0

@pytest.mark.parametrize("ticker", [TICKER])
def test_company_info(ticker):
    info = company_info(ticker)
    assert isinstance(info, dict)
    assert 'name' in info and 'sector' in info

@pytest.mark.parametrize("ticker", [TICKER])
def test_get_sector(ticker):
    sector = get_sector(ticker)
    assert isinstance(sector, str)
    assert len(sector) > 0

@pytest.mark.parametrize("ticker", [TICKER])
def test_news_headlines(ticker):
    news = news_headlines(ticker)
    assert isinstance(news, list)

@pytest.mark.parametrize("ticker", [TICKER])
def test_pe_ratio(ticker):
    val = pe_ratio(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_peg_ratio(ticker):
    val = peg_ratio(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_price_to_book(ticker):
    val = price_to_book(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_eps_earnings_per_share(ticker):
    val = eps_earnings_per_share(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_profit_margin(ticker):
    val = profit_margin(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_operating_margin(ticker):
    val = operating_margin(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_roe_return_on_equity(ticker):
    val = roe_return_on_equity(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_roa_return_on_assets(ticker):
    val = roa_return_on_assets(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_revenue_growth(ticker):
    val = revenue_growth(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_earnings_growth(ticker):
    val = earnings_growth(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_eps_growth(ticker):
    val = eps_growth(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_debt_to_equity(ticker):
    val = debt_to_equity(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_current_ratio(ticker):
    val = current_ratio(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_quick_ratio(ticker):
    val = quick_ratio(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_debt_to_assets(ticker):
    val = debt_to_assets(ticker)
    assert isinstance(val, float)
