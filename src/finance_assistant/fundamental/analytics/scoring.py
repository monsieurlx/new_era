from .data import _get_ticker
from .fundamentals import profit_margin, roe_return_on_equity, roa_return_on_assets, revenue_growth
from .valuation import pe_ratio, peg_ratio
from .health import debt_to_equity, current_ratio, debt_to_assets
import pandas as pd
import yfinance as yf

def fundamental_score(ticker_or_obj) -> dict:
    """
    Get comprehensive fundamental metrics for a stock.
    Returns a dictionary of key ratios and metrics for high-level screening.
    Each metric is a snapshot of a company's financial health, profitability, and valuation.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    
    # Helper function to safely get and convert values
    def safe_get(key, multiplier=1, default=None):
        val = info.get(key)
        if val is not None and val != float('nan'):
            try:
                return round(float(val) * multiplier, 2)
            except (ValueError, TypeError):
                return default
        return default
    
    return {
        'ticker': info.get('symbol', 'Unknown'),
        'profit_margin': safe_get('profitMargins', 100),
        'roe': safe_get('returnOnEquity', 100),
        'roa': safe_get('returnOnAssets', 100),
        'pe_ratio': safe_get('trailingPE', 1),
        'peg_ratio': safe_get('pegRatio', 1),
        'debt_to_equity': safe_get('debtToEquity', 1),
        'current_ratio': safe_get('currentRatio', 1),
        'debt_to_assets': _calculate_debt_to_assets(info),
        'revenue_growth': safe_get('revenueGrowth', 100),
    }

def _calculate_debt_to_assets(info) -> float:
    """
    Calculate debt to assets ratio.
    This ratio measures what proportion of a company's assets are financed by debt.
    High values (>0.5) may indicate higher financial risk, while low values suggest a more conservative balance sheet.
    """
    total_debt = info.get('totalDebt')
    total_assets = info.get('totalAssets')
    
    if total_debt is not None and total_assets is not None and total_assets != 0:
        try:
            return round(float(total_debt) / float(total_assets), 2)
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    return None

# Advanced/extra metrics

def return_on_ebit(ticker_or_obj) -> float:
    """
    Calculate return on EBIT (EBIT margin).
    EBIT (Earnings Before Interest and Taxes) is a measure of operational profitability, showing how much profit a company makes from its core business before financing and tax costs.
    A high EBIT margin indicates strong operational efficiency; a low margin may signal cost issues or weak pricing power.
    """
    stock = _get_ticker(ticker_or_obj)
    
    # Try using financials data
    try:
        financials = stock.financials
        if financials is not None and not financials.empty:
            # Look for EBIT or Operating Income
            ebit = None
            revenue = None
            
            # Check for various EBIT-related fields
            for label in ['EBIT', 'Operating Income', 'Operating Revenue']:
                if label in financials.index:
                    ebit = financials.loc[label].iloc[0]
                    break
            
            # Get total revenue
            for label in ['Total Revenue', 'Revenue']:
                if label in financials.index:
                    revenue = financials.loc[label].iloc[0]
                    break
            
            if ebit is not None and revenue is not None and revenue != 0:
                return float(ebit) / float(revenue)
    except Exception:
        pass
    
    # Fallback to info
    info = stock.info
    operating_margins = info.get('operatingMargins')
    if operating_margins is not None:
        try:
            return float(operating_margins)
        except (ValueError, TypeError):
            pass
    
    return float('nan')

def return_on_capital(ticker_or_obj) -> float:
    """
    Calculate ROIC (Return on Invested Capital).
    ROIC measures how effectively a company uses all capital (debt and equity) to generate profits.
    High ROIC (>10-15%) is a sign of a quality business with a durable competitive advantage; low ROIC may indicate poor capital allocation or a commoditized business.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    
    # Try returnOnCapital or similar fields
    for field in ['returnOnCapital', 'returnOnInvestedCapital']:
        val = info.get(field)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    
    # Manual calculation: NOPAT / Invested Capital
    try:
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        
        if financials is not None and not financials.empty and balance_sheet is not None and not balance_sheet.empty:
            # Get Operating Income (proxy for NOPAT before tax adjustment)
            operating_income = None
            for label in ['Operating Income', 'EBIT']:
                if label in financials.index:
                    operating_income = financials.loc[label].iloc[0]
                    break
            
            # Get Invested Capital = Total Assets - Current Liabilities
            total_assets = None
            current_liabilities = None
            
            for label in ['Total Assets']:
                if label in balance_sheet.index:
                    total_assets = balance_sheet.loc[label].iloc[0]
                    break
            
            for label in ['Current Liabilities']:
                if label in balance_sheet.index:
                    current_liabilities = balance_sheet.loc[label].iloc[0]
                    break
            
            if operating_income and total_assets and current_liabilities:
                invested_capital = total_assets - current_liabilities
                if invested_capital != 0:
                    return float(operating_income) / float(invested_capital)
    except Exception:
        pass
    
    return float('nan')

