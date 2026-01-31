from .data import _get_ticker
import pandas as pd

def profit_margin(ticker_or_obj) -> float:
    """
    Profit Margin: Measures how much of each dollar in revenue a company actually keeps as profit after all expenses.
    High profit margins indicate strong pricing power and cost control; low margins may signal competitive pressure or high costs.
    """
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
    """
    Operating Margin: Shows the proportion of revenue left after paying for variable production costs (wages, raw materials), but before paying interest or tax.
    High operating margins suggest efficient operations and a strong business model; declining margins may indicate rising costs or pricing pressure.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    try:
        financials = stock.quarterly_financials
        if financials.empty:
            return float('nan')
        operating_income = None
        if 'Operating Income' in financials.index:
            operating_income = financials.loc['Operating Income'].iloc[0]
        elif 'EBIT' in financials.index:
            operating_income = financials.loc['EBIT'].iloc[0]
        revenue = financials.loc['Total Revenue'].iloc[0]
        if operating_income is not None and revenue != 0:
            if not pd.isna(operating_income) and not pd.isna(revenue):
                return float(operating_income / revenue)
    except:
        pass
    return float('nan')

def roe_return_on_equity(ticker_or_obj) -> float:
    """
    Return on Equity (ROE): Indicates how effectively management is using shareholders' equity to generate profits.
    High ROE (>15%) is a hallmark of quality businesses; low or volatile ROE may signal poor management or a risky business model.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    roe = info.get('returnOnEquity')
    if roe is not None and not pd.isna(roe):
        try:
            return float(roe)
        except:
            pass
    try:
        financials = stock.quarterly_financials
        balance_sheet = stock.balance_sheet
        if financials.empty or balance_sheet.empty:
            return float('nan')
        net_income = financials.loc['Net Income'].iloc[0]
        equity = balance_sheet.loc['Total Stockholder Equity'].iloc[0]
        if equity != 0 and not pd.isna(net_income) and not pd.isna(equity):
            return float(net_income / equity)
    except:
        pass
    return float('nan')

def roa_return_on_assets(ticker_or_obj) -> float:
    """
    Return on Assets (ROA): Measures how efficiently a company uses its assets to generate net income.
    High ROA means the company is generating more profit per dollar of assets; low ROA may indicate asset-heavy or inefficient operations.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    roa = info.get('returnOnAssets')
    if roa is not None and not pd.isna(roa):
        try:
            return float(roa)
        except:
            pass
    try:
        financials = stock.quarterly_financials
        balance_sheet = stock.balance_sheet
        if financials.empty or balance_sheet.empty:
            return float('nan')
        net_income = financials.loc['Net Income'].iloc[0]
        total_assets = balance_sheet.loc['Total Assets'].iloc[0]
        if total_assets != 0 and not pd.isna(net_income) and not pd.isna(total_assets):
            return float(net_income / total_assets)
    except:
        pass
    return float('nan')

def revenue_growth(ticker_or_obj, periods: int = 4) -> float:
    """
    Revenue Growth: Shows the rate at which a company's sales are increasing (or decreasing) over time.
    Consistent, strong revenue growth is a sign of a healthy, expanding business; negative or volatile growth can be a red flag.
    """
    stock = _get_ticker(ticker_or_obj)
    try:
        financials = stock.quarterly_financials
        if financials.empty or len(financials.columns) < periods:
            return float('nan')
        current_revenue = financials.loc['Total Revenue'].iloc[0]
        past_revenue = financials.loc['Total Revenue'].iloc[periods - 1]
        if past_revenue != 0 and not pd.isna(current_revenue) and not pd.isna(past_revenue):
            return float((current_revenue - past_revenue) / past_revenue)
    except:
        pass
    return float('nan')

def earnings_growth(ticker_or_obj, periods: int = 4) -> float:
    """
    Earnings Growth: Measures the rate at which a company's net income is growing.
    Sustained earnings growth is a key driver of long-term stock performance; negative or inconsistent growth may indicate business challenges.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    try:
        financials = stock.quarterly_financials
        if not financials.empty and len(financials.columns) >= periods:
            current_earnings = financials.loc['Net Income'].iloc[0]
            past_earnings = financials.loc['Net Income'].iloc[periods - 1]
            if past_earnings != 0 and not pd.isna(current_earnings) and not pd.isna(past_earnings):
                return float((current_earnings - past_earnings) / past_earnings)
    except:
        pass
    return float('nan')

def eps_growth(ticker_or_obj) -> float:
    """
    EPS Growth: Year-over-year growth in earnings per share.
    Indicates how quickly a company is increasing the profit allocated to each share of stock.
    High EPS growth is attractive to investors; negative or flat EPS growth may signal trouble.
    """
    stock = _get_ticker(ticker_or_obj)
    eps_this_year = stock.info.get('trailingEps')
    eps_last_year = stock.info.get('forwardEps')
    if eps_this_year in (None, 0) or eps_last_year in (None, 0):
        return float('nan')
    return ((eps_last_year - eps_this_year) / abs(eps_this_year)) * 100
