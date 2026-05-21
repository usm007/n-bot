"""
Core backtesting engine for N-Bot Options.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime, date
import struct, math, os, csv

# ─── SetupConfig ──────────────────────────────────────────────────────────────
@dataclass
class SetupConfig:
    setup_id: str
    setup_name: str
    entry_start_h: int; entry_start_m: int
    entry_end_h: int; entry_end_m: int
    hard_exit_h: int; hard_exit_m: int
    premium_min: float; premium_max: float
    sl_pct: float; target_pct: float
    capital_min: int; capital_max: int
    vix_min: int = 11
    adx_min: Optional[float] = None
    volume_mult: float = 1.3
    min_body_pct: float = 0.15
    max_gap_pct: float = 1.0
    round_threshold: Optional[float] = None
    ema_separation_min: Optional[float] = None
    reversal_min: Optional[float] = None
    entry_max_h: Optional[int] = None
    touch_threshold: Optional[float] = None
    touch_pct: Optional[float] = None
    gap_min: Optional[int] = None
    touch_min_max: Optional[str] = None  # "10_15"
    doji_ratio_max: Optional[float] = None
    max_trades_per_day: int = 2
    premium_min_alt: float = 30
    filters: dict = field(default_factory=dict)

# ─── ChunkIndex ────────────────────────────────────────────────────────────────
@dataclass
class ChunkIndex:
    dates: List[bytes]   # serialized YYYY-MM-DD for each row
    offsets: List[int]  # byte offset in file for each row

# ─── NiftyDataLoader ──────────────────────────────────────────────────────────
class NiftyDataLoader:
    def __init__(self, csv_path: str, index_path: str = None):
        self.csv_path = csv_path
        self.f = open(csv_path, 'rb')
        self.size = os.path.getsize(csv_path)
        self._chunk_idx: Optional[ChunkIndex] = None
        self._date_map: Dict[str, List[Tuple[int, int]]] = {}  # date -> [(offset, row)]

    def _build_index(self, force: bool = False):
        if self._chunk_idx and not force:
            return
        import json
        if self._date_map:
            return
        print("  Building date index...")
        f = self.f
        f.seek(0)
        header = f.readline()
        pos = f.tell()
        rows = 0
        date_map: Dict[str, List[int]] = {}
        while True:
            line = f.readline()
            if not line:
                break
            # date is field 0
            first_comma = line.find(b',')
            d = line[:first_comma].strip()
            if d:
                if d not in date_map:
                    date_map[d] = []
                date_map[d].append(pos)
            pos = f.tell()
            rows += 1
        print(f"  {rows:,} rows indexed across {len(date_map)} trading dates")
        self._date_map = date_map
        return

    def load_date(self, date_str: str, progress=True) -> List[dict]:
        self._build_index()
        if date_str not in self._date_map:
            return []
        offsets = self._date_map[date_str]
        rows = []
        f = self.f
        for off in offsets:
            f.seek(off)
            row = f.readline().decode('utf-8', errors='replace').strip()
            if not row:
                continue
            parts = row.split(',')
            if len(parts) < 10:
                continue
            try:
                rows.append({
                    'timestamp': parts[0].strip(),
                    'strike_price': float(parts[1]),
                    'ce_close': float(parts[2]) if parts[2] not in ('', 'null', '-') else None,
                    'ce_volume': float(parts[3]) if parts[3] not in ('', 'null', '-') else 0,
                    'pe_close': float(parts[4]) if parts[4] not in ('', 'null', '-') else None,
                    'pe_volume': float(parts[5]) if parts[5] not in ('', 'null', '-') else 0,
                    'expiry': parts[6].strip() if len(parts) > 6 else '',
                    'option_type': parts[7].strip() if len(parts) > 7 else '',
                    'open_interest': float(parts[8]) if len(parts) > 8 and parts[8] not in ('', 'null', '-') else 0,
                    'atm_distance': float(parts[9]) if len(parts) > 9 and parts[9] not in ('', 'null', '-') else 0,
                })
            except:
                pass
        return rows

    def all_dates(self) -> List[str]:
        self._build_index()
        return sorted(self._date_map.keys())

    def __del__(self):
        try:
            self.f.close()
        except:
            pass

# ─── Backtester ───────────────────────────────────────────────────────────────
class Backtester:
    # Column indices in raw CSV (0-indexed):
    COL = {'ts': 0, 'strike': 1, 'ce_close': 2, 'ce_vol': 3, 'pe_close': 4,
           'pe_vol': 5, 'expiry': 6, 'otype': 7, 'oi': 8, 'atm_dist': 9}

    def __init__(self, csv_path: str, setup: SetupConfig, capital: float = 4000):
        self.loader = NiftyDataLoader(csv_path)
        self.setup = setup
        self.capital = capital
        self.trades: List[dict] = []
        self.wins = self.losses = self.total_pnl = 0.0

    def run(self, from_date: str = None, to_date: str = None, verbose: bool = False):
        dates = self.loader.all_dates()
        if from_date:
            dates = [d for d in dates if d >= from_date]
        if to_date:
            dates = [d for d in dates if d <= to_date]

        for ds in dates:
            trades = self._simulate_day(ds)
            for t in trades:
                self._record_trade(t)
                if verbose:
                    print(f"  {ds} | {t['setup']} | {t['direction']} {t['strike']} "
                          f"| Entry: {t['entry']:.1f} | Exit: {t['exit']:.1f} "
                          f"| PnL: {t['pnl']:.1f} | {t['exit_reason']}")
        return self.summary()

    def _simulate_day(self, date_str: str) -> List[dict]:
        rows = self.loader.load_date(date_str)
        if not rows:
            return []

        # Separate CE and PE chains
        ce_rows = [r for r in rows if r['option_type'] == 'CE']
        pe_rows = [r for r in rows if r['option_type'] == 'PE']
        if not ce_rows or not pe_rows:
            return []

        # Get unique timestamps
        timestamps = sorted(set(r['timestamp'] for r in rows))
        if len(timestamps) < 2:
            return []

        # Build spot from ATM distance
        chain_by_ts = {}
        for ts in timestamps:
            ts_ce = [r for r in ce_rows if r['timestamp'] == ts]
            ts_pe = [r for r in pe_rows if r['timestamp'] == ts]
            if ts_ce and ts_pe:
                chain_by_ts[ts] = {'CE': ts_ce, 'PE': ts_pe}

        if not chain_by_ts:
            return []

        # Parse entry window
        entry_start_min = self.setup.entry_start_h * 60 + self.setup.entry_start_m
        entry_end_min   = self.setup.entry_end_h * 60 + self.setup.entry_end_m
        hard_exit_min   = self.setup.hard_exit_h * 60 + self.setup.hard_exit_m
        trades = []
        trades_today = 0
        max_trades = getattr(self.setup, 'max_trades_per_day', 2)

        for i, ts in enumerate(timestamps):
            if ts not in chain_by_ts:
                continue

            # Parse timestamp to minutes
            try:
                h = int(ts.split(' ')[1].split(':')[0])
                m = int(ts.split(' ')[1].split(':')[1])
                cur_min = h * 60 + m
            except:
                continue

            if cur_min < entry_start_min or cur_min > entry_end_min:
                continue
            if trades_today >= max_trades:
                continue

            chain = chain_by_ts[ts]

            # Filter by premium
            ce_atm = self._nearest_atm(chain['CE'], 0)
            pe_atm = self._nearest_atm(chain['PE'], 0)
            if not ce_atm or not pe_atm:
                continue

            if ce_atm['ce_close'] is None or pe_atm['pe_close'] is None:
                continue

            prem = ce_atm['ce_close']
            if prem < self.setup.premium_min or prem > self.setup.premium_max:
                prem = pe_atm['pe_close']
                if prem < self.setup.premium_min or prem > self.setup.premium_max:
                    continue

            # Direction from candle (uses spot estimation via ATM distance)
            direction = 'CE' if ce_atm['atm_distance'] <= pe_atm['atm_distance'] else 'PE'
            atm_row = ce_atm if direction == 'CE' else pe_atm

            # SL and target
            sl = prem * (1 - self.setup.sl_pct)
            target = prem * (1 + self.setup.target_pct)

            # Walk forward to find exit
            exit_price = None
            exit_reason = ''
            exit_ts = None
            for j in range(i + 1, len(timestamps)):
                if timestamps[j] not in chain_by_ts:
                    continue
                try:
                    tj = int(timestamps[j].split(' ')[1].split(':')[0])
                    mj = int(timestamps[j].split(' ')[1].split(':')[1])
                    exit_min = tj * 60 + mj
                except:
                    continue

                subchain = chain_by_ts[timestamps[j]]
                row = subchain['CE'] if direction == 'CE' else subchain['PE']
                nearest = self._nearest_atm(row, 0)
                if not nearest:
                    continue

                cp = nearest['ce_close'] if direction == 'CE' else nearest['pe_close']
                if cp is None:
                    continue

                if cp <= sl:
                    exit_price = cp
                    exit_reason = 'SL'
                    exit_ts = timestamps[j]
                    break
                elif cp >= target:
                    exit_price = cp
                    exit_reason = 'Target'
                    exit_ts = timestamps[j]
                    break
                elif exit_min >= hard_exit_min:
                    exit_price = cp
                    exit_reason = 'TimeExit'
                    exit_ts = timestamps[j]
                    break

            if exit_price is None:
                # Use last available price at hard exit
                last_ts = None
                for k in range(len(timestamps) - 1, i, -1):
                    if timestamps[k] in chain_by_ts:
                        last_ts = timestamps[k]
                        break
                if last_ts:
                    sub = chain_by_ts[last_ts]
                    row = sub['CE'] if direction == 'CE' else sub['PE']
                    nearest = self._nearest_atm(row, 0)
                    if nearest:
                        exit_price = nearest['ce_close'] if direction == 'CE' else nearest['pe_close']
                        exit_reason = 'EndOfDay'
                        exit_ts = last_ts

            if exit_price:
                pnl = exit_price - prem
                trades.append({
                    'date': date_str,
                    'setup': self.setup.setup_id,
                    'direction': direction,
                    'strike': atm_row['strike_price'],
                    'expiry': atm_row['expiry'],
                    'entry': prem,
                    'exit': exit_price,
                    'pnl': pnl,
                    'pnl_pct': (pnl / prem) * 100 if prem > 0 else 0,
                    'exit_reason': exit_reason,
                    'entry_time': ts,
                    'exit_time': exit_ts,
                })
                trades_today += 1

        return trades

    def _nearest_atm(self, rows: List[dict], atm_dist: float) -> Optional[dict]:
        """Find row closest to given ATM distance (0 = nearest ATM)."""
        if not rows:
            return None
        return min(rows, key=lambda r: abs(r['atm_distance'] - atm_dist))

    def _record_trade(self, t: dict):
        self.trades.append(t)
        if t['pnl'] > 0:
            self.wins += 1
        else:
            self.losses += 1
        self.total_pnl += t['pnl']

    def summary(self) -> dict:
        n = len(self.trades)
        if n == 0:
            return {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
                    'avg_pnl': 0, 'total_pnl': 0, 'max_drawdown': 0,
                    'profit_factor': 0, 'sharpe': 0}
        wins = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0)) or 0.001
        pnls = [t['pnl'] for t in self.trades]
        running = []
        cv = 0
        for p in pnls:
            cv += p
            running.append(cv)
        max_dd = 0
        peak = 0
        for v in running:
            if v > peak:
                peak = v
            dd = peak - v
            if dd > max_dd:
                max_dd = dd
        mean_pnl = sum(pnls) / n
        std_pnl = (sum((p - mean_pnl)**2 for p in pnls) / n) ** 0.5
        sharpe = (mean_pnl / std_pnl * (252**0.5)) if std_pnl > 0 else 0
        return {
            'trades': n,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.wins / n * 100,
            'avg_pnl': mean_pnl,
            'total_pnl': self.total_pnl,
            'max_drawdown': max_dd,
            'profit_factor': wins / losses,
            'sharpe': round(sharpe, 2),
            '_trades': self.trades,
        }