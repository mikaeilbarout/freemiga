"""Adaptive volatility-filtered XAUUSD scalp (SmartT/comparison-review
style): trades an EMA-cross momentum signal only when ATR volatility is in
a normal band and the spread is tight enough for stable execution, with
stop/target distances scaled to current ATR rather than fixed pips.
Signal-only by default; pass --live to trade.

Run:
    python -m scripts.mt5_strategies.adaptive_volatility_scalp --once
"""
import time

import MetaTrader5 as mt5

from scripts.mt5_strategies import mt5_common
from scripts.mt5_strategies.indicators import atr, ema

TIMEFRAME = mt5.TIMEFRAME_M5
FAST_EMA = 9
SLOW_EMA = 21
ATR_PERIOD = 14
ATR_LOOKBACK = 100
MAX_SPREAD_POINTS = 40
SL_ATR_MULTIPLIER = 1.5
TP_ATR_MULTIPLIER = 3.0
MAGIC = 501004


def volatility_ok(atr_series):
    cur_atr = atr_series.iloc[-1]
    band = atr_series.iloc[-ATR_LOOKBACK:]
    low, high = band.quantile(0.2), band.quantile(0.8)
    return low <= cur_atr <= high


def generate_signal(df):
    df = df.copy()
    df["ema_fast"] = ema(df["close"], FAST_EMA)
    df["ema_slow"] = ema(df["close"], SLOW_EMA)
    df["atr"] = atr(df, ATR_PERIOD)

    if len(df) < ATR_LOOKBACK or not volatility_ok(df["atr"]):
        return None, None

    prev, cur = df.iloc[-2], df.iloc[-1]
    cur_atr = cur["atr"]

    crossed_up = prev["ema_fast"] <= prev["ema_slow"] and cur["ema_fast"] > cur["ema_slow"]
    crossed_down = prev["ema_fast"] >= prev["ema_slow"] and cur["ema_fast"] < cur["ema_slow"]

    if crossed_up:
        return "buy", cur_atr
    if crossed_down:
        return "sell", cur_atr
    return None, None


def run_once(args):
    if mt5_common.has_open_position(args.symbol, MAGIC):
        print("[adaptive_volatility_scalp] position already open, skipping")
        return

    spread = mt5_common.spread_points(args.symbol)
    if spread > MAX_SPREAD_POINTS:
        print(f"[adaptive_volatility_scalp] spread {spread} too wide, skipping")
        return

    df = mt5_common.fetch_rates(args.symbol, TIMEFRAME, ATR_LOOKBACK + 30)
    side, cur_atr = generate_signal(df)
    if side is None:
        print("[adaptive_volatility_scalp] no signal")
        return

    tick = mt5.symbol_info_tick(args.symbol)
    entry_price = tick.ask if side == "buy" else tick.bid
    sl_distance = cur_atr * SL_ATR_MULTIPLIER
    tp_distance = cur_atr * TP_ATR_MULTIPLIER
    sl_price = entry_price - sl_distance if side == "buy" else entry_price + sl_distance
    tp_price = entry_price + tp_distance if side == "buy" else entry_price - tp_distance
    volume = mt5_common.position_size(args.symbol, args.risk_pct, sl_distance)

    print(
        f"[adaptive_volatility_scalp] {side.upper()} signal, entry~{entry_price}, "
        f"sl={sl_price}, tp={tp_price}, volume={volume}, atr={cur_atr}"
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
