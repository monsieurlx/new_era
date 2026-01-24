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


@mcp.tool()
def stock_price(ticker: str) -> str:
    last_month_close = yf_stock_price(ticker)
    return Fore.YELLOW + f"{ticker}'s closing prices for the last month:\n{last_month_close}"


@mcp.tool()
def current_price(ticker: str) -> str:
    price = yf_current_price(ticker)
    return Fore.GREEN + f"Current price of {ticker}: {price}"


@mcp.tool()
def company_info(ticker: str) -> str:
    info = yf_company_info(ticker)
    return (f"{ticker} - {info['name']}\nSector: {info['sector']}\nSummary: {info['summary']}")


@mcp.tool()
def historical_data(ticker: str, period: str = "6mo") -> str:
    hist = yf_historical_data(ticker, period)
    return f"{ticker} historical data for {period}:\n{hist}"


@mcp.tool()
def simple_moving_average(ticker: str, window: int = 20) -> str:
    sma = yf_simple_moving_average(ticker, window)
    return f"{ticker} {window}-day SMA:\n{sma}"


@mcp.tool()
def rsi(ticker: str, period: int = 14) -> str:
    rsi_series = yf_rsi(ticker, period)
    return f"{ticker} {period}-day RSI:\n{rsi_series}"


@mcp.tool()
def news_headlines(ticker: str) -> str:
    news = yf_news_headlines(ticker)
    if not news:
        return f"No news found for {ticker}."
    headlines = [f"- {item['title']} ({item['publisher']})" for item in news]
    return f"Recent news for {ticker}:\n" + "\n".join(headlines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
    # mcp.run(transport="http", host="127.0.0.1", port=8000)
