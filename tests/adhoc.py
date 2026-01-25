import sys
import os
import yfinance as yf
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from finance_assistant.data import _get_ticker
# from finance_assistant.price import stock_price, current_price, simple_moving_average, rsi
# from finance_assistant.info import company_info
# from finance_assistant.news import news_headlines
# from finance_assistant.valuation import pe_ratio
# from finance_assistant.health import debt_to_equity
# from finance_assistant.scoring import return_on_ebit, return_on_capital, roic_greenblatt, magic_formula_score

def return_on_ebit(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    print(info)
    ros = info.get('returnOnSales')
    print(ros)
    if ros is not None:
        try:
            return float(ros)
        except Exception:
            pass
    ebit = info.get('ebit')
    revenue = info.get('totalRevenue')
    if ebit is None or revenue in (None, 0):
        return float('nan')
    return ebit / revenue

ticker = 'AAPL'

print(return_on_ebit(ticker)   )