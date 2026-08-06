"""
Relays client-observed ad-platform events to server-side conversion APIs
— currently just Reddit (see services/reddit_capi.py for why CAPI needs
this server hop instead of firing directly from the browser: it requires
a secret access token that can't live in client JS).

This never trusts the client for anything that affects ad spend/bidding:
the reported purchase value and the email used for attribution always
come from the authenticated customer's own DB row, never from the
request body — a Purchase event only goes out for an order that's
actually provisioned and actually belongs to the logged-in customer.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_current_customer
from app.database import get_db
from app.models import Customer, Order, OrderStatus
from app.schemas import RedditConversionIn
from app.services import reddit_capi

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


@router.post("/reddit-conversion", status_code=204)
async def reddit_conversion(
    payload: RedditConversionIn,
    request: Request,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if not reddit_capi.is_configured():
        return
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if payload.event_type == "SignUp":
        await reddit_capi.send_event(
            "SignUp",
            email=customer.email,
            click_id=payload.click_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return

    order = (
        db.query(Order)
        .filter(
            Order.id == payload.order_id,
            Order.customer_id == customer.id,
            Order.status == OrderStatus.provisioned,
        )
        .first()
    )
    if not order:
        raise HTTPException(404, "Order not found")
    await reddit_capi.send_event(
        "Purchase",
        email=customer.email,
        click_id=payload.click_id,
        ip_address=ip_address,
        user_agent=user_agent,
        conversion_id=order.id,
        value=order.amount_due,
        currency="USD",
    )
