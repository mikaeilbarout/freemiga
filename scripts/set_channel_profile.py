"""
One-off: completes the @freemigacom channel's profile — sets its photo and
"about" description via the Bot API's setChatPhoto / setChatDescription.
Requires the bot to already be a channel admin with "Change Channel Info"
permission (Post Messages alone, granted for scripts/post_channel_announcement.py,
isn't enough for this).

Reuses app/static/img/icon-512.png — the same square logo already used as
the site's Organization schema logo (see _seo_head.html) — as the channel
photo, rather than a separate asset.

Note: this only covers the CHANNEL's profile. A bot's own profile photo
has no Bot API equivalent — it's set manually via @BotFather's
/setuserpic command (upload a square image there directly).

Run on the server:
    docker compose exec app python -m scripts.set_channel_profile
"""
import httpx

from app.config import settings

_API_BASE = "https://api.telegram.org"
_CHANNEL = "@freemigacom"
_LOGO_PATH = "app/static/img/icon-512.png"

DESCRIPTION = "فریمیگا | VPN پرسرعت و بدون لاگ برای دور زدن سانسور.\nسایت: freemiga.com | بات: @FreemigaBot"


def _call(method: str, **kwargs) -> dict:
    r = httpx.post(f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}", timeout=15, **kwargs)
    data = r.json()
    if not data.get("ok"):
        raise SystemExit(
            f"{method} failed: {data}\n"
            f"Most likely cause: the bot doesn't have 'Change Channel Info' "
            f"admin rights on {_CHANNEL} yet."
        )
    print(f"{method}: ok")
    return data


def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set — nothing to do.")

    with open(_LOGO_PATH, "rb") as f:
        _call(
            "setChatPhoto",
            data={"chat_id": _CHANNEL},
            files={"photo": ("icon-512.png", f, "image/png")},
        )

    _call("setChatDescription", json={"chat_id": _CHANNEL, "description": DESCRIPTION})


if __name__ == "__main__":
    main()
