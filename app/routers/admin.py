import hmac
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.background import _provision
from app.config import settings
from app.database import get_db
from app.auth import require_admin
from app.limiter import limiter
from app.models import (
    AdminAuditLog,
    Customer,
    Order,
    OrderStatus,
    PaymentMethod,
    Plan,
    SupportTicket,
    TicketMessage,
    TicketStatus,
)
from app.schemas import (
    AdminLoginIn,
    BanIn,
    CustomerAdminOut,
    GrantPlanIn,
    OrderAdminOut,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    TicketAdminOut,
)
from app.services import email_gateway, marzban, telegram
from app.services.uploads import read_validated_image, save_image

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return email
    visible = local[:1] or "*"
    return f"{visible}{'*' * max(len(local) - 1, 1)}@{domain}"


def _log_action(db: Session, action: str, target: str, detail: str = None) -> None:
    db.add(AdminAuditLog(action=action, target=target, detail=detail))
    db.commit()


@router.post("/login")
@limiter.limit("5/minute")
def admin_login(payload: AdminLoginIn, request: Request):
    ok_user = hmac.compare_digest(payload.username, settings.ADMIN_USERNAME)
    ok_pass = hmac.compare_digest(payload.password, settings.ADMIN_PASSWORD)
    if not (ok_user and ok_pass and settings.ADMIN_PASSWORD):
        raise HTTPException(401, "Invalid admin credentials")
    request.session["is_admin"] = True
    return {"ok": True}


@router.post("/logout")
def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return {"ok": True}


@router.get("/plans", dependencies=[Depends(require_admin)])
def admin_list_plans(db: Session = Depends(get_db), page: int = 1, page_size: int = 10):
    query = db.query(Plan).order_by(Plan.price_usdt)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [PlanOut.model_validate(p) for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/plans", response_model=PlanOut, dependencies=[Depends(require_admin)])
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)):
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    _log_action(db, "create_plan", plan.id, plan.name)
    return plan


@router.put("/plans/{plan_id}", response_model=PlanOut, dependencies=[Depends(require_admin)])
def update_plan(plan_id: str, payload: PlanUpdate, db: Session = Depends(get_db)):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    _log_action(db, "update_plan", plan_id)
    return plan


