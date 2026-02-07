from ..models import FinancialMetrics
from ..base_provider import DataProvider
from datetime import datetime
import os
import requests

class FMPProvider(DataProvider):
    """Financial Modeling Prep - Free tier: 250 requests/day"""
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self.base_url = "https://financialmodelingprep.com/api/v3"
    @property
    def name(self) -> str:
        return "Financial Modeling Prep"
    def is_available(self) -> bool:
        return self.api_key is not None
    def get_metrics(self, ticker: str) -> FinancialMetrics:
        if not self.is_available():
            return FinancialMetrics(data_source=self.name)
        try:
            profile_url = f"{self.base_url}/profile/{ticker}"
            params = {"apikey": self.api_key}
            response = requests.get(profile_url, params=params)
            data = response.json()[0] if response.json() else {}
            metrics_url = f"{self.base_url}/key-metrics-ttm/{ticker}"
            metrics_response = requests.get(metrics_url, params=params)
            metrics_data = metrics_response.json()[0] if metrics_response.json() else {}
            ratios_url = f"{self.base_url}/ratios-ttm/{ticker}"
            ratios_response = requests.get(ratios_url, params=params)
            ratios_data = ratios_response.json()[0] if ratios_response.json() else {}
            return FinancialMetrics(
                company_name=data.get('companyName', 'N/A'),
                sector=data.get('sector', 'N/A'),
                industry=data.get('industry', 'N/A'),
                market_cap=data.get('mktCap', 0),
                current_price=data.get('price', 0),
                pe_ratio=data.get('pe', 0),
                price_to_book=ratios_data.get('priceToBookRatio', 0),
                price_to_sales=ratios_data.get('priceToSalesRatio', 0),
                eps=metrics_data.get('netIncomePerShareTTM', 0),
                profit_margin=ratios_data.get('netProfitMarginTTM', 0),
                operating_margin=ratios_data.get('operatingProfitMarginTTM', 0),
                roe=ratios_data.get('returnOnEquityTTM', 0),
                roa=ratios_data.get('returnOnAssetsTTM', 0),
                revenue_growth=metrics_data.get('revenuePerShareTTM', 0),
                debt_to_equity=ratios_data.get('debtEquityRatioTTM', 0),
                current_ratio=ratios_data.get('currentRatioTTM', 0),
                beta=data.get('beta', 0),
                dividend_yield=data.get('lastDiv', 0),
                data_source=self.name,
                fetch_timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            print(f"❌ FMP error: {e}")
            return FinancialMetrics(data_source=self.name)
