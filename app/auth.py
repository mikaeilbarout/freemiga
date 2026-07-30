import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(dk.hex(), hash_hex)


def get_current_customer(request: Request, db: Session = Depends(get_db)) -> Customer:
    customer_id = request.session.get("customer_id")
    if not customer_id:
        raise HTTPException(401, "Not logged in")
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer or customer.is_deleted:
        raise HTTPException(401, "Not logged in")
    return customer


def require_admin(request: Request) -> None:
    if not request.session.get("is_admin"):
        raise HTTPException(401, "Admin login required")
