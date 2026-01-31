import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from io import StringIO

def get_index_tickers(index):
    """
    Fetch tickers for a given major index using pandas.read_html and a user-agent header.
    Supported indices: 'sp500', 'nasdaq100', 'dowjones', 'ftse100', 'nikkei225', 'cac40', 'dax', 'asx200'
    Returns a list of tickers (with correct suffixes for non-US indices).
    """
    url_map = {
        'sp500': ('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', 'Symbol', 0, None),
        'nasdaq100': ('https://en.wikipedia.org/wiki/NASDAQ-100', 'Ticker', 4, None),
        'dowjones': ('https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average', 'Symbol', 1, None),
        'ftse100': ('https://en.wikipedia.org/wiki/FTSE_100_Index', 'EPIC', 3, '.L'),
        'nikkei225': ('https://en.wikipedia.org/wiki/Nikkei_225', 'Ticker', 3, '.T'),
        'cac40': ('https://en.wikipedia.org/wiki/CAC_40', 'Ticker', 1, '.PA'),
        'dax': ('https://en.wikipedia.org/wiki/DAX', 'Ticker symbol', 1, '.DE'),
        'asx200': ('https://en.wikipedia.org/wiki/S%26P/ASX_200', 'ASX code', 0, '.AX'),
    }
    if index not in url_map:
        raise ValueError(f"Index '{index}' not supported.")
    url, col, table_idx, suffix = url_map[index]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        tables = pd.read_html(StringIO(response.text))
        df = tables[table_idx]
        tickers = df[col].tolist()
        if suffix:
            tickers = [t.strip() + suffix for t in tickers]
        else:
            tickers = [t.strip() for t in tickers]
        print(f"Fetched {len(tickers)} tickers for {index.upper()} from Wikipedia.")
        return tickers
    except Exception as e:
        print(f"Error fetching {index.upper()} tickers: {e}")
        return []

def get_global_index_tickers(indices=None):
    """
    Aggregate tickers from a list of major indices.
    indices: list of index keys (see get_index_tickers)
    Returns a list of unique tickers.
    """
    if indices is None:
        indices = ['sp500', 'nasdaq100', 'dowjones', 'ftse100', 'nikkei225', 'cac40', 'dax', 'asx200']
    all_tickers = set()
    for idx in indices:
        all_tickers.update(get_index_tickers(idx))
        time.sleep(1)  # Be polite to Wikipedia
    print(f"Total unique tickers fetched: {len(all_tickers)}")
    return list(all_tickers)

def get_ticker_info_safe(ticker, max_retries=2):
    """
    Safely fetch ticker info with retry logic using yfinance.
    """
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Validate that we got useful data
            if info and len(info) > 1:
                return info
            
            if attempt < max_retries - 1:
                time.sleep(0.5)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
    
    return None


def get_sector_peers_api(target_ticker, max_peers=20, indices=['sp500', 'nasdaq100']):
    """
    Get a list of peer tickers in the same sector as the target_ticker.
    Dynamically fetches index constituents and filters by sector.
    
    Args:
        target_ticker: Target ticker symbol
        max_peers: Maximum number of peers to return
        indices: Which indices to search (sp500, nasdaq100, dowjones, ftse100)
    
    Returns:
        List of peer ticker symbols
    """
    print(f"\nFinding peers for {target_ticker}...")
    print("=" * 60)
    
    # Get target ticker info
    target_info = get_ticker_info_safe(target_ticker)
    
    if not target_info:
        print(f"Error: Could not fetch info for {target_ticker}")
        return []
    
    target_sector = target_info.get('sector')
    target_industry = target_info.get('industry')
    
    if not target_sector:
        print(f"Warning: No sector information found for {target_ticker}")
        return []
    
    print(f"Target sector: {target_sector}")
    if target_industry:
        print(f"Target industry: {target_industry}")
    
    # Get universe of tickers from indices
    universe = get_global_index_tickers(indices=indices)
    
    # Remove target ticker from universe
    universe = [t for t in universe if t.upper() != target_ticker.upper()]
    
    print(f"\nSearching through {len(universe)} tickers for sector matches...")
    print("-" * 60)
    
    peers = []
    checked = 0
    
    for ticker in universe:
        if len(peers) >= max_peers:
            break
        
        # Get peer info
        peer_info = get_ticker_info_safe(ticker)
        
        if peer_info:
            checked += 1
            peer_sector = peer_info.get('sector')
            
            # Match by sector
            if peer_sector == target_sector:
                peers.append(ticker)
                print(f"  ✓ Found peer {len(peers)}: {ticker} ({peer_sector})")
        
        # Add small delay every 10 requests to avoid rate limiting
        if checked % 10 == 0:
            time.sleep(0.5)
            print(f"  ... checked {checked} tickers so far")
    
    print("-" * 60)
    print(f"Found {len(peers)} peers in sector '{target_sector}' (checked {checked} tickers)")
    print("=" * 60)
    
    return peers


