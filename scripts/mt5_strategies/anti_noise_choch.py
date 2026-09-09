"""Anti-noise liquidity-sweep XAUUSD scalp (FXNX style): trade a Change of
Character on M1 confirmed by a displacement candle, filtered by a 9/21 EMA
cross and the London-NY overlap window (13:00-17:00 UTC). Tight 10-15 pip
stop, 1:2 reward-to-risk exit. Signal-only by default; pass --live to trade.

Run:
    python -m scripts.mt5_strategies.anti_noise_choch --once
"""
import time
from datetime import datetime, timezone

import MetaTrader5 as mt5

from scripts.mt5_strategies import mt5_common
from scripts.mt5_strategies.indicators import ema

TIMEFRAME = mt5.TIMEFRAME_M1
FAST_EMA = 9
SLOW_EMA = 21
SWING_LOOKBACK = 20
MAX_SL_PIPS = 15
MIN_SL_PIPS = 10
SESSION_START_UTC = 13
SESSION_END_UTC = 17
MAGIC = 501003


def in_session(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return SESSION_START_UTC <= now.hour < SESSION_END_UTC


def is_displacement_candle(df, i):
    cur = df.iloc[i]
    body = abs(cur["close"] - cur["open"])
    full_range = cur["high"] - cur["low"]
    if full_range == 0:
        return False
    return body / full_range > 0.7


def find_choch(df):
    swing_high = df["high"].iloc[-SWING_LOOKBACK:-1].max()
    swing_low = df["low"].iloc[-SWING_LOOKBACK:-1].min()
    i = len(df) - 1
    cur = df.iloc[i]
    if cur["close"] > swing_high and is_displacement_candle(df, i):
        return "buy", swing_low
    if cur["close"] < swing_low and is_displacement_candle(df, i):
        return "sell", swing_high
    return None, None


def ema_cross_confirms(df, side):
    df = df.copy()
    df["ema_fast"] = ema(df["close"], FAST_EMA)
    df["ema_slow"] = ema(df["close"], SLOW_EMA)
    cur = df.iloc[-1]
    if side == "buy":
        return cur["ema_fast"] > cur["ema_slow"]
    return cur["ema_fast"] < cur["ema_slow"]


def pip_size(symbol: str) -> float:
    info = mt5.symbol_info(symbol)
    digits = info.digits
    return 10 ** (-(digits - 1)) if digits in (3, 5) else info.point


def generate_signal(df, symbol):
    side, structural_level = find_choch(df)
    if side is None:
        return None, None

    if not ema_cross_confirms(df, side):
        return None, None

    pip = pip_size(symbol)
    cur = df.iloc[-1]
    if side == "buy":
        sl = structural_level - pip
    else:
        sl = structural_level + pip

    sl_pips = abs(cur["close"] - sl) / pip
    if not (MIN_SL_PIPS <= sl_pips <= MAX_SL_PIPS):
        return None, None

    return side, sl


def run_once(args):
    if not in_session():
        print("[anti_noise_choch] outside London-NY overlap window, skipping")
        return

    if mt5_common.has_open_position(args.symbol, MAGIC):
        print("[anti_noise_choch] position already open, skipping")
        return

    df = mt5_common.fetch_rates(args.symbol, TIMEFRAME, SWING_LOOKBACK + 30)
    side, sl_price = generate_signal(df, args.symbol)
    if side is None:
        print("[anti_noise_choch] no signal")
        return

    tick = mt5.symbol_info_tick(args.symbol)
    entry_price = tick.ask if side == "buy" else tick.bid
    sl_distance = abs(entry_price - sl_price)
    tp_price = entry_price + 2 * sl_distance if side == "buy" else entry_price - 2 * sl_distance
    volume = mt5_common.position_size(args.symbol, args.risk_pct, sl_distance)

    print(
        f"[anti_noise_choch] {side.upper()} signal, entry~{entry_price}, "
        f"sl={sl_price}, tp={tp_price}, volume={volume}"
    )
    if args.live:
        result = mt5_common.send_market_order(
            args.symbol, side, volume, sl=sl_price, tp=tp_price, magic=MAGIC
        )
        print(result)


def main():
    args = mt5_common.build_arg_parser(__doc__).parse_args()
    mt5_common.connect(args)
    try:
        while True:
            run_once(args)
            if args.once:
                break
            time.sleep(args.interval)
    finally:
        mt5_common.disconnect()


if __name__ == "__main__":
    main()
