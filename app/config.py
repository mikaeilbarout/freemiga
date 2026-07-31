import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Marzban panel
    MARZBAN_BASE_URL: str = os.getenv("MARZBAN_BASE_URL", "https://panel.freemiga.com:8000")
    MARZBAN_ADMIN_USERNAME: str = os.getenv("MARZBAN_ADMIN_USERNAME", "")
    MARZBAN_ADMIN_PASSWORD: str = os.getenv("MARZBAN_ADMIN_PASSWORD", "")
    MARZBAN_INBOUND_TAG: str = os.getenv("MARZBAN_INBOUND_TAG", "VLESS_WS_TLS")

    # Crypto payment — self-hosted USDT (TRC20) wallet. Customer sends the
    # exact plan price to this address, then submits their transaction hash
    # for on-chain verification via TronGrid. This is a PUBLIC address only —
    # we never hold the private key.
    TRON_USDT_WALLET_ADDRESS: str = os.getenv("TRON_USDT_WALLET_ADDRESS", "")
    TRONGRID_API_KEY: str = os.getenv("TRONGRID_API_KEY", "")
    TRONGRID_API_BASE: str = os.getenv("TRONGRID_API_BASE", "https://api.trongrid.io")
    # Official Tether USDT contract on Tron mainnet — fixed, not meant to change.
    USDT_TRC20_CONTRACT_ADDRESS: str = os.getenv(
        "USDT_TRC20_CONTRACT_ADDRESS", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    )

    # Second crypto network — Polygon. Same self-hosted-wallet approach as
    # Tron above, verified via the unified Etherscan API (PolygonScan's API
    # was folded into it) instead of TronGrid.
    POLYGON_USDT_WALLET_ADDRESS: str = os.getenv("POLYGON_USDT_WALLET_ADDRESS", "")
    POLYGONSCAN_API_KEY: str = os.getenv("POLYGONSCAN_API_KEY", "")
    POLYGONSCAN_API_BASE: str = os.getenv("POLYGONSCAN_API_BASE", "https://api.etherscan.io/v2/api")
    POLYGON_CHAIN_ID: int = int(os.getenv("POLYGON_CHAIN_ID", "137"))
    # Official (PoS) Tether USDT contract on Polygon — fixed, not meant to
    # change. Verified against PolygonScan directly (see app/services/
    # polygon_gateway.py) rather than trusted from memory.
    USDT_POLYGON_CONTRACT_ADDRESS: str = os.getenv(
        "USDT_POLYGON_CONTRACT_ADDRESS", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
    )

    # Crypto payment (NowPayments — legacy, no longer used for checkout)
    NOWPAYMENTS_API_KEY: str = os.getenv("NOWPAYMENTS_API_KEY", "")
    NOWPAYMENTS_IPN_SECRET: str = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
    NOWPAYMENTS_API_BASE: str = os.getenv("NOWPAYMENTS_API_BASE", "https://api.nowpayments.io/v1")

    # Order behaviour
    ORDER_EXPIRY_MINUTES: int = int(os.getenv("ORDER_EXPIRY_MINUTES", "30"))

    # Card/bank payment (Stripe) — alternative to crypto, fixed prices
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./freemiga.db")

    # Public base URL of this site (used to build links, not required for API-only use)
    SITE_BASE_URL: str = os.getenv("SITE_BASE_URL", "http://localhost:8001")

    # Session cookies (customer login + admin panel)
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "")
    # Set to "true" once running behind Cloudflare/Nginx HTTPS (production).
    # Keep "false" only for local http://127.0.0.1 testing.
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
    # Login for THIS site's admin panel — deliberately separate from the
    # Marzban admin account so leaking one doesn't expose the other.
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # Telegram notifications (order delivered, account banned, password reset)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "FreemigaBot")
    # Your own chat id, so the bot can DM *you* about new orders/tickets.
    # Get it by messaging your bot once, then checking:
    #   https://api.telegram.org/bot<TOKEN>/getUpdates
    ADMIN_TELEGRAM_CHAT_ID: str = os.getenv("ADMIN_TELEGRAM_CHAT_ID", "")

    # Direct support contact (shown as buttons in the Telegram bot's support menu)
    TELEGRAM_SUPPORT_USERNAME: str = os.getenv("TELEGRAM_SUPPORT_USERNAME", "")
    SUPPORT_EMAIL: str = os.getenv("SUPPORT_EMAIL", "")

    # Email (Resend) — signup verification
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "Freemiga <onboarding@resend.dev>")

    # Shared secret the separate marzban-guard abuse-detection system uses
    # to authenticate calls to POST /api/integrations/marzban-guard/status
    # (see app/routers/integrations.py). Leave empty to keep that endpoint
    # disabled — marzban-guard still enforces restrictions directly
    # against Marzban either way, this just keeps this shop's own
    # Customer.is_banned flag (and the customer-facing notice) in sync.
    MARZBAN_GUARD_WEBHOOK_SECRET: str = os.getenv("MARZBAN_GUARD_WEBHOOK_SECRET", "")

    # The other direction: this shop pushes each plan's device-count
    # allowance to marzban-guard's admin API whenever an order is
    # provisioned (see app/services/marzban_guard.py). Leave
    # MARZBAN_GUARD_BASE_URL empty to skip this entirely — plans just
    # won't have a per-plan device limit enforced, only marzban-guard's
    # own global default.
    MARZBAN_GUARD_BASE_URL: str = os.getenv("MARZBAN_GUARD_BASE_URL", "")
    MARZBAN_GUARD_ADMIN_API_KEY: str = os.getenv("MARZBAN_GUARD_ADMIN_API_KEY", "")

    SITE_NAME: str = os.getenv("SITE_NAME", "Freemiga")

    # Search engine / analytics verification — all optional, empty means
    # "not set up yet" and the corresponding tag/route is simply omitted
    # rather than emitting a broken placeholder.
    GA_MEASUREMENT_ID: str = os.getenv("GA_MEASUREMENT_ID", "")  # e.g. "G-XXXXXXXXXX"
    GSC_VERIFICATION: str = os.getenv("GSC_VERIFICATION", "")  # Search Console HTML tag content=""
    BING_VERIFICATION: str = os.getenv("BING_VERIFICATION", "")  # Bing Webmaster Tools meta content
    # IndexNow key — any string you choose. Once set, the site serves
    # GET /{key}.txt (required by the protocol so search engines can
    # confirm you control the domain) and pings IndexNow after each blog
    # post is published (see app/services/indexnow.py).
    INDEXNOW_KEY: str = os.getenv("INDEXNOW_KEY", "")

    # Language (website i18n)
    # Local MaxMind GeoLite2-Country database used to pick the default
    # language for a first-time visitor. See README for how to get one —
    # the site works fine without it, it just always falls back to
    # DEFAULT_LANGUAGE for new visitors until the file is in place.
    GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "app/data/GeoLite2-Country.mmdb")
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")
    # ISO country codes that default to Persian, comma-separated.
    PERSIAN_COUNTRIES: set = {c.strip().upper() for c in os.getenv("PERSIAN_COUNTRIES", "IR,AF").split(",") if c.strip()}


settings = Settings()
