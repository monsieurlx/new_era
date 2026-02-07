import pytest
from finance_assistant.providers.yfinance.scoring import (
    fundamental_score,
    return_on_ebit,
    return_on_capital,
    roic_greenblatt,
    magic_formula_score,
    # All functions below are re-exported from __init__.py
    stock_price, current_price, historical_data, simple_moving_average, rsi,
    news_headlines, company_info, get_sector,
    profit_margin, operating_margin, roe_return_on_equity, roa_return_on_assets, revenue_growth, earnings_growth, eps_growth,
    pe_ratio, peg_ratio, price_to_book, eps_earnings_per_share,
    debt_to_equity, current_ratio, quick_ratio, debt_to_assets
)

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
def test_stock_price(ticker):
    s = stock_price(ticker)
    assert hasattr(s, 'index')
    c = current_price(ticker)
    assert isinstance(c, float)
    h = historical_data(ticker)
    assert hasattr(h, 'empty')

@pytest.mark.parametrize("ticker", [TICKER])
def test_fundamentals_module(ticker):
    pm = profit_margin(ticker)
    assert isinstance(pm, float)
    om = operating_margin(ticker)
    assert isinstance(om, float)
    roe = roe_return_on_equity(ticker)
    assert isinstance(roe, float)
    roa = roa_return_on_assets(ticker)
    assert isinstance(roa, float)
    rev = revenue_growth(ticker)
    assert isinstance(rev, float)
    earn = earnings_growth(ticker)
    assert isinstance(earn, float)
    eps = eps_growth(ticker)
    assert isinstance(eps, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_valuation_module(ticker):
    pe = pe_ratio(ticker)
    assert isinstance(pe, float)
    peg = peg_ratio(ticker)
    assert isinstance(peg, float)
    pb = price_to_book(ticker)
    assert isinstance(pb, float)
    eps = eps_earnings_per_share(ticker)
    assert isinstance(eps, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_health_module(ticker):
    debt = debt_to_equity(ticker)
    assert isinstance(debt, float)
    current = current_ratio(ticker)
    assert isinstance(current, float)
    quick = quick_ratio(ticker)
    assert isinstance(quick, float)
    dta = debt_to_assets(ticker)
    assert isinstance(dta, float)

@pytest.mark.parametrize("ticker", [TICKER])
def test_news_module(ticker):
    headlines = news_headlines(ticker)
    assert isinstance(headlines, list)

@pytest.mark.parametrize("ticker", [TICKER])
def test_info_module(ticker):
    info_dict = company_info(ticker)
    assert isinstance(info_dict, dict)
    sector = get_sector(ticker)
    assert isinstance(sector, str)
