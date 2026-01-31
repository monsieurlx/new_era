from .data import _get_ticker

def company_info(ticker_or_obj) -> dict:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    return {
        'name': info.get('shortName', 'N/A'),
        'sector': info.get('sector', 'N/A'),
        'summary': info.get('longBusinessSummary', 'N/A')
    }

def get_sector(ticker_or_obj) -> str:
    stock = _get_ticker(ticker_or_obj)
    return stock.info.get('sector', 'N/A')
