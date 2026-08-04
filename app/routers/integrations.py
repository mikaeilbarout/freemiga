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
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AdminAuditLog, Customer
from app.schemas import MarzbanGuardStatusIn
from app.services import telegram

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
    customer.is_banned = payload.banned
    customer.ban_reason = payload.reason if payload.banned else None
    db.add(AdminAuditLog(
        action="marzban_guard_ban" if payload.banned else "marzban_guard_unban",
        target=customer.id,
        detail=payload.reason,
    ))
    db.commit()

    if customer.telegram_chat_id and was_banned != payload.banned:
        if payload.banned:
            text = (
                f"⚠️ Your account has been suspended.\nReason: {payload.reason}\n"
                "Contact support from the site to follow up."
            )
        else:
            text = "✅ Your account has been reinstated."
        await telegram.send_message(customer.telegram_chat_id, text)

    return {"ok": True, "matched": True}
