from .data import _get_ticker
import pandas as pd

def debt_to_equity(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    de = info.get('debtToEquity')
    if de is not None and not pd.isna(de):
        try:
            return float(de)
        except:
            pass
    try:
        balance_sheet = stock.balance_sheet
        if balance_sheet.empty:
            return float('nan')
        total_debt = balance_sheet.loc['Total Debt'].iloc[0]
        equity = balance_sheet.loc['Total Stockholder Equity'].iloc[0]
        if equity != 0 and not pd.isna(total_debt) and not pd.isna(equity):
            return float(total_debt / equity)
    except:
        pass
    return float('nan')

def current_ratio(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    try:
        balance_sheet = stock.balance_sheet
        if balance_sheet.empty:
            return float('nan')
        current_assets = balance_sheet.loc['Current Assets'].iloc[0]
        current_liabilities = balance_sheet.loc['Current Liabilities'].iloc[0]
        if current_liabilities != 0 and not pd.isna(current_assets) and not pd.isna(current_liabilities):
            return float(current_assets / current_liabilities)
    except:
        pass
    return float('nan')

def quick_ratio(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    try:
        balance_sheet = stock.balance_sheet
        if balance_sheet.empty:
            return float('nan')
        current_assets = balance_sheet.loc['Current Assets'].iloc[0]
        inventory = balance_sheet.loc['Inventory'].iloc[0] if 'Inventory' in balance_sheet.index else 0
        current_liabilities = balance_sheet.loc['Current Liabilities'].iloc[0]
        quick_assets = current_assets - inventory
        if current_liabilities != 0 and not pd.isna(quick_assets):
            return float(quick_assets / current_liabilities)
    except:
        pass
    return float('nan')

def debt_to_assets(ticker_or_obj) -> float:
    stock = _get_ticker(ticker_or_obj)
    try:
        balance_sheet = stock.balance_sheet
        if balance_sheet.empty:
            return float('nan')
        total_debt = balance_sheet.loc['Total Debt'].iloc[0]
        total_assets = balance_sheet.loc['Total Assets'].iloc[0]
        if total_assets != 0 and not pd.isna(total_debt) and not pd.isna(total_assets):
            return float(total_debt / total_assets)
    except:
        pass
    return float('nan')
