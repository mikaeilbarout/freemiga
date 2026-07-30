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
