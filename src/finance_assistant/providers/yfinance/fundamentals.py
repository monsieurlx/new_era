from .data import _get_ticker
import pandas as pd

def profit_margin(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    margin = info.get('profitMargins')
    if margin is not None and not pd.isna(margin):
        try:
            return float(margin)
        except:
            pass
    try:
        financials = stock.quarterly_financials
        if financials.empty:
            return float('nan')
        net_income = financials.loc['Net Income'].iloc[0]
        revenue = financials.loc['Total Revenue'].iloc[0]
        if revenue != 0 and not pd.isna(net_income) and not pd.isna(revenue):
            return float(net_income / revenue)
    except:
        pass
    return float('nan')

def operating_margin(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    try:
        financials = stock.quarterly_financials
        if financials.empty:
            return float('nan')
        operating_income = None
        if 'Operating Income' in financials.index:
            operating_income = financials.loc['Operating Income'].iloc[0]
        elif 'OperatingIncome' in financials.index:
            operating_income = financials.loc['OperatingIncome'].iloc[0]
        revenue = financials.loc['Total Revenue'].iloc[0]
        if revenue != 0 and operating_income is not None and not pd.isna(operating_income) and not pd.isna(revenue):
            return float(operating_income / revenue)
    except:
        pass
    return float('nan')
