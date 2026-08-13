"""
One-off: posts the Freemiga intro announcement to the official channel
(@freemigacom) via the bot — requires the bot to already be an admin of
that channel with "Post Messages" permission.

Uses TELEGRAM_BOT_TOKEN from settings, same as every other script in this
directory. Edit ANNOUNCEMENT below before running if the wording needs to
change.

Run on the server:
    docker compose exec app python -m scripts.post_channel_announcement
"""
import httpx

from app.config import settings

_API_BASE = "https://api.telegram.org"
_CHANNEL = "@freemigacom"

ANNOUNCEMENT = (
    "<b>🛡 فریمیگا | Freemiga</b>\n\n"
    "فیلترشکن پرسرعت، بدون ثبت لاگ، برای دور زدن سانسور و دسترسی آزاد به "
    "اینترنت — از هر جا، از جمله ایران.\n\n"
    "<b>چرا فریمیگا؟</b>\n"
    "🔹 سیاست کاملاً بدون لاگ — هیچ ردی از فعالیت، بازدید یا دانلودت ذخیره نمی‌شه\n"
    "🔹 مبتنی بر پروتکل‌های V2Ray / VLESS / Xray — طوری طراحی شده که ترافیکش "
    "شبیه یک اتصال HTTPS معمولی به‌نظر برسه، نه یک VPN قابل‌شناسایی\n"
    "🔹 پشتیبانی از iOS، Android، Windows و macOS\n"
    "🔹 پرداخت با کارت یا ارز دیجیتال (USDT روی شبکه ترون یا پالیگان)\n"
    "🔹 پشتیبانی ۲۴ ساعته\n\n"
    "<b>۳۰ گیگ رایگان برای ۳۰ روز</b> — همین الان امتحانش کن، بدون نیاز به کارت بانکی.\n\n"
    "📲 شروع سریع از داخل بات: @FreemigaBot\n"
    "🌐 وبسایت و مشاهده پلن‌ها: freemiga.com"
)


def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set — nothing to do.")
    r = httpx.post(
        f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": _CHANNEL, "text": ANNOUNCEMENT, "parse_mode": "HTML"},
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
