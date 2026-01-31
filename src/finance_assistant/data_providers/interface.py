from typing import List, Dict, Any
from finance_assistant.shared.utils import logger, safe_get

class DataProviderInterface:
    """
    Interface for financial data providers.
    Implementations should provide these methods for analytics modules.
    """
    # Provider-specific sector slugs (Yahoo/yfinance style)
    SECTORS = [
        'energy',
        'basic-materials',
        'industrials',
        'consumer-cyclical',
        'consumer-defensive',
        'healthcare',
        'financial-services',
        'technology',
        'communication-services',
        'utilities',
        'real-estate',
    ]

    def _get_ticker(ticker_or_obj):
        raise NotImplementedError
    def get_sector_companies(self, sector_name: str, n: int = 20) -> List[str]:
        """Return up to n tickers in the given sector (case-insensitive)."""
        sector_name = sector_name.lower() if sector_name else sector_name
        return sector_name


    def get_sector_name(self, ticker: str) -> str:
        """Return the sector for a given ticker (always lowercase)."""
        sector = self._get_sector_name_impl(ticker)
        return sector.lower() if sector else sector
    
    def get_sector_list(self) -> List[str]:
        """Return the provider's sector slugs."""
        return self.SECTORS

    # INDUSTRY SUPPORT
    def get_industry_list(self) -> List[str]:
        """Return all unique industries from all tickers."""
        industries = set()
        for t in self.get_all_tickers():
            info = self.get_company_info(t)
            industry = info.get('industry', None)
            if industry:
                industries.add(industry)
        return sorted(industries)

    def get_industry_companies(self, industry_name: str, n: int = 20) -> List[str]:
        """Return up to n tickers in the given industry."""
        tickers = []
        for t in self.get_all_tickers():
            info = self.get_company_info(t)
            if info.get('industry', None) == industry_name:
                tickers.append(t)
                if len(tickers) >= n:
                    break
        return tickers

    def get_industry_name(self, ticker: str) -> str:
        """Return the industry for a given ticker."""
        info = self.get_company_info(ticker)
        return info.get('industry', None)
