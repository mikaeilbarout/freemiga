import asyncio
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import i18n
from app.auth import get_current_customer
from app.config import settings
from app.database import get_db
from app.lang import get_lang
from app.models import Customer, Order, OrderStatus, PaymentMethod, Plan
from app.schemas import OrderCreate, OrderOut, VerifyPaymentIn
from app.services import marzban, order_service, polygon_gateway, stripe_gateway, tron_gateway

CRYPTO_GATEWAYS = {"tron": tron_gateway, "polygon": polygon_gateway}

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=OrderOut)
async def create_order(
    payload: OrderCreate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    if customer.is_banned:
        reason = customer.ban_reason or i18n.t(lang, "err_account_suspended_generic")
        raise HTTPException(403, i18n.t(lang, "err_account_suspended", reason=reason))
    if not customer.email_verified:
        raise HTTPException(403, i18n.t(lang, "err_verify_email_first"))
    if not customer.terms_accepted_at:
        raise HTTPException(403, i18n.t(lang, "err_terms_not_accepted"))

    plan = db.query(Plan).filter(Plan.id == payload.plan_id, Plan.is_active.is_(True)).first()
    if not plan:
        raise HTTPException(404, i18n.t(lang, "err_plan_not_found"))

    # A customer can only ever be mid-checkout on one thing at a time. Rather
    # than silently cancelling whatever they started before (surprising if
    # they come back to that tab expecting it to still work) or letting a
    # second pending order pile up alongside the first (confusing — two
    # rows in order history both showing "Pay now" / "Cancel"), require an
    # explicit confirm: the client re-sends with confirm_cancel_pending=true
    # once the customer says yes. Mirrors the Telegram bot's existing
    # "cancel & choose again" flow (services/telegram_bot.py) — same
    # situation, same resolution, just adapted to a web request/response
    # instead of a chat prompt.
    pending = (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.status == OrderStatus.pending)
        .first()
    )
    if pending:
        if not payload.confirm_cancel_pending:
            raise HTTPException(
                409,
                {
                    "code": "pending_order_exists",
                    "message": i18n.t(lang, "err_pending_order_exists", plan_name=pending.plan.name),
                    "pending_order_id": pending.id,
                    "pending_plan_name": pending.plan.name,
                },
            )
        order_service.cancel_pending_order(db, pending)

    already_has_account = (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.status == OrderStatus.provisioned)
        .first()
        is not None
    )

    # Free trial plans skip payment entirely and are provisioned
    # immediately instead of going through a checkout session. They can be
    # claimed again, but only after the previous free plan has expired or
    # run out of data (see order_service.has_usable_free_plan).
    if plan.price_usdt == 0:
        # Lock the customer row for the duration of the check-and-create so
        # a fast double-click / retry-before-response can't pass the
        # "no usable free plan" check twice concurrently (both requests
        # would see no prior order before either commits) and end up
        # creating two separate free-plan orders. Released on the commit
        # just below.
        db.query(Customer).filter(Customer.id == customer.id).with_for_update().first()

        if await order_service.has_usable_free_plan(db, customer, plan):
            raise HTTPException(409, i18n.t(lang, "err_free_plan_already_used"))

        order = Order(
            customer_id=customer.id,
            plan_id=plan.id,
            is_renewal=already_has_account,
            payment_method=PaymentMethod.free,
            amount_due=0,
            status=OrderStatus.pending,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.ORDER_EXPIRY_MINUTES),
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Local import to avoid a circular import at module load time
        # (payments.py doesn't import orders.py, so this is safe).
        from app.routers.payments import _mark_paid_and_provision
        await _mark_paid_and_provision(order.id)
        db.refresh(order)

        return OrderOut.model_validate(order)

    try:
        method = PaymentMethod(payload.payment_method)
    except ValueError:
        raise HTTPException(400, i18n.t(lang, "err_invalid_payment_method"))

    if method == PaymentMethod.card and not stripe_gateway.is_configured():
        raise HTTPException(400, i18n.t(lang, "err_card_unavailable"))

    crypto_network = None
    if method == PaymentMethod.crypto:
        crypto_network = (payload.crypto_network or "tron").strip().lower()
        gateway = CRYPTO_GATEWAYS.get(crypto_network)
        if not gateway:
            raise HTTPException(400, i18n.t(lang, "err_invalid_payment_method"))
        if not gateway.is_configured():
            raise HTTPException(400, i18n.t(lang, "err_crypto_unavailable"))

    order = Order(
        customer_id=customer.id,
        plan_id=plan.id,
        is_renewal=already_has_account,  # server decides this, not the client
        payment_method=method,
        crypto_network=crypto_network,
        amount_due=plan.price_usdt,  # fixed price — the gateway tells us which order was paid, not amount matching
        status=OrderStatus.pending,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ORDER_EXPIRY_MINUTES),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    checkout_url = await order_service.create_checkout(db, order, plan)

    result = OrderOut.model_validate(order)
    result.checkout_url = checkout_url
    return result


