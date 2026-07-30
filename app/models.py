import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime, Enum, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=gen_id)
    username = Column(String, unique=True, nullable=False)  # also the Marzban username
    # Nullable only for accounts created before the bot started collecting
    # email at signup — those were grandfathered in as email_verified=True
    # (a live chat_id was their trust signal instead). New signups, whether
    # via the website or the Telegram bot, always provide an email and must
    # verify it before their first purchase.
    email = Column(String, unique=True, nullable=True)
    email_verified = Column(Boolean, default=False)
    password_hash = Column(String, nullable=False)
    contact = Column(String, nullable=True)  # optional telegram handle (just text, not linked)
    telegram_chat_id = Column(String, nullable=True, unique=True)  # set once they link via /start
    language = Column(String, default="en")  # bot UI language ("en" or "fa")

    is_banned = Column(Boolean, default=False)
    ban_reason = Column(String, nullable=True)
    # Acceptable Use Policy (see /terms#acceptable-use). Required before the
    # first order — checked in routers/orders.py — and, once set, never
    # needs re-accepting unless we explicitly reset it for a policy change.
    terms_accepted_at = Column(DateTime, nullable=True)

    @property
    def terms_accepted(self) -> bool:
        return self.terms_accepted_at is not None
    # Soft-delete: PII is scrubbed and the Marzban VPN account is removed,
    # but the row (and its historical orders) stays for bookkeeping.
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="customer")
    tickets = relationship("SupportTicket", back_populates="customer")


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"

    id = Column(String, primary_key=True, default=gen_id)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    code_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(String, primary_key=True, default=gen_id)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    token = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    price_usdt = Column(Float, nullable=False)
    data_limit_gb = Column(Integer, nullable=False)
    duration_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    # How many devices/IPs at once this plan allows — enforced by the
    # separate marzban-guard abuse-detection system, not by this app.
    # NULL means "use marzban-guard's own global default", not "unlimited".
    max_devices = Column(Integer, nullable=True)

    orders = relationship("Order", back_populates="plan")


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    provisioned = "provisioned"
    expired = "expired"
    failed = "failed"
    cancelled = "cancelled"


class PaymentMethod(str, enum.Enum):
    crypto = "crypto"
    card = "card"
    free = "free"


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=gen_id)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    is_renewal = Column(Boolean, default=False)

    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.crypto, nullable=False)
    amount_due = Column(Float, nullable=False)  # the fixed plan price charged

    # Payment tracking (card / Stripe)
    stripe_session_id = Column(String, nullable=True, unique=True)

    # Payment tracking (crypto / NowPayments — legacy)
    nowpayments_invoice_id = Column(String, nullable=True, unique=True)

    # Payment tracking (crypto / self-hosted USDT wallet). Unique constraint
    # is the hard guarantee that the same on-chain transaction can never be
    # credited to two different orders, even under concurrent submissions.
    tx_hash = Column(String, nullable=True, unique=True)
    # Which chain the customer is paying USDT on — "tron" or "polygon".
    # Only meaningful when payment_method == crypto.
    crypto_network = Column(String, nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)

    subscription_url = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # payment deadline for this order
    paid_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="orders")
    plan = relationship("Plan", back_populates="orders")


class TicketStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(String, primary_key=True, default=gen_id)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    guest_username = Column(String, nullable=True)  # set when customer_id is null
    guest_contact = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    status = Column(Enum(TicketStatus), default=TicketStatus.open, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="tickets")
    messages = relationship(
        "TicketMessage", back_populates="ticket", order_by="TicketMessage.created_at"
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(String, primary_key=True, default=gen_id)
    ticket_id = Column(String, ForeignKey("support_tickets.id"), nullable=False)
    sender = Column(String, nullable=False)  # "customer" or "admin"
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("SupportTicket", back_populates="messages")


class Banner(Base):
    __tablename__ = "banners"

    id = Column(String, primary_key=True, default=gen_id)
    image_path = Column(String, nullable=False)  # served from /static/uploads/banners/...
    headline = Column(String, nullable=True)
    subtext = Column(String, nullable=True)
    link_url = Column(String, nullable=True)  # where clicking the banner sends the customer
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id = Column(String, primary_key=True, default=gen_id)
    action = Column(String, nullable=False)  # e.g. "ban", "unban", "confirm_order", "reply_ticket"
    target = Column(String, nullable=False)  # customer_id / order_id / ticket_id
    detail = Column(String, nullable=True)   # e.g. ban reason
    created_at = Column(DateTime, default=datetime.utcnow)
