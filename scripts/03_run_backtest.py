#!/usr/bin/env python3
"""
03_run_backtest.py — Run all 23 setups, print summary table.
Data: backtester/data/{nifty50_1m.csv, vix_1m.csv}
"""
import sys, time
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

import pandas as pd
from engine.backtester import Backtester, _estimate_option, _in_window, _atm_strike
from dataclasses import dataclass
import math

# ── Setup configs ──────────────────────────────────────────────────────────────

@dataclass
class SetupConfig:
    setup_id: str
    entry_start_h: int; entry_end_h: int
    entry_start_m: int = 0; entry_end_m: int = 0
    premium_min: float = 30; premium_max: float = 150
    sl_pct: float = 0.25; target_pct: float = 0.45
    hard_exit_h: int = 15; hard_exit_m: int = 0
    capital_min: float = 3000; capital_max: float = 4000
    max_trades_per_day: int = 1
    vix_min: int = 11; vix_max: int = 0
    adx_min: float = 0; adx_max: float = 0
    volume_mult: float = 0; min_body_pct: float = 0; min_body_ratio: float = 0
    max_gap_pct: float = 0; rsi_max: float = 0; rsi_min: float = 0
    ema_period: int = 0; ema_separation_pct: float = 0
    doji_ratio_max: float = 0; vwap_extreme_pct: float = 0
    nr7_lookback: int = 7; atr_mult: float = 0; expiry_skip: bool = False

SETUPS = [
    # ID, name, entry_start_h/m, entry_end_h/m, premium_min/max, sl%, tgt%, hard_exit_h/m
    ('11', 'Opening Drive',          9, 20, 9, 20, 50, 130, 0.30, 0.60, 10, 30),
    ('12', 'Pre-Close Momentum',   14, 15, 14, 45, 30,  80, 0.40, 0.70, 15, 15),
    ('13', 'Round Number',          9, 15, 9, 30, 50, 150, 0.25, 0.50, 15, 15),
    ('14', 'EMA Pullback',         10,  0, 14, 30, 40, 120, 0.25, 0.50, 15,  0),
    ('15', 'BB Snapback',           9, 20, 15,  0, 30, 100, 0.20, 0.40, 15, 15),
    ('16', 'ORB Range',             9, 15, 15, 30, 40, 100, 0.30, 0.60, 15, 15),
    ('17', 'Volume Climax',        10,  0, 14, 30, 40, 120, 0.25, 0.45, 15,  0),
    ('18', 'Mean Reversion',       10, 30, 14,  0, 40, 100, 0.25, 0.45, 15,  0),
    ('19', 'First Hour Breakout',  10,  0, 11,  0, 40, 120, 0.25, 0.50, 15,  0),
    ('20', 'Bar Exhaustion',       11, 30, 14,  0, 30, 100, 0.25, 0.45, 15,  0),
    ('21', 'Pivot Bounce',         10,  0, 14, 30, 30, 100, 0.25, 0.45, 15,  0),
    ('22', 'EMA Crossover',         9, 30, 15,  0, 40, 110, 0.25, 0.50, 15, 15),
    ('23', 'Gap and Go',            9, 15, 10, 30, 50, 150, 0.30, 0.60, 15,  0),
    ('24', 'Double Top/Bottom',    10,  0, 14, 30, 40, 110, 0.25, 0.45, 15,  0),
    ('25', 'Afternoon Range',      14,  0, 15,  0, 30,  80, 0.30, 0.50, 15, 15),
    ('26', 'EMA VWAP Combo',       10, 30, 14,  0, 40, 110, 0.20, 0.40, 15,  0),
    ('27', 'VWAP Round Combo',     10,  0, 14, 30, 40, 110, 0.20, 0.40, 15,  0),
    ('28', 'EMA5 Scalp',            9, 20, 15,  0, 30, 100, 0.20, 0.35, 15, 15),
    ('29', 'RSI(2) Extreme',        10, 30, 14,  0, 30,  80, 0.20, 0.35, 15,  0),
    ('30', 'Afternoon Momentum',   13,  0, 14, 30, 40, 110, 0.20, 0.35, 15,  0),
    ('31', 'ADX Surge Breakout',   10,  0, 14, 30, 40, 110, 0.20, 0.35, 15,  0),
    ('33', 'NR7 Breakout',         10,  0, 14, 30, 40, 110, 0.25, 0.45, 15,  0),
    ('35', 'ATR Expansion',        10,  0, 14, 30, 40, 110, 0.25, 0.50, 15,  0),
]

