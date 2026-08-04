"""
Push side of the marzban-guard integration (the pull side — marzban-guard
reporting a ban back to us — is app/routers/integrations.py). marzban-guard
enforces one global device-count limit by default; this lets each of our
own plans carry a different allowance (e.g. a "Family" plan permitting
more concurrent devices) without marzban-guard needing to know anything
about plans.

Best-effort only: a failure here must never block order provisioning,
since the VPN account itself is already active by the time this runs —
worst case, that one customer is enforced under marzban-guard's global
default instead of their plan's allowance until the next successful call.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger("marzban_guard")


def is_configured() -> bool:
    return bool(settings.MARZBAN_GUARD_BASE_URL)


async def push_device_limit(username: str, max_devices: int | None) -> None:
    if not is_configured():
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"{settings.MARZBAN_GUARD_BASE_URL}/api/v1/admin/users/{username}/device-limit",
                json={"max_devices": max_devices},
                headers={"Authorization": f"Bearer {settings.MARZBAN_GUARD_ADMIN_API_KEY}"},
            )
            if resp.status_code >= 300:
                logger.warning(
                    "Failed to push device limit for %s to marzban-guard: %s %s",
                    username, resp.status_code, resp.text,
                )
    except Exception:
        logger.exception("Error pushing device limit for %s to marzban-guard", username)


async def push_ban_status(username: str, banned: bool, reason: str) -> None:
    """Admin-initiated ban/unban (routers/admin.py) calls Marzban directly
    to actually cut off access, but marzban-guard tracks its own
    active/suspended/disabled/blacklisted status per account independently
    (it never reads freemiga's database) — without this, a ban applied
    from freemiga's admin panel is invisible to marzban-guard's own
    dashboard/scoring, which would keep showing the account as "active"
    even though it's disabled in Marzban. This reuses marzban-guard's own
    manual-override endpoint (the same one an operator would use directly
    against marzban-guard) rather than needing marzban-guard to poll
    Marzban's status field to notice the change.

    Best-effort, same as push_device_limit: marzban-guard staying in sync
    is a dashboard/scoring-accuracy concern, not something that should be
    allowed to block a ban/unban that's already been applied to the real
    VPN account."""
    if not is_configured():
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.MARZBAN_GUARD_BASE_URL}/api/v1/admin/users/{username}/override",
                json={
                    "status": "disabled" if banned else "active",
                    "reason": reason,
                    "actor": "freemiga_admin",
                },
                headers={"Authorization": f"Bearer {settings.MARZBAN_GUARD_ADMIN_API_KEY}"},
            )
            if resp.status_code >= 300:
                logger.warning(
                    "Failed to push ban status for %s to marzban-guard: %s %s",
                    username, resp.status_code, resp.text,
                )
    except Exception:
        logger.exception("Error pushing ban status for %s to marzban-guard", username)
