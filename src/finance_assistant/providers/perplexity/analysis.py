from ..models import FinancialMetrics
from datetime import datetime
import os
from perplexity import Perplexity

class PerplexityAnalysisProvider:
    """Qualitative analysis and news using Perplexity AI"""
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if self.api_key:
            self.client = Perplexity(api_key=self.api_key)
    def is_available(self) -> bool:
        return self.api_key is not None
    def get_news_analysis(self, ticker: str) -> str:
        if not self.is_available():
            return "Perplexity analysis unavailable (no API key)"
        try:
            prompt = f"""
Provide a concise analysis for {ticker} stock:
1. **Recent News** (last 30 days): 3-5 key headlines with dates
2. **Sentiment**: Bullish/Bearish/Neutral with reasoning
3. **Catalysts**: Upcoming events that could move the stock
4. **Analyst Actions**: Recent upgrades/downgrades
Keep it factual and under 250 words.
"""
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a financial analyst providing objective market updates."},
                    {"role": "user", "content": prompt}
                ],
                model="sonar",
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"News analysis error: {str(e)}"
    def get_peer_analysis(self, ticker: str, sector: str) -> str:
        if not self.is_available():
            return "Peer analysis unavailable"
        try:
            prompt = f"List the top 4-5 direct competitors of {ticker} in the {sector} sector. Just list ticker symbols and company names, one per line."
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="sonar",
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Peer analysis error: {str(e)}"
