"""
Sector Analytics - Calculate Average Metrics Across Entire Sectors
Provider-based implementation (modular, extensible)
"""

import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from ...data_providers.interface import DataProviderInterface



    
# ============================================================================
# GET TOP COMPANIES IN SECTOR (Provider-based)
# ============================================================================
def get_sector_companies(sector_name: str, n: int = 20, provider: DataProviderInterface = None) -> List[str]:
    """Get top N companies in a sector using provider"""
    if provider is None:
        raise ValueError("Provider must be specified")
    return provider.get_sector_companies(sector_name, n)

# ============================================================================
# INDIVIDUAL METRICS (Provider-based)
# ============================================================================
def get_stock_metrics(ticker: str, provider: DataProviderInterface = None) -> Dict:
    """Get all key metrics for a single stock using provider"""
    if provider is None:
        raise ValueError("Provider must be specified")
    return provider.get_company_metrics(ticker)

# ============================================================================
# SECTOR-WIDE AVERAGES (Provider-based)
# ============================================================================
def _aggregate_metrics(df: pd.DataFrame, metrics_to_analyze: List[str]) -> Dict:
    results = {}
    for metric in metrics_to_analyze:
        valid_values = df[metric].dropna()
        if len(valid_values) > 0:
            results[metric] = {
                'average': float(valid_values.mean()),
                'median': float(valid_values.median()),
                'min': float(valid_values.min()),
                'max': float(valid_values.max()),
                'std_dev': float(valid_values.std()),
                'valid_count': len(valid_values),
                'missing_count': len(df) - len(valid_values)
            }
        else:
            results[metric] = {'error': 'No data available'}
    return results

def calculate_sector_averages(sector_name: str, n: int = 20, provider: DataProviderInterface = None) -> Dict:
    """Calculate average metrics for entire sector using provider"""
    if provider is None:
        raise ValueError("Provider must be specified")
    print(f"📊 Analyzing {sector_name} sector...")
    tickers = get_sector_companies(sector_name, n, provider)
    if not tickers:
        return {'error': f'Could not get companies for {sector_name}'}
    print(f"   Found {len(tickers)} companies")
    all_metrics = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_ticker = {executor.submit(get_stock_metrics, t, provider): t for t in tickers}
        for i, future in enumerate(as_completed(future_to_ticker), 1):
            ticker = future_to_ticker[future]
            try:
                metrics = future.result()
                print(f"   [{i}/{len(tickers)}] Got {ticker}")
                all_metrics.append(metrics)
            except Exception as e:
                print(f"   [{i}/{len(tickers)}] Error for {ticker}: {e}")
    df = pd.DataFrame(all_metrics)
    results = {
        'sector': sector_name,
        'companies_analyzed': len(tickers),
        'timestamp': datetime.now().isoformat(),
        'companies_list': tickers,
    }
    metrics_to_analyze = [
        'pe_ratio', 'peg_ratio', 'profit_margin', 'roe', 'roa',
        'debt_to_equity', 'current_ratio', 'dividend_yield', 'eps'
    ]
    results.update(_aggregate_metrics(df, metrics_to_analyze))
    return results

# ============================================================================
# SECTOR COMPARISON (Provider-based)
# ============================================================================
def compare_sectors(sector_list: List[str], metric: str = 'pe_ratio', provider: DataProviderInterface = None) -> pd.DataFrame:
    """Compare a metric across multiple sectors using provider"""
    if provider is None:
        raise ValueError("Provider must be specified")
    comparison_data = {}
    for sector in sector_list:
        print(f"\n📊 Analyzing {sector}...")
        sector_data = calculate_sector_averages(sector, 20, provider)
        if metric in sector_data:
            stats = sector_data[metric]
            comparison_data[sector] = {
                'Average': stats.get('average', 0),
                'Median': stats.get('median', 0),
                'Min': stats.get('min', 0),
                'Max': stats.get('max', 0),
                'Valid': stats.get('valid_count', 0)
            }
    return pd.DataFrame(comparison_data).T

# ============================================================================
# GET TOP COMPANIES IN INDUSTRY (Provider-based)
# ============================================================================
def get_industry_companies(industry_name: str, n: int = 20, provider: DataProviderInterface = None) -> List[str]:
    """Get top N companies in an industry using provider"""
    if provider is None:
        raise ValueError("Provider must be specified")
    return provider.get_industry_companies(industry_name, n)

# ============================================================================
# INDUSTRY-WIDE AVERAGES (Provider-based)
# ============================================================================
def calculate_industry_averages(industry_name: str, n: int = 20, provider: DataProviderInterface = None) -> Dict:
    """Calculate average metrics for entire industry using provider"""
    if provider is None:
        raise ValueError("Provider must be specified")
    print(f"📊 Analyzing {industry_name} industry...")
    tickers = get_industry_companies(industry_name, n, provider)
    if not tickers:
        return {'error': f'Could not get companies for {industry_name}'}
    print(f"   Found {len(tickers)} companies")
    all_metrics = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_ticker = {executor.submit(get_stock_metrics, t, provider): t for t in tickers}
        for i, future in enumerate(as_completed(future_to_ticker), 1):
            ticker = future_to_ticker[future]
            try:
                metrics = future.result()
                print(f"   [{i}/{len(tickers)}] Got {ticker}")
                all_metrics.append(metrics)
            except Exception as e:
                print(f"   [{i}/{len(tickers)}] Error for {ticker}: {e}")
    df = pd.DataFrame(all_metrics)
    results = {
        'industry': industry_name,
        'companies_analyzed': len(tickers),
        'timestamp': datetime.now().isoformat(),
        'companies_list': tickers,
    }
    metrics_to_analyze = [
        'pe_ratio', 'peg_ratio', 'profit_margin', 'roe', 'roa',
        'debt_to_equity', 'current_ratio', 'dividend_yield', 'eps'
    ]
    results.update(_aggregate_metrics(df, metrics_to_analyze))
    return results

# ============================================================================
# INDUSTRY COMPARISON (Provider-based)
# ============================================================================
def compare_industries(industry_list: List[str], metric: str = 'pe_ratio', provider: DataProviderInterface = None) -> pd.DataFrame:
    """Compare a metric across multiple industries using provider"""
    if provider is None:
        raise ValueError("Provider must be specified")
    comparison_data = {}
    for industry in industry_list:
        print(f"\n📊 Analyzing {industry}...")
        industry_data = calculate_industry_averages(industry, 20, provider)
        if metric in industry_data:
            stats = industry_data[metric]
            comparison_data[industry] = {
                'Average': stats.get('average', 0),
                'Median': stats.get('median', 0),
                'Min': stats.get('min', 0),
                'Max': stats.get('max', 0),
                'Valid': stats.get('valid_count', 0)
            }
    return pd.DataFrame(comparison_data).T


