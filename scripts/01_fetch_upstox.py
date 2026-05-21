#!/usr/bin/env python3
"""
01_fetch_upstox.py
Fetches Nifty 50 + India VIX 1-minute OHLCV from Upstox API v3.
Saves as CSV (one file per instrument, one row per candle).
Idempotent — skips already-fetched dates.

Usage:
    python3 01_fetch_upstox.py                          # last 30 days
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
TOKEN = os.environ.get('UPSTOX_TOKEN', '')
INSTRUMENTS = {
    'nifty50': 'NSE_INDEX|Nifty 50',
    'vix':     'NSE_INDEX|India VIX',
}
BASE_URL = 'https://api.upstox.com/v3/historical-candle'
OUT_DIR  = Path('/home/workspace/backtester/data')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ─────────────────────────────────────────────────────────────────

def fetch_candles(instrument_key: str, date: str, retries: int = 3) -> list:
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
                # Drop zero-volume rows (pre/post market). But index candles often have 0 volume in
                # Upstox free tier — keep them anyway for OHLC accuracy.
                return [c for c in candles if len(c) >= 6]
            elif resp.status_code == 429:
                print(f'  ⚠ Rate limited — waiting 65s...')
                time.sleep(65)
            else:
                err = resp.json().get('errors', [{}])[0].get('errorCode', resp.status_code)
                print(f'  ✗ {resp.status_code} [{err}]')
                return []
        except Exception as e:
            print(f'  ✗ Attempt {attempt+1} failed: {e}')
            time.sleep(3)
    return []

def parse_candles(candles: list, instrument: str) -> pd.DataFrame:
    rows = []
    for c in candles:
        rows.append({
            'timestamp':   c[0],
            'open':       round(float(c[1]), 2),
            'high':       round(float(c[2]), 2),
            'low':        round(float(c[3]), 2),
            'close':      round(float(c[4]), 2),
            'volume':     int(c[5]) if len(c) > 5 else 0,
            'instrument': instrument,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
    return df

def trading_dates(from_date: str, to_date: str) -> list:
    dates = []
    f = datetime.strptime(from_date, '%Y-%m-%d')
    t = datetime.strptime(to_date,   '%Y-%m-%d')
    while f <= t:
        if f.weekday() < 5:
            dates.append(f.strftime('%Y-%m-%d'))
        f += timedelta(days=1)
    return dates

def load_cached_dates(csv_path: Path) -> set:
    if csv_path.exists():
        df = pd.read_csv(csv_path, usecols=['timestamp'], parse_dates=['timestamp'])
        return set(df['timestamp'].dt.strftime('%Y-%m-%d').unique())
    return set()

def append_csv(df: pd.DataFrame, path: Path):
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    if path.exists():
        existing = pd.read_csv(path, parse_dates=['timestamp'])
        combined = pd.concat([existing, df], ignore_index=True)
        combined['timestamp'] = pd.to_datetime(combined['timestamp'])
        combined = combined.drop_duplicates(['timestamp', 'instrument']).sort_values('timestamp')
        combined.to_csv(path, index=False)
    else:
        df.to_csv(path, index=False)

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='from_date', default=None)
    ap.add_argument('--to',   dest='to_date',   default=None)
    ap.add_argument('--months', type=int, default=None)
    ap.add_argument('--instrument', default=None)
    args = ap.parse_args()

    today = datetime.today().strftime('%Y-%m-%d')
    if args.months:
        to_dt   = datetime.today()
        from_dt = to_dt - timedelta(days=args.months * 30)
        from_date = from_dt.strftime('%Y-%m-%d')
        to_date   = to_dt.strftime('%Y-%m-%d')
    elif args.from_date and args.to_date:
        from_date, to_date = args.from_date, args.to_date
    else:
        from_date, to_date = '2025-04-21', today

    if not TOKEN:
        print('[ERROR] UPSTOX_TOKEN not set.')
        print('  Add it at: Settings > Advanced > Secrets')
        sys.exit(1)

    instruments = dict(INSTRUMENTS)
    if args.instrument:
        instruments = {args.instrument: INSTRUMENTS[args.instrument]}

    dates = trading_dates(from_date, to_date)

    print(f'\n[Upstox Fetcher]')
    print(f'  Dates       : {from_date} → {to_date}  ({len(dates)} trading days)')
    print(f'  Instruments : {list(instruments.keys())}')
    print(f'  Output      : {OUT_DIR}')
    print()

    for iname, ikey in instruments.items():
        out_path = OUT_DIR / f'{iname}_1m.csv'
        cached  = load_cached_dates(out_path)
        missing = [d for d in dates if d not in cached]
        print(f'[{iname}] {len(cached)} dates cached, {len(missing)} to fetch')

        if missing:
            pbar = tqdm(missing, desc=f'[{iname}]', unit='day', ncols=80)
            for date in pbar:
                candles = fetch_candles(ikey, date)
                if candles:
                    df = parse_candles(candles, iname)
                    append_csv(df, out_path)
                    pbar.set_postfix(rows=len(df))
                time.sleep(1.1)

        df_final = pd.read_csv(out_path, parse_dates=['timestamp'])
        print(f'  ✓ {iname}: {len(df_final):,} candles')
        print(f'    {df_final.timestamp.min().date()} → {df_final.timestamp.max().date()}')
        print(f'    {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)')

    print('\n[Done]')

if __name__ == '__main__':
    main()