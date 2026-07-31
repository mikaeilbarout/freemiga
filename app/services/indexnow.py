import logging

import httpx

from app.config import settings

logger = logging.getLogger("indexnow")

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"


async def ping_urls(urls: list[str]) -> None:
    """
    Tells IndexNow-participating search engines (Bing, Yandex, and others)
    that these URLs changed, instead of waiting for their next crawl.
    No-ops silently if INDEXNOW_KEY isn't configured — this is best-effort
    notification, never something a request should fail over.
    """
    if not settings.INDEXNOW_KEY or not urls:
        return
    host = settings.SITE_BASE_URL.rstrip("/").split("://", 1)[-1]
    payload = {
        "host": host,
        "key": settings.INDEXNOW_KEY,
        "keyLocation": f"{settings.SITE_BASE_URL.rstrip('/')}/{settings.INDEXNOW_KEY}.txt",
        "urlList": urls,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(INDEXNOW_ENDPOINT, json=payload)
    except httpx.HTTPError:
        logger.exception("IndexNow ping failed")
