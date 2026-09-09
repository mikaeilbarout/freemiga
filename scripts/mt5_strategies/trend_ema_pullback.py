"""Trend-following XAUUSD strategy (AlgoTrader.ch style): ride the trend
defined by the 200 EMA, enter on 50-EMA pullbacks, exit when price closes
back through the 200 EMA. Signal-only by default; pass --live to trade.

Run:
    python -m scripts.mt5_strategies.trend_ema_pullback --once
"""
import time

import MetaTrader5 as mt5

from scripts.mt5_strategies import mt5_common
from scripts.mt5_strategies.indicators import ema

TIMEFRAME = mt5.TIMEFRAME_M15
FAST_EMA = 50
SLOW_EMA = 200
MAGIC = 501001


def generate_signal(df):
    df = df.copy()
    df["ema_fast"] = ema(df["close"], FAST_EMA)
    df["ema_slow"] = ema(df["close"], SLOW_EMA)
    prev, cur = df.iloc[-2], df.iloc[-1]

    uptrend = cur["close"] > cur["ema_slow"]
    downtrend = cur["close"] < cur["ema_slow"]

    pulled_back_up = prev["low"] <= prev["ema_fast"] and cur["close"] > cur["open"] and cur["close"] > cur["ema_fast"]
    pulled_back_down = prev["high"] >= prev["ema_fast"] and cur["close"] < cur["open"] and cur["close"] < cur["ema_fast"]

    if uptrend and pulled_back_up:
        sl = min(prev["low"], cur["low"])
        return "buy", sl
    if downtrend and pulled_back_down:
        sl = max(prev["high"], cur["high"])
        return "sell", sl
    return None, None


def trend_invalidated(df, side):
    cur = df.iloc[-1]
    cur_ema_slow = ema(df["close"], SLOW_EMA).iloc[-1]
    if side == "buy":
        return cur["close"] < cur_ema_slow
    return cur["close"] > cur_ema_slow


def run_once(args):
    df = mt5_common.fetch_rates(args.symbol, TIMEFRAME, SLOW_EMA + 50)

    open_positions = [p for p in mt5.positions_get(symbol=args.symbol) or [] if p.magic == MAGIC]
    for pos in open_positions:
        side = "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell"
        if trend_invalidated(df, side):
            print(f"[trend_ema_pullback] trend invalidated, closing {side} position {pos.ticket}")
            if args.live:
                mt5_common.send_market_order(
                    args.symbol, "sell" if side == "buy" else "buy", pos.volume, magic=MAGIC
                )
        return

    side, sl_price = generate_signal(df)
    if side is None:
        print("[trend_ema_pullback] no signal")
        return

    tick = mt5.symbol_info_tick(args.symbol)
    entry_price = tick.ask if side == "buy" else tick.bid
    sl_distance = abs(entry_price - sl_price)
    volume = mt5_common.position_size(args.symbol, args.risk_pct, sl_distance)

    print(f"[trend_ema_pullback] {side.upper()} signal, entry~{entry_price}, sl={sl_price}, volume={volume}")
    if args.live:
        result = mt5_common.send_market_order(args.symbol, side, volume, sl=sl_price, magic=MAGIC)
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
