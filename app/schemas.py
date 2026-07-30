import re
from datetime import datetime
from typing import Optional

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

    class Config:
        from_attributes = True


class PlanCreate(BaseModel):
    name: str
    price_usdt: float
    data_limit_gb: int
    duration_days: int


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price_usdt: Optional[float] = None
    data_limit_gb: Optional[int] = None
    duration_days: Optional[int] = None
    is_active: Optional[bool] = None


class OrderCreate(BaseModel):
    plan_id: str
    is_renewal: bool = False
    payment_method: str = "crypto"  # "crypto" or "card"
    crypto_network: Optional[str] = None  # "tron" or "polygon" — only used when payment_method == crypto


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

class TicketCreate(BaseModel):
    subject: str
    message: str


class GuestTicketCreate(BaseModel):
    username: str
    contact: Optional[str] = None
    subject: str
    message: str


class MessageCreate(BaseModel):
    message: str


class TicketMessageOut(BaseModel):
    sender: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: str
    subject: str
    status: str
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


class TicketAdminOut(BaseModel):
    id: str
    customer_id: str
    customer_username: str
    subject: str
    status: str
    created_at: datetime
    messages: list[TicketMessageOut]


# ---- Integrations (marzban-guard) ----

class MarzbanGuardStatusIn(BaseModel):
    username: str
    banned: bool
    reason: str = ""
