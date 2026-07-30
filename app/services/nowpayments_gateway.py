"""
Crypto payment via NowPayments hosted invoice — replaces the old manual
TRC20-wallet + amount-matching flow. NowPayments assigns a unique deposit
address per invoice, so prices stay clean/fixed, and notifies us via an IPN
webhook once paid, matched back to our order by the order_id we send them.
"""
import hashlib
import hmac
import json

import httpx

from app.config import settings


def is_configured() -> bool:
    return bool(settings.NOWPAYMENTS_API_KEY and settings.NOWPAYMENTS_IPN_SECRET)


def create_invoice(order, plan) -> dict:
    resp = httpx.post(
        f"{settings.NOWPAYMENTS_API_BASE}/invoice",
        headers={"x-api-key": settings.NOWPAYMENTS_API_KEY},
        json={
            "price_amount": plan.price_usdt,
            "price_currency": "usd",
            "order_id": order.id,
            "order_description": f"{plan.name} — {plan.duration_days} days / {plan.data_limit_gb} GB",
            "success_url": f"{settings.SITE_BASE_URL}/pay/{order.id}?nowpayments=success",
            "cancel_url": f"{settings.SITE_BASE_URL}/pay/{order.id}?nowpayments=cancel",
            "ipn_callback_url": f"{settings.SITE_BASE_URL}/api/payments/nowpayments/webhook",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def verify_ipn_signature(payload: dict, signature: str) -> bool:
    """
    NowPayments signs the IPN body as compact JSON with keys sorted
    alphabetically, HMAC-SHA512'd with the IPN secret.
    """
    if not signature:
        return False
    ordered = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    computed = hmac.new(
        settings.NOWPAYMENTS_IPN_SECRET.encode(), ordered.encode(), hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(computed, signature)
