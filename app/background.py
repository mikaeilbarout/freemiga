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
    try:
        if order.is_renewal:
            result = await marzban.extend_vpn_user(
                username=customer.username,
                data_limit_gb=plan.data_limit_gb,
                duration_days=plan.duration_days,
            )
        else:
            result = await marzban.create_vpn_user(
                username=customer.username,
                data_limit_gb=plan.data_limit_gb,
                duration_days=plan.duration_days,
            )
        order.subscription_url = result["subscription_url"]
        order.status = OrderStatus.provisioned
        logger.info("Provisioned VPN for order %s (customer %s)", order.id, customer.username)
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

    await _notify(
        marzban_guard.push_device_limit(customer.username, plan.max_devices),
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
