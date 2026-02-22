# Swing Trading Scanner — Interactive Brokers Edition

Rules-based weekly swing trade asset finder. Connects to Interactive Brokers via `ib_async`, screens the S&P 500, scores candidates with a composite indicator system, and displays results in a Plotly Dash dashboard.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start TWS or IB Gateway (paper trading port: 7497)

# 3. Run a fast test on 10 tickers
python run.py --mode test

# 4. Run a full weekly scan
python run.py --mode weekly

# 5. View the dashboard
python run.py --mode dashboard
# Then open: http://127.0.0.1:8050
```

---

## Project Structure

```
swing_scanner/
├── config.py       ← ALL parameters (only file you tune)
├── run.py          ← Entry point (CLI)
├── scanner.py      ← Main orchestrator
├── ib_client.py    ← IB data layer (+ yfinance fallback)
├── universe.py     ← Ticker list provider
├── indicators.py   ← TA calculations (pure functions)
├── regime.py       ← Market regime detection
├── filters.py      ← Hard binary filters
├── patterns.py     ← Breakout / pullback / squeeze detection
├── scorer.py       ← Composite scoring engine
├── risk.py         ← Stop / target / position sizing
├── dashboard.py    ← Plotly Dash visualization
└── requirements.txt
```

---

## Configuration

All parameters live in `config.py`. Never edit logic modules to change thresholds. Key settings:

| Parameter | Default | What It Does |
|---|---|---|
| `account_size` | 1000 | Your account in USD |
| `risk_per_trade_pct` | 0.01 | 1% risk per trade |
| `min_rr_ratio` | 2.0 | Minimum R:R to qualify |
| `universe` | "sp500" | "sp500", "nasdaq100", or "custom" |
| `rsi_min` / `rsi_max` | 45 / 70 | RSI filter band |
| `atr_pct_min` / `max` | 2 / 8 | Volatility band (%) |
| `adx_min` | 20 | Trend strength floor |
| `min_trend_conditions` | 3 | Out of 5 trend conditions needed |
| `ib_port` | 7497 | TWS paper=7497, live=7496, Gateway paper=4002 |

---

## IB Connection

The scanner connects to IB TWS or IB Gateway. Make sure:
1. TWS or Gateway is running and logged in
2. API connections are enabled (Settings → API → Enable ActiveX and Socket Clients)
3. The correct port matches `cfg["ib_port"]`
4. `cfg["ib_client_id"]` is unique if multiple scripts connect simultaneously

**No IB?** The scanner falls back to `yfinance` automatically for development.

---

## Scoring System

Each ticker receives a composite score 0–100 from 8 components:

| Component | Weight | Ideal Condition |
|---|---|---|
| Trend alignment | 20% | Price > SMA20 > SMA50 > SMA200, ADX > 20 |
| Pattern quality | 20% | Clean breakout/pullback/squeeze |
| Relative strength | 15% | Outperforms SPY on 1M, 3M, 6M |
| Relative volume | 12% | RVOL > 3x |
| RSI alignment | 10% | RSI near 60 |
| Risk:Reward | 10% | R:R > 5:1 |
| ATR% fit | 8% | ATR% near 4.5% |
| OBV slope | 5% | OBV trending up |

Score is then multiplied by a regime factor: Bull × 1.1, Neutral × 1.0, Bear × 0.6.

---

## Dashboard

The Dash UI provides:
- **Regime banner**: Market regime + VIX level
- **Watchlist table**: Sortable, filterable, clickable rows
- **Radar chart**: 8-component score breakdown for selected ticker
- **Candlestick chart**: Price + SMA20/50/EMA20 + entry/stop/target levels + volume

---

## CLI Options

```bash
python run.py --mode weekly              # full scan
python run.py --mode test                # 10 tickers (fast)
python run.py --mode test --tickers AAPL,MSFT,NVDA  # custom list
python run.py --mode dashboard           # visualization server
python run.py --port 7496                # override IB port (live)
python run.py --port 4002                # override for IB Gateway paper

LOG_LEVEL=DEBUG python run.py --mode test   # verbose logging
```

---

## Tuning Tips

**Too few results:**
- Lower `min_trend_conditions` (3 → 2)
- Widen ATR band (`atr_pct_max` 8 → 10)
- Lower `adx_min` (20 → 15)

**Too many results:**
- Raise `min_score_display` (40 → 55)
- Raise `adx_min` (20 → 25)
- Tighten `consolidation_tight` (0.12 → 0.08)

**R:R too strict:**
- Lower `min_rr_ratio` (2.0 → 1.5) for less ideal markets

---

## Risk Disclaimer

Educational purposes only. Trading involves substantial risk of loss.
Past patterns do not guarantee future results. Always paper-trade before using real capital.
