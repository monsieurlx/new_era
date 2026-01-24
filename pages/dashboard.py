import sys
import os
import yfinance as yf

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
    pe_ratio,
    eps_growth,
    profit_margin,
    debt_to_equity,
)

st.title('Finance Assistant Stock Screener')

# Sidebar: Ticker input (comma-separated)
ticker_input = st.sidebar.text_area('Enter tickers (comma-separated)', 'AAPL, MSFT, GOOGL')
tickers = [t.strip().upper() for t in ticker_input.split(',') if t.strip()]
period = st.sidebar.selectbox('Price History Period', ['1mo', '3mo', '6mo', '1y', '5y', 'max'], index=3)
sma_window = st.sidebar.number_input('SMA Window', min_value=2, max_value=200, value=20)
rsi_period = st.sidebar.number_input('RSI Period', min_value=2, max_value=50, value=14)

# Table to collect results
results = []
for t in tickers:
    try:
        stock = yf.Ticker(t)
        price = current_price(stock)
        pe = pe_ratio(stock)
        epsg = eps_growth(stock)
        margin = profit_margin(stock)
        dte = debt_to_equity(stock)
        sma_val = simple_moving_average(stock, sma_window, period=period).iloc[-1] if not simple_moving_average(stock, sma_window, period=period).empty else float('nan')
        rsi_val = rsi(stock, rsi_period, price_period=period).iloc[-1] if not rsi(stock, rsi_period, price_period=period).empty else float('nan')
        results.append({
            'Ticker': t,
            'Price': price,
            'P/E': pe,
            'EPS Growth %': epsg,
            'Profit Margin %': margin,
            'Debt/Equity': dte,
            f'SMA{int(sma_window)}': sma_val,
            f'RSI{int(rsi_period)}': rsi_val,
        })
    except Exception as e:
        results.append({'Ticker': t, 'Error': str(e)})

if results:
    df = pd.DataFrame(results)
    st.dataframe(df)
    st.caption('Tip: Sort columns by clicking headers. Filter by typing in the table.')

    # Plot price, SMA, and RSI for the first ticker (if available)
    if len(tickers) > 0 and 'Error' not in df.columns:
        stock = yf.Ticker(tickers[0])
        price_series = stock_price(stock, period=period)
        sma_series = simple_moving_average(stock, sma_window, period=period)
        rsi_series = rsi(stock, rsi_period, price_period=period)
        chart_df = pd.DataFrame({'Close': price_series})
        chart_df[f'SMA{int(sma_window)}'] = sma_series
        chart_df[f'RSI{int(rsi_period)}'] = rsi_series
        st.line_chart(chart_df)
else:
    st.info('Enter tickers to screen.')
