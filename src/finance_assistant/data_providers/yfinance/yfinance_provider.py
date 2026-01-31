import yfinance as yf
from typing import List, Dict, Any
from finance_assistant.data_providers.interface import DataProviderInterface
from finance_assistant.data_providers.yfinance.sector import get_sector_companies as yfin_get_sector_companies
from finance_assistant.data_providers.yfinance.company import get_company_metrics as yfin_get_company_metrics, get_company_info as yfin_get_company_info, get_sector_name as yfin_get_sector_name

class YFinanceProvider(DataProviderInterface):
    def get_sector_companies(self, sector_name: str, n: int = 20) -> List[str]:
        return yfin_get_sector_companies(sector_name, n)

    def get_company_metrics(self, ticker: str) -> Dict[str, Any]:
        return yfin_get_company_metrics(ticker)

    def get_sector_name(self, ticker: str) -> str:
        return yfin_get_sector_name(ticker)

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        return yfin_get_company_info(ticker)

    # INDUSTRY SUPPORT: Inherit default logic from interface (uses get_company_info)
    # No need to override unless you want a faster implementation
