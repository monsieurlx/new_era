import pytest
from finance_assistant.macro.analytics import get_misery_index, get_dollar_index, get_cpi, get_unemployment_rate, get_gdp_growth

# Test the macroeconomic index functions for basic data retrieval and structure

def test_get_misery_index():
    series = get_misery_index()
    assert series is not None
    assert not series.empty
    assert 'Misery Index' in series.name

def test_get_dollar_index():
    series = get_dollar_index()
    assert series is not None
    assert not series.empty
    assert 'DXY' in series.name

def test_get_cpi():
    series = get_cpi()
    assert series is not None
    assert not series.empty
    assert 'CPI' in series.name

def test_get_unemployment_rate():
    series = get_unemployment_rate()
    assert series is not None
    assert not series.empty
    assert 'Unemployment Rate' in series.name

def test_get_gdp_growth():
    series = get_gdp_growth()
    assert series is not None
    assert not series.empty
    assert 'GDP Growth' in series.name
