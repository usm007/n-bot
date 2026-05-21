"""Core backtesting engine — pure Python, no external deps."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
import math

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

@dataclass
class TradeResult:
    setup_id: str; setup_name: str; direction: str; strike: int
    entry_time: str; entry_price: float; sl_price: float; target_price: float
    exit_time: str = ''; exit_price: float = 0; pnl_pct: float = 0
    exit_reason: str = ''; won: bool = False; capital: float = 0

@dataclass
class BacktestResult:
    setup_id: str; setup_name: str
    total_trades: int = 0; wins: int = 0; losses: int = 0
    win_rate: float = 0; avg_pnl: float = 0; total_pnl: float = 0
    max_dd: float = 0; best_trade: float = 0; worst_trade: float = 0
    trades: List[TradeResult] = field(default_factory=list)

def _atm_strike(spot: float) -> int:
    return round(spot / 50) * 50

def _in_window(h: int, m: int, entry_start_h: int, entry_start_m: int,
              entry_end_h: int, entry_end_m: int) -> bool:
    total = h * 60 + m
    start = entry_start_h * 60 + entry_start_m
    end   = entry_end_h   * 60 + entry_end_m
    return start <= total <= end

def _is_expiry_thursday(dt) -> bool:
    return dt.weekday() == 3

def _estimate_option(spot: float, strike: int, direction: str, iv: float, dt: float) -> float:
    """Simplified ATM option pricing.
    ATM premium ≈ IV * sqrt(T) * spot * 0.4
    ITM adds intrinsic value.
    """
    moneyness = abs(spot - strike) / spot
    base = iv * math.sqrt(dt) * spot * 0.4
    if direction == 'CE' and strike > spot:
        base += (strike - spot)
    elif direction == 'PE' and strike < spot:
        base += (spot - strike)
    return max(base, 1.0)

def _simulate_exit(entry_spot, entry_premium, strike, direction,
                   nifty_df, entry_idx, hard_exit_ts, sl_pct, target_pct):
    """Find when SL/target/hard-exit fires, return (exit_ts, exit_price, reason)."""
    sl_price  = entry_premium * (1 - sl_pct)
    tgt_price = entry_premium * (1 + target_pct)

    future = nifty_df[nifty_df.index > entry_idx]
    for exit_idx, exit_row in future.iterrows():
        if exit_idx > hard_exit_ts:
            return exit_idx, entry_spot, 'hard_exit'

        exit_spot = exit_row['close']
        delta = max(0.1, 0.5 * (1 - abs(exit_spot - strike) / strike))
        opt_price = entry_premium * (exit_spot / entry_spot) * delta

        if opt_price <= sl_price:
            return exit_idx, opt_price, 'sl'
        if opt_price >= tgt_price:
            return exit_idx, opt_price, 'target'

    # Hard exit fallback
    return hard_exit_ts, entry_spot, 'hard_exit'

class Backtester:
    """Iterate 1-min candles, fire setups, simulate option trades."""

    def __init__(self, nifty_df, vix_df, config, setup_name: str, check_fn):
        self.nifty_df = nifty_df.copy()
        self.vix_df    = vix_df.copy()
        self.cfg      = config
        self.name     = setup_name
        self.check_fn = check_fn
        self._prepare()

    def _prepare(self):
        """Build 5-min resample and indicators."""
        import pandas as pd

        df = self.nifty_df

        # Ensure tz-aware
        if hasattr(df.index, 'tz') and df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('Asia/Kolkata')
        elif hasattr(df.index, 'tz') and str(df.index.tz) != 'Asia/Kolkata':
            df = df.index.tz_convert('Asia/Kolkata')

        self.nifty_df = df

        # 5-min resample
        self.candle_5m = df[['open','high','low','close']].resample('5min').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
        }).dropna()

        # Daily
        self.daily = df[['open','high','low','close']].resample('1d').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
        }).dropna()

        # VIX 5-min
        vix = self.vix_df.copy()
        if hasattr(vix.index, 'tz') and vix.index.tz is None:
            vix.index = vix.index.tz_localize('UTC').tz_convert('Asia/Kolkata')
        elif hasattr(vix.index, 'tz') and str(vix.index.tz) != 'Asia/Kolkata':
            vix.index = vix.index.tz_convert('Asia/Kolkata')
        self.vix_df = vix
        self.vix_5m = vix[['close']].resample('5min').last().dropna()

        # Indicators
        from engine.indicators import calc_ema, calc_adx, calc_vwap, calc_rsi, calc_atr, calc_bb

        closes = self.candle_5m['close'].tolist()
        highs  = self.candle_5m['high'].tolist()
        lows   = self.candle_5m['low'].tolist()

        self.ema20  = calc_ema(closes, 20)
        self.ema5   = calc_ema(closes, 5)
        self.adx_vals = calc_adx(highs, lows, closes, 14)['adx']

        candle_tuples = [(i, r['open'], r['high'], r['low'], r['close'], 0)
                          for i, r in self.candle_5m.iterrows()]
        self.vwap_vals = calc_vwap(candle_tuples)

        self.rsi2    = calc_rsi(closes, 2)
        self.atr_vals = calc_atr(highs, lows, closes, 14)
        bb_up, bb_mid, bb_lo = calc_bb(closes, 20, 2.0)
        self.bb_upper = bb_up
        self.bb_mid    = bb_mid
        self.bb_lower  = bb_lo

        self._closes = closes
        self._highs  = highs
        self._lows   = lows

    def _get_indicators(self, ci: int):
        ema20 = self.ema20[ci] if ci < len(self.ema20) else math.nan
        ema5  = self.ema5[ci]  if ci < len(self.ema5)  else math.nan
        adx   = self.adx_vals[ci] if ci < len(self.adx_vals) else math.nan
        vwap  = self.vwap_vals[ci] if ci < len(self.vwap_vals) else math.nan
        rsi2  = self.rsi2[ci] if ci < len(self.rsi2) else math.nan
        atr   = self.atr_vals[ci] if ci < len(self.atr_vals) else math.nan
        return ema20, ema5, adx, vwap, rsi2, atr

    def _get_day_candles(self, ts):
        day_start = ts.replace(hour=9, minute=15, second=0, microsecond=0)
        day_end   = ts.replace(hour=15, minute=30, second=0, microsecond=0)
        mask = (self.candle_5m.index >= day_start) & (self.candle_5m.index <= day_end)
        day_candles = self.candle_5m[mask]
        return [(r.name, r['open'], r['high'], r['low'], r['close'], 0)
                for _, r in day_candles.iterrows()]

    def _get_daily_candles(self, date):
        daily_list = [(r.name, r['open'], r['high'], r['low'], r['close'], 0)
                      for _, r in self.daily.iterrows() if r.name.date() == date]
        return daily_list

    def _get_vix(self, ts) -> float:
        try:
            v = self.vix_5m.loc[:ts]
            return float(v['close'].iloc[-1]) if len(v) > 0 else 12.0
        except Exception:
            return 12.0

    def run(self) -> BacktestResult:
        result = BacktestResult(setup_id=self.cfg.setup_id, setup_name=self.name)
        state  = {'_last_setup_num': self.cfg.setup_id, f's{self.cfg.setup_id}_done': False}

        # Build index list once
        idx_list = list(self.candle_5m.index)
        n_candles = len(idx_list)

        for ci in range(n_candles):
            ts = idx_list[ci]
            h, m = ts.hour, ts.minute

            # Skip non-trading hours
            if h < 9 or (h == 9 and m < 15) or h >= 15:
                continue

            if not _in_window(h, m,
                              self.cfg.entry_start_h, self.cfg.entry_start_m,
                              self.cfg.entry_end_h,   self.cfg.entry_end_m):
                continue

            date = ts.date()
            vix  = self._get_vix(ts)
            spot = self.candle_5m['close'].iloc[ci]
            ema20, ema5, adx, vwap, rsi2, atr = self._get_indicators(ci)

            # Check setup
            if state.get(f's{self.cfg.setup_id}_done'):
                continue

            day_c   = self._get_day_candles(ts)
            daily_c = self._get_daily_candles(date)

            signal = self.check_fn(state, day_c, self._closes[:ci+1],
                                   self._highs[:ci+1], self._lows[:ci+1],
                                   spot, vix, ema20, ema5, adx, vwap, rsi2, atr,
                                   daily_c)

            if not signal or signal.get('status') != 'triggered':
                continue

            state[f's{self.cfg.setup_id}_done'] = True

            direction = signal['direction']
            strike    = signal['strike']

            # Estimate entry premium
            iv   = vix / 100
            premium = _estimate_option(spot, strike, direction, iv, 1.0)
            premium = max(self.cfg.premium_min, min(self.cfg.premium_max, premium))

            sl_price  = premium * (1 - self.cfg.sl_pct)
            target    = premium * (1 + self.cfg.target_pct)

            hard_exit = ts.replace(hour=self.cfg.hard_exit_h,
                                   minute=self.cfg.hard_exit_m,
                                   second=0, microsecond=0)

            exit_ts, exit_price, exit_reason = _simulate_exit(
                spot, premium, strike, direction,
                self.nifty_df, ts, hard_exit,
                self.cfg.sl_pct, self.cfg.target_pct
            )

            pnl_pct = (exit_price - premium) / premium * 100
            won     = pnl_pct > 0

            result.total_trades += 1
            if won: result.wins += 1
            else:   result.losses += 1
            result.total_pnl += pnl_pct
            result.best_trade  = max(result.best_trade, pnl_pct)
            result.worst_trade = min(result.worst_trade, pnl_pct)

            result.trades.append(TradeResult(
                setup_id=self.cfg.setup_id, setup_name=self.name,
                direction=direction, strike=strike,
                entry_time=str(ts), entry_price=premium,
                sl_price=sl_price, target_price=target,
                exit_time=str(exit_ts), exit_price=exit_price,
                pnl_pct=pnl_pct, exit_reason=exit_reason, won=won,
                capital=self.cfg.capital_min,
            ))

        if result.total_trades > 0:
            result.win_rate = result.wins / result.total_trades
            result.avg_pnl  = result.total_pnl / result.total_trades
        return result