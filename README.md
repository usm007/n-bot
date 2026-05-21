# N-Bot Options Backtester

Backtest engine for Nifty 50 options buying setups, using historical Kaggle 1-minute OHOL data.

## Setup

```bash
# Install deps
pip install kagglehub tqdm

# Download data (~6.8 GB)
python3 scripts/01_download_data.py

# Run all setups
python3 scripts/03_run_backtest.py

# Run specific setup
python3 scripts/03_run_backtest.py --setup 11

# Run date range
python3 scripts/03_run_backtest.py --from 2025-01-01 --to 2025-12-31
```

## Data

- Source: [Kaggle - Nifty Option Chain (Oct 2024 → Mar 2026)](https://www.kaggle.com/datasets/pariminikhil/nifty-option-chain-3-oct-24-to-24-mar-26)
- 36M rows of 1-minute Nifty option chain data
- Stored at: `data/nifty_options_raw.csv`
- Date index: `data/date_index.json`

## Setups (23 total)

| ID | Name | Window | SL | Target |
|----|------|--------|----|----|
| 11 | Opening Drive | 9:16–9:25 | 30% | 60% |
| 12 | Pre-Close Momentum | 14:15–14:45 | 40% | 70% |
| 13 | Round Number Bounce | 10:00–14:30 | 25% | 40% |
| 14 | EMA Pullback | 10:00–14:00 | 20% | 40% |
| 15 | Bollinger Snapback | 10:00–14:00 | 25% | 50% |
| 16 | ORB Range | 9:20–10:00 | 30% | 60% |
| 17 | Volume Climax | 10:00–14:30 | 20% | 40% |
| 18 | Mean Reversion | 10:00–14:30 | 25% | 50% |
| 19 | First Hour Breakout | 9:20–10:00 | 30% | 60% |
| 20 | Bar Exhaustion | 12:00–14:00 | 25% | 50% |
| 21 | Pivot Bounce | 10:00–14:30 | 20% | 40% |
| 22 | EMA Crossover | 10:00–14:30 | 25% | 50% |
| 23 | Gap and Go | 9:15–10:00 | 30% | 60% |
| 24 | Double Top/Bottom | 10:00–14:30 | 25% | 50% |
| 25 | Afternoon Range | 13:00–14:30 | 20% | 40% |
| 26 | EMA VWAP Combo | 10:00–14:00 | 20% | 40% |
| 27 | VWAP Round | 10:00–14:30 | 25% | 50% |
| 28 | EMA5 Scalp | 10:00–14:00 | 15% | 30% |
| 29 | RSI2 Extreme | 10:00–14:30 | 20% | 40% |
| 30 | Afternoon Momentum | 13:30–14:45 | 25% | 50% |
| 31 | ADX Surge Breakout | 10:00–14:30 | 20% | 40% |
| 33 | NR7 Breakout | 10:00–14:30 | 20% | 40% |
| 35 | ATR Expansion Breakout | 10:00–14:30 | 20% | 40% |

## Engine

- `engine/backtester.py` — Core engine: data loader, trade simulation, metrics
- `engine/setups.py` — All 23 SetupConfig definitions (extracted from JS)
- `engine/__init__.py` — Package init

## Output

Results saved to `results/setup_XX.json` for each setup with:
- Trade count, win rate, avg P&L, total P&L
- Profit factor, Sharpe ratio, max drawdown
- Full trade-by-trade log