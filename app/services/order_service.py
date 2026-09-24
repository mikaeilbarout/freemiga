"""
Shared order-checkout logic used by both the web API (routers/orders.py)
and the Telegram bot (services/telegram_bot.py), so both surfaces create
hosted payment sessions the exact same way.
"""
import httpx
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.models import Customer, Order, OrderStatus, PaymentMethod, Plan
from app.services import marzban, stripe_gateway

# Marzban statuses that mean an account can still be used. "on_hold" is an
# account that hasn't been connected to yet — its clock hasn't started.
_USABLE_MARZBAN_STATUSES = {"active", "on_hold"}


def cancel_pending_order(db: Session, order: Order) -> None:
    order.status = OrderStatus.cancelled
    db.commit()
    db.refresh(order)


async def has_usable_free_plan(db: Session, customer: Customer, plan: Plan) -> bool:
    """True if the customer still has a free-plan order that isn't used up.

    The free plan can be claimed again, but only once the previous free
    plan has expired or run out of data — never two usable free plans at
    once. An order that is still pending/paid counts as usable (it's about
    to be provisioned). Provisioned orders are checked live in Marzban,
    since expiry and data usage only live there. If Marzban can't be
    reached, this fails closed (counts as usable) rather than handing out
    a second free plan it couldn't verify.

    A free plan the customer deleted themselves (status "removed") doesn't
    count — deleting it frees them to claim a new one right away.
    """
    orders = (
        db.query(Order)
        .filter(
            Order.customer_id == customer.id,
            Order.plan_id == plan.id,
            Order.status.in_([OrderStatus.pending, OrderStatus.paid, OrderStatus.provisioned]),
        )
        .all()
    )
    for order in orders:
        if order.status != OrderStatus.provisioned:
            return True
        try:
            data = await marzban.get_vpn_user(order.marzban_username)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                continue  # account was deleted in Marzban — nothing left to use
            return True
        except httpx.HTTPError:
            return True
        if data.get("status") in _USABLE_MARZBAN_STATUSES:
            return True
    return False


async def create_checkout(db: Session, order: Order, plan: Plan) -> str | None:
    """Creates a fresh hosted-payment-page session for a pending order and
    returns its URL, for payment methods that use an external hosted page.
    Safe to call more than once for the same order (e.g. customer revisits
    the pay page) — the gateway matches whichever session ends up paid back
    to us via order_id.

    Crypto (self-hosted USDT wallet) has no external checkout page — the
    customer pays our fixed wallet address directly and submits their
    transaction hash for verification — so this returns None for crypto;
    the pay page renders the wallet address + tx-hash form instead.

    The Stripe SDK has no async client, so it's run in a threadpool to avoid
    stalling the event loop for other requests while waiting on it."""
    if order.payment_method == PaymentMethod.card:
        session = await run_in_threadpool(stripe_gateway.create_checkout_session, order, plan)
        order.stripe_session_id = session.id
        checkout_url = session.url
        db.commit()
        db.refresh(order)
        return checkout_url
    return None
