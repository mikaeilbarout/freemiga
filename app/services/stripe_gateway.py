"""
Card/bank payment via Stripe Checkout — the fixed-price alternative to the
unique-amount crypto flow. We never touch card details ourselves; Stripe's
hosted Checkout page handles that, and notifies us via a webhook once paid.
"""
import stripe

from app.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def is_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET)


def create_checkout_session(order, plan) -> "stripe.checkout.Session":
    return stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"{plan.name} — {plan.duration_days} days / {plan.data_limit_gb} GB"},
                "unit_amount": round(plan.price_usdt * 100),
            },
            "quantity": 1,
        }],
        client_reference_id=order.id,
        metadata={"order_id": order.id},
        success_url=f"{settings.SITE_BASE_URL}/pay/{order.id}?stripe=success",
        cancel_url=f"{settings.SITE_BASE_URL}/pay/{order.id}?stripe=cancel",
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> "stripe.Event":
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
