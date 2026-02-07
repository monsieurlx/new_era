import os
from perplexity import Perplexity


def screener_query(ticker: str):
    """
    Financial screener using Perplexity AI API
    
    Args:
        ticker (str): Stock ticker symbol (e.g., 'GOOGL', 'AAPL')
    """
    
    # Initialize Perplexity client with API key
    client = Perplexity(
        api_key=os.environ.get("PERPLEXITY_API_KEY")
    )
    
    # Construct a detailed financial analysis prompt
    prompt = f"""
Perform a comprehensive financial analysis for ticker {ticker} as of February 2026:

## 1. Company Overview
- Main index membership (S&P 500, NASDAQ 100, Dow Jones, Russell 2000, etc.)
- Sector and industry classification
- Market capitalization

## 2. Price Information
- Current stock price
- 52-week high and low
- Year-to-date performance
- Key moving averages (50-day, 200-day SMA)

## 3. Valuation Metrics
- P/E Ratio (Price-to-Earnings) and interpretation
- Forward P/E
- PEG Ratio (Price/Earnings to Growth)
- Price-to-Book (P/B) ratio
- Price-to-Sales (P/S) ratio
- EPS (Earnings Per Share) - current and historical

## 4. Profitability Metrics
- Profit margin (net margin)
- Operating margin
- ROE (Return on Equity)
- ROA (Return on Assets)
- EBITDA margin

## 5. Growth Metrics
- Revenue growth (YoY and QoQ)
- Earnings growth (YoY and QoQ)
- EPS growth rate

## 6. Financial Health
- Debt-to-Equity ratio
- Current ratio
- Quick ratio
- Debt-to-Assets ratio
- Interest coverage ratio

## 7. Recent News & Events
- Top 3-5 recent news headlines impacting the stock

## 8. Peer Comparison
- List 3-5 main competitors
- Compare key metrics: P/E, market cap, revenue growth, profit margin

## 9. Sector Averages
- How does {ticker} compare to sector averages for P/E, ROE, and debt ratios?

## 10. Summary Analysis
- Fundamental score (1-10)
- Key strengths (3-5 points)
- Key weaknesses/risks (3-5 points)
- Investment thesis summary

Format the response in a clear, structured way with headers and bullet points.
"""
    
    try:
        # Make API call using chat completions
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional financial analyst providing detailed stock analysis and screener reports."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="sonar",  # Use 'sonar' model for current web-connected results
        )
        
        # Extract and print the response
        analysis = response.choices[0].message.content
        
        print("=" * 80)
        print(f"FINANCIAL SCREENER REPORT: {ticker.upper()}")
        print("=" * 80)
        print(analysis)
        print("=" * 80)
        
        return analysis
        
    except Exception as e:
        print(f"Error performing analysis for {ticker}: {str(e)}")
        return None


def batch_screener(tickers: list[str]):
    """
    Screen multiple tickers and compare them
    
    Args:
        tickers (list): List of ticker symbols
    """
    results = {}
    
    for ticker in tickers:
        print(f"\n\nAnalyzing {ticker}...\n")
        results[ticker] = screener_query(ticker)
    
    return results


if __name__ == "__main__":
    # Single stock analysis
    screener_query("GOOGL")
    
    # Uncomment for batch analysis
    # batch_screener(["GOOGL", "MSFT", "AAPL"])