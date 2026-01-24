import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import streamlit as st
import pandas as pd
from finance_assistant.yfinance_functions import (
    stock_price,
    current_price,
    company_info,
    historical_data,
    simple_moving_average,
    rsi,
    news_headlines,
)

st.title('Finance Assistant Dashboard')

# Sidebar for ticker selection
TICKER = st.sidebar.text_input('Ticker Symbol', 'AAPL')

# Sidebar options for overlays and parameters
show_sma = st.sidebar.checkbox('Show SMA', value=True)
sma_window = st.sidebar.number_input('SMA Window', min_value=2, max_value=200, value=20) if show_sma else 20
show_rsi = st.sidebar.checkbox('Show RSI', value=True)
rsi_period = st.sidebar.number_input('RSI Period', min_value=2, max_value=50, value=14) if show_rsi else 14

# Company Info
info = company_info(TICKER)
st.subheader(f"{TICKER} - {info['name']}")
st.write(f"Sector: {info['sector']}")
st.write(info['summary'])

period = "5y"
# Price, SMA, and RSI
price = stock_price(TICKER, period=period)
sma = simple_moving_average(TICKER, sma_window, period=period) if show_sma else None
rsi_series = rsi(TICKER, rsi_period, price_period=period) if show_rsi else None

plot_df = pd.DataFrame({'Close': price})
if show_sma:
    plot_df[f'SMA_{sma_window}'] = sma
if show_rsi:
    plot_df[f'RSI_{rsi_period}'] = rsi_series

st.line_chart(plot_df)

# News
news = news_headlines(TICKER)
if news:
    st.subheader('Recent News')
    for item in news:
        st.write(f"- {item['title']} ({item['publisher']})")
else:
    st.write('No news found.')
