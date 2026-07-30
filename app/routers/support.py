from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import i18n
from app.auth import get_current_customer
from app.database import get_db
from app.lang import get_lang
from app.models import Customer, SupportTicket, TicketMessage, TicketStatus
from app.schemas import GuestTicketCreate, MessageCreate, TicketCreate, TicketOut
from app.services import telegram

router = APIRouter(prefix="/api/support", tags=["support"])


@router.post("/guest-tickets")
async def create_guest_ticket(payload: GuestTicketCreate, db: Session = Depends(get_db)):
    """
    Lets someone contact support without being logged in — mainly for
    'I'm locked out and can't reset my password' cases. Shows up in the
    admin panel same as normal tickets, just without a linked customer.
    """
    ticket = SupportTicket(
        guest_username=payload.username.strip().lower(),
        guest_contact=payload.contact,
        subject=payload.subject,
    )
    db.add(ticket)
    db.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender="customer", body=payload.message)
    db.add(msg)
    db.commit()

    await telegram.notify_admin(
        f"📩 پیام جدید (بدون ورود) از {ticket.guest_username}: {payload.subject}"
    )
    return {"ok": True}


@router.post("/tickets", response_model=TicketOut)
async def create_ticket(
    payload: TicketCreate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    ticket = SupportTicket(customer_id=customer.id, subject=payload.subject)
    db.add(ticket)
    db.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender="customer", body=payload.message)
    db.add(msg)
    db.commit()
    db.refresh(ticket)

    await telegram.notify_admin(f"📩 تیکت جدید از {customer.username}: {payload.subject}")
    return ticket


@router.get("/tickets", response_model=list[TicketOut])
def my_tickets(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    return (
        db.query(SupportTicket)
        .filter(SupportTicket.customer_id == customer.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )


@router.post("/tickets/{ticket_id}/messages", response_model=TicketOut)
async def reply_to_ticket(
    ticket_id: str,
    payload: MessageCreate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id, SupportTicket.customer_id == customer.id)
        .first()
    )
    if not ticket:
        raise HTTPException(404, i18n.t(lang, "err_ticket_not_found"))

    msg = TicketMessage(ticket_id=ticket.id, sender="customer", body=payload.message)
    db.add(msg)
    ticket.status = TicketStatus.open
    db.commit()
    db.refresh(ticket)

    await telegram.notify_admin(f"📩 پیام جدید تو تیکت «{ticket.subject}» از {customer.username}")
    return ticket
