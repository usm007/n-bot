"""
Setup definitions — extracted from Articles/strategies/setup*.js
Each SetupConfig mirrors the JS CONFIG objects.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

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
    touch_min_max: Optional[str] = None
    doji_ratio_max: Optional[float] = None
    max_trades_per_day: int = 2
    premium_min_alt: float = 30
    filters: dict = None

    def __post_init__(self):
        if self.filters is None:
            self.filters = {}

SETUPS = [

    # ── 11: Opening Drive ──────────────────────────────────────────
    SetupConfig(
        setup_id='11', setup_name='Opening Drive',
        entry_start_h=9, entry_start_m=16, entry_end_h=9, entry_end_m=25,
        hard_exit_h=10, hard_exit_m=30,
        premium_min=50, premium_max=130,
        sl_pct=0.30, target_pct=0.60,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.5,
        min_body_pct=0.15, max_gap_pct=1.0,
        filters={'vixMin': 11, 'maxGapPct': 1.0, 'minBodyRatio': 0.6,
                 'volumeMultiplier': 1.5, 'minBodyPct': 0.15}
    ),

    # ── 12: Pre-Close Momentum ────────────────────────────────────
    SetupConfig(
        setup_id='12', setup_name='Pre-Close Momentum',
        entry_start_h=14, entry_start_m=15, entry_end_h=14, entry_end_m=45,
        hard_exit_h=15, hard_exit_m=15,
        premium_min=30, premium_max=80,
        sl_pct=0.40, target_pct=0.70,
        capital_min=2500, capital_max=3500,
        vix_min=11, adx_min=20,
        filters={'adxMin': 20, 'vixMin': 11, 'premiumMin': 30}
    ),

    # ── 13: Round Number Bounce ───────────────────────────────────
    SetupConfig(
        setup_id='13', setup_name='Round Number Bounce',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.25, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, round_threshold=0.15, volume_mult=1.2,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.2, 'maxTradesPerDay': 2,
                 'roundThreshold': 0.15}
    ),

    # ── 14: EMA Pullback ───────────────────────────────────────────
    SetupConfig(
        setup_id='14', setup_name='EMA Pullback',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=0,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=100,
        sl_pct=0.20, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, ema_separation_min=0.3, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'emaSeparationMin': 0.3, 'volumeMultiplier': 1.3,
                 'maxTradesPerDay': 2}
    ),

    # ── 15: Bollinger Snapback ─────────────────────────────────────
    SetupConfig(
        setup_id='15', setup_name='Bollinger Snapback',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=0,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=100,
        sl_pct=0.25, target_pct=0.50,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.3, 'maxTradesPerDay': 2}
    ),

    # ── 16: ORB Range ──────────────────────────────────────────────
    SetupConfig(
        setup_id='16', setup_name='ORB Range',
        entry_start_h=9, entry_start_m=20, entry_end_h=10, entry_end_m=0,
        hard_exit_h=10, hard_exit_m=30,
        premium_min=40, premium_max=120,
        sl_pct=0.30, target_pct=0.60,
        capital_min=3000, capital_max=4000,
        vix_min=11, max_gap_pct=0.8,
        filters={'vixMin': 11, 'maxGapPct': 0.8}
    ),

    # ── 17: Volume Climax ──────────────────────────────────────────
    SetupConfig(
        setup_id='17', setup_name='Volume Climax',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.20, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.5,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.5, 'maxTradesPerDay': 2}
    ),

    # ── 18: Mean Reversion ────────────────────────────────────────
    SetupConfig(
        setup_id='18', setup_name='Mean Reversion',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.25, target_pct=0.50,
        capital_min=3000, capital_max=4000,
        vix_min=11, reversal_min=0.5, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'reversalMin': 0.5, 'volumeMultiplier': 1.3,
                 'maxTradesPerDay': 2}
    ),

    # ── 19: First Hour Breakout ───────────────────────────────────
    SetupConfig(
        setup_id='19', setup_name='First Hour Breakout',
        entry_start_h=9, entry_start_m=20, entry_end_h=10, entry_end_m=0,
        hard_exit_h=10, hard_exit_m=30,
        premium_min=40, premium_max=120,
        sl_pct=0.30, target_pct=0.60,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.4,
        filters={'vixMin': 11, 'volumeMultiplier': 1.4}
    ),

    # ── 20: Bar Exhaustion ───────────────────────────────────────
    SetupConfig(
        setup_id='20', setup_name='Bar Exhaustion',
        entry_start_h=12, entry_start_m=0, entry_end_h=14, entry_end_m=0,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=100,
        sl_pct=0.25, target_pct=0.50,
        capital_min=3000, capital_max=4000,
        vix_min=11, doji_ratio_max=0.3, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'dojiRatioMax': 0.3, 'volumeMultiplier': 1.3,
                 'maxTradesPerDay': 2}
    ),

    # ── 21: Pivot Bounce ───────────────────────────────────────────
    SetupConfig(
        setup_id='21', setup_name='Pivot Bounce',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.20, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.3, 'maxTradesPerDay': 2}
    ),

    # ── 22: EMA Crossover ─────────────────────────────────────────
    SetupConfig(
        setup_id='22', setup_name='EMA Crossover',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.25, target_pct=0.50,
        capital_min=3000, capital_max=4000,
        vix_min=11, ema_separation_min=0.3, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'emaSeparationMin': 0.3, 'volumeMultiplier': 1.3,
                 'maxTradesPerDay': 2}
    ),

    # ── 23: Gap and Go ────────────────────────────────────────────
    SetupConfig(
        setup_id='23', setup_name='Gap and Go',
        entry_start_h=9, entry_start_m=15, entry_end_h=10, entry_end_m=0,
        hard_exit_h=10, hard_exit_m=30,
        premium_min=50, premium_max=130,
        sl_pct=0.30, target_pct=0.60,
        capital_min=3000, capital_max=4000,
        vix_min=11, max_gap_pct=0.8, volume_mult=1.5,
        filters={'vixMin': 11, 'maxGapPct': 0.8, 'volumeMultiplier': 1.5}
    ),

    # ── 24: Double Top/Bottom Breakdown ───────────────────────────
    SetupConfig(
        setup_id='24', setup_name='Double Top/Bottom Breakdown',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.25, target_pct=0.50,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.3, 'maxTradesPerDay': 2}
    ),

    # ── 25: Afternoon Range ───────────────────────────────────────
    SetupConfig(
        setup_id='25', setup_name='Afternoon Range',
        entry_start_h=13, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=100,
        sl_pct=0.20, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.2,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.2, 'maxTradesPerDay': 2}
    ),

    # ── 26: EMA VWAP Combo ────────────────────────────────────────
    SetupConfig(
        setup_id='26', setup_name='EMA VWAP Combo',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=0,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=100,
        sl_pct=0.20, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, ema_separation_min=0.3, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'emaSeparationMin': 0.3, 'volumeMultiplier': 1.3,
                 'maxTradesPerDay': 2}
    ),

    # ── 27: VWAP Round ────────────────────────────────────────────
    SetupConfig(
        setup_id='27', setup_name='VWAP Round',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.25, target_pct=0.50,
        capital_min=3000, capital_max=4000,
        vix_min=11, round_threshold=0.15, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'roundThreshold': 0.15, 'volumeMultiplier': 1.3,
                 'maxTradesPerDay': 2}
    ),

    # ── 28: EMA5 Scalp ────────────────────────────────────────────
    SetupConfig(
        setup_id='28', setup_name='EMA5 Scalp',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=0,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=30, premium_max=80,
        sl_pct=0.15, target_pct=0.30,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.3,
        max_trades_per_day=3,
        filters={'vixMin': 11, 'volumeMultiplier': 1.3, 'maxTradesPerDay': 3}
    ),

    # ── 29: RSI2 Extreme ───────────────────────────────────────────
    SetupConfig(
        setup_id='29', setup_name='RSI2 Extreme',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.20, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.3, 'maxTradesPerDay': 2}
    ),

    # ── 30: Afternoon Momentum ────────────────────────────────────
    SetupConfig(
        setup_id='30', setup_name='Afternoon Momentum',
        entry_start_h=13, entry_start_m=30, entry_end_h=14, entry_end_m=45,
        hard_exit_h=15, hard_exit_m=15,
        premium_min=40, premium_max=100,
        sl_pct=0.25, target_pct=0.50,
        capital_min=3000, capital_max=4000,
        vix_min=11, adx_min=20, volume_mult=1.3,
        filters={'vixMin': 11, 'adxMin': 20, 'volumeMultiplier': 1.3}
    ),

    # ── 31: ADX Surge Breakout ────────────────────────────────────
    SetupConfig(
        setup_id='31', setup_name='ADX Surge Breakout',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.20, target_pct=0.40,
        capital_min=3000, capital_max=4000,
        vix_min=11, adx_min=25, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'adxMin': 25, 'volumeMultiplier': 1.3,
                 'maxTradesPerDay': 2}
    ),

    # ── 33: NR7 Breakout ──────────────────────────────────────────
    SetupConfig(
        setup_id='33', setup_name='NR7 Breakout',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.20, target_pct=0.40,
        capital_min=4000, capital_max=4000,
        vix_min=11, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'volumeMultiplier': 1.3, 'maxTradesPerDay': 2}
    ),

    # ── 35: ATR Expansion Breakout ───────────────────────────────
    SetupConfig(
        setup_id='35', setup_name='ATR Expansion Breakout',
        entry_start_h=10, entry_start_m=0, entry_end_h=14, entry_end_m=30,
        hard_exit_h=15, hard_exit_m=0,
        premium_min=40, premium_max=110,
        sl_pct=0.20, target_pct=0.40,
        capital_min=4000, capital_max=4000,
        vix_min=11, adx_min=22, volume_mult=1.3,
        max_trades_per_day=2,
        filters={'vixMin': 11, 'adxMin': 22, 'rangeLookback': 5,
                 'volumeMultiplier': 1.3, 'maxTradesPerDay': 2}
    ),
]