def compute_sector_averages_api(target_ticker, metrics_func, max_peers=20, indices=['sp500', 'nasdaq100']):
    """
    Compute the average of each metric for all peers in the same sector as the target_ticker.
    
    Args:
        target_ticker: The ticker symbol to find peers for
        metrics_func: A function that takes a ticker and returns a dict of metrics
        max_peers: Maximum number of peers to analyze
        indices: Which indices to search for peers
    
    Returns:
        A dict of sector averages for each metric
    """
    print(f"\n{'='*70}")
    print(f"COMPUTING SECTOR AVERAGES FOR {target_ticker}")
    print(f"{'='*70}")
    
    # Get peers in the same sector
    peers = get_sector_peers_api(target_ticker, max_peers=max_peers, indices=indices)
    
    if not peers:
        print(f"\nWarning: No peers found for {target_ticker}")
        return {}
    
    print(f"\nComputing metrics for {len(peers)} peers...")
    print("-" * 70)
    
    # Collect metrics from all peers
    results = []
    successful = 0
    
    for i, peer in enumerate(peers, 1):
        try:
            print(f"  [{i}/{len(peers)}] Computing metrics for {peer}...", end=' ')
            metrics = metrics_func(peer)
            
            if metrics and isinstance(metrics, dict):
                results.append(metrics)
                successful += 1
                print("✓")
            else:
                print("✗ (no data)")
        except Exception as e:
            print(f"✗ (error: {str(e)[:50]})")
            continue
        
        # Small delay to avoid rate limiting
        if i % 5 == 0:
            time.sleep(0.5)
    
    if not results:
        print(f"\nWarning: No valid metrics computed for any peers of {target_ticker}")
        return {}
    
    print("-" * 70)
    print(f"Successfully computed metrics for {successful}/{len(peers)} peers")
    print("-" * 70)
    
    # Compute averages for each metric
    all_keys = set()
    for result in results:
        all_keys.update(result.keys())
    
    averages = {}
    
    print(f"\nComputing averages for {len(all_keys)} metrics...")
    print("-" * 70)
    
    for key in all_keys:
        values = []
        for result in results:
            if key in result and result[key] is not None:
                try:
                    val = float(result[key])
                    if not np.isnan(val) and not np.isinf(val):
                        values.append(val)
                except (ValueError, TypeError):
                    continue
        
        if values:
            avg_value = np.mean(values)
            averages[key] = round(avg_value, 3)
            print(f"  {key:25s}: {averages[key]:>12.3f} (from {len(values)} peers)")
        else:
            averages[key] = None
            print(f"  {key:25s}: {'N/A':>12s} (no valid data)")
    
    print(f"{'='*70}")
    print(f"SECTOR AVERAGES COMPUTED FROM {len(results)} PEERS")
    print(f"{'='*70}\n")
    
    return averages


# Example usage
if __name__ == "__main__":
    # Example metrics function
    def get_financial_metrics(ticker):
        """
        Example function that computes financial metrics for a ticker.
        Replace this with your actual metrics computation function.
        """
        stock = yf.Ticker(ticker)
        info = stock.info
        
        metrics = {
            'pe_ratio': info.get('trailingPE'),
            'forward_pe': info.get('forwardPE'),
            'price_to_book': info.get('priceToBook'),
            'debt_to_equity': info.get('debtToEquity'),
            'roe': info.get('returnOnEquity'),
            'profit_margin': info.get('profitMargins'),
            'revenue_growth': info.get('revenueGrowth'),
            'market_cap': info.get('marketCap'),
        }
        
        return metrics
    
    # Test with a sample ticker
    target = "AAPL"
    
    print(f"\n{'*'*70}")
    print(f"TESTING SECTOR PEER ANALYSIS FOR {target}")
    print(f"{'*'*70}")
    
    # Get sector averages (search in S&P 500 and NASDAQ-100)
    sector_avgs = compute_sector_averages_api(
        target_ticker=target,
        metrics_func=get_financial_metrics,
        max_peers=15,
        indices=['sp500', 'nasdaq100']  # Can add 'dowjones', 'ftse100'
    )
    
    # Display results
    print("\n" + "="*70)
    print("FINAL SECTOR AVERAGE METRICS:")
    print("="*70)
    for metric, value in sector_avgs.items():
        if value is not None:
            print(f"{metric:25s}: {value:>15.3f}")
        else:
            print(f"{metric:25s}: {'N/A':>15s}")
    print("="*70)