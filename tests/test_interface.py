from finance_assistant.data_providers.yfinance.yfinance_provider import YFinanceProvider

def test_interface():
    provider = YFinanceProvider()
    print('Testing get_sector_companies:')
    print(provider.get_sector_companies('Technology', 5))

    print('\nTesting get_company_metrics:')
    print(provider.get_company_metrics('AAPL'))

    print('\nTesting get_sector_name:')
    print(provider.get_sector_name('AAPL'))

    print('\nTesting get_company_info:')
    print(provider.get_company_info('AAPL'))

    print('\nTesting get_sector_list:')
    print(provider.get_sector_list())

if __name__ == '__main__':
    test_interface()
