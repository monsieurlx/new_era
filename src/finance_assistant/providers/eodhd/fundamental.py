from ..models import FinancialMetrics
from ..base_provider import DataProvider
from datetime import datetime
import os
import requests

class EODHDProvider(DataProvider):
    """EODHD - Free tier: 20 API calls/day"""
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("EODHD_API_KEY")
        self.base_url = "https://eodhd.com/api"
    @property
    def name(self) -> str:
        return "EODHD"
    def is_available(self) -> bool:
        return self.api_key is not None
    def get_metrics(self, ticker: str) -> FinancialMetrics:
        if not self.is_available():
            return FinancialMetrics(data_source=self.name)
        try:
            fundamentals_url = f"{self.base_url}/fundamentals/{ticker}.US"
            params = {"api_token": self.api_key, "fmt": "json"}
            response = requests.get(fundamentals_url, params=params)
            data = response.json()
            general = data.get('General', {})
            highlights = data.get('Highlights', {})
            valuation = data.get('Valuation', {})
            technicals = data.get('Technicals', {})
            return FinancialMetrics(
                company_name=general.get('Name', 'N/A'),
                sector=general.get('Sector', 'N/A'),
                industry=general.get('Industry', 'N/A'),
                market_cap=highlights.get('MarketCapitalization', 0),
                pe_ratio=highlights.get('PERatio', 0),
                peg_ratio=highlights.get('PEGRatio', 0),
                price_to_book=valuation.get('PriceBookMRQ', 0),
                price_to_sales=valuation.get('PriceSalesTTM', 0),
                eps=highlights.get('EarningsShare', 0),
                profit_margin=highlights.get('ProfitMargin', 0),
                roe=highlights.get('ReturnOnEquityTTM', 0),
                roa=highlights.get('ReturnOnAssetsTTM', 0),
                revenue_growth=highlights.get('RevenuePerShareTTM', 0),
                dividend_yield=highlights.get('DividendYield', 0),
                beta=technicals.get('Beta', 0),
                week_52_high=technicals.get('52WeekHigh', 0),
                week_52_low=technicals.get('52WeekLow', 0),
                sma_50=technicals.get('50DayMA', 0),
                sma_200=technicals.get('200DayMA', 0),
                data_source=self.name,
                fetch_timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            print(f"❌ EODHD error: {e}")
            return FinancialMetrics(data_source=self.name)
