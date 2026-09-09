"""Five-filter XAUUSD scalp (xmsignal.com style): M5 EMA20 direction filter,
M1 pullback to an 8 EMA, a closed candlestick reversal pattern at that level,
an RSI(7) exhaustion filter, and a volume-spike confirmation. All five must
align. Signal-only by default; pass --live to trade.

Run:
    python -m scripts.mt5_strategies.five_filter_scalp --once
"""
import time

import MetaTrader5 as mt5

from scripts.mt5_strategies import mt5_common
from scripts.mt5_strategies.indicators import ema, is_bearish_engulfing, is_bullish_engulfing, rsi

M5_TIMEFRAME = mt5.TIMEFRAME_M5
M1_TIMEFRAME = mt5.TIMEFRAME_M1
M5_EMA = 20
M1_EMA = 8
RSI_PERIOD = 7
VOLUME_SPIKE_MULTIPLIER = 1.5
MAGIC = 501002


def macro_direction(m5_df):
    m5_df = m5_df.copy()
    m5_df["ema20"] = ema(m5_df["close"], M5_EMA)
    cur = m5_df.iloc[-1]
    if cur["close"] > cur["ema20"]:
        return "buy"
    if cur["close"] < cur["ema20"]:
        return "sell"
    return None


def generate_signal(m5_df, m1_df):
    direction = macro_direction(m5_df)
    if direction is None:
        return None, None

    m1_df = m1_df.copy()
    m1_df["ema8"] = ema(m1_df["close"], M1_EMA)
    m1_df["rsi"] = rsi(m1_df["close"], RSI_PERIOD)
    m1_df["vol_avg"] = m1_df["tick_volume"].rolling(20).mean()

    i = len(m1_df) - 1
    cur = m1_df.iloc[i]

    pulled_back = abs(cur["low"] - cur["ema8"]) / cur["ema8"] < 0.001 or (
        cur["low"] <= cur["ema8"] <= cur["high"]
    )
    volume_spike = cur["tick_volume"] > cur["vol_avg"] * VOLUME_SPIKE_MULTIPLIER

    if direction == "buy":
        pattern = is_bullish_engulfing(m1_df, i)
        exhausted = cur["rsi"] > 80
        if pulled_back and pattern and volume_spike and not exhausted:
            return "buy", min(cur["low"], m1_df.iloc[i - 1]["low"])
    else:
        pattern = is_bearish_engulfing(m1_df, i)
        exhausted = cur["rsi"] < 20
        if pulled_back and pattern and volume_spike and not exhausted:
            return "sell", max(cur["high"], m1_df.iloc[i - 1]["high"])

    return None, None


def run_once(args):
    if mt5_common.has_open_position(args.symbol, MAGIC):
        print("[five_filter_scalp] position already open, skipping")
        return

    m5_df = mt5_common.fetch_rates(args.symbol, M5_TIMEFRAME, M5_EMA + 20)
    m1_df = mt5_common.fetch_rates(args.symbol, M1_TIMEFRAME, 60)

    side, sl_price = generate_signal(m5_df, m1_df)
    if side is None:
        print("[five_filter_scalp] no signal")
        return

    tick = mt5.symbol_info_tick(args.symbol)
    entry_price = tick.ask if side == "buy" else tick.bid
    sl_distance = abs(entry_price - sl_price)
    volume = mt5_common.position_size(args.symbol, args.risk_pct, sl_distance)
    tp_price = entry_price + 2 * sl_distance if side == "buy" else entry_price - 2 * sl_distance

    print(
        f"[five_filter_scalp] {side.upper()} signal, entry~{entry_price}, "
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
