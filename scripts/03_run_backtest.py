#!/usr/bin/env python3
"""
03_run_backtest.py — Run all setups with progress bar.
Usage: python3 scripts/03_run_backtest.py [--setup SETUP_ID] [--from YYYY-MM-DD] [--to YYYY-MM-DD]
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import Backtester, SETUPS, NiftyDataLoader

DATA_DIR = '/home/workspace/backtester/data'
RESULTS_DIR = '/home/workspace/backtester/results'
os.makedirs(RESULTS_DIR, exist_ok=True)

CSV_PATH = os.path.join(DATA_DIR, 'nifty_options_raw.csv')
IDX_PATH = os.path.join(DATA_DIR, 'date_index.json')

# ── Parse args ─────────────────────────────────────────────────────────────────
setup_filter = None
from_date = None
to_date = None
args = sys.argv[1:]
while args:
    if args[0] == '--setup' and len(args) > 1:
        setup_filter = args[1]; args = args[2:]
    elif args[0] == '--from' and len(args) > 1:
        from_date = args[1]; args = args[2:]
    elif args[0] == '--to' and len(args) > 1:
        to_date = args[1]; args = args[2:]
    else:
        args = args[1:]

# ── Load data ───────────────────────────────────────────────────────────────────
print("=" * 70)
print(" N-BOT OPTIONS BACKTESTER")
print("=" * 70)
print()

if not os.path.exists(CSV_PATH):
    print(f"ERROR: Data not found at {CSV_PATH}")
    print("Run: python3 scripts/01_download_data.py first")
    sys.exit(1)

print(f"Loading data index...", flush=True)
import json
with open(IDX_PATH) as f:
    date_map = json.load(f)
all_dates = sorted(date_map.keys())
print(f"  {len(all_dates)} trading dates loaded ({all_dates[0]} → {all_dates[-1]})")
print()

# Filter dates
if from_date:
    all_dates = [d for d in all_dates if d >= from_date]
if to_date:
    all_dates = [d for d in all_dates if d <= to_date]
print(f"Backtest period: {all_dates[0]} → {all_dates[-1]} ({len(all_dates)} days)")
print()

# ── Run backtests ──────────────────────────────────────────────────────────────
subset = [s for s in SETUPS if (setup_filter is None or s.setup_id == setup_filter)]
total = len(subset)
bar = None

for idx, setup in enumerate(subset):
    # Progress bar
    pct = (idx + 1) / total
    filled = int(pct * 40)
    bar = f"[{'█' * filled}{'░' * (40 - filled)}] {idx+1}/{total} setups"
    print(f"\r{bar} — {setup.setup_id}: {setup.setup_name}...", end='', flush=True)

    bt = Backtester(CSV_PATH, setup, capital=4000)
    t0 = time.time()

    # Count rows to show % during run
    total_rows = sum(len(date_map[d]) for d in all_dates if d in date_map)

    result = bt.run(from_date=all_dates[0] if from_date else None,
                    to_date=all_dates[-1] if to_date else None,
                    verbose=False)

    elapsed = time.time() - t0

    # Save result
    out = {
        'setup_id': setup.setup_id,
        'setup_name': setup.setup_name,
        'period': f"{all_dates[0]}→{all_dates[-1]}",
        'trades': result['trades'],
        'wins': result['wins'],
        'losses': result['losses'],
        'win_rate': round(result['win_rate'], 1),
        'avg_pnl': round(result['avg_pnl'], 2),
        'total_pnl': round(result['total_pnl'], 2),
        'max_drawdown': round(result['max_drawdown'], 2),
        'profit_factor': round(result['profit_factor'], 2),
        'sharpe': result['sharpe'],
        'elapsed_s': round(elapsed, 1),
        'trades_detail': result.get('_trades', []),
    }
    out_path = os.path.join(RESULTS_DIR, f"setup_{setup.setup_id}.json")
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)

print()  # clear progress line
print()

# ── Summary table ──────────────────────────────────────────────────────────────
print("=" * 70)
print(" RESULTS")
print("=" * 70)
print()
print(f"{'ID':<5} {'Setup':<30} {'Trades':>6} {'Win%':>6} {'Avg P&L':>9} "
      f"{'Tot P&L':>9} {'PF':>5} {'Sharpe':>6}")
print("-" * 70)

rows = []
for setup in subset:
    p = os.path.join(RESULTS_DIR, f"setup_{setup.setup_id}.json")
    if os.path.exists(p):
        with open(p) as f:
            r = json.load(f)
        rows.append(r)

rows.sort(key=lambda x: x['total_pnl'], reverse=True)

for r in rows:
    flag = ' ◀' if r['win_rate'] >= 55 and r['total_pnl'] > 0 else ''
    print(f"{r['setup_id']:<5} {r['setup_name']:<30} {r['trades']:>6} "
          f"{r['win_rate']:>5.1f}% {r['avg_pnl']:>9.2f} "
          f"{r['total_pnl']:>9.2f} {r['profit_factor']:>5.2f} "
          f"{r['sharpe']:>6.2f}{flag}")

print()
tot_trades = sum(r['trades'] for r in rows)
tot_pnl = sum(r['total_pnl'] for r in rows)
wins = sum(1 for r in rows if r['win_rate'] >= 55 and r['total_pnl'] > 0)
print(f"Total: {tot_trades} trades across {len(rows)} setups | "
      f"Combined P&L: {tot_pnl:,.2f} | Profitable: {wins}/{len(rows)}")
print()
print(f"Results saved to: {RESULTS_DIR}/")