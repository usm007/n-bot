"""Setup definitions — ported from the JS strategies."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

@dataclass
class SetupConfig:
    """Runtime config mirror of every JS CONFIG object."""
    setup_id: str
    entry_start_h: int; entry_end_h: int
    entry_start_m: int = 0; entry_end_m: int = 0
    premium_min: float = 30; premium_max: float = 150
    sl_pct: float = 0.25; target_pct: float = 0.45
    hard_exit_h: int = 15; hard_exit_m: int = 0
    capital_min: float = 3000; capital_max: float = 4000
    max_trades_per_day: int = 1
    # Filters
    vix_min: int = 11; vix_max: int = 0
    adx_min: float = 0; adx_max: float = 0
    volume_mult: float = 0
    min_body_pct: float = 0
    min_body_ratio: float = 0
    max_gap_pct: float = 0
    premium_min_alt: float = 0
    rsi_max: float = 0; rsi_min: float = 0
    ema_period: int = 0; ema_separation_pct: float = 0
    doji_ratio_max: float = 0
    vwap_extreme_pct: float = 0
    touch_pct: float = 0
    nr7_lookback: int = 7
    atr_mult: float = 0
    expiry_skip: bool = False

def _in_window(h: int, m: int, start_h: int, start_m: int, end_h: int, end_m: int) -> bool:
    total = h * 60 + m
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    return start <= total <= end

def _gap_pct(open_price: float, prev_close: float) -> float:
    return abs(open_price - prev_close) / prev_close * 100 if prev_close else 0

def _atm_strike(spot: float) -> int:
    return round(spot / 50) * 50

# ── SETUP 11 ─────────────────────────────────────────────────────────────────
SETUP_11 = SetupConfig(
    setup_id='11',
    entry_start_h=9, entry_end_h=9, entry_start_m=20, entry_end_m=20,
    premium_min=50, premium_max=130,
    sl_pct=0.30, target_pct=0.60,
    hard_exit_h=10, hard_exit_m=30,
    vix_min=11, min_body_pct=0.15, min_body_ratio=0.6,
    volume_mult=1.5, max_gap_pct=1.0,
)

def check_setup_11(state, candles_5m, daily_candles, spot, vix) -> Optional[dict]:
    """Opening Drive — 9:20 momentum continuation on first 5-min candle."""
    if not _in_window(9, 20, 9, 20, 9, 20):
        return None
    if state.get('s11_done'): return None
    if vix < SETUP_11.vix_min: return None
    if not candles_5m or len(candles_5m) < 1: return None

    first = candles_5m[0]
    m = _candle_metrics(first)
    body_pct = m['body'] / m['open'] * 100 if m['open'] else 0

    if body_pct < SETUP_11.min_body_pct: return None
    if m['ratio'] < SETUP_11.min_body_ratio: return None

    volumes = [c[5] if len(c) > 5 else 0 for c in candles_5m]
    vol_ma = _volume_ma(volumes, 20)
    last_vol_ma = vol_ma[-1] if vol_ma else None
    if last_vol_ma and first[5] < last_vol_ma * SETUP_11.volume_mult:
        return None

    if daily_candles and len(daily_candles) >= 2:
        prev_close = daily_candles[-2][4]
        gap = _gap_pct(first[1], prev_close)
        if gap >= SETUP_11.max_gap_pct: return None

    direction = 'CE' if m['is_green'] else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Opening Drive', state=state,
                 reason=f"9:20 Drive {direction}. Body:{body_pct:.2f}% Ratio:{m['ratio']:.2f}")

# ── SETUP 12 ─────────────────────────────────────────────────────────────────
SETUP_12 = SetupConfig(
    setup_id='12',
    entry_start_h=14, entry_end_h=14, entry_start_m=15, entry_end_m=45,
    premium_min=30, premium_max=80,
    sl_pct=0.40, target_pct=0.70,
    hard_exit_h=15, hard_exit_m=15,
    vix_min=11, adx_min=20,
)

def check_setup_12(state, candles_5m, spot, vix, adx, vwap_val, vwap_slope) -> Optional[dict]:
    """Pre-Close Momentum — 2:15-2:45 VWAP slope continuation."""
    if not _in_window(14, 15, 14, 15, 14, 45):
        return None
    if state.get('s12_done'): return None
    if vix < SETUP_12.vix_min: return None
    if not adx or adx < SETUP_12.adx_min: return None

    is_bullish = spot > vwap_val and vwap_slope > 0
    is_bearish = spot < vwap_val and vwap_slope < 0
    if not is_bullish and not is_bearish: return None

    dist = abs(spot - vwap_val) / vwap_val * 100 if vwap_val else 0
    if dist > 0.3: return None  # Not near VWAP

    last = candles_5m[-1]
    last_close, last_open = last[4], last[1]
    if is_bullish and last_close <= last_open: return None
    if is_bearish and last_close >= last_open: return None

    direction = 'CE' if is_bullish else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Pre-Close Momentum', state=state,
                 reason=f"2:30 PM VWAP {direction}. ADX:{adx:.1f} slope:{vwap_slope:.2f}%")

# ── SETUP 13 ─────────────────────────────────────────────────────────────────
SETUP_13 = SetupConfig(
    setup_id='13',
    entry_start_h=9, entry_end_h=15, entry_start_m=15, entry_end_m=0,
    premium_min=50, premium_max=150,
    sl_pct=0.25, target_pct=0.50,
    hard_exit_h=15, hard_exit_m=15,
    vix_min=11,
)

def check_setup_13(state, spot) -> Optional[dict]:
    """Round Number — spot near 50-point round level."""
    if state.get('s13_done'): return None
    if not (9 * 60 + 15 <= 9 * 60 + 30 or True): pass  # Window handled externally
    remainder = spot % 50
    near_round = remainder < 5 or remainder > 45
    if not near_round: return None
    direction = 'CE' if remainder < 25 else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Round Number', state=state,
                 reason=f"Round Number {direction} @{spot:.0f}")

# ── SETUP 14 ─────────────────────────────────────────────────────────────────
SETUP_14 = SetupConfig(
    setup_id='14',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=120,
    sl_pct=0.25, target_pct=0.50,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, adx_max=25, volume_mult=1.5, min_body_ratio=0.7,
)

def check_setup_14(state, candles_5m, closes, spot, vix, adx, ema_val) -> Optional[dict]:
    """EMA Rejection — price bounced off 20 EMA."""
    if not _in_window(10, 0, 10, 0, 14, 30):
        return None
    if state.get('s14_done'): return None
    if vix < SETUP_14.vix_min: return None
    if adx > SETUP_14.adx_max: return None  # Not trending

    if not candles_5m or len(candles_5m) < 5: return None
    last = candles_5m[-1]
    prev = candles_5m[-2]

    # Price must be near EMA
    dist_ema = abs(spot - ema_val) / ema_val * 100 if ema_val else 0
    if dist_ema > 0.5: return None

    # Prev candle touches EMA
    prev_touched = (abs(prev[3] - ema_val) / ema_val * 100 < 0.3) if ema_val else False
    if not prev_touched: return None

    m = _candle_metrics(last)
    if m['ratio'] < SETUP_14.min_body_ratio: return None

    volumes = [c[5] if len(c) > 5 else 0 for c in candles_5m]
    vol_ma = _volume_ma(volumes, 20)
    if vol_ma and last[5] < vol_ma[-1] * SETUP_14.volume_mult: return None

    direction = 'PE' if m['is_green'] else 'CE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='EMA Pullback', state=state,
                 reason=f"EMA Pullback {direction}. ADX:{adx:.1f}")

# ── SETUP 15 ─────────────────────────────────────────────────────────────────
SETUP_15 = SetupConfig(
    setup_id='15',
    entry_start_h=9, entry_end_h=15, entry_start_m=20, entry_end_m=0,
    premium_min=30, premium_max=100,
    sl_pct=0.20, target_pct=0.40,
    hard_exit_h=15, hard_exit_m=15,
    vix_min=11,
)

def check_setup_15(state, spot, closes) -> Optional[dict]:
    """Bollinger Band Snapback — price at lower/upper band."""
    if state.get('s15_done'): return None
    if len(closes) < 20: return None
    _, mid, lower = _bb(closes, 20, 2.0)
    if not mid or math.isnan(mid[-1]): return None

    lower_band = lower[-1]
    upper_band = _bb(closes, 20, 2.0)[0][-1]
    dist_lower = (spot - lower_band) / lower_band * 100 if lower_band else 0
    dist_upper = (upper_band - spot) / spot * 100 if spot else 0

    if dist_lower < 1.0 and dist_lower > -0.5:
        direction = 'CE'
    elif dist_upper < 1.0 and dist_upper > -0.5:
        direction = 'PE'
    else:
        return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='BB Snapback', state=state,
                 reason=f"BB Snapback {direction}")

# ── SETUP 16 ─────────────────────────────────────────────────────────────────
SETUP_16 = SetupConfig(
    setup_id='16',
    entry_start_h=9, entry_end_h=15, entry_start_m=15, entry_end_m=30,
    premium_min=40, premium_max=100,
    sl_pct=0.30, target_pct=0.60,
    hard_exit_h=15, hard_exit_m=15,
    vix_min=11,
)

def check_setup_16(state, candles_5m) -> Optional[dict]:
    """ORB Range — breakout of opening range."""
    if state.get('s16_done'): return None
    if len(candles_5m) < 5: return None
    # First 30 mins high/low
    early = candles_5m[:6]
    orb_high = max(c[2] for c in early)
    orb_low = min(c[3] for c in early)
    last = candles_5m[-1]
    if last[4] > orb_high:
        direction = 'CE'
    elif last[4] < orb_low:
        direction = 'PE'
    else:
        return None
    spot = last[4]
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='ORB Range', state=state,
                 reason=f"ORB Breakout {direction}")

# ── SETUP 17 ─────────────────────────────────────────────────────────────────
SETUP_17 = SetupConfig(
    setup_id='17',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=120,
    sl_pct=0.25, target_pct=0.45,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=12, adx_max=30, vwap_extreme_pct=0.5, doji_ratio_max=0.3, volume_mult=2.5,
)

def check_setup_17(state, candles_5m, closes, highs, lows, spot, vix, adx, vwap_arr) -> Optional[dict]:
    """Volume Climax Reversal — VWAP extreme + doji + volume spike."""
    if not _in_window(10, 0, 10, 0, 14, 30): return None
    if state.get('s17_done'): return None
    if vix < SETUP_17.vix_min: return None
    if adx > SETUP_17.adx_max: return None
    if not candles_5m or len(candles_5m) < 22: return None

    vwap_val = vwap_arr[-1] if vwap_arr else None
    if not vwap_val: return None
    vwap_dist = (spot - vwap_val) / vwap_val * 100

    if abs(vwap_dist) < SETUP_17.vwap_extreme_pct: return None

    prev = candles_5m[-2]
    last = candles_5m[-1]
    pm = _candle_metrics(prev)
    if pm['ratio'] >= SETUP_17.doji_ratio_max: return None

    volumes = [c[5] if len(c) > 5 else 0 for c in candles_5m]
    vol_ma = _volume_ma(volumes, 20)
    prev_vol_ma = vol_ma[-2] if vol_ma else None
    if prev_vol_ma and prev[5] < prev_vol_ma * SETUP_17.volume_mult: return None

    # Entry: next candle confirms reversal
    lm = _candle_metrics(last)
    if vwap_dist > 0 and not lm['is_green']:
        direction = 'PE'
    elif vwap_dist < 0 and lm['is_green']:
        direction = 'CE'
    else:
        return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Volume Climax', state=state,
                 reason=f"Volume Climax {direction}. VWAP dist:{vwap_dist:.2f}% ADX:{adx:.1f}")

# ── SETUP 18 ─────────────────────────────────────────────────────────────────
SETUP_18 = SetupConfig(
    setup_id='18',
    entry_start_h=10, entry_end_h=14, entry_start_m=30, entry_end_m=0,
    premium_min=40, premium_max=100,
    sl_pct=0.25, target_pct=0.45,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, ema_period=20,
)

def check_setup_18(state, candles_5m, closes, spot, vix, ema_val) -> Optional[dict]:
    """Mean Reversion — price far from 20 EMA."""
    if not _in_window(10, 30, 10, 30, 14, 0): return None
    if state.get('s18_done'): return None
    if vix < SETUP_18.vix_min: return None
    if not ema_val: return None

    dist = abs(spot - ema_val) / ema_val * 100
    if dist < 0.5: return None  # Not far from EMA

    direction = 'PE' if spot > ema_val else 'CE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Mean Reversion', state=state,
                 reason=f"Mean Reversion {direction}. Dist from EMA:{dist:.2f}%")

# ── SETUP 19 ─────────────────────────────────────────────────────────────────
SETUP_19 = SetupConfig(
    setup_id='19',
    entry_start_h=10, entry_end_h=11, entry_start_m=0, entry_end_m=0,
    premium_min=40, premium_max=120,
    sl_pct=0.25, target_pct=0.50,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, volume_mult=2.0,
)

def check_setup_19(state, candles_5m, closes, spot, vix) -> Optional[dict]:
    """First Hour Breakout — strong candle in first hour."""
    if not _in_window(10, 0, 10, 0, 11, 0): return None
    if state.get('s19_done'): return None
    if vix < SETUP_19.vix_min: return None
    if len(candles_5m) < 12: return None

    first_hour = candles_5m[:12]
    prev_day_close = None
    m = _candle_metrics(first_hour[-1])
    body_pct = m['body'] / m['open'] * 100

    volumes = [c[5] if len(c) > 5 else 0 for c in first_hour]
    vol_ma = _volume_ma(volumes, 20)
    if vol_ma and first_hour[-1][5] < vol_ma[-1] * SETUP_19.volume_mult: return None

    direction = 'CE' if m['is_green'] else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='First Hour Breakout', state=state,
                 reason=f"First Hour Breakout {direction}")

# ── SETUP 20 ─────────────────────────────────────────────────────────────────
SETUP_20 = SetupConfig(
    setup_id='20',
    entry_start_h=11, entry_end_h=14, entry_start_m=30, entry_end_m=0,
    premium_min=30, premium_max=100,
    sl_pct=0.25, target_pct=0.45,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11,
)

def check_setup_20(state, candles_5m, closes, spot, vix, adx) -> Optional[dict]:
    """Bar Exhaustion — big candle with decreasing volume."""
    if not _in_window(11, 30, 11, 30, 14, 0): return None
    if state.get('s20_done'): return None
    if vix < SETUP_20.vix_min: return None
    if len(candles_5m) < 5: return None

    last = candles_5m[-1]
    prev = candles_5m[-2]
    last_v = last[5] if len(last) > 5 else 0
    prev_v = prev[5] if len(prev) > 5 else 0

    if last_v >= prev_v: return None  # Volume should be decreasing
    m = _candle_metrics(last)
    if m['body_pct'] < 0.5: return None

    direction = 'PE' if m['is_green'] else 'CE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Bar Exhaustion', state=state,
                 reason=f"Bar Exhaustion {direction}")

# ── SETUP 21 ─────────────────────────────────────────────────────────────────
SETUP_21 = SetupConfig(
    setup_id='21',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=30, premium_max=100,
    sl_pct=0.25, target_pct=0.45,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11,
)

def check_setup_21(state, candles_5m, closes, spot, vix) -> Optional[dict]:
    """Pivot Bounce — price bounced from daily pivot point."""
    if state.get('s21_done'): return None
    if vix < SETUP_21.vix_min: return None
    if len(candles_5m) < 3: return None

    # Pivot = (prev_high + prev_low + prev_close) / 3
    if len(closes) < 2: return None
    pivot = (closes[-1] + closes[-1] + closes[-1]) / 3  # simplified

    last = candles_5m[-1]
    if abs(last[4] - pivot) / pivot * 100 < 0.3: return None

    direction = 'CE' if last[4] > pivot else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Pivot Bounce', state=state,
                 reason=f"Pivot Bounce {direction}")

# ── SETUP 22 ─────────────────────────────────────────────────────────────────
SETUP_22 = SetupConfig(
    setup_id='22',
    entry_start_h=9, entry_end_h=15, entry_start_m=30, entry_end_m=0,
    premium_min=40, premium_max=110,
    sl_pct=0.25, target_pct=0.50,
    hard_exit_h=15, hard_exit_m=15,
    vix_min=11,
)

def check_setup_22(state, candles_5m, closes, spot, vix, ema_fast, ema_slow) -> Optional[dict]:
    """EMA Crossover — fast EMA crosses slow EMA."""
    if state.get('s22_done'): return None
    if vix < SETUP_22.vix_min: return None
    if len(candles_5m) < 2: return None

    last = candles_5m[-1]
    prev = candles_5m[-2]
    if math.isnan(ema_fast) or math.isnan(ema_slow): return None
    if math.isnan(prev[4]): return None

    # Simple crossover check
    cross_up = last[4] > ema_fast and prev[4] <= ema_slow
    cross_dn = last[4] < ema_fast and prev[4] >= ema_slow

    if cross_up: direction = 'CE'
    elif cross_dn: direction = 'PE'
    else: return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='EMA Crossover', state=state,
                 reason=f"EMA Crossover {direction}")

# ── SETUP 23 ─────────────────────────────────────────────────────────────────
SETUP_23 = SetupConfig(
    setup_id='23',
    entry_start_h=9, entry_end_h=10, entry_start_m=15, entry_end_m=30,
    premium_min=50, premium_max=150,
    sl_pct=0.30, target_pct=0.60,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, max_gap_pct=1.0,
)

def check_setup_23(state, candles_5m, daily_candles, spot, vix) -> Optional[dict]:
    """Gap and Go — price gapped up/down at open."""
    if not _in_window(9, 15, 9, 15, 10, 30): return None
    if state.get('s23_done'): return None
    if vix < SETUP_23.vix_min: return None
    if len(candles_5m) < 1 or len(daily_candles) < 2: return None

    first = candles_5m[0]
    prev_close = daily_candles[-2][4]
    gap = _gap_pct(first[1], prev_close)
    if gap < SETUP_23.max_gap_pct: return None

    direction = 'CE' if first[4] > first[1] else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Gap and Go', state=state,
                 reason=f"Gap and Go {direction}. Gap:{gap:.2f}%")

# ── SETUP 24 ─────────────────────────────────────────────────────────────────
SETUP_24 = SetupConfig(
    setup_id='24',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=110,
    sl_pct=0.25, target_pct=0.45,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11,
)

def check_setup_24(state, candles_5m, closes, spot, vix) -> Optional[dict]:
    """Double Top/Bottom — S/R rejection."""
    if state.get('s24_done'): return None
    if vix < SETUP_24.vix_min: return None
    if len(candles_5m) < 10: return None

    recent = candles_5m[-10:]
    highs = [c[2] for c in recent]
    lows = [c[3] for c in recent]

    # Check for double top (two touches of same resistance)
    top = max(highs)
    top_touches = sum(1 for h in highs if abs(h - top) / top < 0.001)
    if top_touches >= 2:
        direction = 'PE'
    else:
        bottom = min(lows)
        bot_touches = sum(1 for l in lows if abs(l - bottom) / bottom < 0.001)
        if bot_touches >= 2:
            direction = 'CE'
        else:
            return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Double Top/Bottom', state=state,
                 reason=f"Double {'Top' if direction == 'PE' else 'Bottom'} {direction}")

# ── SETUP 25 ─────────────────────────────────────────────────────────────────
SETUP_25 = SetupConfig(
    setup_id='25',
    entry_start_h=14, entry_end_h=15, entry_start_m=0, entry_end_m=0,
    premium_min=30, premium_max=80,
    sl_pct=0.30, target_pct=0.50,
    hard_exit_h=15, hard_exit_m=15,
    vix_min=11,
)

def check_setup_25(state, candles_5m, closes, spot, vix) -> Optional[dict]:
    """Afternoon Range — breakout from range established 1-2 PM."""
    if not _in_window(14, 0, 14, 0, 15, 0): return None
    if state.get('s25_done'): return None
    if vix < SETUP_25.vix_min: return None
    if len(candles_5m) < 12: return None

    range_candles = candles_5m[12:24] if len(candles_5m) >= 24 else candles_5m
    high = max(c[2] for c in range_candles)
    low = min(c[3] for c in range_candles)
    last = candles_5m[-1]

    if last[4] > high:
        direction = 'CE'
    elif last[4] < low:
        direction = 'PE'
    else:
        return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Afternoon Range', state=state,
                 reason=f"Afternoon Range Breakout {direction}")

# ── SETUP 26 ─────────────────────────────────────────────────────────────────
SETUP_26 = SetupConfig(
    setup_id='26',
    entry_start_h=10, entry_end_h=14, entry_start_m=30, entry_end_m=0,
    premium_min=40, premium_max=110,
    sl_pct=0.20, target_pct=0.40,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, ema_period=20,
)

def check_setup_26(state, candles_5m, closes, spot, vix, ema_val, vwap_val) -> Optional[dict]:
    """EMA + VWAP Combo — both aligned."""
    if not _in_window(10, 30, 10, 30, 14, 0): return None
    if state.get('s26_done'): return None
    if vix < SETUP_26.vix_min: return None
    if not ema_val or not vwap_val: return None

    above_both = spot > ema_val and spot > vwap_val
    below_both = spot < ema_val and spot < vwap_val
    if not above_both and not below_both: return None

    last = candles_5m[-1]
    m = _candle_metrics(last)
    direction = 'CE' if (above_both and m['is_green']) else ('PE' if below_both and not m['is_green'] else None)
    if not direction: return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='EMA VWAP Combo', state=state,
                 reason=f"EMA VWAP Combo {direction}")

# ── SETUP 27 ─────────────────────────────────────────────────────────────────
SETUP_27 = SetupConfig(
    setup_id='27',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=110,
    sl_pct=0.20, target_pct=0.40,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11,
)

def check_setup_27(state, candles_5m, spot, vix, vwap_arr) -> Optional[dict]:
    """VWAP Round Combo — spot at VWAP and near round number."""
    if state.get('s27_done'): return None
    if vix < SETUP_27.vix_min: return None
    if not vwap_arr: return None

    vwap_val = vwap_arr[-1]
    remainder_spot = spot % 50
    remainder_vwap = vwap_val % 50 if not math.isnan(vwap_val) else 0
    near_spot = remainder_spot < 5 or remainder_spot > 45
    near_vwap = abs(remainder_vwap) < 5

    if not (near_spot and near_vwap): return None

    direction = 'CE' if spot > vwap_val else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='VWAP Round Combo', state=state,
                 reason=f"VWAP Round Combo {direction}")

# ── SETUP 28 ─────────────────────────────────────────────────────────────────
SETUP_28 = SetupConfig(
    setup_id='28',
    entry_start_h=9, entry_end_h=15, entry_start_m=20, entry_end_m=0,
    premium_min=30, premium_max=100,
    sl_pct=0.20, target_pct=0.35,
    hard_exit_h=15, hard_exit_m=15,
    vix_min=11,
)

def check_setup_28(state, candles_5m, closes, spot, vix) -> Optional[dict]:
    """EMA5 Scalp — quick 5 EMA scalps."""
    if state.get('s28_done'): return None
    if vix < SETUP_28.vix_min: return None
    if len(closes) < 5: return None

    ema5 = _ema(closes, 5)[-1]
    if math.isnan(ema5): return None

    dist = abs(spot - ema5) / ema5 * 100
    if dist > 0.3: return None

    last = candles_5m[-1]
    direction = 'CE' if last[4] > ema5 else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='EMA5 Scalp', state=state,
                 reason=f"EMA5 Scalp {direction}")

# ── SETUP 29 ─────────────────────────────────────────────────────────────────
SETUP_29 = SetupConfig(
    setup_id='29',
    entry_start_h=10, entry_end_h=14, entry_start_m=30, entry_end_m=0,
    premium_min=30, premium_max=80,
    sl_pct=0.20, target_pct=0.35,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, rsi_max=30, adx_min=20,
)

def check_setup_29(state, candles_5m, closes, spot, vix, rsi2, adx) -> Optional[dict]:
    """RSI(2) Extreme — mean reversion from oversold/overbought."""
    if not _in_window(10, 30, 10, 30, 14, 0): return None
    if state.get('s29_done'): return None
    if vix < SETUP_29.vix_min: return None
    if not rsi2 or rsi2 > SETUP_29.rsi_max: return None
    if adx and adx < SETUP_29.adx_min: return None

    direction = 'CE' if rsi2 < 30 else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='RSI(2) Extreme', state=state,
                 reason=f"RSI(2) Extreme {direction}. RSI:{rsi2:.1f}")

# ── SETUP 30 ─────────────────────────────────────────────────────────────────
SETUP_30 = SetupConfig(
    setup_id='30',
    entry_start_h=13, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=110,
    sl_pct=0.20, target_pct=0.35,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, adx_min=28, volume_mult=1.5,
)

def check_setup_30(state, candles_5m, closes, spot, vix, adx, ema_val, vwap_val) -> Optional[dict]:
    """Afternoon Momentum — trend continuation with pullback."""
    if not _in_window(13, 0, 13, 0, 14, 30): return None
    if state.get('s30_done'): return None
    if vix < SETUP_30.vix_min: return None
    if not adx or adx < SETUP_30.adx_min: return None

    last = candles_5m[-1]
    m = _candle_metrics(last)
    body_pct = m['body'] / last[1] if last[1] else 0

    above = spot > ema_val and spot > vwap_val
    below = spot < ema_val and spot < vwap_val
    if above and m['is_green']:
        direction = 'CE'
    elif below and not m['is_green']:
        direction = 'PE'
    else:
        return None

    volumes = [c[5] if len(c) > 5 else 0 for c in candles_5m]
    vol_ma = _volume_ma(volumes, 20)
    if vol_ma and last[5] < vol_ma[-1] * SETUP_30.volume_mult: return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='Afternoon Momentum', state=state,
                 reason=f"Afternoon Momentum {direction}")

# ── SETUP 31 ─────────────────────────────────────────────────────────────────
SETUP_31 = SetupConfig(
    setup_id='31',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=110,
    sl_pct=0.20, target_pct=0.35,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, adx_min=20, volume_mult=1.2,
)

def check_setup_31(state, candles_5m, closes, highs, lows, spot, vix, adx) -> Optional[dict]:
    """ADX Surge Breakout — ADX rising fast + range breakout."""
    if not _in_window(10, 0, 10, 0, 14, 30): return None
    if state.get('s31_done'): return None
    if vix < SETUP_31.vix_min: return None
    if not adx or adx < SETUP_31.adx_min: return None

    if len(candles_5m) < 4: return None
    prev_adx = _adx(highs, lows, closes, 14)[-4] if len(closes) >= 4 else 0
    if (adx - prev_adx) < 3: return None  # No surge

    last = candles_5m[-1]
    m = _candle_metrics(last)
    range_high = max(c[2] for c in candles_5m[-4:])
    range_low = min(c[3] for c in candles_5m[-4:])

    if m['is_green'] and last[4] > range_high:
        direction = 'CE'
    elif not m['is_green'] and last[4] < range_low:
        direction = 'PE'
    else:
        return None

    volumes = [c[5] if len(c) > 5 else 0 for c in candles_5m]
    vol_ma = _volume_ma(volumes, 20)
    if vol_ma and last[5] < vol_ma[-1] * SETUP_31.volume_mult: return None

    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='ADX Surge Breakout', state=state,
                 reason=f"ADX Surge {direction}. ADX:{adx:.1f}")

# ── SETUP 33 ─────────────────────────────────────────────────────────────────
SETUP_33 = SetupConfig(
    setup_id='33',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=110,
    sl_pct=0.25, target_pct=0.45,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, nr7_lookback=7,
)

def check_setup_33(state, candles_5m, closes, spot, vix) -> Optional[dict]:
    """NR7 Breakout — today's range is smallest in last 7 periods."""
    if state.get('s33_done'): return None
    if vix < SETUP_33.vix_min: return None
    if len(candles_5m) < SETUP_33.nr7_lookback + 1: return None

    today_range = candles_5m[-1][2] - candles_5m[-1][3]
    past_ranges = [candles_5m[i][2] - candles_5m[i][3] for i in range(-SETUP_33.nr7_lookback, -1)]
    if min(past_ranges) >= today_range: return None  # Not the smallest

    last = candles_5m[-1]
    direction = 'CE' if last[4] > last[1] else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='NR7 Breakout', state=state,
                 reason=f"NR7 Breakout {direction}")

