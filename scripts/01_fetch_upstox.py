#!/usr/bin/env python3
"""
01_fetch_upstox.py
Fetches Nifty 50 + India VIX 1-minute OHLCV from Upstox API v3.
Saves as parquet. Idempotent — skips already-fetched dates.

Usage:
    python3 01_fetch_upstox.py                          # fetch last 30 days
    python3 01_fetch_upstox.py --months 6              # last 6 months
    python3 01_fetch_upstox.py --from 2025-01-02 --to 2025-05-20
"""
import os, sys, argparse, time, json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

# ── Config ──────────────────────────────────────────────────────────────────
TOKEN     = os.environ.get('UPSTOX_TOKEN', '')
INSTRUMENTS = {
    'nifty50':  'NSE_INDEX|Nifty 50',
    'vix':      'NSE_INDEX|India VIX',
}
BASE_URL  = 'https://api.upstox.com/v3/historical-candle'
OUT_DIR   = Path('/home/workspace/backtester/data')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ─────────────────────────────────────────────────────────────────

def fetch_candles(instrument_key: str, date: str, retries: int = 3) -> list:
    """Fetch all minute candles for a single date."""
    # URL pattern: /v3/historical-candle/{key}/{unit}/{to_date}/{from_date}
    url = f'{BASE_URL}/{requests.utils.quote(instrument_key, safe="")}/minutes/1/{date}/{date}'
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={
                'Authorization': f'Bearer {TOKEN}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                candles = data.get('data', {}).get('candles', [])
                # Filter out zero-volume candles (pre/post market noise)
                return [c for c in candles if c[5] > 0]
            elif resp.status_code == 429:
                print(f'  ⚠ Rate limited, waiting 65s...')
                time.sleep(65)
            else:
                err = resp.json().get('errors', [{}])[0].get('errorCode', resp.status_code)
                print(f'  ✗ HTTP {resp.status_code} [{err}]: {resp.text[:100]}')
                return []
        except Exception as e:
            print(f'  ✗ Attempt {attempt+1} failed: {e}')
            time.sleep(5)
    return []

def parse_candles(candles: list, label: str) -> pd.DataFrame:
    rows = []
    for c in candles:
        if len(c) >= 6:
            rows.append({
                'timestamp': pd.to_datetime(c[0]),
                'open':      float(c[1]),
                'high':      float(c[2]),
                'low':       float(c[3]),
                'close':     float(c[4]),
                'volume':    int(c[5]),
                'instrument': label,
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
    return df

def trading_dates(from_date: str, to_date: str) -> list:
    """Generate list of trading dates (Mon–Fri, no NSE holidays approximation)."""
    dates = []
    f = datetime.strptime(from_date, '%Y-%m-%d')
    t = datetime.strptime(to_date,   '%Y-%m-%d')
    while f <= t:
        if f.weekday() < 5:  # Mon=0, ..., Fri=4
            dates.append(f.strftime('%Y-%m-%d'))
        f += timedelta(days=1)
    return dates

def load_existing_dates(path: Path) -> set:
    if path.exists():
        df = pd.read_parquet(path)
        return set(df['timestamp'].dt.strftime('%Y-%m-%d').unique())
    return set()

def append_parquet(df: pd.DataFrame, path: Path):
    existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    combined = pd.concat([existing, df], ignore_index=True)
    combined = combined.drop_duplicates(['timestamp', 'instrument']).sort_values('timestamp')
    combined.to_parquet(path, index=False)

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Fetch Upstox historical minute candles')
    ap.add_argument('--from', dest='from_date', default=None)
    ap.add_argument('--to',   dest='to_date',   default=None)
    ap.add_argument('--months', type=int, default=None)
    ap.add_argument('--instrument', default=None, help='nifty50, vix, or all')
    args = ap.parse_args()

    # Determine date range
    today = datetime.today().strftime('%Y-%m-%d')
    if args.months:
        to_dt   = datetime.today()
        from_dt = to_dt - timedelta(days=args.months * 30)
        from_date = from_dt.strftime('%Y-%m-%d')
        to_date   = to_dt.strftime('%Y-%m-%d')
    elif args.from_date and args.to_date:
        from_date, to_date = args.from_date, args.to_date
    else:
        from_date, to_date = '2025-04-21', today  # default: last 30 days

    if not TOKEN:
        print('[ERROR] UPSTOX_TOKEN not set.')
        print('  Add it at: Settings > Advanced > Secrets')
        sys.exit(1)

    instruments = {k: v for k, v in INSTRUMENTS.items()}
    if args.instrument:
        instruments = {args.instrument: INSTRUMENTS[args.instrument]}

    dates = trading_dates(from_date, to_date)
    total_calls = len(dates) * len(instruments)
    print(f'\n[Upstox Fetcher]')
    print(f'  Dates     : {from_date} → {to_date} ({len(dates)} trading days)')
    print(f'  Instruments: {list(instruments.keys())}')
    print(f'  Total API calls: {total_calls}')
    print(f'  Output    : {OUT_DIR}')
    print()

    for iname, ikey in instruments.items():
        out_path = OUT_DIR / f'{iname}_1m.parquet'
        existing = load_existing_dates(out_path)
        new_dates = [d for d in dates if d not in existing]
        print(f'[{iname}] {len(existing)} dates already cached, {len(new_dates)} to fetch')

        if new_dates:
            pbar = tqdm(new_dates, desc=f'[{iname}] Fetching', unit='day')
            for date in pbar:
                pbar.set_description(f'[{iname}] {date}')
                candles = fetch_candles(ikey, date)
                if candles:
                    df = parse_candles(candles, iname)
                    append_parquet(df, out_path)
                    pbar.set_postfix(rows=len(df))
                time.sleep(1.1)  # be polite

        df_final = pd.read_parquet(out_path)
        print(f'  ✓ {iname}: {len(df_final):,} candles, {df_final.timestamp.min().date()} → {df_final.timestamp.max().date()}')

    print('\n[Done] Data saved to:')
    for iname in instruments:
        p = OUT_DIR / f'{iname}_1m.parquet'
        if p.exists():
            print(f'  {p}  ({p.stat().st_size/1e6:.1f} MB)')

if __name__ == '__main__':
    main()