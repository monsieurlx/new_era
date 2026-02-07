from .models import FinancialMetrics
from .base_provider import DataProvider
from datetime import datetime
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.timeseries import TimeSeries
import os

class AlphaVantageProvider(DataProvider):
    """Alpha Vantage - Free tier: 25 requests/day"""
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if self.api_key:
            self.fd = FundamentalData(key=self.api_key, output_format='json')
            self.ts = TimeSeries(key=self.api_key, output_format='json')
    @property
    def name(self) -> str:
        return "Alpha Vantage"
    def is_available(self) -> bool:
        return self.api_key is not None
    def get_metrics(self, ticker: str) -> FinancialMetrics:
        if not self.is_available():
            return FinancialMetrics(data_source=self.name)
        try:
            overview, _ = self.fd.get_company_overview(ticker)
            metrics = FinancialMetrics(
                company_name=overview.get('Name', 'N/A'),
                sector=overview.get('Sector', 'N/A'),
                industry=overview.get('Industry', 'N/A'),
                market_cap=float(overview.get('MarketCapitalization', 0)),
                pe_ratio=float(overview.get('TrailingPE', 0)),
                forward_pe=float(overview.get('ForwardPE', 0)),
                peg_ratio=float(overview.get('PEGRatio', 0)),
                price_to_book=float(overview.get('PriceToBookRatio', 0)),
                price_to_sales=float(overview.get('PriceToSalesRatioTTM', 0)),
                eps=float(overview.get('EPS', 0)),
                profit_margin=float(overview.get('ProfitMargin', 0)),
                operating_margin=float(overview.get('OperatingMarginTTM', 0)),
                roe=float(overview.get('ReturnOnEquityTTM', 0)),
                roa=float(overview.get('ReturnOnAssetsTTM', 0)),
                revenue_growth=float(overview.get('QuarterlyRevenueGrowthYOY', 0)),
                earnings_growth=float(overview.get('QuarterlyEarningsGrowthYOY', 0)),
                beta=float(overview.get('Beta', 0)),
                dividend_yield=float(overview.get('DividendYield', 0)),
                analyst_rating=overview.get('AnalystTargetPrice', 'N/A'),
                data_source=self.name,
                fetch_timestamp=datetime.now().isoformat()
            )
            quote, _ = self.ts.get_quote_endpoint(ticker)
            metrics.current_price = float(quote.get('05. price', 0))
            return metrics
        except Exception as e:
            print(f"❌ Alpha Vantage error: {e}")
            return FinancialMetrics(data_source=self.name)