# ── SETUP 35 ─────────────────────────────────────────────────────────────────
SETUP_35 = SetupConfig(
    setup_id='35',
    entry_start_h=10, entry_end_h=14, entry_start_m=0, entry_end_m=30,
    premium_min=40, premium_max=110,
    sl_pct=0.25, target_pct=0.50,
    hard_exit_h=15, hard_exit_m=0,
    vix_min=11, atr_mult=1.5,
)

def check_setup_35(state, candles_5m, closes, highs, lows, spot, vix, atr_val) -> Optional[dict]:
    """ATR Expansion Breakout — range expanding after compression."""
    if state.get('s35_done'): return None
    if vix < SETUP_35.vix_min: return None
    if not atr_val or math.isnan(atr_val): return None
    if len(candles_5m) < 14: return None

    today_range = candles_5m[-1][2] - candles_5m[-1][3]
    if today_range < atr_val * SETUP_35.atr_mult: return None  # Not expanded

    last = candles_5m[-1]
    direction = 'CE' if last[4] > last[1] else 'PE'
    strike = _atm_strike(spot)
    return _entry(signal='triggered', direction=direction, strike=strike,
                 premium=None, setup='ATR Expansion Breakout', state=state,
                 reason=f"ATR Expansion {direction}")

# ── Master dispatch ─────────────────────────────────────────────────────────

