"""
Black-Scholes option pricing + Greeks for realistic backtesting.
"""
from __future__ import annotations
import math
from scipy.stats import norm

def bs_price(spot: float, strike: int, iv: float, dt: float, direction: str) -> float:
    """Return option price using Black-Scholes."""
    if dt <= 0:
        # ATM intrinsic at expiry
        if direction == 'CE':
            return max(spot - strike, 0.1)
        else:
            return max(strike - spot, 0.1)

    if iv <= 0:
        return 0.1

    d1 = (math.log(spot / strike) + (0.5 * iv * iv) * dt) / (iv * math.sqrt(dt))
    d2 = d1 - iv * math.sqrt(dt)

    if direction == 'CE':
        price = spot * norm.cdf(d1) - strike * math.exp(-0.05 * dt) * norm.cdf(d2)
    else:
        price = strike * math.exp(-0.05 * dt) * norm.cdf(-d2) - spot * norm.cdf(-d1)

    return max(price, 0.1)


def bs_delta(spot: float, strike: int, iv: float, dt: float, direction: str) -> float:
    """Delta of the option."""
    if dt <= 0 or iv <= 0:
        if direction == 'CE':
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0

    d1 = (math.log(spot / strike) + (0.5 * iv * iv) * dt) / (iv * math.sqrt(dt))
    if direction == 'CE':
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1


def estimate_option_premium(spot: float, strike: int, direction: str, vix: float, dt_frac: float = 1.0) -> float:
    """Estimate ATM option premium using Black-Scholes with VIX as IV.
    dt_frac: fraction of day (1.0 = full day to expiry, 0.041 = 15 min).
    """
    iv = vix / 100
    # For short-dated options (intraday), use dt in years
    dt = dt_frac / 252
    price = bs_price(spot, strike, iv, dt, direction)
    return round(price, 1)


def simulate_exit(spot: float, entry_premium: float, strike: int, direction: str,
                  nifty_df, entry_ts, hard_exit_ts, sl_pct: float, target_pct: float):
    """Simulate option exit based on real price moves using BS delta.
    Returns (exit_ts, exit_price, reason).
    """
    vix = 15.0  # assume avg VIX for simulation

    sl_price  = entry_premium * (1 - sl_pct)
    tgt_price = entry_premium * (1 + target_pct)

    future = nifty_df[nifty_df.index > entry_ts]
    for exit_ts, exit_row in future.iterrows():
        if exit_ts >= hard_exit_ts:
            # Hard exit — estimate P&L at exit time
            exit_price = bs_price(exit_row['close'], strike, vix/100, 0.9/252, direction)
            return exit_ts, round(exit_price, 2), 'hard_exit'

        exit_spot = exit_row['close']
        # True BS option price at this point in time
        dt_remaining = 0.9 / 252  # ~22 min to expiry from 15 min after entry
        exit_price = bs_price(exit_spot, strike, vix/100, dt_remaining, direction)

        if exit_price <= sl_price:
            return exit_ts, round(exit_price, 2), 'sl'
        if exit_price >= tgt_price:
            return exit_ts, round(exit_price, 2), 'target'

    # Hard exit fallback
    last_row = nifty_df[nifty_df.index <= hard_exit_ts].iloc[-1]
    exit_price = bs_price(last_row['close'], strike, vix/100, 0.01/252, direction)
    return exit_ts, round(exit_price, 2), 'hard_exit'