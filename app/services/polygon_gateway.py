"""
Self-hosted USDT (Polygon) payment verification — same approach as
app/services/tron_gateway.py (a customer-submitted transaction hash is
verified directly on-chain, no third-party payment processor) but for the
Polygon network, using the unified Etherscan V2 API (PolygonScan's own API
was folded into this).

Why offer Polygon alongside Tron: some wallets/apps (e.g. Revolut) cover
gas on Polygon but charge a real network fee plus their own service fee on
Tron, so the customer's actual cost to pay a small order can differ a lot
depending on which network they use — offering both lets them pick
whichever is cheap for their situation.

Standard EVM addresses/hashes throughout (no address-format conversion
needed, unlike Tron).
"""
import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger("polygon_gateway")

USDT_DECIMALS = 6
# keccak256("Transfer(address,address,uint256)") — standard ERC20 Transfer
# event signature, identical across every EVM chain.
TRANSFER_EVENT_SIG = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class PolygonVerificationError(Exception):
    """code is a stable string used to look up a translated error message."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def is_configured() -> bool:
    return bool(settings.POLYGON_USDT_WALLET_ADDRESS and settings.POLYGONSCAN_API_KEY)


def _find_matching_log(logs: list[dict], usdt_contract: str, our_wallet: str, expected_amount: float) -> dict:
    """A transaction can contain more than one Transfer event on the USDT
    contract (e.g. an exchange withdrawal or a smart-contract/batch-wallet
    transaction) — the real payment to our wallet isn't always the first
    matching log, so every candidate is checked instead of just the first
    one found. Raises the most specific error code found across all
    candidates if none of them pays us exactly this order's amount (exact,
    for the same reason as tron_gateway._find_matching_transfer)."""
    expected_units = round(expected_amount * 10 ** USDT_DECIMALS)
    best_code = "not_found"
    for log in logs:
        if log.get("address", "").lower() != usdt_contract:
            continue
        topics = log.get("topics") or []
        if not topics or topics[0].lower() != TRANSFER_EVENT_SIG or len(topics) < 3:
            continue
        if best_code == "not_found":
            best_code = "wrong_recipient"
        # topics[2] is the recipient, left-padded to 32 bytes — the address
        # is the last 40 hex chars (20 bytes).
        recipient = "0x" + topics[2][-40:]
        if recipient.lower() != our_wallet:
            continue
        try:
            units = int(log["data"], 16)
        except (KeyError, ValueError, TypeError):
            continue
        if units < expected_units:
            best_code = "amount_too_low"
            continue
        if units != expected_units:
            best_code = "amount_mismatch"
            continue
        return log
    raise PolygonVerificationError(best_code)


def _get(client: httpx.Client, params: dict) -> dict:
    resp = client.get(
        settings.POLYGONSCAN_API_BASE,
        params={"chainid": settings.POLYGON_CHAIN_ID, "module": "proxy",
                "apikey": settings.POLYGONSCAN_API_KEY, **params},
    )
    resp.raise_for_status()
    return resp.json()


def verify_transaction(tx_hash: str, expected_amount: float) -> datetime:
    """Raises PolygonVerificationError on any failure. On success, returns
    when the transaction was included in a block (UTC)."""
    tx_hash = (tx_hash or "").strip().lower()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    hex_part = tx_hash[2:]
    if len(hex_part) != 64 or any(c not in "0123456789abcdef" for c in hex_part):
        raise PolygonVerificationError("invalid_hash")

    with httpx.Client(timeout=15) as client:
        try:
            data = _get(client, {"action": "eth_getTransactionReceipt", "txhash": tx_hash})
        except httpx.HTTPError:
            logger.exception("PolygonScan receipt lookup failed for %s", tx_hash)
            raise PolygonVerificationError("network_error")

    result = data.get("result")
    if not result:
        # Also covers "not mined yet" — Polygon's ~2s block time makes this
        # a short-lived state, so we don't need a separate "unconfirmed"
        # distinction like Tron's events index gave us.
        raise PolygonVerificationError("not_found")
    if result.get("status") != "0x1":
        raise PolygonVerificationError("failed")

    usdt_contract = settings.USDT_POLYGON_CONTRACT_ADDRESS.lower()
    our_wallet = settings.POLYGON_USDT_WALLET_ADDRESS.lower()

    _find_matching_log(result.get("logs", []), usdt_contract, our_wallet, expected_amount)

    # The receipt has no timestamp — it lives on the block.
    with httpx.Client(timeout=15) as client:
        try:
            block = _get(client, {
                "action": "eth_getBlockByNumber", "tag": result.get("blockNumber"), "boolean": "false",
            }).get("result") or {}
            return datetime.utcfromtimestamp(int(block["timestamp"], 16))
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            logger.exception("PolygonScan block lookup failed for %s", tx_hash)
            raise PolygonVerificationError("network_error")
