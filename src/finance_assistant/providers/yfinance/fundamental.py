# yfinance fundamental data provider
from ..models import FinancialMetrics
from ..base_provider import DataProvider
import yfinance as yf
from datetime import datetime

class YFinanceFundamentalProvider(DataProvider):
    """Yahoo Finance fundamental metrics"""
    @property
    def name(self) -> str:
        return "yfinance (Yahoo Finance) - Fundamental"
    def is_available(self) -> bool:
        return True
    def get_metrics(self, ticker: str) -> FinancialMetrics:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return FinancialMetrics(
                company_name=info.get('longName', 'N/A'),
                sector=info.get('sector', 'N/A'),
                industry=info.get('industry', 'N/A'),
                market_cap=info.get('marketCap', 0),
                current_price=info.get('currentPrice', info.get('regularMarketPrice', 0)),
                week_52_high=info.get('fiftyTwoWeekHigh', 0),
                week_52_low=info.get('fiftyTwoWeekLow', 0),
                pe_ratio=info.get('trailingPE', 0),
                forward_pe=info.get('forwardPE', 0),
                peg_ratio=info.get('pegRatio', 0),
                price_to_book=info.get('priceToBook', 0),
                price_to_sales=info.get('priceToSalesTrailing12Months', 0),
                eps=info.get('trailingEps', 0),
                profit_margin=info.get('profitMargins', 0),
                operating_margin=info.get('operatingMargins', 0),
                roe=info.get('returnOnEquity', 0),
                roa=info.get('returnOnAssets', 0),
                revenue_growth=info.get('revenueGrowth', 0),
                earnings_growth=info.get('earningsGrowth', 0),
                debt_to_equity=info.get('debtToEquity', 0),
                current_ratio=info.get('currentRatio', 0),
                quick_ratio=info.get('quickRatio', 0),
                beta=info.get('beta', 0),
                dividend_yield=info.get('dividendYield', 0),
                analyst_rating=info.get('recommendationKey', 'N/A'),
                data_source=self.name,
                fetch_timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            print(f"❌ YFinance error: {e}")
            return FinancialMetrics(data_source=self.name)
