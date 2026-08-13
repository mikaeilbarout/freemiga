"""
One-off: sets the Telegram bot's profile description and short description
via the Bot API, adding a pointer to the official channel (@freemigacom).

Uses TELEGRAM_BOT_TOKEN from settings, same as app/services/telegram.py —
requires a real token in the environment (production only; the .env.example
placeholder is empty).

Edit DESCRIPTION / SHORT_DESCRIPTION below before running if the wording
needs to change — this only sets whatever is defined here, it doesn't read
or preserve whatever bio is currently live.

Run on the server:
    docker compose exec app python -m scripts.set_telegram_bot_bio
"""
import httpx

from app.config import settings

_API_BASE = "https://api.telegram.org"

# Shown on the bot's profile, next to its name (Bot API limit: 120 chars).
SHORT_DESCRIPTION = "Fast, no-log VPN to bypass censorship. 30 GB free for 30 days. freemiga.com | @freemigacom"

# Shown on the empty chat screen before a user taps Start (Bot API limit: 512 chars).
DESCRIPTION = (
    "Fast, no-log VPN to bypass censorship\n"
    "30 GB Free For 30 Days\n"
    "Website: freemiga.com\n"
    "Channel: @freemigacom"
)


def _call(method: str, **params) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set — nothing to do.")
    r = httpx.post(f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}", json=params, timeout=10)
    data = r.json()
    if not data.get("ok"):
        raise SystemExit(f"{method} failed: {data}")
    print(f"{method}: ok")


def main() -> None:
    _call("setMyDescription", description=DESCRIPTION)
    _call("setMyShortDescription", short_description=SHORT_DESCRIPTION)


if __name__ == "__main__":
    main()
