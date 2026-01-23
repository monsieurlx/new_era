import yfinance as yf
from colorama import Fore



apple = yf.Ticker("AAPL")

hist = apple.history(period="1mo")

last_month_close = hist['Close']
print(Fore.YELLOW + "Apple's closing prices for the last month:")
print(last_month_close)