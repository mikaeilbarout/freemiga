import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---- Auth ----

class SignupIn(BaseModel):
    username: str
    email: str
    password: str
    confirm_password: str
    contact: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not v.isalnum() or not (3 <= len(v) <= 20):
            raise ValueError("username must be 3-20 alphanumeric characters")
        return v

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("passwords don't match")
        return self


class LoginIn(BaseModel):
    username: str
    password: str


class RequestResetIn(BaseModel):
    username: str


class ResetIn(BaseModel):
    username: str
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v


class UpdateProfileIn(BaseModel):
    contact: Optional[str] = None


class DeleteAccountIn(BaseModel):
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("passwords don't match")
        return self


class CustomerOut(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    email_verified: bool
    contact: Optional[str] = None
    is_banned: bool
    ban_reason: Optional[str] = None
    terms_accepted: bool

    class Config:
        from_attributes = True


# ---- Plans / Orders ----

class PlanOut(BaseModel):
    id: str
    name: str
    price_usdt: float
    data_limit_gb: int
    duration_days: int
    is_active: bool = True
    max_devices: Optional[int] = None
    is_featured: bool = False

    class Config:
        from_attributes = True


class PlanCreate(BaseModel):
    name: str
    price_usdt: float
    data_limit_gb: int
    duration_days: int
    max_devices: Optional[int] = None
    is_featured: bool = False


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price_usdt: Optional[float] = None
    data_limit_gb: Optional[int] = None
    duration_days: Optional[int] = None
    is_active: Optional[bool] = None
    max_devices: Optional[int] = None
    is_featured: Optional[bool] = None


class OrderCreate(BaseModel):
    plan_id: str
    is_renewal: bool = False
    payment_method: str = "crypto"  # "crypto" or "card"
    crypto_network: Optional[str] = None  # "tron" or "polygon" — only used when payment_method == crypto
    # Set on the retry after the customer confirms "cancel my other pending
    # order and start this one instead" (see routers/orders.py's 409 check).
    confirm_cancel_pending: bool = False


class VerifyPaymentIn(BaseModel):
    tx_hash: str


class OrderOut(BaseModel):
    id: str
    plan_id: str
    status: str
    payment_method: str
    crypto_network: Optional[str] = None
    amount_due: float
    is_renewal: bool
    expires_at: datetime
    created_at: datetime
    subscription_url: Optional[str] = None
    checkout_url: Optional[str] = None  # hosted payment page URL, present once on order creation
    tx_hash: Optional[str] = None

    class Config:
        from_attributes = True


# ---- Support ----
# Ticket/message creation endpoints take multipart form fields (not these
# models) since they accept an optional attachment — see routers/support.py
# and routers/admin.py. These remain as the response-side shapes.

class TicketMessageOut(BaseModel):
    sender: str
    body: str
    attachment_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: str
    subject: str
    status: str
    customer_unread: bool
    created_at: datetime
    messages: list[TicketMessageOut]

    class Config:
        from_attributes = True


# ---- Admin ----

class AdminLoginIn(BaseModel):
    username: str
    password: str


class CustomerAdminOut(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    email_verified: bool
    contact: Optional[str] = None
    is_banned: bool
    ban_reason: Optional[str] = None
    is_deleted: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Banners ----

class BannerOut(BaseModel):
    id: str
    image_path: str
    headline: Optional[str] = None
    subtext: Optional[str] = None
    link_url: Optional[str] = None
    sort_order: int
    is_active: bool

    class Config:
        from_attributes = True


class BanIn(BaseModel):
    reason: str


class GrantPlanIn(BaseModel):
    plan_id: str
    note: Optional[str] = None


class OrderAdminOut(BaseModel):
    id: str
    customer_username: str
    plan_name: str
    status: str
    payment_method: str
    crypto_network: Optional[str] = None
    amount_due: float
    is_renewal: bool
    expires_at: datetime
    created_at: datetime
    # Only set for provisioned orders — that's the only time a real Marzban
    # account (and thus a marzban-guard-tracked one) exists for this order.
    marzban_username: Optional[str] = None
    # Live-checked, best-effort (see admin.py's _order_real_status) —
    # None means "either everything's fine, or the check couldn't run".
    # Order.status alone never reflects a plan running out of data, its
    # expiry passing, or a restriction applied directly against Marzban
    # or marzban-guard after provisioning.
    real_status: Optional[str] = None
    real_status_reason: Optional[str] = None


class MarzbanGuardStatusOut(BaseModel):
    """marzban-guard tracks this independently of freemiga's own is_banned
    flag — see app/services/marzban_guard.py. configured=False means
    MARZBAN_GUARD_BASE_URL isn't set, not that the account is unprotected."""
    configured: bool
    reachable: bool
    username: Optional[str] = None
    status: Optional[str] = None
    status_reason: Optional[str] = None
    risk_score: Optional[float] = None
    last_seen_at: Optional[datetime] = None


class TicketAdminOut(BaseModel):
    id: str
    customer_id: str
    customer_username: str
    guest_contact: Optional[str] = None
    # Set only for guest tickets whose claimed username matches a real
    # account — lets the admin cross-check the guest-supplied contact
    # against the account's actual registered contact info before acting
    # on the ticket (e.g. an unban/unlock request).
    registered_email: Optional[str] = None
    identity_mismatch: bool = False
    needs_reply: bool
    subject: str
    status: str
    created_at: datetime
    messages: list[TicketMessageOut]


# ---- Integrations (marzban-guard) ----

class MarzbanGuardStatusIn(BaseModel):
    username: str
    banned: bool
    reason: str = ""


class MarzbanGuardDeviceLimitWarningIn(BaseModel):
    username: str
    reason: str = ""


# ---- Customer alerts ----

class CustomerAlertOut(BaseModel):
    id: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Blog ----

class BlogCategoryOut(BaseModel):
    id: str
    slug: str
    name_en: str
    name_fa: str

    class Config:
        from_attributes = True


class BlogTagOut(BaseModel):
    id: str
    slug: str
    name_en: str
    name_fa: str

    class Config:
        from_attributes = True


class BlogPostAdminOut(BaseModel):
    id: str
    slug: str
    category: Optional[BlogCategoryOut] = None
    title_en: str
    title_fa: str
    excerpt_en: str
    excerpt_fa: str
    content_en: str
    content_fa: str
    featured_image: Optional[str] = None
    og_image: Optional[str] = None
    author: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None
    updated_at: datetime
    created_at: datetime
    reading_time_min: int
    tags: list[BlogTagOut] = []

    class Config:
        from_attributes = True


class RedditConversionIn(BaseModel):
    event_type: Literal["SignUp", "Purchase"]
    order_id: Optional[str] = None
    click_id: Optional[str] = None