def roic_greenblatt(ticker_or_obj) -> float:
    """
    Calculate Greenblatt's ROIC (EBIT / (Net Working Capital + Net Fixed Assets)).
    This version of ROIC, popularized by Joel Greenblatt, focuses on tangible capital employed in the business.
    High values suggest efficient use of working capital and fixed assets; low or negative values may indicate capital inefficiency or business stress.
    """
    stock = _get_ticker(ticker_or_obj)
    
    try:
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        
        if financials is None or financials.empty or balance_sheet is None or balance_sheet.empty:
            return float('nan')
        
        # Get EBIT
        ebit = None
        for label in ['EBIT', 'Operating Income']:
            if label in financials.index:
                ebit = financials.loc[label].iloc[0]
                break
        
        if ebit is None:
            return float('nan')
        
        # Get components for tangible capital
        current_assets = None
        current_liabilities = None
        net_ppe = None
        
        for label in ['Current Assets', 'Total Current Assets']:
            if label in balance_sheet.index:
                current_assets = balance_sheet.loc[label].iloc[0]
                break
        
        for label in ['Current Liabilities', 'Total Current Liabilities']:
            if label in balance_sheet.index:
                current_liabilities = balance_sheet.loc[label].iloc[0]
                break
        
        for label in ['Net PPE', 'Property Plant Equipment Net', 'Net Property Plant And Equipment']:
            if label in balance_sheet.index:
                net_ppe = balance_sheet.loc[label].iloc[0]
                break
        
        if current_assets and current_liabilities and net_ppe:
            net_working_capital = current_assets - current_liabilities
            tangible_capital = net_working_capital + net_ppe
            
            if tangible_capital != 0:
                return float(ebit) / float(tangible_capital)
    except Exception:
        pass
    
    return float('nan')

def magic_formula_score(ticker_or_obj) -> dict:
    """
    Calculate Magic Formula components: Earnings Yield (EBIT/EV) and ROIC.
    - EBIT/EV (Earnings Yield) measures how much operating profit you get for each dollar invested in the business (enterprise value).
      High values indicate a potentially undervalued stock; low or negative values may signal overvaluation or business trouble.
    - ROIC (see above) measures capital efficiency.
    The Magic Formula ranks stocks by both metrics to find high-quality, attractively priced companies.
    """
    stock = _get_ticker(ticker_or_obj)
    info = stock.info
    
    # Calculate EBIT/EV (Earnings Yield)
    ebit_ev = float('nan')
    ebit = info.get('ebit')
    enterprise_value = info.get('enterpriseValue')
    
    if ebit is not None and enterprise_value is not None and enterprise_value != 0:
        try:
            ebit_ev = float(ebit) / float(enterprise_value)
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    
    # If not in info, try financials
    if pd.isna(ebit_ev):
        try:
            financials = stock.financials
            if financials is not None and not financials.empty:
                for label in ['EBIT', 'Operating Income']:
                    if label in financials.index:
                        ebit = financials.loc[label].iloc[0]
                        break
                
                if ebit and enterprise_value and enterprise_value != 0:
                    ebit_ev = float(ebit) / float(enterprise_value)
        except Exception:
            pass
    
    # Use Greenblatt's ROIC calculation
    roc = roic_greenblatt(ticker_or_obj)
    
    return {
        'ebit_ev': ebit_ev if not pd.isna(ebit_ev) else float('nan'),
        'roc': roc
    }

def get_global_index_tickers():
    """
    Robustly aggregate tickers from major world indices (S&P 500, FTSE 100, DAX, CAC 40, Nikkei 225, ASX 200).
    Tries yfinance index constituents, falls back to static lists if needed.
    Returns a list of tickers (strings).
    """
    tickers = set()
    # Try yfinance index constituents
    index_symbols = {
        'S&P 500': '^GSPC',
        'FTSE 100': '^FTSE',
        'DAX': '^GDAXI',
        'CAC 40': '^FCHI',
        'Nikkei 225': '^N225',
        'ASX 200': '^AXJO',
    }
    for name, symbol in index_symbols.items():
        try:
            idx = yf.Ticker(symbol)
            # yfinance may expose constituents via .constituents or .tickers
            if hasattr(idx, 'constituents') and idx.constituents:
                tickers.update(idx.constituents)
            elif hasattr(idx, 'tickers') and idx.tickers:
                tickers.update(idx.tickers)
        except Exception:
            pass
    return list(tickers)

def get_sector_peers_api(target_ticker, max_peers=20):
    """
    Get a list of peer tickers in the same sector and country as the target_ticker using yfinance.
    Aggregates tickers from major world indices for a global universe.
    """
    stock = yf.Ticker(target_ticker)
    sector = stock.info.get('sector')
    country = stock.info.get('country')
    if not sector:
        return []
    tickers = get_global_index_tickers()
    peers = []
    for t in tickers:
        if t == target_ticker:
            continue
        try:
            peer_info = yf.Ticker(t).info
            if peer_info.get('sector') == sector and peer_info.get('country') == country:
                peers.append(t)
            if len(peers) >= max_peers:
                break
        except Exception:
            continue
    return peers

def compute_sector_averages_api(target_ticker, metrics_func, max_peers=20):
    """
    Compute the average of each metric for all peers in the same sector and country as the target_ticker using yfinance.
    Returns a dict of sector averages for each metric.
    """
    peers = get_sector_peers_api(target_ticker, max_peers=max_peers)
    results = []
    for peer in peers:
        try:
            results.append(metrics_func(peer))
        except Exception:
            continue
    if not results:
        return {}
    import numpy as np
    keys = results[0].keys()
    avg = {k: round(np.nanmean([r[k] for r in results if r[k] is not None]), 3) for k in keys}
    return avg