# ── Setup check functions ─────────────────────────────────────────────────────

def _cm(c):
    o, h, l, cl = c[1], c[2], c[3], c[4]
    body = abs(cl - o); rng = h - l
    return {'body': body, 'body_pct': body/o*100 if o else 0,
            'range': rng, 'ratio': body/rng if rng else 0,
            'is_green': cl > o, 'open': o}

def _vol_ma(vols, p=20):
    out = []
    for i in range(len(vols)):
        if i < p-1: out.append(math.nan)
        else: out.append(sum(vols[i-p+1:i+1])/p)
    return out

def _ema(closes, p):
    k = 2/(p+1)
    ema = [math.nan]*(p-1)
    if len(closes) >= p:
        ema.append(sum(closes[:p])/p)
        for c in closes[p:]: ema.append(c*k + ema[-1]*(1-k))
    return ema

def _bb(closes, p=20, n=2.0):
    up, mid, lo = [], [], []
    for i in range(len(closes)):
        if i < p-1: up.append(math.nan); mid.append(math.nan); lo.append(math.nan)
        else:
            w = closes[i-p+1:i+1]
            m = sum(w)/p
            v = sum((x-m)**2 for x in w)/p
            s = math.sqrt(v)
            up.append(m+n*s); mid.append(m); lo.append(m-n*s)
    return up, mid, lo

def _entry(sid, direction, strike, setup, state, reason):
    state[f's{sid}_done'] = True
    return {'status': 'triggered', 'direction': direction,
            'strike': strike, 'setup': setup, 'reason': reason}

