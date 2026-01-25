import pytest
import yfinance as yf
import sys
import os 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from finance_assistant.scoring import (
    fundamental_score,
    return_on_ebit,
    return_on_capital,
    roic_greenblatt,
    magic_formula_score,
)
from finance_assistant import data, price, fundamentals, valuation, health, news, info

TICKER = 'AAPL'

@pytest.mark.parametrize("ticker", [TICKER])
def test_fundamental_score(ticker):
    result = fundamental_score(ticker)
    assert isinstance(result, dict)
    assert 'ticker' in result
    # Check that at least one metric is not None
    assert any(v is not None for k, v in result.items() if k != 'ticker')

@pytest.mark.parametrize("ticker", [TICKER])
def test_return_on_ebit(ticker):
    val = return_on_ebit(ticker)
    assert isinstance(val, float)
    assert val == val  # not nan

@pytest.mark.parametrize("ticker", [TICKER])
def test_return_on_capital(ticker):
    val = return_on_capital(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_roic_greenblatt(ticker):
    val = roic_greenblatt(ticker)
    assert isinstance(val, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_magic_formula_score(ticker):
    val = magic_formula_score(ticker)
    assert isinstance(val, dict)
    assert 'ebit_ev' in val and 'roc' in val

@pytest.mark.parametrize("ticker", [TICKER])
def test_data_module(ticker):
    # No public function in data.py to test
    pass

@pytest.mark.parametrize("ticker", [TICKER])
def test_price_module(ticker):
    s = price.stock_price(ticker)
    assert hasattr(s, 'index')
    c = price.current_price(ticker)
    assert isinstance(c, float)
    h = price.historical_data(ticker)
    assert hasattr(h, 'empty')

@pytest.mark.parametrize("ticker", [TICKER])
def test_fundamentals_module(ticker):
    pm = fundamentals.profit_margin(ticker)
    assert isinstance(pm, float)
    om = fundamentals.operating_margin(ticker)
    assert isinstance(om, float)
    roe = fundamentals.roe_return_on_equity(ticker)
    assert isinstance(roe, float)
    roa = fundamentals.roa_return_on_assets(ticker)
    assert isinstance(roa, float)
    rev = fundamentals.revenue_growth(ticker)
    assert isinstance(rev, float)
    earn = fundamentals.earnings_growth(ticker)
    assert isinstance(earn, float)
    eps = fundamentals.eps_growth(ticker)
    assert isinstance(eps, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_valuation_module(ticker):
    pe = valuation.pe_ratio(ticker)
    assert isinstance(pe, float)
    peg = valuation.peg_ratio(ticker)
    assert isinstance(peg, float)
    pb = valuation.price_to_book(ticker)
    assert isinstance(pb, float)
    eps = valuation.eps_earnings_per_share(ticker)
    assert isinstance(eps, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_health_module(ticker):
    debt = health.debt_to_equity(ticker)
    assert isinstance(debt, float)
    current = health.current_ratio(ticker)
    assert isinstance(current, float)
    quick = health.quick_ratio(ticker)
    assert isinstance(quick, float)
    dta = health.debt_to_assets(ticker)
    assert isinstance(dta, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_news_module(ticker):
    headlines = news.news_headlines(ticker)
    assert isinstance(headlines, list)

@pytest.mark.parametrize("ticker", [TICKER])
def test_info_module(ticker):
    info_dict = info.company_info(ticker)
    assert isinstance(info_dict, dict)
    sector = info.get_sector(ticker)
    assert isinstance(sector, str)
