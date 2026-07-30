import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

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
    Plan,
    SupportTicket,
    TicketMessage,
    TicketStatus,
)
from app.schemas import (
    AdminLoginIn,
    BanIn,
    CustomerAdminOut,
    MessageCreate,
    OrderOut,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    TicketAdminOut,
)
from app.services import marzban, telegram

router = APIRouter(prefix="/api/admin", tags=["admin"])


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


@router.get("/plans", response_model=list[PlanOut], dependencies=[Depends(require_admin)])
def admin_list_plans(db: Session = Depends(get_db)):
    return db.query(Plan).order_by(Plan.price_usdt).all()


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
def deactivate_plan(plan_id: str, db: Session = Depends(get_db)):
    """Soft-delete: plans are never hard-deleted since past orders reference
    them. This just hides it from customers."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    plan.is_active = False
    db.commit()
    _log_action(db, "deactivate_plan", plan_id)
    return {"ok": True}


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
    page: int = 1,
    page_size: int = 25,
):
    query = db.query(Order)
    if status:
        try:
            query = query.filter(Order.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(400, "Invalid status")
    total = query.count()
    items = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [OrderOut.model_validate(o) for o in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


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
    page: int = 1,
    page_size: int = 25,
):
    query = db.query(SupportTicket)
    if open_only:
        query = query.filter(SupportTicket.status == TicketStatus.open)
    total = query.count()
    tickets = (
        query.order_by(SupportTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out = []
    for t in tickets:
        display_name = t.customer.username if t.customer else f"{t.guest_username} (guest)"
        out.append(
            TicketAdminOut(
                id=t.id,
                customer_id=t.customer_id or "",
                customer_username=display_name,
                subject=t.subject,
                status=t.status,
                created_at=t.created_at,
                messages=t.messages,
            )
        )
    return {"items": out, "total": total, "page": page, "page_size": page_size}


@router.post("/tickets/{ticket_id}/reply", dependencies=[Depends(require_admin)])
async def reply_ticket(ticket_id: str, payload: MessageCreate, db: Session = Depends(get_db)):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    msg = TicketMessage(ticket_id=ticket.id, sender="admin", body=payload.message)
    db.add(msg)
    db.commit()
    _log_action(db, "reply_ticket", ticket_id)

    if ticket.customer and ticket.customer.telegram_chat_id:
        await telegram.send_message(
            ticket.customer.telegram_chat_id,
            f"📩 Support replied to your ticket \"{ticket.subject}\" — check it on the site.",
        )
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