@router.delete("/plans/{plan_id}", dependencies=[Depends(require_admin)])
def delete_plan(plan_id: str, db: Session = Depends(get_db)):
    """Permanently deletes a plan that's never actually been ordered.
    A plan with order history can't be hard-deleted (past orders
    reference it via a NOT NULL foreign key, for bookkeeping) — it's
    deactivated instead, which hides it from new customers without
    touching existing history."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    plan_name = plan.name
    has_orders = db.query(Order).filter(Order.plan_id == plan_id).first() is not None

    if not has_orders:
        db.delete(plan)
        try:
            db.commit()
        except IntegrityError:
            # A customer's checkout raced us and created an order for this
            # plan between our check above and this commit — fall through
            # to deactivating it instead of surfacing a raw 500.
            db.rollback()
            has_orders = True
        else:
            _log_action(db, "delete_plan", plan_id, plan_name)
            return {"ok": True, "deleted": True}

    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    plan.is_active = False
    db.commit()
    _log_action(db, "deactivate_plan", plan_id, plan_name)
    return {"ok": True, "deleted": False}


@router.get("/stats", dependencies=[Depends(require_admin)])
def admin_stats(db: Session = Depends(get_db)):
    """Powers the at-a-glance summary strip and tab badges at the top of
    the admin panel — lets an admin see what needs attention without
    clicking through every tab."""
    total_customers = db.query(Customer).filter(Customer.is_deleted.is_(False)).count()
    banned_customers = db.query(Customer).filter(
        Customer.is_deleted.is_(False), Customer.is_banned.is_(True)
    ).count()

    # Same condition the Orders tab's "Confirm manually" button checks —
    # a crypto order stuck pending/failed usually means the on-chain
    # payment needs the admin to verify and confirm it by hand.
    orders_needing_confirm = (
        db.query(Order)
        .filter(
            Order.payment_method == PaymentMethod.crypto,
            Order.status.in_([OrderStatus.pending, OrderStatus.failed]),
        )
        .count()
    )

    # needs_reply isn't a DB column (mirrors the same last-message check
    # list_tickets does) — cheap enough at this scale to compute in Python.
    open_tickets = (
        db.query(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .filter(SupportTicket.status == TicketStatus.open)
        .all()
    )
    tickets_needing_reply = sum(
        1 for t in open_tickets if t.messages and t.messages[-1].sender == "customer"
    )

    return {
        "total_customers": total_customers,
        "banned_customers": banned_customers,
        "orders_needing_confirm": orders_needing_confirm,
        "open_tickets": len(open_tickets),
        "tickets_needing_reply": tickets_needing_reply,
    }


@router.get("/customers", dependencies=[Depends(require_admin)])
def list_customers(
    db: Session = Depends(get_db),
    search: str = "",
    page: int = 1,
    page_size: int = 25,
):
    query = db.query(Customer)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Customer.username.ilike(like), Customer.email.ilike(like)))
    total = query.count()
    items = (
        query.order_by(Customer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [CustomerAdminOut.model_validate(c) for c in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/orders", dependencies=[Depends(require_admin)])
def list_orders(
    db: Session = Depends(get_db),
    status: str = "",
    q: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    # Cancelled orders are checkout abandonment noise (e.g. a customer
    # switched plans mid-checkout) — same reasoning as hiding them from the
    # customer's own order history, they're not useful here either.
    query = (
        db.query(Order)
        .join(Customer, Order.customer_id == Customer.id)
        .join(Plan, Order.plan_id == Plan.id)
        # The joins above are for filtering (status/q) only — a bare join
        # doesn't populate o.customer/o.plan, so without this every order
        # in the page would trigger two more lazy-load queries below.
        .options(selectinload(Order.customer), selectinload(Order.plan))
        .filter(Order.status != OrderStatus.cancelled)
    )
    if status:
        try:
            query = query.filter(Order.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(400, "Invalid status")
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Customer.username.ilike(like), Plan.name.ilike(like)))
    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        OrderAdminOut(
            id=o.id,
            customer_username=o.customer.username,
            plan_name=o.plan.name,
            status=o.status,
            payment_method=o.payment_method,
            crypto_network=o.crypto_network,
            amount_due=o.amount_due,
            is_renewal=o.is_renewal,
            expires_at=o.expires_at,
            created_at=o.created_at,
        )
        for o in orders
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/customers/{customer_id}/ban", dependencies=[Depends(require_admin)])
async def ban_customer(customer_id: str, payload: BanIn, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")

    customer.is_banned = True
    customer.ban_reason = payload.reason
    db.commit()
    _log_action(db, "ban", customer_id, payload.reason)

    try:
        await marzban.set_user_status(customer.username, active=False)
    except Exception:
        # Customer is still marked banned locally even if the VPN user
        # doesn't exist yet (e.g. banned before their first purchase).
        pass

    if customer.telegram_chat_id:
        await telegram.send_message(
            customer.telegram_chat_id,
            f"⚠️ Your account has been suspended.\nReason: {payload.reason}\n"
            "Contact support from the site to follow up.",
        )

    return {"ok": True}


@router.post("/customers/{customer_id}/unban", dependencies=[Depends(require_admin)])
async def unban_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")

    customer.is_banned = False
    customer.ban_reason = None
    db.commit()
    _log_action(db, "unban", customer_id)

    try:
        await marzban.set_user_status(customer.username, active=True)
    except Exception:
        pass

    if customer.telegram_chat_id:
        await telegram.send_message(customer.telegram_chat_id, "✅ Your account suspension has been lifted.")

    return {"ok": True}


@router.post("/customers/{customer_id}/grant-plan", dependencies=[Depends(require_admin)])
async def grant_plan(customer_id: str, payload: GrantPlanIn, db: Session = Depends(get_db)):
    """The correct way to hand a customer VPN access outside a normal
    purchase (comp access, support goodwill, etc.) — creates the same
    Order + provisioning trail a real purchase would, at $0, so the
    customer's dashboard, order history, and vpn-status all stay accurate
    instead of silently going out of sync with what's actually running in
    Marzban. Reuses create_vpn_user/extend_vpn_user exactly as a normal
    order does, including the fallback that now handles a username Marzban
    already knows about (e.g. one an admin created directly in Marzban's
    own panel before this endpoint existed) instead of failing outright."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    if customer.is_deleted:
        raise HTTPException(400, "Cannot grant a plan to a deleted account")
    if customer.is_banned:
        # Provisioning always sets the Marzban user's status to "active" —
        # granting a plan to a suspended customer would silently undo their
        # own suspension. Lift it first if that's really the intent.
        raise HTTPException(400, "This customer is suspended — lift the suspension before granting a plan")

    plan = db.query(Plan).filter(Plan.id == payload.plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    already_has_account = (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.status == OrderStatus.provisioned)
        .first()
        is not None
    )

    order = Order(
        customer_id=customer.id,
        plan_id=plan.id,
        is_renewal=already_has_account,
        payment_method=PaymentMethod.free,
        amount_due=0,
        status=OrderStatus.pending,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ORDER_EXPIRY_MINUTES),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    _log_action(
        db, "grant_plan", customer_id,
        f"{plan.name}" + (f" — {payload.note}" if payload.note else ""),
    )

    await _provision(order, db)
    db.refresh(order)
    return {"ok": True, "status": order.status.value, "subscription_url": order.subscription_url}


