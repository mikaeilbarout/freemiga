"""Shared MetaTrader5 connection, data-fetch, sizing and order-send helpers.

Requires the `MetaTrader5` and `pandas` packages and a running MT5 terminal
(Windows only). Credentials come from CLI flags or the MT5_LOGIN /
MT5_PASSWORD / MT5_SERVER / MT5_PATH environment variables.
"""
import argparse
import os

import pandas as pd

import MetaTrader5 as mt5

DEFAULT_SYMBOL = "XAUUSD"


def build_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--login", type=int, default=_env_int("MT5_LOGIN"))
    parser.add_argument("--password", default=os.environ.get("MT5_PASSWORD"))
    parser.add_argument("--server", default=os.environ.get("MT5_SERVER"))
    parser.add_argument("--path", default=os.environ.get("MT5_PATH"))
    parser.add_argument(
        "--risk-pct",
        type=float,
        default=0.5,
        help="Percent of account balance risked per trade (default 0.5).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between checks when running continuously (default 60).",
    )
    parser.add_argument(
        "--once", action="store_true", help="Evaluate the strategy a single time and exit."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually send orders. Without this flag the script only prints signals.",
    )
    return parser


def _env_int(name: str):
    value = os.environ.get(name)
    return int(value) if value else None


def connect(args: argparse.Namespace) -> None:
    if not mt5.initialize(
        path=args.path, login=args.login, password=args.password, server=args.server
    ):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")


def disconnect() -> None:
    mt5.shutdown()


def fetch_rates(symbol: str, timeframe: int, count: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Failed to fetch rates for {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def spread_points(symbol: str) -> float:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info failed for {symbol}: {mt5.last_error()}")
    return info.spread


def position_size(symbol: str, risk_pct: float, sl_distance_price: float) -> float:
    account = mt5.account_info()
    info = mt5.symbol_info(symbol)
    if account is None or info is None:
        raise RuntimeError(f"account_info/symbol_info failed: {mt5.last_error()}")
    if sl_distance_price <= 0 or info.trade_tick_size == 0:
        return info.volume_min
    risk_amount = account.balance * (risk_pct / 100)
    value_per_price_unit = info.trade_tick_value / info.trade_tick_size
    volume = risk_amount / (sl_distance_price * value_per_price_unit)
    step = info.volume_step or 0.01
    volume = round(volume / step) * step
    return max(info.volume_min, min(info.volume_max, round(volume, 2)))


def send_market_order(
    symbol: str,
    side: str,
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 20,
    magic: int = 0,
    comment: str = "",
):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"symbol_info_tick failed for {symbol}: {mt5.last_error()}")
    price = tick.ask if side == "buy" else tick.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if sl is not None:
        request["sl"] = sl
    if tp is not None:
        request["tp"] = tp
    return mt5.order_send(request)


def has_open_position(symbol: str, magic: int) -> bool:
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return False
    return any(p.magic == magic for p in positions)
