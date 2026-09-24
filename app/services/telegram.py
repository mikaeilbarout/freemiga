"""
Low-level Telegram Bot API client + the long-poll loop. The actual
conversation (menus, signup-in-chat, checkout) lives in telegram_bot.py —
this module just knows how to talk to Telegram's HTTP API.
"""
import asyncio
import logging
import os
import sys
import tempfile

import httpx

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger("telegram")

_API_BASE = "https://api.telegram.org"

if sys.platform == "win32":
    import msvcrt

    _LOCK_PATH = os.path.join(tempfile.gettempdir(), "freemiga_telegram_poller.lock")
else:
    import fcntl

    _LOCK_PATH = "/tmp/freemiga_telegram_poller.lock"

_lock_file = None


def _acquire_singleton_lock() -> bool:
    global _lock_file
    _lock_file = open(_LOCK_PATH, "w")
    try:
        if sys.platform == "win32":
            _lock_file.write("lock")
            _lock_file.flush()
            _lock_file.seek(0)
            msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def is_configured() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN)


async def send_message(chat_id: str, text: str, reply_markup: dict | None = None) -> None:
    if not is_configured():
        logger.debug("Telegram not configured — skipping message to %s", chat_id)
        return
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
        )
        if resp.status_code != 200:
            logger.warning("Telegram sendMessage failed: %s", resp.text)


async def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    if not is_configured():
        return
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json=payload,
        )
        if resp.status_code != 200:
            logger.warning("Telegram answerCallbackQuery failed: %s", resp.text)


async def send_invoice(chat_id: str, title: str, description: str, payload: str, amount_stars: int) -> None:
    """Sends a native Telegram Stars invoice (currency "XTR") — the only
    payment path Telegram's own Affiliate Program pays commission on.
    provider_token must be present but empty for Stars; amount_stars is a
    plain integer count of Stars, not a minor-unit amount like normal
    currencies use."""
    if not is_configured():
        logger.debug("Telegram not configured — skipping invoice to %s", chat_id)
        return
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendInvoice",
            json={
                "chat_id": chat_id,
                "title": title,
                "description": description,
                "payload": payload,
                "provider_token": "",
                "currency": "XTR",
                "prices": [{"label": title, "amount": amount_stars}],
            },
        )
        if resp.status_code != 200:
            logger.warning("Telegram sendInvoice failed: %s", resp.text)


async def answer_pre_checkout_query(pre_checkout_query_id: str, ok: bool, error_message: str | None = None) -> None:
    if not is_configured():
        return
    payload = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
    if error_message:
        payload["error_message"] = error_message
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/answerPreCheckoutQuery",
            json=payload,
        )
        if resp.status_code != 200:
            logger.warning("Telegram answerPreCheckoutQuery failed: %s", resp.text)


def deep_link(token: str) -> str:
    """token is a one-time TelegramLinkToken (see routers/auth.py), never
    the customer id — this link hands over the account's Telegram channel,
    including password-reset codes."""
    if not settings.TELEGRAM_BOT_USERNAME:
        return ""
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"


async def notify_admin(text: str) -> None:
    if settings.ADMIN_TELEGRAM_CHAT_ID:
        await send_message(settings.ADMIN_TELEGRAM_CHAT_ID, text)


async def telegram_link_loop() -> None:
    if not is_configured():
        logger.info("TELEGRAM_BOT_TOKEN not set — telegram linking disabled")
        return

    if not _acquire_singleton_lock():
        logger.warning("Another process already holds the telegram-poller lock — skipping.")
        return

    # Imported here (not at module load) to avoid a circular import —
    # telegram_bot.py imports send_message/answer_callback_query from this module.
    from app.services import telegram_bot

    offset = 0
    async with httpx.AsyncClient(timeout=35) as client:
        while True:
            try:
                resp = await client.get(
                    f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                resp.raise_for_status()
                data = resp.json()
                updates = data.get("result", [])

                if updates:
                    db = SessionLocal()
                    try:
                        for update in updates:
                            await telegram_bot.handle_update(update, db)
                            offset = update["update_id"] + 1
                    finally:
                        db.close()
            except Exception:
                logger.exception("Telegram polling iteration failed")
                await asyncio.sleep(5)
