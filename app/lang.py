"""
Shared language-resolution helpers used by both page routes (app/main.py)
and API routers that need to localize error messages. Split out from
main.py to avoid a circular import (main.py imports the routers).
"""
from fastapi import Request

from app.config import settings
from app.services.geoip import country_for_ip

LANG_COOKIE = "lang"
SUPPORTED_LANGUAGES = ("en", "fa")


def client_ip(request: Request) -> str:
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # nginx appends the actual connecting IP as the last hop; trust
        # that one rather than the first (client-suppliable) entry.
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else ""


def resolve_lang(request: Request) -> str:
    cookie_lang = request.cookies.get(LANG_COOKIE)
    if cookie_lang in SUPPORTED_LANGUAGES:
        return cookie_lang
    country = country_for_ip(client_ip(request))
    if country and country in settings.PERSIAN_COUNTRIES:
        return "fa"
    return settings.DEFAULT_LANGUAGE if settings.DEFAULT_LANGUAGE in SUPPORTED_LANGUAGES else "en"


def get_lang(request: Request) -> str:
    """FastAPI dependency — Depends(get_lang) in any router."""
    return resolve_lang(request)
