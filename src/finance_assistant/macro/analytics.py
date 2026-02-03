"""
Macro Analytics: Key Economic Indices and Indicators
- Misery Index
- US Dollar Index (DXY)
- CPI, Unemployment Rate, GDP Growth, etc.
"""

import yfinance as yf
import pandas as pd
from typing import Optional

# --- CPI (Consumer Price Index) ---
def get_cpi(period: str = '5y') -> Optional[pd.Series]:
    try:
        cpi = yf.download('CPIAUCSL', period=period)['Close']
        cpi.name = 'CPI'
        return cpi.dropna()
    except Exception as e:
        print(f"Error fetching CPI: {e}")
        return None

# --- Unemployment Rate ---
def get_unemployment_rate(period: str = '5y') -> Optional[pd.Series]:
    try:
        unemp = yf.download('UNRATE', period=period)['Close']
        unemp.name = 'Unemployment Rate'
        return unemp.dropna()
    except Exception as e:
        print(f"Error fetching Unemployment Rate: {e}")
        return None

# --- Misery Index (Inflation + Unemployment) ---
def get_misery_index(period: str = '5y') -> Optional[pd.Series]:
    """
    Returns the Misery Index (CPI YoY + Unemployment Rate) as a time series.
    """
    try:
        cpi = get_cpi(period)
        unemp = get_unemployment_rate(period)
        if cpi is None or unemp is None:
            return None
        cpi_yoy = cpi.pct_change(periods=12) * 100
        misery = cpi_yoy.add(unemp, fill_value=0)
        misery.name = 'Misery Index'
        return misery.dropna()
    except Exception as e:
        print(f"Error fetching Misery Index: {e}")
        return None

# --- US Dollar Index (DXY) ---
def get_dollar_index(period: str = '5y') -> Optional[pd.Series]:
    """
    Returns the US Dollar Index (DXY) as a time series.
    """
    try:
        dxy = yf.download('DX-Y.NYB', period=period)['Close']
        dxy.name = 'DXY'
        return dxy.dropna()
    except Exception as e:
        print(f"Error fetching DXY: {e}")
        return None

# --- GDP Growth (YoY, US) ---
def get_gdp_growth(period: str = '10y') -> Optional[pd.Series]:
    try:
        gdp = yf.download('GDP', period=period)['Close']
        gdp_growth = gdp.pct_change(periods=4) * 100  # Quarterly YoY
        gdp_growth.name = 'GDP Growth YoY (%)'
        return gdp_growth.dropna()
    except Exception as e:
        print(f"Error fetching GDP Growth: {e}")
        return None
