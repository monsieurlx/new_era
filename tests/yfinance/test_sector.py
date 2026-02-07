import pytest
import pandas as pd
from finance_assistant.providers.yfinance.sector import calculate_sector_averages
from finance_assistant.providers.yfinance.yfinance_provider import YFinanceProvider

provider = YFinanceProvider()

def test_get_sector_list():
    sectors = provider.get_sector_list()
    print('Sectors:', sectors)
    assert isinstance(sectors, list)
    assert 'technology' in sectors
    assert 'energy' in sectors
    assert len(sectors) >= 10

def test_calculate_sector_averages():
    # Use provider.get_sector_name to get the sector for a known ticker (e.g., 'AAPL')
    ticker = 'AAPL'
    sector_name = provider.get_sector_name(ticker)
    print(f"Sector for {ticker}: {sector_name}")
    result = calculate_sector_averages(sector_name, 5, provider=provider)
    print(f'Result for sector {sector_name}:', result)
    if 'error' in result:
        print('Error:', result['error'])
        assert False, f"Sector analytics failed: {result['error']}"
    assert isinstance(result, dict)
    assert 'pe_ratio' in result
    assert 'roe' in result
    assert result['companies_analyzed'] > 0

def test_compare_company_to_sector():
    pass

def test_find_sectors_for_strategy():
    pass
