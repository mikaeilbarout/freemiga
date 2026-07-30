"""
Shared email-verification-token logic, used by both the web signup flow
(routers/auth.py) and the Telegram bot's in-chat signup flow
(services/telegram_bot.py) so both surfaces issue/send verification links
the exact same way.
"""
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Customer, EmailVerificationToken
from app.services import email_gateway

logger = logging.getLogger("verification")


async def send_verification_email(db: Session, customer: Customer) -> None:
    """Best-effort — a failure here (e.g. the email provider rejects the
    address) must never block signup, since the account already exists.
    The customer can always retry via "Resend email" (website) or the
    resend button (Telegram bot)."""
    token = secrets.token_urlsafe(32)
    db.add(EmailVerificationToken(
        customer_id=customer.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    ))
    db.commit()
    verify_url = f"{settings.SITE_BASE_URL}/api/auth/verify-email?token={token}"
    try:
        await email_gateway.send_verification_email(customer.email, verify_url)
    except Exception:
        logger.exception("Failed to send verification email to %s", customer.email)
