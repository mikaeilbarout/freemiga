import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Header, HTTPException, Request

from app.background import _provision
from app.config import settings
from app.database import SessionLocal
from app.models import Order, OrderStatus
from app.services import nowpayments_gateway, polygon_gateway, stripe_gateway, telegram, tron_gateway
from app.services.order_service import PAYABLE_STATUSES

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/methods")
def payment_methods():
    tron_ok = tron_gateway.is_configured()
    polygon_ok = polygon_gateway.is_configured()
    return {
        "crypto": tron_ok or polygon_ok,
        "card": stripe_gateway.is_configured(),
        # Legacy field — kept for any old cached frontend, mirrors "tron".
        "crypto_wallet_address": settings.TRON_USDT_WALLET_ADDRESS if tron_ok else None,
        "crypto_networks": {
            "tron": settings.TRON_USDT_WALLET_ADDRESS if tron_ok else None,
            "polygon": settings.POLYGON_USDT_WALLET_ADDRESS if polygon_ok else None,
        },
    }


async def _mark_paid_and_provision(order_id: str, payment_received: bool = False) -> None:
    """payment_received=True means real money was confirmed (card, crypto,
    Stars). Such a payment is credited even if the order already expired or
    was cancelled — e.g. the customer switched plans on the site but still
    paid in the old Stripe tab. Before, that payment was silently dropped:
    money taken, no plan, nobody told. Free claims and admin grants pass
    False and only ever act on a pending order."""
    db = SessionLocal()
    try:
        # with_for_update() row-locks the order until commit, so a second
        # concurrent webhook delivery (Stripe/NowPayments both retry) for
        # the same order blocks here instead of racing the status check
        # below and double-provisioning the VPN account.
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        allowed = PAYABLE_STATUSES if payment_received else (OrderStatus.pending,)
        if not order or order.status not in allowed:
            db.rollback()
            return

        previous_status = order.status
        customer = order.customer
        order.status = OrderStatus.paid
        order.paid_at = datetime.utcnow()
        db.commit()

        if customer.is_banned or customer.is_deleted:
            # Provisioning would hand an active VPN account to a suspended
            # (or deleted) account. Keep it paid and let the admin decide:
            # refund, or confirm it by hand from the admin panel.
            await _notify_admin_safely(
                f"⚠️ Payment received for order {order.id}, but the customer "
                f"({customer.username}) is {'deleted' if customer.is_deleted else 'suspended'} — "
                "NOT provisioned. Refund it or confirm it manually from the admin panel."
            )
            return
        if previous_status != OrderStatus.pending:
            await _notify_admin_safely(
                f"ℹ️ Payment arrived for order {order.id} ({customer.username}) after it was "
                f"{previous_status.value} — provisioned anyway."
            )

        await _provision(order, db)
    finally:
        db.close()


async def _notify_admin_safely(text: str) -> None:
    try:
        await telegram.notify_admin(text)
    except Exception:
        logging.getLogger("payments").exception("Failed to send admin notice")


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None, alias="Stripe-Signature")):
    if not stripe_gateway.is_configured():
        # Without this, an unset STRIPE_WEBHOOK_SECRET means
        # construct_webhook_event verifies against an empty-string key —
        # trivially forgeable by anyone, since HMAC with a known (empty)
        # key is no security at all. Reject outright instead.
        raise HTTPException(503, "Stripe integration not configured")
    payload = await request.body()
    try:
        event = stripe_gateway.construct_webhook_event(payload, stripe_signature)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")

    if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("order_id")
        # "completed" only means the customer finished the checkout form —
        # for delayed payment methods the money may not have arrived yet
        # (it's then confirmed later by async_payment_succeeded).
        if order_id and session.get("payment_status") == "paid":
            await _mark_paid_and_provision(order_id, payment_received=True)

    return {"ok": True}


@router.post("/nowpayments/webhook")
async def nowpayments_webhook(
    request: Request,
    x_nowpayments_sig: str = Header(None, alias="x-nowpayments-sig"),
):
    if not nowpayments_gateway.is_configured():
        # Critical: without this, an unset NOWPAYMENTS_IPN_SECRET (the
        # current state — see config.py, this gateway is legacy and no
        # invoice is ever created through it anymore) means
        # verify_ipn_signature checks a submitted signature against an
        # HMAC computed with an empty-string key. Anyone can compute that
        # exact same HMAC themselves with no secret knowledge at all, so
        # this endpoint would accept a forged "payment_status": "finished"
        # for ANY pending order_id — a complete, unauthenticated payment
        # bypass. Reject outright unless a real IPN secret is configured.
        raise HTTPException(503, "NowPayments integration not configured")
    payload = await request.json()
    if not nowpayments_gateway.verify_ipn_signature(payload, x_nowpayments_sig):
        raise HTTPException(400, "Invalid IPN signature")

    order_id = payload.get("order_id")
    status = payload.get("payment_status")
    if order_id and status == "finished":
        await _mark_paid_and_provision(order_id, payment_received=True)

    return {"ok": True}
