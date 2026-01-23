import yfinance as yf
from colorama import Fore
from fastmcp import FastMCP

mcp = FastMCP("finance-assistant")

@mcp.tool()
def stock_price(ticker: str) -> str:
    """Get the current stock price for a given ticker symbol."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1mo")
    last_month_close = hist['Close']
    return Fore.YELLOW + f"{ticker}'s closing prices for the last month:\n{last_month_close}"


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
    # mcp.run(transport="stdio")