from datetime import datetime

import stripe
from fastapi import APIRouter, Header, HTTPException, Request

from app.background import _provision
from app.config import settings
from app.database import SessionLocal
from app.models import Order, OrderStatus
from app.services import nowpayments_gateway, polygon_gateway, stripe_gateway, tron_gateway

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


async def _mark_paid_and_provision(order_id: str) -> None:
    db = SessionLocal()
    try:
        # with_for_update() row-locks the order until commit, so a second
        # concurrent webhook delivery (Stripe/NowPayments both retry) for
        # the same order blocks here instead of racing the pending check
        # below and double-provisioning the VPN account.
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if order and order.status == OrderStatus.pending:
            order.status = OrderStatus.paid
            order.paid_at = datetime.utcnow()
            db.commit()
            await _provision(order, db)
        else:
            db.rollback()
    finally:
        db.close()


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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("order_id")
        if order_id:
            await _mark_paid_and_provision(order_id)

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
        await _mark_paid_and_provision(order_id)

    return {"ok": True}
