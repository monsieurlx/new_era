"""
Multi-Source Financial Screener
Supports: yfinance, Alpha Vantage, EODHD, Financial Modeling Prep, Perplexity
"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
import sys

from finance_assistant.providers.models import FinancialMetrics
from finance_assistant.providers.base_provider import DataProvider
from finance_assistant.providers.yfinance.yfinance_provider import YFinanceProvider
from finance_assistant.providers.alpha_vantage.fundamental import AlphaVantageProvider
from finance_assistant.providers.eodhd.fundamental import EODHDProvider
from finance_assistant.providers.fmp.fundamental import FMPProvider
from finance_assistant.providers.perplexity.analysis import PerplexityAnalysisProvider
load_dotenv()


# ============================================================================
# MULTI-SOURCE SCREENER
# ============================================================================

class MultiSourceScreener:
    """
    Intelligent screener that combines multiple data sources
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize with configuration
        
        Args:
            config: Dict with provider preferences and API keys
                {
                    "preferred_provider": "yfinance",  # Primary data source
                    "fallback_providers": ["alpha_vantage", "fmp"],
                    "enable_perplexity": True,
                    "api_keys": {
                        "alpha_vantage": "YOUR_KEY",
                        "eodhd": "YOUR_KEY",
                        "fmp": "YOUR_KEY",
                        "perplexity": "YOUR_KEY"
                    }
                }
        """
        self.config = config or {}
        
        # Initialize providers
        self.providers = {
            "yfinance": YFinanceProvider(),
            "alpha_vantage": AlphaVantageProvider(self.config.get("api_keys", {}).get("alpha_vantage")),
            "eodhd": EODHDProvider(self.config.get("api_keys", {}).get("eodhd")),
            "fmp": FMPProvider(self.config.get("api_keys", {}).get("fmp")),
        }

        # Initialize Perplexity
        self.perplexity = PerplexityAnalysisProvider(
            self.config.get("api_keys", {}).get("perplexity")
        )
        
        # Set provider priority
        self.provider_priority = self._build_provider_priority()
    
    def _build_provider_priority(self) -> List[str]:
        """Build provider priority list"""
        preferred = self.config.get("preferred_provider", "yfinance")
        fallbacks = self.config.get("fallback_providers", ["alpha_vantage", "fmp", "eodhd"])
        
        priority = [preferred] + [p for p in fallbacks if p != preferred]
        
        # Filter to only available providers
        return [p for p in priority if self.providers[p].is_available()]
    
    def get_financial_data(self, ticker: str, provider: Optional[str] = None) -> FinancialMetrics:
        """
        Get financial data using specified or fallback providers
        
        Args:
            ticker: Stock ticker symbol
            provider: Specific provider to use (optional)
        
        Returns:
            FinancialMetrics object
        """
        if provider:
            # Use specific provider
            if provider in self.providers and self.providers[provider].is_available():
                return self.providers[provider].get_metrics(ticker)
            else:
                print(f"⚠️  Provider '{provider}' not available, using fallback")
        
        # Try providers in priority order
        for provider_name in self.provider_priority:
            try:
                print(f"📡 Fetching data from {provider_name}...")
                metrics = self.providers[provider_name].get_metrics(ticker)
                
                if metrics.company_name != "N/A":
                    print(f"✅ Successfully fetched from {provider_name}")
                    return metrics
                    
            except Exception as e:
                print(f"❌ {provider_name} failed: {e}")
                continue
        
        print("❌ All providers failed")
        return FinancialMetrics(ticker=ticker)
    
    def generate_report(self, ticker: str, provider: Optional[str] = None) -> str:
        """
        Generate comprehensive financial report
        
        Args:
            ticker: Stock ticker
            provider: Optional specific provider to use
        """
        print(f"\n{'='*80}")
        print(f"MULTI-SOURCE FINANCIAL SCREENER: {ticker.upper()}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # Get financial metrics
        metrics = self.get_financial_data(ticker, provider)
        
        # Display data source
        print(f"📊 Data Source: {metrics.data_source}")
        print(f"🕒 Fetch Time: {metrics.fetch_timestamp}\n")
        
        # Company Overview
        print("## 1. COMPANY OVERVIEW")
        print(f"Company: {metrics.company_name}")
        print(f"Sector: {metrics.sector}")
        print(f"Industry: {metrics.industry}")
        print(f"Market Cap: ${metrics.market_cap:,.0f}" if metrics.market_cap else "Market Cap: N/A")
        
        # Price Information
        print("\n## 2. PRICE INFORMATION")
        print(f"Current Price: ${metrics.current_price:.2f}" if metrics.current_price else "Current Price: N/A")
        print(f"52-Week High: ${metrics.week_52_high:.2f}" if metrics.week_52_high else "52-Week High: N/A")
        print(f"52-Week Low: ${metrics.week_52_low:.2f}" if metrics.week_52_low else "52-Week Low: N/A")
        print(f"50-Day SMA: ${metrics.sma_50:.2f}" if metrics.sma_50 else "50-Day SMA: N/A")
        print(f"200-Day SMA: ${metrics.sma_200:.2f}" if metrics.sma_200 else "200-Day SMA: N/A")
        
        # Valuation Metrics
        print("\n## 3. VALUATION METRICS")
        print(f"P/E Ratio: {metrics.pe_ratio:.2f}" if metrics.pe_ratio else "P/E Ratio: N/A")
        print(f"Forward P/E: {metrics.forward_pe:.2f}" if metrics.forward_pe else "Forward P/E: N/A")
        print(f"PEG Ratio: {metrics.peg_ratio:.2f}" if metrics.peg_ratio else "PEG Ratio: N/A")
        print(f"Price-to-Book: {metrics.price_to_book:.2f}" if metrics.price_to_book else "Price-to-Book: N/A")
        print(f"Price-to-Sales: {metrics.price_to_sales:.2f}" if metrics.price_to_sales else "Price-to-Sales: N/A")
        print(f"EPS: ${metrics.eps:.2f}" if metrics.eps else "EPS: N/A")
        
        # Profitability
        print("\n## 4. PROFITABILITY METRICS")
        print(f"Profit Margin: {metrics.profit_margin*100:.2f}%" if metrics.profit_margin else "Profit Margin: N/A")
        print(f"Operating Margin: {metrics.operating_margin*100:.2f}%" if metrics.operating_margin else "Operating Margin: N/A")
        print(f"ROE: {metrics.roe*100:.2f}%" if metrics.roe else "ROE: N/A")
        print(f"ROA: {metrics.roa*100:.2f}%" if metrics.roa else "ROA: N/A")
        
        # Growth
        print("\n## 5. GROWTH METRICS")
        print(f"Revenue Growth: {metrics.revenue_growth*100:.2f}%" if metrics.revenue_growth else "Revenue Growth: N/A")
        print(f"Earnings Growth: {metrics.earnings_growth*100:.2f}%" if metrics.earnings_growth else "Earnings Growth: N/A")
        
        # Health
        print("\n## 6. FINANCIAL HEALTH")
        print(f"Debt-to-Equity: {metrics.debt_to_equity:.2f}" if metrics.debt_to_equity else "Debt-to-Equity: N/A")
        print(f"Current Ratio: {metrics.current_ratio:.2f}" if metrics.current_ratio else "Current Ratio: N/A")
        print(f"Quick Ratio: {metrics.quick_ratio:.2f}" if metrics.quick_ratio else "Quick Ratio: N/A")
        
        # Perplexity Analysis
        if self.config.get("enable_perplexity", True) and self.perplexity.is_available():
            print("\n## 7. NEWS & SENTIMENT ANALYSIS")
            news = self.perplexity.get_news_analysis(ticker)
            print(news)
        
        print(f"\n{'='*80}\n")
        
        return "Report completed"
    
    def compare_providers(self, ticker: str) -> Dict[str, FinancialMetrics]:
        """
        Fetch data from all available providers for comparison
        
        Args:
            ticker: Stock ticker
            
        Returns:
            Dict mapping provider names to their metrics
        """
        results = {}
        
        for provider_name, provider in self.providers.items():
            if provider.is_available():
                print(f"Fetching from {provider_name}...")
                results[provider_name] = provider.get_metrics(ticker)
        
        return results


# ============================================================================
# CONFIGURATION EXAMPLES
# ============================================================================

def screener_query(ticker: str, config: Optional[Dict] = None):
    """
    Main function to run financial screener
    
    Args:
        ticker: Stock ticker symbol
        config: Optional configuration dict
    """
    screener = MultiSourceScreener(config)
    screener.generate_report(ticker)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    
    # Example 1: Use yfinance only (default, free)
    print("\n### EXAMPLE 1: YFinance Only ###")
    screener_query("GOOGL")
    
    # Example 2: Custom configuration with API keys
    # print("\n### EXAMPLE 2: Custom Configuration ###")
    # custom_config = {
    #     "preferred_provider": "fmp",  # Use FMP as primary
    #     "fallback_providers": ["yfinance"], #, "alpha_vantage", "eodhd"
    #     "enable_perplexity": True,
    #     "api_keys": {
    #         "alpha_vantage": os.getenv("ALPHA_VANTAGE_API_KEY"),
    #         "eodhd": os.getenv("EODHD_API_KEY"),
    #         "fmp": os.getenv("FMP_API_KEY"),
    #         "perplexity": os.getenv("PERPLEXITY_API_KEY"),
    #     }
    # }
    # screener_query("AAPL", custom_config)
    
    # Example 3: Compare data from all providers
    # print("\n### EXAMPLE 3: Compare All Providers ###")
    # screener = MultiSourceScreener(custom_config)
    # comparison = screener.compare_providers("MSFT")
    
    # # Print P/E ratios from different sources
    # print("\nP/E Ratio Comparison:")
    # for provider_name, metrics in comparison.items():
    #     print(f"{provider_name:25} P/E: {metrics.pe_ratio:.2f}" if metrics.pe_ratio else f"{provider_name:25} P/E: N/A")
