from dataclasses import dataclass

@dataclass
class FinancialMetrics:
    """Standardized financial metrics structure"""
    company_name: str = "N/A"
    sector: str = "N/A"
    industry: str = "N/A"
    market_cap: float = 0
    current_price: float = 0
    week_52_high: float = 0
    week_52_low: float = 0
    sma_50: float = 0
    sma_200: float = 0
    pe_ratio: float = 0
    forward_pe: float = 0
    peg_ratio: float = 0
    price_to_book: float = 0
    price_to_sales: float = 0
    eps: float = 0
    profit_margin: float = 0
    operating_margin: float = 0
    roe: float = 0
    roa: float = 0
    revenue_growth: float = 0
    earnings_growth: float = 0
    debt_to_equity: float = 0
    current_ratio: float = 0
    quick_ratio: float = 0
    beta: float = 0
    dividend_yield: float = 0
    analyst_rating: str = "N/A"
    data_source: str = "Unknown"
    fetch_timestamp: str = ""
