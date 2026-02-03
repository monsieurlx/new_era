from finance_assistant.data_providers import yfinance
import pandas as pd
from typing import Optional
from .provider_interface import MacroDataProviderInterface

class YFinanceMacroProvider(MacroDataProviderInterface):
    def get_macro_series(self, name: str, period: str = '5y') -> Optional[pd.Series]:
        try:
            data = yfinance.yf.download(name, period=period)['Close']
            data.name = name
            return data.dropna()
        except Exception as e:
            print(f"Error fetching {name} from yfinance: {e}")
            return None
