"""
Self-hosted USDT (TRC20) payment verification. We hold only a PUBLIC
receiving address (TRON_USDT_WALLET_ADDRESS) — never a private key — and
verify customer-submitted transaction hashes directly against the Tron
blockchain via TronGrid. This replaces NowPayments for crypto checkout,
whose per-transaction minimums (~$11+ across every network, as of writing)
made it unusable for plans priced under $10.

Why a transaction hash instead of amount-matching: a tx hash is unique by
construction (derived from the transaction's own contents + signature), so
there's no ambiguity even if many customers pay the exact same amount at
the exact same time — unlike the old amount-matching approach this project
used before NowPayments, which needed decimal-adjusted prices to
disambiguate concurrent payments to a shared address.
"""
import hashlib
import logging

import httpx

from app.config import settings

logger = logging.getLogger("tron_gateway")

USDT_DECIMALS = 6
_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class TronVerificationError(Exception):
    """code is a stable string used to look up a translated error message."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def is_configured() -> bool:
    return bool(settings.TRON_USDT_WALLET_ADDRESS and settings.TRONGRID_API_KEY)


def _hex_to_base58(hex_addr: str) -> str:
    """Tron addresses in TronGrid event payloads come back as raw 20-byte
    EVM-style hex (no 0x41 version byte, unlike Tron's own wallet API). We
    normalize by prepending the Tron mainnet version byte (0x41) and
    base58check-encoding, then compare against our configured T... address."""
    hex_addr = hex_addr[2:] if hex_addr.startswith("0x") else hex_addr
    if not hex_addr.startswith("41"):
        hex_addr = "41" + hex_addr
    payload = bytes.fromhex(hex_addr)
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    data = payload + checksum
    num = int.from_bytes(data, "big")
    encoded = ""
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = _ALPHABET[rem] + encoded
    n_leading_zeros = len(data) - len(data.lstrip(b"\x00"))
    return "1" * n_leading_zeros + encoded


def _headers() -> dict:
    return {"TRON-PRO-API-KEY": settings.TRONGRID_API_KEY} if settings.TRONGRID_API_KEY else {}


def verify_transaction(tx_hash: str, expected_amount: float) -> None:
    """Raises TronVerificationError on any failure. Returns None on success."""
    tx_hash = (tx_hash or "").strip().lower().removeprefix("0x")
    if not tx_hash or len(tx_hash) != 64 or any(c not in "0123456789abcdef" for c in tx_hash):
        raise TronVerificationError("invalid_hash")

    with httpx.Client(timeout=15, headers=_headers()) as client:
        try:
            events_resp = client.get(
                f"{settings.TRONGRID_API_BASE}/v1/transactions/{tx_hash}/events"
            )
            events_resp.raise_for_status()
            events = events_resp.json()
        except httpx.HTTPError:
            logger.exception("TronGrid events lookup failed for %s", tx_hash)
            raise TronVerificationError("network_error")

    transfers = [
        e for e in events.get("data", [])
        if e.get("event_name") == "Transfer" and e.get("contract_address") == settings.USDT_TRC20_CONTRACT_ADDRESS
    ]
    if not transfers:
        raise TronVerificationError("not_found")

    transfer = transfers[0]
    if transfer.get("_unconfirmed"):
        raise TronVerificationError("unconfirmed")

    result = transfer.get("result", {})
    try:
        recipient = _hex_to_base58(result["to"])
        amount = int(result["value"]) / (10 ** USDT_DECIMALS)
    except (KeyError, ValueError):
        raise TronVerificationError("not_found")

    if recipient != settings.TRON_USDT_WALLET_ADDRESS:
        raise TronVerificationError("wrong_recipient")
    if amount < expected_amount:
        raise TronVerificationError("amount_too_low")

    with httpx.Client(timeout=15, headers=_headers()) as client:
        try:
            info_resp = client.post(
                f"{settings.TRONGRID_API_BASE}/wallet/gettransactioninfobyid",
                json={"value": tx_hash},
            )
            info_resp.raise_for_status()
            info = info_resp.json()
        except httpx.HTTPError:
            logger.exception("TronGrid transaction info lookup failed for %s", tx_hash)
            raise TronVerificationError("network_error")

    if not info or info.get("receipt", {}).get("result") != "SUCCESS":
        raise TronVerificationError("failed")