SETUP_CONFIGS = [
    SETUP_11, SETUP_12, SETUP_13, SETUP_14, SETUP_15,
    SETUP_16, SETUP_17, SETUP_18, SETUP_19, SETUP_20,
    SETUP_21, SETUP_22, SETUP_23, SETUP_24, SETUP_25,
    SETUP_26, SETUP_27, SETUP_28, SETUP_29, SETUP_30,
    SETUP_31, SETUP_33, SETUP_35,
]

# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _candle_metrics(c: tuple) -> dict:
    o, h, l, cl = c[1], c[2], c[3], c[4]
    body = abs(cl - o)
    rng = h - l
    return {
        'body': body,
        'body_pct': body / o * 100 if o else 0,
        'range': rng,
        'ratio': body / rng if rng else 0,
        'is_green': cl > o,
        'open': o, 'close': cl, 'high': h, 'low': l,
    }

def _volume_ma(volumes: list, period: int = 20) -> list:
    out = []
    for i in range(len(volumes)):
        if i < period - 1:
            out.append(float('nan'))
        else:
            out.append(sum(volumes[i - period + 1:i + 1]) / period)
    return out

def _ema(closes: list, period: int) -> list:
    k = 2 / (period + 1)
    ema = [float('nan')] * (period - 1)
    if len(closes) >= period:
        ema.append(sum(closes[:period]) / period)
        for price in closes[period:]:
            ema.append(price * k + ema[-1] * (1 - k))
    return ema

def _bb(closes: list, period: int = 20, std_mult: float = 2.0):
    upper, mid, lower = [], [], []
    for i in range(len(closes)):
        if i < period - 1:
            upper.append(float('nan')); mid.append(float('nan')); lower.append(float('nan'))
        else:
            window = closes[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            upper.append(mean + std_mult * std)
            mid.append(mean)
            lower.append(mean - std_mult * std)
    return upper, mid, lower

def _adx(highs: list, lows: list, closes: list, period: int = 14) -> list:
    from engine.indicators import calc_adx
    result = calc_adx(highs, lows, closes, period)
    return result['adx']

def _entry(signal, direction, strike, premium, setup, state, reason) -> dict:
    state[f's{direction[0]}done'] = True  # mark sX_done
    # Map direction to state key
    num = state.get('_last_setup_num', '')
    state[f's{num}_done'] = True
    return {
        'status': signal,
        'setup': setup,
        'direction': direction,
        'strike': strike,
        'entry_price': premium,
        'reason': reason,
    }