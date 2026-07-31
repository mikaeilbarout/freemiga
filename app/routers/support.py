from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app import i18n
from app.auth import get_current_customer
from app.config import settings
from app.database import get_db
from app.lang import get_lang
from app.limiter import limiter
from app.models import Customer, SupportTicket, TicketMessage, TicketStatus
from app.schemas import TicketOut
from app.services import telegram
from app.services.uploads import read_validated_image, save_image

router = APIRouter(prefix="/api/support", tags=["support"])


async def _save_attachment(attachment: UploadFile | None) -> str | None:
    if attachment is None or not attachment.filename:
        return None
    data, ext = await read_validated_image(attachment)
    return save_image(data, ext, "tickets")


def _admin_notify_text(header: str, body: str, attachment_path: str | None) -> str:
    # The admin previously only got a one-line summary ("New ticket from X:
    # <subject>") and had to open the site to read what was actually said —
    # the full message body (and a link to any attachment) now goes straight
    # into the Telegram notification.
    text = f"{header}\n\n{body}"
    if attachment_path:
        text += f"\n\n📎 {settings.SITE_BASE_URL}{attachment_path}"
    return text


@router.post("/guest-tickets")
@limiter.limit("5/minute")
async def create_guest_ticket(
    request: Request,
    username: str = Form(...),
    contact: str | None = Form(None),
    subject: str = Form(...),
    message: str = Form(...),
    attachment: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """
    Lets someone contact support without being logged in — mainly for
    'I'm locked out and can't reset my password' cases. Shows up in the
    admin panel same as normal tickets, just without a linked customer.
    """
    attachment_path = await _save_attachment(attachment)
    ticket = SupportTicket(
        guest_username=username.strip().lower(),
        guest_contact=contact,
        subject=subject,
    )
    db.add(ticket)
    db.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender="customer", body=message, attachment_path=attachment_path)
    db.add(msg)
    db.commit()

    contact_line = f"\nContact: {contact}" if contact else ""
    await telegram.notify_admin(
        _admin_notify_text(
            f"📩 New message (guest, not logged in) from {ticket.guest_username}\n"
            f"Subject: {subject}{contact_line}",
            message,
            attachment_path,
        )
    )
    return {"ok": True}


@router.post("/tickets", response_model=TicketOut)
@limiter.limit("10/minute")
async def create_ticket(
    request: Request,
    subject: str = Form(...),
    message: str = Form(...),
    attachment: UploadFile | None = File(None),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    attachment_path = await _save_attachment(attachment)
    ticket = SupportTicket(customer_id=customer.id, subject=subject)
    db.add(ticket)
    db.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender="customer", body=message, attachment_path=attachment_path)
    db.add(msg)
    db.commit()
    db.refresh(ticket)

    await telegram.notify_admin(
        _admin_notify_text(
            f"📩 New ticket from {customer.username}\nSubject: {subject}",
            message,
            attachment_path,
        )
    )
    return ticket


@router.get("/tickets", response_model=list[TicketOut])
def my_tickets(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    # Tickets render collapsed — a customer sees the subject/status list
    # without necessarily opening any of them, so fetching this list must
    # NOT clear customer_unread itself. See /tickets/{id}/mark-read, called
    # only when a ticket is actually expanded.
    return (
        db.query(SupportTicket)
        .filter(SupportTicket.customer_id == customer.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )


@router.get("/unread-count")
def unread_count(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    count = (
        db.query(SupportTicket)
        .filter(SupportTicket.customer_id == customer.id, SupportTicket.customer_unread.is_(True))
        .count()
    )
    return {"count": count}


@router.post("/tickets/{ticket_id}/mark-read")
def mark_ticket_read(
    ticket_id: str,
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
    if ticket.customer_unread:
        ticket.customer_unread = False
        db.commit()
    return {"ok": True}


@router.post("/tickets/{ticket_id}/messages", response_model=TicketOut)
@limiter.limit("10/minute")
async def reply_to_ticket(
    request: Request,
    ticket_id: str,
    message: str = Form(...),
    attachment: UploadFile | None = File(None),
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

    attachment_path = await _save_attachment(attachment)
    msg = TicketMessage(ticket_id=ticket.id, sender="customer", body=message, attachment_path=attachment_path)
    db.add(msg)
    ticket.status = TicketStatus.open
    db.commit()
    db.refresh(ticket)

    await telegram.notify_admin(
        _admin_notify_text(
            f"📩 New message from {customer.username} on ticket \"{ticket.subject}\"",
            message,
            attachment_path,
        )
    )
    return ticket