@router.post("/orders/{order_id}/confirm", dependencies=[Depends(require_admin)])
async def manually_confirm_order(order_id: str, db: Session = Depends(get_db)):
    """Escape hatch for when a payment gateway webhook misses/fails to
    deliver — admin can confirm by hand after checking the payment
    themselves in the Stripe/NowPayments dashboard."""
    # Row-locked to avoid racing an in-flight webhook delivery for the same
    # order (see the matching with_for_update() in payments._mark_paid_and_provision).
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == OrderStatus.provisioned:
        db.rollback()
        raise HTTPException(409, "Already provisioned")

    order.status = OrderStatus.paid
    db.commit()
    _log_action(db, "manual_confirm_order", order_id)
    await _provision(order, db)
    return {"ok": True, "status": order.status}


@router.get("/audit-log", dependencies=[Depends(require_admin)])
def audit_log(db: Session = Depends(get_db), page: int = 1, page_size: int = 25):
    query = db.query(AdminAuditLog)
    total = query.count()
    logs = (
        query.order_by(AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {"action": l.action, "target": l.target, "detail": l.detail, "created_at": l.created_at}
            for l in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/tickets", dependencies=[Depends(require_admin)])
def list_tickets(
    db: Session = Depends(get_db),
    open_only: bool = False,
    q: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    query = db.query(SupportTicket).options(
        selectinload(SupportTicket.customer), selectinload(SupportTicket.messages)
    )
    if open_only:
        query = query.filter(SupportTicket.status == TicketStatus.open)
    if q:
        like = f"%{q.strip()}%"
        query = query.outerjoin(Customer, SupportTicket.customer_id == Customer.id).filter(
            or_(
                SupportTicket.subject.ilike(like),
                SupportTicket.guest_username.ilike(like),
                Customer.username.ilike(like),
            )
        )
    total = query.count()
    tickets = (
        query.order_by(SupportTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # One batched lookup for every guest ticket's claimed username instead
    # of a query per ticket (was a real N+1 — a page of mostly-guest
    # tickets meant one extra round trip per row).
    guest_usernames = {t.guest_username for t in tickets if not t.customer_id and t.guest_username}
    matched_by_username = {}
    if guest_usernames:
        for c in db.query(Customer).filter(Customer.username.in_(guest_usernames)).all():
            matched_by_username[c.username] = c

    out = []
    for t in tickets:
        display_name = t.customer.username if t.customer else f"{t.guest_username} (guest)"
        needs_reply = bool(t.messages) and t.messages[-1].sender == "customer"

        # A guest ticket's claimed identity is unverified — if the claimed
        # username belongs to a real account, surface that account's actual
        # registered email so the admin can spot an impersonation attempt
        # (e.g. someone claiming to be another customer to get their ban lifted).
        registered_email = None
        identity_mismatch = False
        if not t.customer and t.guest_username:
            matched = matched_by_username.get(t.guest_username)
            if matched and matched.email:
                registered_email = _mask_email(matched.email)
                claimed = (t.guest_contact or "").strip().lower()
                known = {matched.email.strip().lower(), (matched.contact or "").strip().lower()}
                identity_mismatch = bool(claimed) and claimed not in known

        out.append(
            TicketAdminOut(
                id=t.id,
                customer_id=t.customer_id or "",
                customer_username=display_name,
                guest_contact=t.guest_contact,
                registered_email=registered_email,
                identity_mismatch=identity_mismatch,
                needs_reply=needs_reply,
                subject=t.subject,
                status=t.status,
                created_at=t.created_at,
                messages=t.messages,
            )
        )
    return {"items": out, "total": total, "page": page, "page_size": page_size}


@router.post("/tickets/{ticket_id}/reply", dependencies=[Depends(require_admin)])
async def reply_ticket(
    ticket_id: str,
    message: str = Form(...),
    attachment: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    attachment_path = None
    if attachment is not None and attachment.filename:
        data, ext = await read_validated_image(attachment)
        attachment_path = save_image(data, ext, "tickets")

    msg = TicketMessage(ticket_id=ticket.id, sender="admin", body=message, attachment_path=attachment_path)
    db.add(msg)
    ticket.customer_unread = True
    db.commit()
    _log_action(db, "reply_ticket", ticket_id)

    if ticket.customer:
        if ticket.customer.telegram_chat_id:
            await telegram.send_message(
                ticket.customer.telegram_chat_id,
                f"📩 Support replied to your ticket \"{ticket.subject}\" — check it on the site.",
            )
        if ticket.customer.email:
            try:
                await email_gateway.send_support_reply_email(ticket.customer.email, ticket.subject)
            except Exception:
                pass
    elif ticket.guest_contact and "@" in ticket.guest_contact:
        try:
            await email_gateway.send_support_reply_email(ticket.guest_contact, ticket.subject)
        except Exception:
            pass

    return {"ok": True}


@router.post("/tickets/{ticket_id}/close", dependencies=[Depends(require_admin)])
def close_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    ticket.status = TicketStatus.closed
    db.commit()
    _log_action(db, "close_ticket", ticket_id)
    return {"ok": True}
