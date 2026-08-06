import logging

from app.models import Order, OrderStatus
from app.services import marzban, marzban_guard, telegram

logger = logging.getLogger("payment_poller")


async def _notify(coro, description: str, order_id: str) -> None:
    # Notifications are best-effort — a Telegram/network hiccup here must
    # never propagate up and overwrite an order status that provisioning
    # (or the failure path) has already committed to the DB.
    try:
        await coro
    except Exception:
        logger.exception("Failed to send %s for order %s", description, order_id)


async def _provision(order: Order, db) -> None:
    plan = order.plan
    customer = order.customer
    marzban_username = order.marzban_username
    try:
        # Always create — never extend an existing account. Every order is
        # its own independent Marzban account (order.marzban_username is
        # unique per order), specifically so that a customer buying a
        # second, different plan gets a second, independent VPN account
        # instead of that purchase's data/duration getting merged into
        # whatever they already had. create_vpn_user's own 409 fallback
        # still covers the narrow case of retrying a provisioning attempt
        # for this exact order after a prior partial failure.
        result = await marzban.create_vpn_user(
            username=marzban_username,
            data_limit_gb=plan.data_limit_gb,
            duration_days=plan.duration_days,
        )
        order.subscription_url = result["subscription_url"]
        order.status = OrderStatus.provisioned
        logger.info("Provisioned VPN for order %s (marzban user %s)", order.id, marzban_username)
    except Exception:
        logger.exception("Failed to provision Marzban user for order %s", order.id)
        order.status = OrderStatus.failed
        db.commit()
        await _notify(
            telegram.notify_admin(
                f"🔴 Failed to create/renew account for {customer.username} (order {order.id}) — please check."
            ),
            "admin failure alert", order.id,
        )
        if customer.telegram_chat_id:
            await _notify(
                telegram.send_message(
                    customer.telegram_chat_id,
                    "⚠️ Your payment was received, but something went wrong setting up/renewing "
                    "your account. Please contact support from the site.",
                ),
                "customer failure alert", order.id,
            )
        return

    db.commit()

    # +2 over the plan's own advertised limit: marzban-guard's device count
    # is a distinct-client-IP proxy, not a real device count, so ordinary
    # network roaming (Wi-Fi/cellular handoff, a carrier IP rotating
    # mid-session) can look like extra "devices" for a customer who only
    # ever uses exactly their allowed number of devices. This buys that
    # margin back without loosening what the plan is actually sold as.
    # None (no configured limit) stays None — nothing to add to.
    guard_device_limit = plan.max_devices + 2 if plan.max_devices is not None else None
    await _notify(
        marzban_guard.push_device_limit(marzban_username, guard_device_limit),
        "marzban-guard device-limit push", order.id,
    )

    kind = "Renewal" if order.is_renewal else "New purchase"
    await _notify(
        telegram.notify_admin(f"💰 {kind}: {customer.username} — {plan.name} ({plan.price_usdt}$)"),
        "admin success alert", order.id,
    )

    if customer.telegram_chat_id:
        kind = "renewed" if order.is_renewal else "activated"
        await _notify(
            telegram.send_message(
                customer.telegram_chat_id,
                f"✅ Your VPN account has been {kind}.\n\nConnection link:\n{result['subscription_url']}",
            ),
            "customer success alert", order.id,
        )
