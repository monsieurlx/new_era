import yfinance as yf
from typing import List

def get_sector_companies(sector_name: str, n: int = 20) -> List[str]:
    try:
        sector_name = sector_name.lower() if sector_name else sector_name
        sector = yf.Sector(sector_name)
        df = sector.top_companies
        if df is not None and not df.empty:
            return df.head(n).index.tolist()
        return []
    except Exception:
        return []