def check_11(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(9, 20, 9, 20, 9, 20): return None
    if state.get('s11_done') or vix < 11: return None
    if not day_c: return None
    c = day_c[0]; m = _cm(c)
    if m['body_pct'] < 0.15 or m['ratio'] < 0.6: return None
    vols = [x[5] for x in day_c]
    vma = _vol_ma(vols, 20)
    if not (vma and math.isnan(vma[-1]) is False) or (vma[-1] and day_c[0][5] < vma[-1]*1.5): return None
    if daily_c and len(daily_c) >= 2:
        prev_close = daily_c[-2][4]
        gap = abs(day_c[0][1] - prev_close) / prev_close * 100 if prev_close else 0
        if gap >= 1.0: return None
    direction = 'CE' if m['is_green'] else 'PE'
    return _entry('11', direction, _atm_strike(spot), 'Opening Drive', state,
                 f"9:20 Drive {direction}. Body:{m['body_pct']:.2f}%")

def check_12(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(14, 15, 14, 15, 14, 45): return None
    if state.get('s12_done') or vix < 11: return None
    if not adx or adx < 20: return None
    if not vwap or math.isnan(vwap): return None
    dist = abs(spot - vwap)/vwap*100
    if dist > 0.3: return None
    is_bull = spot > vwap; is_bear = spot < vwap
    if not is_bull and not is_bear: return None
    if not day_c: return None
    last = day_c[-1]
    if is_bull and last[4] <= last[1]: return None
    if is_bear and last[4] >= last[1]: return None
    direction = 'CE' if is_bull else 'PE'
    return _entry('12', direction, _atm_strike(spot), 'Pre-Close Momentum', state,
                 f"VWAP {direction}")

def check_13(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s13_done') or vix < 11: return None
    r = spot % 50
    if r >= 5 and r <= 45: return None
    direction = 'CE' if r < 25 else 'PE'
    return _entry('13', direction, _atm_strike(spot), 'Round Number', state,
                 f"Round {direction}")

def check_14(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(10, 0, 14, 0, 14, 30): return None
    if state.get('s14_done') or vix < 11: return None
    if not ema20 or math.isnan(ema20): return None
    if adx and adx > 25: return None
    if not day_c or len(day_c) < 5: return None
    dist = abs(spot - ema20)/ema20*100
    if dist > 0.5: return None
    prev = day_c[-2]
    if abs(prev[3] - ema20)/ema20*100 > 0.3: return None
    m = _cm(day_c[-1])
    if m['ratio'] < 0.7: return None
    direction = 'PE' if m['is_green'] else 'CE'
    return _entry('14', direction, _atm_strike(spot), 'EMA Pullback', state,
                 f"EMA Pullback {direction}")

def check_15(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s15_done') or vix < 11: return None
    if len(closes) < 20: return None
    _, bb_mid, bb_low = _bb(closes, 20, 2.0)
    bb_up = _bb(closes, 20, 2.0)[0]
    lo = bb_low[-1]; up = bb_up[-1]
    if math.isnan(lo) or math.isnan(up): return None
    dl = (spot - lo)/lo*100 if lo else 0
    du = (up - spot)/spot*100 if spot else 0
    if dl < 1.0 and dl > -0.5: direction = 'CE'
    elif du < 1.0 and du > -0.5: direction = 'PE'
    else: return None
    return _entry('15', direction, _atm_strike(spot), 'BB Snapback', state,
                 f"BB Snapback {direction}")

def check_16(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s16_done') or vix < 11: return None
    if len(day_c) < 6: return None
    early = day_c[:6]
    high = max(x[2] for x in early); low = min(x[3] for x in early)
    last = day_c[-1]
    if last[4] > high: direction = 'CE'
    elif last[4] < low: direction = 'PE'
    else: return None
    return _entry('16', direction, _atm_strike(spot), 'ORB Range', state,
                 f"ORB {direction}")

def check_17(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(10, 0, 14, 0, 14, 30): return None
    if state.get('s17_done') or vix < 12: return None
    if not adx or adx > 30: return None
    if not vwap or math.isnan(vwap): return None
    dist = (spot - vwap)/vwap*100
    if abs(dist) < 0.5: return None
    if len(day_c) < 2: return None
    pm = _cm(day_c[-2]); lm = _cm(day_c[-1])
    if pm['ratio'] >= 0.3: return None
    vols = [x[5] for x in day_c]
    vma = _vol_ma(vols, 20)
    if vma and not math.isnan(vma[-2]) and day_c[-2][5] < vma[-2]*2.5: return None
    if dist > 0 and not lm['is_green']: direction = 'PE'
    elif dist < 0 and lm['is_green']: direction = 'CE'
    else: return None
    return _entry('17', direction, _atm_strike(spot), 'Volume Climax', state,
                 f"Volume Climax {direction}. VWAP:{dist:.1f}%")

def check_18(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(10, 30, 14, 0, 14, 0): return None
    if state.get('s18_done') or vix < 11: return None
    if not ema20 or math.isnan(ema20): return None
    dist = abs(spot - ema20)/ema20*100
    if dist < 0.5: return None
    direction = 'PE' if spot > ema20 else 'CE'
    return _entry('18', direction, _atm_strike(spot), 'Mean Reversion', state,
                 f"Mean Reversion {direction}")

def check_19(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(10, 0, 11, 0, 11, 0): return None
    if state.get('s19_done') or vix < 11: return None
    if len(day_c) < 12: return None
    vols = [x[5] for x in day_c[:12]]
    vma = _vol_ma(vols, 20)
    if vma and not math.isnan(vma[-1]) and day_c[-1][5] < vma[-1]*2.0: return None
    m = _cm(day_c[-1])
    direction = 'CE' if m['is_green'] else 'PE'
    return _entry('19', direction, _atm_strike(spot), 'First Hour Breakout', state,
                 f"First Hour {direction}")

def check_20(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(11, 30, 14, 0, 14, 0): return None
    if state.get('s20_done') or vix < 11: return None
    if len(day_c) < 2: return None
    lv = day_c[-1][5] if len(day_c[-1]) > 5 else 0
    pv = day_c[-2][5] if len(day_c[-2]) > 5 else 0
    if lv >= pv: return None
    m = _cm(day_c[-1])
    if m['body_pct'] < 0.5: return None
    direction = 'PE' if m['is_green'] else 'CE'
    return _entry('20', direction, _atm_strike(spot), 'Bar Exhaustion', state,
                 f"Bar Exhaustion {direction}")

def check_21(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s21_done') or vix < 11: return None
    if len(closes) < 2: return None
    pivot = (closes[-1] + closes[-1] + closes[-1]) / 3
    if abs(day_c[-1][4] - pivot)/pivot*100 < 0.3: return None
    direction = 'CE' if day_c[-1][4] > pivot else 'PE'
    return _entry('21', direction, _atm_strike(spot), 'Pivot Bounce', state,
                 f"Pivot Bounce {direction}")

def check_22(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s22_done') or vix < 11: return None
    if len(day_c) < 2: return None
    if math.isnan(ema5) or math.isnan(ema20): return None
    last = day_c[-1]; prev = day_c[-2]
    if last[4] > ema5 and prev[4] <= ema20: direction = 'CE'
    elif last[4] < ema5 and prev[4] >= ema20: direction = 'PE'
    else: return None
    return _entry('22', direction, _atm_strike(spot), 'EMA Crossover', state,
                 f"EMA Crossover {direction}")

def check_23(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(9, 15, 9, 15, 10, 30): return None
    if state.get('s23_done') or vix < 11: return None
    if not day_c or not daily_c or len(daily_c) < 2: return None
    prev_close = daily_c[-2][4]
    gap = abs(day_c[0][1] - prev_close)/prev_close*100 if prev_close else 0
    if gap < 1.0: return None
    direction = 'CE' if day_c[0][4] > day_c[0][1] else 'PE'
    return _entry('23', direction, _atm_strike(spot), 'Gap and Go', state,
                 f"Gap {direction}. Gap:{gap:.1f}%")

def check_24(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s24_done') or vix < 11: return None
    if len(day_c) < 10: return None
    rec = day_c[-10:]
    tops = [c[2] for c in rec]; bots = [c[3] for c in rec]
    top = max(tops); bot = min(bots)
    if sum(1 for t in tops if abs(t-top)/top < 0.001) >= 2: direction = 'PE'
    elif sum(1 for b in bots if abs(b-bot)/bot < 0.001) >= 2: direction = 'CE'
    else: return None
    return _entry('24', direction, _atm_strike(spot), 'Double Top/Bottom', state,
                 f"Double {'Top' if direction=='PE' else 'Bottom'} {direction}")

def check_25(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(14, 0, 14, 0, 15, 0): return None
    if state.get('s25_done') or vix < 11: return None
    if len(day_c) < 12: return None
    rng = day_c[12:24] if len(day_c) >= 24 else day_c
    high = max(x[2] for x in rng); low = min(x[3] for x in rng)
    last = day_c[-1]
    if last[4] > high: direction = 'CE'
    elif last[4] < low: direction = 'PE'
    else: return None
    return _entry('25', direction, _atm_strike(spot), 'Afternoon Range', state,
                 f"Afternoon Range {direction}")

def check_26(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(10, 30, 10, 30, 14, 0): return None
    if state.get('s26_done') or vix < 11: return None
    if math.isnan(ema20) or math.isnan(vwap): return None
    above = spot > ema20 and spot > vwap
    below = spot < ema20 and spot < vwap
    if not above and not below: return None
    m = _cm(day_c[-1]) if day_c else None
    if not m: return None
    if above and m['is_green']: direction = 'CE'
    elif below and not m['is_green']: direction = 'PE'
    else: return None
    return _entry('26', direction, _atm_strike(spot), 'EMA VWAP Combo', state,
                 f"EMA VWAP {direction}")

def check_27(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s27_done') or vix < 11: return None
    if math.isnan(vwap): return None
    rs = spot % 50; rv = vwap % 50
    if not ((rs < 5 or rs > 45) and (abs(rv) < 5)): return None
    direction = 'CE' if spot > vwap else 'PE'
    return _entry('27', direction, _atm_strike(spot), 'VWAP Round Combo', state,
                 f"VWAP Round {direction}")

def check_28(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s28_done') or vix < 11: return None
    if math.isnan(ema5): return None
    if abs(spot - ema5)/ema5*100 > 0.3: return None
    direction = 'CE' if day_c[-1][4] > ema5 else 'PE' if day_c else None
    if not direction: return None
    return _entry('28', direction, _atm_strike(spot), 'EMA5 Scalp', state,
                 f"EMA5 Scalp {direction}")

def check_29(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(10, 30, 10, 30, 14, 0): return None
    if state.get('s29_done') or vix < 11: return None
    if not rsi2 or rsi2 > 30: return None
    if adx and adx < 20: return None
    direction = 'CE' if rsi2 < 30 else 'PE'
    return _entry('29', direction, _atm_strike(spot), 'RSI(2) Extreme', state,
                 f"RSI(2) {direction}")

def check_30(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(13, 0, 13, 0, 14, 30): return None
    if state.get('s30_done') or vix < 11: return None
    if not adx or adx < 28: return None
    if math.isnan(ema20) or math.isnan(vwap): return None
    m = _cm(day_c[-1]) if day_c else None
    if not m: return None
    above = spot > ema20 and spot > vwap
    below = spot < ema20 and spot < vwap
    if above and m['is_green']: direction = 'CE'
    elif below and not m['is_green']: direction = 'PE'
    else: return None
    vols = [x[5] for x in day_c]
    vma = _vol_ma(vols, 20)
    if vma and not math.isnan(vma[-1]) and day_c[-1][5] < vma[-1]*1.5: return None
    return _entry('30', direction, _atm_strike(spot), 'Afternoon Momentum', state,
                 f"Afternoon Momentum {direction}")

def check_31(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if not _in_window(10, 0, 10, 0, 14, 30): return None
    if state.get('s31_done') or vix < 11: return None
    if not adx or adx < 20: return None
    if len(day_c) < 4: return None
    m = _cm(day_c[-1])
    rh = max(x[2] for x in day_c[-4:])
    rl = min(x[3] for x in day_c[-4:])
    if m['is_green'] and day_c[-1][4] > rh: direction = 'CE'
    elif not m['is_green'] and day_c[-1][4] < rl: direction = 'PE'
    else: return None
    vols = [x[5] for x in day_c]
    vma = _vol_ma(vols, 20)
    if vma and not math.isnan(vma[-1]) and day_c[-1][5] < vma[-1]*1.2: return None
    return _entry('31', direction, _atm_strike(spot), 'ADX Surge Breakout', state,
                 f"ADX Surge {direction}")

def check_33(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s33_done') or vix < 11: return None
    if len(day_c) < 8: return None
    today_r = day_c[-1][2] - day_c[-1][3]
    past_r = [day_c[i][2] - day_c[i][3] for i in range(-8, -1)]
    if min(past_r) >= today_r: return None
    direction = 'CE' if day_c[-1][4] > day_c[-1][1] else 'PE'
    return _entry('33', direction, _atm_strike(spot), 'NR7 Breakout', state,
                 f"NR7 {direction}")

def check_35(state, day_c, closes, highs, lows, spot, vix, ema20, ema5, adx, vwap, rsi2, atr, daily_c):
    if state.get('s35_done') or vix < 11: return None
    if not atr or math.isnan(atr): return None
    if len(day_c) < 14: return None
    today_r = day_c[-1][2] - day_c[-1][3]
    if today_r < atr * 1.5: return None
    direction = 'CE' if day_c[-1][4] > day_c[-1][1] else 'PE'
    return _entry('35', direction, _atm_strike(spot), 'ATR Expansion', state,
                 f"ATR Expansion {direction}")

CHECK_FNS = {
    '11': check_11, '12': check_12, '13': check_13, '14': check_14,
    '15': check_15, '16': check_16, '17': check_17, '18': check_18,
    '19': check_19, '20': check_20, '21': check_21, '22': check_22,
    '23': check_23, '24': check_24, '25': check_25, '26': check_26,
    '27': check_27, '28': check_28, '29': check_29, '30': check_30,
    '31': check_31, '33': check_33, '35': check_35,
}

def make_config(sid, name, entry_start_h, entry_start_m, entry_end_h, entry_end_m,
                premium_min, premium_max, sl_pct, target_pct, hard_exit_h, hard_exit_m):
    return SetupConfig(
        setup_id=sid,
        entry_start_h=int(entry_start_h), entry_start_m=int(entry_start_m),
        entry_end_h=int(entry_end_h),     entry_end_m=int(entry_end_m),
        premium_min=float(premium_min), premium_max=float(premium_max),
        sl_pct=float(sl_pct),            target_pct=float(target_pct),
        hard_exit_h=int(hard_exit_h),    hard_exit_m=int(hard_exit_m),
    )

# ── Main runner ────────────────────────────────────────────────────────────────

def load_data():
    nifty = pd.read_csv('data/nifty50_1m.csv', parse_dates=['timestamp'], index_col='timestamp')
    vix   = pd.read_csv('data/vix_1m.csv',  parse_dates=['timestamp'], index_col='timestamp')
    # Data is already UTC+05:30 from Upstox
    try:
        nifty.index = nifty.index.tz_convert('Asia/Kolkata')
        vix.index   = vix.index.tz_convert('Asia/Kolkata')
    except Exception:
        pass
    return nifty, vix

def main():
    print("=" * 95)
    print("  N-Bot Backtester — Nifty 50 Options (All Setups)")
    print("=" * 95)
    nifty_df, vix_df = load_data()
    print(f"\n[Data] Nifty50: {len(nifty_df):,} rows  {nifty_df.index.min()} → {nifty_df.index.max()}")
    print(f"[Data] India VIX: {len(vix_df):,} rows   {vix_df.index.min()} → {vix_df.index.max()}\n")

    rows = []
    for entry in SETUPS:
        sid, name = entry[0], entry[1]
        cfg = make_config(*entry)
        check_fn = CHECK_FNS.get(sid)
        if not check_fn:
            print(f"  [{sid}] {name:<28} | NO CHECK FUNCTION")
            continue

        t0 = time.time()
        try:
            bt = Backtester(nifty_df, vix_df, cfg, name, check_fn)
            res = bt.run()
            elapsed = time.time() - t0
            wr   = res.win_rate * 100
            pnl  = res.avg_pnl
            tot  = res.total_pnl
            print(f"  [{sid:>2}] {name:<28} | "
                  f"Trades: {res.total_trades:<4} | WR: {wr:5.1f}% | "
                  f"Avg: {pnl:>+6.2f}% | Total: {tot:>+7.2f}% | "
                  f"Best: {res.best_trade:>+7.2f}% | Worst: {res.worst_trade:>+8.2f}% | {elapsed:.1f}s")
            rows.append({
                'Setup': f"{sid} {name}",
                'Trades': res.total_trades, 'Wins': res.wins, 'Losses': res.losses,
                'Win Rate': f"{wr:.1f}%", 'Avg PnL': f"{pnl:+.2f}%",
                'Total PnL': f"{tot:+.2f}%",
                'Best': f"{res.best_trade:+.2f}%", 'Worst': f"{res.worst_trade:+.2f}%",
            })
        except Exception as e:
            import traceback
            print(f"  [{sid:>2}] {name:<28} | ERROR: {e}")
            traceback.print_exc()
            rows.append({
                'Setup': f"{sid} {name}",
                'Trades': 0, 'Wins': 0, 'Losses': 0,
                'Win Rate': 'N/A', 'Avg PnL': 'N/A', 'Total PnL': 'N/A',
                'Best': 'N/A', 'Worst': 'N/A',
            })

    import os; os.makedirs('results', exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv('results/all_setups_summary.csv', index=False)
    print(f"\n[DONE] Results → results/all_setups_summary.csv")
    print(df.to_string(index=False))

if __name__ == '__main__':
    main()