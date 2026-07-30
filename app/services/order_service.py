"""
Shared order-checkout logic used by both the web API (routers/orders.py)
and the Telegram bot (services/telegram_bot.py), so both surfaces create
hosted payment sessions the exact same way.
"""
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, PaymentMethod, Plan
from app.services import stripe_gateway


def cancel_pending_order(db: Session, order: Order) -> None:
    order.status = OrderStatus.cancelled
    db.commit()
    db.refresh(order)


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
