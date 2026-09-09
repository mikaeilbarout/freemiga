"""5-1-5 XAUUSD model (FXNX style): identify the dominant liquidity pool on
H1, trigger entries on M5 breakouts of that level during the London-NY
overlap, size the stop at 1.5x the M5 ATR(14). Optionally filtered by DXY
moving inverse to gold. Signal-only by default; pass --live to trade.

Run:
    python -m scripts.mt5_strategies.five_one_five_model --once [--dxy-symbol USDX]
"""
import time
from datetime import datetime, timezone

import MetaTrader5 as mt5

from scripts.mt5_strategies import mt5_common
from scripts.mt5_strategies.indicators import atr

H1_TIMEFRAME = mt5.TIMEFRAME_H1
M5_TIMEFRAME = mt5.TIMEFRAME_M5
STRUCTURE_LOOKBACK = 24
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5
SESSION_START_UTC = 13
SESSION_END_UTC = 17
MAGIC = 501005


def in_session(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return SESSION_START_UTC <= now.hour < SESSION_END_UTC


def liquidity_pool(h1_df):
    recent = h1_df.iloc[-STRUCTURE_LOOKBACK:-1]
    return recent["high"].max(), recent["low"].min()


def dxy_confirms(symbol, side):
    if not symbol:
        return True
    df = mt5_common.fetch_rates(symbol, M5_TIMEFRAME, 5)
    dxy_falling = df["close"].iloc[-1] < df["close"].iloc[-3]
    dxy_rising = df["close"].iloc[-1] > df["close"].iloc[-3]
    if side == "buy":
        return dxy_falling
    return dxy_rising


def generate_signal(h1_df, m5_df):
    pool_high, pool_low = liquidity_pool(h1_df)
    m5_df = m5_df.copy()
    m5_df["atr"] = atr(m5_df, ATR_PERIOD)
    cur = m5_df.iloc[-1]

    if cur["close"] > pool_high:
        return "buy", cur["atr"]
    if cur["close"] < pool_low:
        return "sell", cur["atr"]
    return None, None


def run_once(args):
    if not in_session():
        print("[five_one_five_model] outside London-NY overlap window, skipping")
        return

    if mt5_common.has_open_position(args.symbol, MAGIC):
        print("[five_one_five_model] position already open, skipping")
        return

    h1_df = mt5_common.fetch_rates(args.symbol, H1_TIMEFRAME, STRUCTURE_LOOKBACK + 5)
    m5_df = mt5_common.fetch_rates(args.symbol, M5_TIMEFRAME, ATR_PERIOD + 10)

    side, cur_atr = generate_signal(h1_df, m5_df)
    if side is None:
        print("[five_one_five_model] no signal")
        return

    if not dxy_confirms(args.dxy_symbol, side):
        print("[five_one_five_model] DXY filter rejected signal")
        return

    tick = mt5.symbol_info_tick(args.symbol)
    entry_price = tick.ask if side == "buy" else tick.bid
    sl_distance = cur_atr * ATR_SL_MULTIPLIER
    sl_price = entry_price - sl_distance if side == "buy" else entry_price + sl_distance
    volume = mt5_common.position_size(args.symbol, args.risk_pct, sl_distance)

    print(
        f"[five_one_five_model] {side.upper()} signal, entry~{entry_price}, "
        f"sl={sl_price}, volume={volume}, atr={cur_atr}"
    )
    if args.live:
        result = mt5_common.send_market_order(args.symbol, side, volume, sl=sl_price, magic=MAGIC)
        print(result)


def main():
    parser = mt5_common.build_arg_parser(__doc__)
    parser.add_argument(
        "--dxy-symbol",
        default=None,
        help="Broker symbol for the US Dollar Index, used as a confirmation filter. Omit to skip the filter.",
    )
    args = parser.parse_args()
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
