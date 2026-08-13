"""
One-off: prints the bot's current Telegram Stars balance via the Bot API's
getMyStarBalance method — useful when BotFather's own menus don't surface
it directly (it only shows up there once the bot has star transactions,
and the exact menu path has moved around across Telegram app versions).

Run on the server:
    docker compose exec app python -m scripts.check_telegram_star_balance
"""
import httpx

from app.config import settings

_API_BASE = "https://api.telegram.org"


def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set — nothing to check.")
    r = httpx.get(f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/getMyStarBalance", timeout=10)
    data = r.json()
    if not data.get("ok"):
        raise SystemExit(f"getMyStarBalance failed: {data}")
    amount = data["result"].get("amount", 0)
    print(f"Bot Stars balance: {amount} ⭐")
    print(
        "Withdrawable via Fragment (fragment.com) once you have at least "
        "1,000 Stars — newly earned Stars become withdrawable 21 days "
        "after being received."
    )


if __name__ == "__main__":
    main()
