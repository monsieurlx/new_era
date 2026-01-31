from .data import _get_ticker

def news_headlines(ticker_or_obj) -> list:
    stock = _get_ticker(ticker_or_obj)
    news = getattr(stock, 'news', None)
    if not news or not isinstance(news, list):
        return []
    return [
        {
            'title': item.get('title', 'No Title'),
            'publisher': item.get('publisher', 'Unknown')
        }
        for item in news[:5]
    ]
