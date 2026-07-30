"""
Thin client around the Marzban REST API.

Only the two calls this shop needs: get an admin token, and create a new
user tied to the VLESS inbound so it immediately gets a working
subscription link.
"""
import time
from datetime import datetime, timedelta

import httpx

from app.config import settings

_token_cache = {"token": None, "expires_at": 0}


async def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.MARZBAN_BASE_URL}/api/admin/token",
            data={
                "username": settings.MARZBAN_ADMIN_USERNAME,
                "password": settings.MARZBAN_ADMIN_PASSWORD,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"] = data["access_token"]
        # Tokens are typically valid ~24h server side; refresh a bit early.
        _token_cache["expires_at"] = now + 60 * 60 * 20
        return _token_cache["token"]


async def create_vpn_user(username: str, data_limit_gb: int, duration_days: int) -> dict:
    """
    Creates (or, if it already exists, raises) a Marzban user wired to the
    configured VLESS inbound, and returns the full subscription URL.
    """
    token = await _get_token()
    expire_ts = int((datetime.utcnow() + timedelta(days=duration_days)).timestamp())
    data_limit_bytes = data_limit_gb * 1024 * 1024 * 1024

    payload = {
        "username": username,
        "proxies": {"vless": {"flow": ""}},
        "inbounds": {"vless": [settings.MARZBAN_INBOUND_TAG]},
        "expire": expire_ts,
        "data_limit": data_limit_bytes,
        "data_limit_reset_strategy": "no_reset",
        "status": "active",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.MARZBAN_BASE_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    sub_path = data.get("subscription_url", "")
    full_sub_url = f"{settings.MARZBAN_BASE_URL}{sub_path}" if sub_path else None

    return {
        "username": data.get("username"),
        "subscription_url": full_sub_url,
    }


async def get_vpn_user(username: str) -> dict:
    token = await _get_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{settings.MARZBAN_BASE_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def extend_vpn_user(username: str, data_limit_gb: int, duration_days: int) -> dict:
    """
    Used for renewals: extends the user's expiry from whichever is later
    (their current expiry, or now) and tops up their data limit by the
    renewed plan's allowance. If the user no longer exists in Marzban
    (e.g. an admin deleted them by hand), falls back to creating them fresh
    instead of failing the renewal.
    """
    token = await _get_token()

    try:
        current = await get_vpn_user(username)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return await create_vpn_user(username, data_limit_gb, duration_days)
        raise

    now_ts = int(datetime.utcnow().timestamp())
    current_expire = current.get("expire") or now_ts
    base_ts = current_expire if current_expire > now_ts else now_ts
    new_expire = base_ts + duration_days * 24 * 60 * 60

    current_limit = current.get("data_limit")
    if not current_limit:
        # 0 (or unset) means unlimited in Marzban — stays unlimited on
        # renewal rather than being silently capped to just the newly-added
        # allowance.
        new_limit = 0
    else:
        added_bytes = data_limit_gb * 1024 * 1024 * 1024
        new_limit = current_limit + added_bytes

    payload = {"expire": new_expire, "data_limit": new_limit, "status": "active"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.put(
            f"{settings.MARZBAN_BASE_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    sub_path = data.get("subscription_url", "")
    full_sub_url = f"{settings.MARZBAN_BASE_URL}{sub_path}" if sub_path else None
    return {"username": data.get("username"), "subscription_url": full_sub_url}


async def set_user_status(username: str, active: bool) -> None:
    """Enables or disables a user's VPN access (used for ban/unban)."""
    token = await _get_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.put(
            f"{settings.MARZBAN_BASE_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "active" if active else "disabled"},
        )
        resp.raise_for_status()


async def delete_vpn_user(username: str) -> None:
    """Permanently removes a user from Marzban (used for account deletion).
    A 404 means it's already gone — treated as success, not an error."""
    token = await _get_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{settings.MARZBAN_BASE_URL}/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 404:
            return
        resp.raise_for_status()
