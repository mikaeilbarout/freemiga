import logging
import random
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import i18n
from app.auth import get_current_customer, hash_password, verify_password
from app.database import get_db
from app.lang import get_lang
from app.limiter import limiter
from app.models import Customer, EmailVerificationToken, Order, OrderStatus, PasswordResetCode
from app.schemas import (
    ChangePasswordIn,
    CustomerOut,
    DeleteAccountIn,
    LoginIn,
    RequestResetIn,
    ResetIn,
    SignupIn,
    UpdateProfileIn,
)
from app.services import email_gateway, marzban, telegram, telegram_bot, verification

logger = logging.getLogger("auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=CustomerOut)
@limiter.limit("5/minute")
async def signup(payload: SignupIn, request: Request, db: Session = Depends(get_db), lang: str = Depends(get_lang)):
    if db.query(Customer).filter(Customer.username == payload.username).first():
        raise HTTPException(409, i18n.t(lang, "err_username_taken"))
    if db.query(Customer).filter(Customer.email == payload.email).first():
        raise HTTPException(409, i18n.t(lang, "err_email_exists"))

    customer = Customer(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        contact=payload.contact,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    await verification.send_verification_email(db, customer)

    request.session["customer_id"] = customer.id
    return customer


@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    record = db.query(EmailVerificationToken).filter(EmailVerificationToken.token == token).first()
    if not record:
        return RedirectResponse(url="/dashboard?verify=invalid")

    if record.used:
        # Some email clients (e.g. Gmail's link-scanning) visit the link
        # once before the person ever clicks it, consuming the one-time
        # token early. If verification already succeeded, treat a repeat
        # visit as a no-op success instead of a scary "invalid" error.
        customer = db.query(Customer).filter(Customer.id == record.customer_id).first()
        if customer and customer.email_verified:
            return RedirectResponse(url="/dashboard?verify=success")
        return RedirectResponse(url="/dashboard?verify=invalid")

    if record.expires_at < datetime.utcnow():
        return RedirectResponse(url="/dashboard?verify=invalid")

    record.used = True
    customer = db.query(Customer).filter(Customer.id == record.customer_id).first()
    if customer:
        customer.email_verified = True
    db.commit()

    if customer:
        await telegram_bot.notify_email_verified(customer)

    return RedirectResponse(url="/dashboard?verify=success")


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if customer.email_verified:
        return {"already_verified": True}
    await verification.send_verification_email(db, customer)
    return {"sent": True}


@router.post("/login", response_model=CustomerOut)
@limiter.limit("10/minute")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db), lang: str = Depends(get_lang)):
    customer = db.query(Customer).filter(Customer.username == payload.username.strip().lower()).first()
    if not customer or customer.is_deleted or not verify_password(payload.password, customer.password_hash):
        raise HTTPException(401, i18n.t(lang, "err_invalid_credentials"))

    request.session["customer_id"] = customer.id
    return customer


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=CustomerOut)
def me(customer: Customer = Depends(get_current_customer)):
    return customer


@router.post("/accept-terms", response_model=CustomerOut)
def accept_terms(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    # Always re-stamps, even if already accepted before — acceptance is
    # required fresh on every purchase (the checkbox on /billing is never
    # pre-checked from a prior visit), so this timestamp should reflect the
    # most recent one, not just the first-ever one.
    customer.terms_accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(customer)
    return customer


@router.patch("/me", response_model=CustomerOut)
def update_profile(
    payload: UpdateProfileIn,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    customer.contact = payload.contact or None
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/delete-account")
@limiter.limit("3/minute")
async def delete_account(
    payload: DeleteAccountIn,
    request: Request,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """Customer-initiated account deletion. Every Marzban VPN account this
    customer has (one per provisioned order — see Order.marzban_username)
    is permanently removed. The Customer row itself is anonymized rather
    than hard-deleted, so historical orders/tickets stay intact for
    bookkeeping — the username is freed up and every other identifying
    field is cleared."""
    if not verify_password(payload.password, customer.password_hash):
        raise HTTPException(401, i18n.t(lang, "err_incorrect_password"))

    provisioned_orders = db.query(Order).filter(
        Order.customer_id == customer.id, Order.status == OrderStatus.provisioned
    ).all()
    for order in provisioned_orders:
        try:
            await marzban.delete_vpn_user(order.marzban_username)
        except Exception:
            logger.exception(
                "Failed to delete Marzban user %s during account deletion", order.marzban_username
            )

    customer.username = f"deleted_{customer.id}"
    customer.email = None
    customer.contact = None
    customer.telegram_chat_id = None
    customer.password_hash = hash_password(secrets.token_urlsafe(32))
    customer.is_deleted = True
    db.commit()

    request.session.clear()
    return {"ok": True}


@router.post("/change-password")
@limiter.limit("5/minute")
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    if not verify_password(payload.current_password, customer.password_hash):
        raise HTTPException(401, i18n.t(lang, "err_current_password_incorrect"))
    customer.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


@router.get("/telegram-link")
def telegram_link(customer: Customer = Depends(get_current_customer)):
    return {
        "linked": bool(customer.telegram_chat_id),
        "link": telegram.deep_link(customer.id),
    }


@router.post("/request-reset")
@limiter.limit("3/minute")
async def request_reset(payload: RequestResetIn, request: Request, db: Session = Depends(get_db), lang: str = Depends(get_lang)):
    customer = db.query(Customer).filter(Customer.username == payload.username.strip().lower()).first()

    # Always return the same generic response whether or not the username
    # exists, so this endpoint can't be used to check which usernames are
    # registered.
    generic_response = {
        "sent": False,
        "message": i18n.t(lang, "reset_generic_message"),
    }

    # Same response as "no such user" when there's nowhere to actually send
    # a code (an old account with no email on file and no Telegram link) —
    # both keeps this endpoint from leaking which usernames exist, and stops
    # it from claiming "sent" when nothing could ever be delivered.
    if not customer or not (customer.email or customer.telegram_chat_id):
        return generic_response

    code = f"{random.randint(0, 999999):06d}"
    reset = PasswordResetCode(
        customer_id=customer.id,
        code_hash=hash_password(code),
        expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    db.add(reset)
    db.commit()

    if customer.email:
        try:
            await email_gateway.send_password_reset_email(customer.email, code)
        except Exception:
            logger.exception("Failed to send password reset email to %s", customer.email)

    if customer.telegram_chat_id:
        await telegram.send_message(
            customer.telegram_chat_id,
            f"Your password reset code: {code}\nValid for 15 minutes.",
        )

    generic_response["sent"] = True
    return generic_response


@router.post("/reset", response_model=CustomerOut)
@limiter.limit("10/minute")
def reset_password(payload: ResetIn, request: Request, db: Session = Depends(get_db), lang: str = Depends(get_lang)):
    customer = db.query(Customer).filter(Customer.username == payload.username.strip().lower()).first()
    if not customer:
        raise HTTPException(400, i18n.t(lang, "err_invalid_code"))

    now = datetime.utcnow()
    candidates = (
        db.query(PasswordResetCode)
        .filter(
            PasswordResetCode.customer_id == customer.id,
            PasswordResetCode.used.is_(False),
            PasswordResetCode.expires_at > now,
        )
        .order_by(PasswordResetCode.created_at.desc())
        .all()
    )

    matched = next((c for c in candidates if verify_password(payload.code, c.code_hash)), None)
    if not matched:
        raise HTTPException(400, i18n.t(lang, "err_invalid_or_expired_code"))

    matched.used = True
    customer.password_hash = hash_password(payload.new_password)
    db.commit()

    request.session["customer_id"] = customer.id
    return customer
