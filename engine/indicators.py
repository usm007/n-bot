"""Technical indicators — computed from OHLCV arrays."""
from __future__ import annotations
import math
from typing import List, Tuple

# ── Basic candle metrics ──────────────────────────────────────────────────────

def ohlcv(candle: tuple) -> tuple:
    t, o, h, l, c, v = candle[0], candle[1], candle[2], candle[3], candle[4], candle[5] if len(candle) > 5 else 0
    return o, h, l, c, v

def get_candle_metrics(candle: tuple) -> dict:
    """Returns body, body_pct, range, ratio (body/range), is_green."""
    o, h, l, c, v = ohlcv(candle)
    body  = abs(c - o)
    rng   = h - l
    body_pct = (body / o * 100) if o != 0 else 0
    ratio = (body / rng) if rng != 0 else 0
    return {
        'body': body,
        'body_pct': body_pct,
        'range': rng,
        'ratio': ratio,
        'is_green': c > o,
        'open': o, 'high': h, 'low': l, 'close': c, 'volume': v
    }

def calc_volume_ma(volumes: List[float], period: int = 20) -> List[float]:
    out = []
    for i in range(len(volumes)):
        if i < period - 1:
            out.append(math.nan)
        else:
            out.append(sum(volumes[i - period + 1:i + 1]) / period)
    return out

# ── EMA ─────────────────────────────────────────────────────────────────────

def calc_ema(closes: List[float], period: int) -> List[float]:
    k = 2 / (period + 1)
    ema = [math.nan] * (period - 1)
    if len(closes) >= period:
        ema.append(sum(closes[:period]) / period)
        for price in closes[period:]:
            ema.append(price * k + ema[-1] * (1 - k))
    return ema

# ── VWAP ───────────────────────────────────────────────────────────────────

def calc_vwap(candles: List[tuple]) -> List[float]:
    """Typical-price * cumulative volume approach."""
    vwap, cum_vol = [], 0.0
    for c in candles:
        o, h, l, cl, v = ohlcv(c)
        tp = (o + h + l + cl) / 4
        cum_vol += v
        vwap.append(tp * cum_vol / cum_vol if cum_vol > 0 else math.nan)
    return vwap

def calc_vwap_slope(vwap_arr: List[float], period: int = 6) -> float:
    """Slope of last `period` VWAP values as % of mean."""
    valid = [x for x in vwap_arr[-period:] if not math.isnan(x)]
    if len(valid) < 2:
        return 0.0
    n = len(valid)
    mid = valid[n // 2]
    if mid == 0:
        return 0.0
    return (valid[-1] - valid[0]) / mid * 100

# ── ADX (Average Directional Index) ─────────────────────────────────────────

def calc_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14
             ) -> dict:
    """Returns {'adx': [...], 'pdi': [...], 'mdi': [...]}."""
    if len(closes) < period + 2:
        n = len(closes)
        return {'adx': [math.nan] * n, 'pdi': [math.nan] * n, 'mdi': [math.nan] * n}

    tr_list = [math.nan]
    dm_plus, dm_minus = [math.nan], [math.nan]
    for i in range(1, len(closes)):
        h, l, c, pc = highs[i], lows[i], closes[i], closes[i - 1]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        up = h - highs[i - 1]
        dn = lows[i - 1] - l
        dm_plus.append(max(up, 0) if up > dn else 0)
        dm_minus.append(max(dn, 0) if dn > up else 0)
        tr_list.append(tr)

    def smoothed(data: List[float], period: int) -> List[float]:
        out = [math.nan] * period
        out.append(sum(data[1:period + 1]))
        for i in range(period + 1, len(data)):
            s = out[-1] - out[-1] / period + data[i]
            out.append(s)
        return out

    tr_sm  = smoothed(tr_list, period)
    dmp_sm = smoothed(dm_plus, period)
    dmm_sm = smoothed(dm_minus, period)

    pdi, mdi, adx_vals = [math.nan] * (period + 1), [math.nan] * (period + 1), [math.nan] * (period + 1)
    for i in range(period + 1, len(tr_sm)):
        tr = tr_sm[i]
        pdi_val = dmp_sm[i] / tr * 100 if tr != 0 else 0
        mdi_val = dmm_sm[i] / tr * 100 if tr != 0 else 0
        pdi.append(pdi_val)
        mdi.append(mdi_val)
        dx = abs(pdi_val - mdi_val) / (pdi_val + mdi_val) * 100 if (pdi_val + mdi_val) > 0 else 0
        adx_vals.append(dx)

    # Smooth DX into ADX
    adx_out = [math.nan] * (period + 1)
    adx_out.append(sum(adx_vals[period + 1:2 * period + 1]) / period)
    for i in range(2 * period + 1, len(adx_vals)):
        val = adx_vals[i]
        prev = adx_out[-1]
        adx_out.append(prev + (val - prev) * (1 / period))

    min_len = len(adx_out)
    return {
        'adx': adx_out[:min_len],
        'pdi': pdi[:min_len],
        'mdi': mdi[:min_len]
    }

# ── RSI(2) ───────────────────────────────────────────────────────────────────

def calc_rsi(closes: List[float], period: int = 2) -> List[float]:
    if len(closes) < period + 1:
        return [math.nan] * len(closes)
    rsi = [math.nan] * period
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi.append(100 - 100 / (1 + rs))
    return rsi

# ── Bollinger Bands ─────────────────────────────────────────────────────────

def calc_bb(closes: List[float], period: int = 20, std_mult: float = 2.0
           ) -> Tuple[List[float], List[float], List[float]]:
    mid = []
    for i in range(len(closes)):
        if i < period - 1:
            mid.append(math.nan)
        else:
            window = closes[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            mid.append(mean)
    upper = [m + std_mult * (math.sqrt(variance if (v := sum((x - m) ** 2 for x in closes[max(0, i - period + 1):i + 1]) / period) != 0 else 0) if not math.isnan(m) else math.nan) if not math.isnan(m) else math.nan for i, m in enumerate(mid)]
    lower = [m - std_mult * (math.sqrt(variance if (v := sum((x - m) ** 2 for x in closes[max(0, i - period + 1):i + 1]) / period) != 0 else 0) if not math.isnan(m) else math.nan) if not math.isnan(m) else math.nan for i, m in enumerate(mid)]
    # Simplified — recalculate properly
    upper, lower = [], []
    for i in range(len(closes)):
        if i < period - 1:
            upper.append(math.nan); lower.append(math.nan)
        else:
            window = closes[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            upper.append(mean + std_mult * std)
            lower.append(mean - std_mult * std)
    return upper, mid, lower

# ── ATR ─────────────────────────────────────────────────────────────────────

def calc_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14
            ) -> List[float]:
    if len(closes) < period + 1:
        return [math.nan] * len(closes)
    tr = [math.nan]
    for i in range(1, len(closes)):
        h, l, c, pc = highs[i], lows[i], closes[i], closes[i - 1]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = [math.nan] * period
    atr.append(sum(tr[1:period + 1]) / period)
    for i in range(period + 1, len(tr)):
        atr.append((atr[-1] * (period - 1) + tr[i]) / period)
    return atr