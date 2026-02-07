import pytest
from finance_assistant.providers.yfinance.scoring import fundamental_score, return_on_ebit, return_on_capital, roic_greenblatt, magic_formula_score
    get_global_index_tickers,
    get_sector_peers_api,
    compute_sector_averages_api,
)

def test_get_global_index_tickers():
    tickers = get_global_index_tickers()
    if not tickers:
        pytest.skip("No tickers found (network or parsing issue)")
    assert isinstance(tickers, list)
    assert len(tickers) > 100  # Should be a large global set
    assert all(isinstance(t, str) for t in tickers)

def test_get_sector_peers_api_valid():
    # Use a well-known ticker with sector/country info (e.g., 'AAPL')
    peers = get_sector_peers_api('AAPL', max_peers=5)
    assert isinstance(peers, list)
    assert len(peers) <= 5
    assert all(isinstance(t, str) for t in peers)
    # Should not include the target ticker
    assert 'AAPL' not in peers

def test_get_sector_peers_api_no_sector():
    # Use a fake ticker or one with missing info
    peers = get_sector_peers_api('FAKE123', max_peers=5)
    assert peers == []

def test_compute_sector_averages_api():
    # Use a real ticker and the fundamental_score function
    avg = compute_sector_averages_api('AAPL', fundamental_score, max_peers=3)
    if not avg:
        pytest.skip("No sector averages found (no peers or metrics failed)")
    assert isinstance(avg, dict)
    # Should contain keys from fundamental_score
    for k in ['profit_margin', 'roe', 'roa', 'pe_ratio', 'peg_ratio', 'debt_to_equity', 'current_ratio', 'debt_to_assets', 'revenue_growth']:
        assert k in avg

def test_compute_sector_averages_api_no_peers():
    avg = compute_sector_averages_api('FAKE123', fundamental_score, max_peers=3)
    assert avg == {}
