from .data import _get_ticker

def _get_info(ticker_or_obj):
    stock = _get_ticker(ticker_or_obj)
    return stock.info

def company_info(ticker_or_obj) -> dict:
    info = _get_info(ticker_or_obj)
    return {
        'name': info.get('shortName', 'N/A'),
        'sector': info.get('sector', 'N/A'),
        'summary': info.get('longBusinessSummary', 'N/A')
    }

def get_sector(ticker_or_obj) -> str:
    info = _get_info(ticker_or_obj)
    return info.get('sector', 'N/A')
