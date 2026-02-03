from typing import Optional
import pandas as pd

class MacroDataProviderInterface:
    """
    Interface for macroeconomic data providers.
    Implementations should provide these methods for macro analytics modules.
    """
    def get_macro_series(self, name: str, period: str = '5y') -> Optional[pd.Series]:
        """Return a time series for a macroeconomic indicator by name (e.g., 'CPIAUCSL', 'UNRATE', 'DX-Y.NYB')."""
        raise NotImplementedError
