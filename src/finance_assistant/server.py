from colorama import Fore
from fastmcp import FastMCP
from .yfinance_functions import (
    stock_price as yf_stock_price,
    current_price as yf_current_price,
    company_info as yf_company_info,
    historical_data as yf_historical_data,
    simple_moving_average as yf_simple_moving_average,
    rsi as yf_rsi,
    news_headlines as yf_news_headlines,
)

mcp = FastMCP("finance-assistant")


if __name__ == "__main__":
    mcp.run(transport="stdio")
    # mcp.run(transport="http", host="127.0.0.1", port=8000)