@router.post("/{order_id}/verify-payment", response_model=OrderOut)
async def verify_payment(
    order_id: str,
    payload: VerifyPaymentIn,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """Customer submits the hash of their on-chain USDT transfer to our
    wallet. Verified directly against the relevant blockchain (recipient,
    amount, contract, success, confirmation) before the order is marked
    paid — see app/services/tron_gateway.py for why a tx hash rather than
    amount-matching is safe even under many concurrent payments. Routes to
    the gateway matching the network the customer chose at checkout
    (order.crypto_network)."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id)
        .first()
    )
    if not order:
        raise HTTPException(404, i18n.t(lang, "err_order_not_found"))
    if order.status != OrderStatus.pending:
        raise HTTPException(409, i18n.t(lang, "err_order_no_longer_pending"))
    if order.payment_method != PaymentMethod.crypto:
        raise HTTPException(400, i18n.t(lang, "err_invalid_payment_method"))

    gateway = CRYPTO_GATEWAYS.get(order.crypto_network or "tron")
    if not gateway:
        raise HTTPException(400, i18n.t(lang, "err_invalid_payment_method"))

    try:
        await run_in_threadpool(gateway.verify_transaction, payload.tx_hash, order.amount_due)
    except (tron_gateway.TronVerificationError, polygon_gateway.PolygonVerificationError) as e:
        raise HTTPException(400, i18n.t(lang, f"err_crypto_{e.code}"))

    # Set tx_hash in its own commit first — the column's unique constraint
    # is what actually prevents the same transaction being credited twice
    # under a race (two requests reusing one hash concurrently); everything
    # else here is defense in depth, not the real guarantee.
    order.tx_hash = payload.tx_hash.strip().lower().removeprefix("0x")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, i18n.t(lang, "err_tx_hash_already_used"))

    from app.routers.payments import _mark_paid_and_provision
    await _mark_paid_and_provision(order.id)
    db.refresh(order)
    return OrderOut.model_validate(order)


@router.post("/{order_id}/checkout", response_model=OrderOut)
async def resume_checkout(
    order_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """Gets a working hosted-payment-page link for a pending order —
    used when the customer returns to the pay page without a cached
    checkout URL (new tab, different device, closed the original one)."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id)
        .first()
    )
    if not order:
        raise HTTPException(404, i18n.t(lang, "err_order_not_found"))
    if order.status != OrderStatus.pending:
        raise HTTPException(409, i18n.t(lang, "err_order_no_longer_pending"))

    plan = db.query(Plan).filter(Plan.id == order.plan_id).first()
    checkout_url = await order_service.create_checkout(db, order, plan)

    result = OrderOut.model_validate(order)
    result.checkout_url = checkout_url
    return result


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """Lets a customer abandon their own pending order — mainly so they can
    switch payment methods (e.g. picked crypto, wants to try card instead)
    without waiting out the full order expiry window."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id)
        .first()
    )
    if not order:
        raise HTTPException(404, i18n.t(lang, "err_order_not_found"))
    if order.status != OrderStatus.pending:
        raise HTTPException(409, i18n.t(lang, "err_only_pending_cancellable"))

    order_service.cancel_pending_order(db, order)
    return order


@router.delete("/{order_id}", response_model=OrderOut)
async def remove_order(
    order_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """Lets a customer delete one of their own plans from the dashboard.
    Its Marzban account is permanently removed (the VPN link stops working
    right away); the order row itself is kept, marked as removed, so order
    history and bookkeeping stay intact. No refund is involved."""
    if customer.is_banned:
        # A suspended customer's accounts are the admin's to manage — see
        # routers/admin.py's ban/unban, which works on provisioned orders.
        reason = customer.ban_reason or i18n.t(lang, "err_account_suspended_generic")
        raise HTTPException(403, i18n.t(lang, "err_account_suspended", reason=reason))

    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id)
        .first()
    )
    if not order:
        raise HTTPException(404, i18n.t(lang, "err_order_not_found"))
    if order.status != OrderStatus.provisioned:
        raise HTTPException(409, i18n.t(lang, "err_only_active_removable"))

    # Delete in Marzban first: if that fails, the order must stay
    # provisioned, or the dashboard would hide a VPN account that still works.
    try:
        await marzban.delete_vpn_user(order.marzban_username)
    except httpx.HTTPError:
        raise HTTPException(502, i18n.t(lang, "err_remove_failed"))

    order.status = OrderStatus.removed
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id)
        .first()
    )
    if not order:
        raise HTTPException(404, i18n.t(lang, "err_order_not_found"))
    return order


@router.get("", response_model=list[OrderOut])
def my_orders(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    # Cancelled orders are excluded on purpose — a customer never
    # deliberately created these (auto-cancelled when they picked a
    # different plan mid-checkout, see create_order's pending-order
    # handling, or from the "cancel" link on a pending order they
    # abandoned) and they carry no useful information for the customer,
    # just noise in their order history.
    return (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.status != OrderStatus.cancelled)
        .order_by(Order.created_at.desc())
        .all()
    )


async def _live_status_for_order(order: Order) -> dict:
    marzban_username = order.marzban_username
    base = {
        "order_id": order.id,
        "plan_id": order.plan_id,
        "plan_name": order.plan.name,
    }
    try:
        data = await marzban.get_vpn_user(marzban_username)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {
                **base, "has_account": False, "subscription_url": None,
                "marzban_status": None, "expire_at": None, "unreachable": False,
            }
        return {
            **base, "has_account": False, "subscription_url": order.subscription_url,
            "marzban_status": None, "expire_at": None, "unreachable": True,
        }
    except httpx.HTTPError:
        return {
            **base, "has_account": False, "subscription_url": order.subscription_url,
            "marzban_status": None, "expire_at": None, "unreachable": True,
        }

    sub_path = data.get("subscription_url") or ""
    expire_ts = data.get("expire")
    return {
        **base,
        "has_account": True,
        "subscription_url": f"{settings.MARZBAN_BASE_URL}{sub_path}" if sub_path else order.subscription_url,
        "marzban_status": data.get("status"),  # "active" | "expired" | "limited" | "disabled"
        "expire_at": datetime.utcfromtimestamp(expire_ts).isoformat() + "Z" if expire_ts else None,
        "unreachable": False,
    }


@router.get("/vpn-status/me")
async def vpn_status(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    """Every provisioned order is its own independent Marzban account (see
    Order.marzban_username) — a plan doesn't share state with any other
    plan the customer bought, so 'is my plan still active' has to be
    answered per order, live from Marzban, rather than picking one
    account to represent the whole customer the way this used to."""
    orders = (
        db.query(Order)
        .options(selectinload(Order.plan))
        .filter(Order.customer_id == customer.id, Order.status == OrderStatus.provisioned)
        .order_by(Order.created_at.desc())
        .all()
    )
    plans = await asyncio.gather(*(_live_status_for_order(o) for o in orders))
    return {"plans": list(plans)}
