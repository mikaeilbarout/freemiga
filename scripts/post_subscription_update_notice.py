"""
One-off: posts a notice to the official channel (@freemigacom) telling
users to refresh their existing subscription in their app to pick up newly
added connection options — no new link/config needed.

Requires the bot to already be an admin of that channel with "Post
Messages" permission. Uses TELEGRAM_BOT_TOKEN from settings.

Run on the server:
    docker compose exec app python -m scripts.post_subscription_update_notice
"""
import httpx

from app.config import settings

_API_BASE = "https://api.telegram.org"
_CHANNEL = "@freemigacom"

ANNOUNCEMENT = (
    "🛡 بروزرسانی مهم فریمیگا\n\n"
    "گزینه‌های اتصال جدیدی (سرعت و پایداری بهتر) به اشتراک شما اضافه شد.\n\n"
    "برای دریافتشون نیازی به کانفیگ یا لینک جدید نیست — فقط کافیه تو اپتون "
    "(v2rayNG یا هر اپ دیگه‌ای که استفاده می‌کنید) اشتراک فعلی‌تون رو "
    "بروزرسانی/Refresh/Update کنید:\n\n"
    "📱 معمولاً یه آیکون رفرش یا دکمه \"Update Subscription\" کنار اسم "
    "اشتراکتون هست — روش بزنید.\n\n"
    "اگه بازم سوالی بود، همینجا در خدمتم."
)


def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set — nothing to do.")
    r = httpx.post(
        f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": _CHANNEL, "text": ANNOUNCEMENT},
        timeout=10,
    )
    data = r.json()
    if not data.get("ok"):
        raise SystemExit(
            f"sendMessage failed: {data}\n"
            f"Most likely cause: the bot isn't an admin of {_CHANNEL} yet, "
            "or doesn't have Post Messages permission there."
        )
    print(f"Posted to {_CHANNEL}: message_id {data['result']['message_id']}")


if __name__ == "__main__":
    main()
