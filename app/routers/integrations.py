"""
Machine-to-machine endpoint for the separate marzban-guard abuse-detection
system to report account restrictions back into this shop's database.

This is the only connection between the two systems — marzban-guard talks
to Marzban's admin API directly to actually suspend/disable/blacklist an
account; it never touches this shop's database or provisions/deletes
accounts. This endpoint exists only to keep this shop's own
Customer.is_banned flag (and the customer-facing dashboard/Telegram
notice) in sync with a restriction that already happened, so a customer
doesn't see "active" on the site while their VPN is actually blocked.
"""
import asyncio
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import i18n
from app.config import settings
from app.database import get_db
from app.models import AdminAuditLog, Customer, CustomerAlert, Order, OrderStatus
from app.schemas import MarzbanGuardDeviceLimitWarningIn, MarzbanGuardStatusIn
from app.services import marzban_guard, telegram

logger = logging.getLogger("integrations")

router = APIRouter(prefix="/api/integrations/marzban-guard", tags=["integrations"])


def _require_webhook_secret(authorization: str = Header(default="")) -> None:
    if not settings.MARZBAN_GUARD_WEBHOOK_SECRET:
        raise HTTPException(503, "marzban-guard integration not configured")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not hmac.compare_digest(token, settings.MARZBAN_GUARD_WEBHOOK_SECRET):
        raise HTTPException(401, "Invalid or missing webhook secret")


@router.post("/status", dependencies=[Depends(_require_webhook_secret)])
async def report_status(payload: MarzbanGuardStatusIn, db: Session = Depends(get_db)):
    """Does NOT call Marzban itself — marzban-guard already did that
    directly. This only mirrors local state and, if the ban state
    actually changed, sends the same customer-facing Telegram notice the
    admin-initiated ban/unban flow sends (see routers/admin.py)."""
    # payload.username is a Marzban username, which — since Order.marzban_username
    # — is "{customer.username}_{order_id_prefix}", not the bare customer
    # username. customer.username is strictly alphanumeric (see
    # SignupIn.username_ok), so it can never itself contain "_", making the
    # split unambiguous: everything before the first "_" is the customer.
    base_username = payload.username.split("_", 1)[0]
    customer = db.query(Customer).filter(Customer.username == base_username).first()
    if not customer:
        # Not necessarily an error (e.g. a renamed/deleted username) —
        # still 200 so marzban-guard doesn't keep retrying pointlessly.
        logger.info("Got marzban-guard status report for unknown username %s", payload.username)
        return {"ok": True, "matched": False}

    was_banned = customer.is_banned

    if payload.banned:
        # Restricting is always safe to apply immediately, regardless of
        # what else is going on with this customer's other orders.
        customer.is_banned = True
        customer.ban_reason = payload.reason
    else:
        # This ONE order's Marzban account was cleared — but a customer can
        # have several independent provisioned orders (see
        # Order.marzban_username), each tracked separately by
        # marzban-guard. Blindly clearing customer.is_banned here would
        # wrongly reinstate a customer who still has a DIFFERENT order
        # under active guard restriction, or override an admin-initiated
        # ban (routers/admin.py) that only an admin should be able to
        # lift. Only actually clear the flag if neither of those applies.
        last_ban_action = (
            db.query(AdminAuditLog)
            .filter(
                AdminAuditLog.target == customer.id,
                AdminAuditLog.action.in_(["ban", "marzban_guard_ban"]),
            )
            .order_by(AdminAuditLog.created_at.desc())
            .first()
        )
        admin_initiated = last_ban_action is not None and last_ban_action.action == "ban"

        still_restricted = False
        if not admin_initiated:
            other_usernames = [
                o.marzban_username for o in db.query(Order).filter(
                    Order.customer_id == customer.id, Order.status == OrderStatus.provisioned
                ).all()
                if o.marzban_username != payload.username
            ]
            if other_usernames:
                statuses = await asyncio.gather(*(marzban_guard.get_status(u) for u in other_usernames))
                still_restricted = any(s and s.get("status") not in (None, "active") for s in statuses)

        if not admin_initiated and not still_restricted:
            customer.is_banned = False
            customer.ban_reason = None

    db.add(AdminAuditLog(
        action="marzban_guard_ban" if payload.banned else "marzban_guard_unban",
        target=customer.id,
        detail=payload.reason,
    ))
    db.commit()

    if customer.telegram_chat_id and was_banned != customer.is_banned:
        if customer.is_banned:
            text = (
                f"⚠️ Your account has been suspended.\nReason: {payload.reason}\n"
                "Contact support from the site to follow up."
            )
        else:
            text = "✅ Your account has been reinstated."
        await telegram.send_message(customer.telegram_chat_id, text)

    return {"ok": True, "matched": True}


@router.post("/device-limit-warning", dependencies=[Depends(_require_webhook_secret)])
async def report_device_limit_warning(payload: MarzbanGuardDeviceLimitWarningIn, db: Session = Depends(get_db)):
    """marzban-guard's soft alternative to /status for a device_limit-only
    trigger (see that project's MitigationConfig.device_limit_warn_only):
    no ban, no Marzban status change — just a heads-up the customer should
    see. Stored as a CustomerAlert (shown in their dashboard) and, if
    linked, sent over Telegram too. payload.reason carries marzban-guard's
    own technical detector reason, which isn't customer-facing — the
    stored/sent message is our own wording instead."""
    base_username = payload.username.split("_", 1)[0]
    customer = db.query(Customer).filter(Customer.username == base_username).first()
    if not customer:
        logger.info("Got marzban-guard device-limit warning for unknown username %s", payload.username)
        return {"ok": True, "matched": False}

    message = i18n.t(customer.language or "en", "device_limit_warning_msg")
    db.add(CustomerAlert(customer_id=customer.id, message=message))
    db.commit()

    if customer.telegram_chat_id:
        await telegram.send_message(customer.telegram_chat_id, message)

    return {"ok": True, "matched": True}
