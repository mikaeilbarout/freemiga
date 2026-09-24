import asyncio
import logging
import os

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app import i18n
from app.auth import session_customer
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.lang import LANG_COOKIE, SUPPORTED_LANGUAGES, resolve_lang
from app.limiter import limiter
from app.models import BlogPost, BlogPostStatus, Customer, Plan
from app.routers import admin, auth, banners, blog_admin, integrations, orders, payments, plans, support, tracking
from app.services.minify import build_minified_assets
from app.services.telegram import telegram_link_loop

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.SITE_NAME)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many attempts — please slow down."})


@app.exception_handler(StarletteHTTPException)
async def branded_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exc)
    lang = resolve_lang(request)
    message = i18n.t(lang, "error_404_message") if exc.status_code == 404 else (exc.detail or i18n.t(lang, "error_generic_message"))
    return render(request, "error.html", code=exc.status_code, message=message, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error on %s", request.url.path)
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    lang = resolve_lang(request)
    return render(
        request, "error.html", code=500,
        message=i18n.t(lang, "error_500_message"),
        status_code=500,
    )

# The fallback and the .env.example placeholder are both public (the repo is
# public) — signing sessions with either lets anyone forge any session,
# including an admin one. Refuse to start in production (Secure cookies on)
# without a real secret; only a local http:// dev setup may fall back.
_PUBLIC_SESSION_SECRETS = {"", "change_me_to_a_random_64_char_hex_string"}
if settings.SESSION_SECRET in _PUBLIC_SESSION_SECRETS:
    if settings.SESSION_COOKIE_SECURE:
        raise RuntimeError(
            "SESSION_SECRET is not set to a real random value in .env — refusing to start. "
            "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    logging.warning(
        "SESSION_SECRET is not set in .env — using an insecure default. "
        "Only acceptable for local testing (SESSION_COOKIE_SECURE=false)."
    )
if settings.STRIPE_SECRET_KEY and not settings.STRIPE_WEBHOOK_SECRET:
    logging.warning(
        "STRIPE_SECRET_KEY is set but STRIPE_WEBHOOK_SECRET is not — "
        "card payments are disabled until the webhook secret is configured."
    )
if settings.NOWPAYMENTS_API_KEY and not settings.NOWPAYMENTS_IPN_SECRET:
    logging.warning(
        "NOWPAYMENTS_API_KEY is set but NOWPAYMENTS_IPN_SECRET is not — "
        "crypto payments are disabled until the IPN secret is configured."
    )
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET or "insecure-dev-secret-change-me",
    same_site="lax",
    https_only=settings.SESSION_COOKIE_SECURE,
)
# Compresses every response body over 500 bytes (HTML/CSS/JS/JSON) —
# added last so it wraps everything else and compresses the final output.
app.add_middleware(GZipMiddleware, minimum_size=500)

_CSP = (
    "default-src 'self'; "
    # Inline <script> blocks and onclick="..." handlers are used
    # throughout every template (not a build-step SPA) — 'unsafe-inline'
    # is required or the entire site's interactivity breaks. A stricter
    # nonce-based policy would need every inline handler rewritten to
    # addEventListener first; noted as follow-up work, not attempted here
    # given "never break existing functionality".
    # googletagmanager.com is gtag.js itself (see _fonts.html) — without
    # it here, the browser silently blocks the script (a CSP violation
    # logs to the console, nothing user-visible) and GA never receives a
    # single hit no matter how correctly GA_MEASUREMENT_ID is set.
    # redditstatic.com is the Reddit Pixel base script (same file, same
    # silent-block problem as gtag.js above).
    "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.redditstatic.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    # alb.reddit.com is where the Reddit Pixel actually sends its rp.gif
    # conversion beacon — loaded as an <img>, not fetched, so it belongs
    # in img-src rather than connect-src.
    "img-src 'self' data: https://www.googletagmanager.com https://alb.reddit.com; "
    # Where gtag.js actually sends hit data — googletagmanager.com for its
    # own config/collect calls, google-analytics.com (and its region1/2/...
    # subdomains) for the GA4 collect endpoint itself. Without these,
    # gtag.js loads fine but every measurement request it tries to send
    # is blocked the same silent way.
    # pixel-config.reddit.com is a config fetch the Reddit Pixel makes on
    # init, separate from the rp.gif beacon above.
    "connect-src 'self' https://www.googletagmanager.com https://www.google-analytics.com https://*.google-analytics.com https://*.analytics.google.com https://pixel-config.reddit.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = _CSP
    if settings.SESSION_COOKIE_SECURE:
        # Only advertised when the deployment actually expects HTTPS (same
        # flag that gates Secure-only cookies) — sending this over plain
        # HTTP is meaningless and would be actively wrong for local/dev use.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class CachedStaticFiles(StaticFiles):
    """Static assets are already cache-busted via the ?v=asset_version
    query param appended everywhere they're linked (see ASSET_VERSION
    below), so it's safe to tell browsers to cache the underlying files
    indefinitely — a new deploy changes the URL, not the cached one."""

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


templates = Jinja2Templates(directory="app/templates")
app.mount("/static", CachedStaticFiles(directory="app/static"), name="static")

# Minified .min.css/.min.js siblings, served instead of the hand-written
# originals — must run before ASSET_VERSION below, since that value gets
# baked into every asset URL the templates render.
build_minified_assets()

# Cache-busting query param for static assets (?v=...) — computed once at
# startup from style.css's mtime, which changes on every image rebuild
# (COPY resets file times) even when its content didn't change. Without
# this, browsers can keep serving an old cached CSS/JS file indefinitely
# after a deploy since /static/* has no other versioning.
try:
    ASSET_VERSION = str(int(os.path.getmtime("app/static/css/style.css")))
except OSError:
    ASSET_VERSION = "1"

# Order here drives both the hub page's card order and each dedicated
# page's "other devices" cross-link order (see guide.html / guide_os.html).
GUIDE_OS_SLUGS = ["ios", "android", "windows", "macos"]
GUIDE_APPS = {
    "ios": ["Streisand", "Hiddify", "V2Box"],
    "android": ["v2rayNG", "Hiddify", "NekoBox"],
    "windows": ["v2rayN", "Hiddify Next", "NekoRay"],
    "macos": ["Hiddify Next", "V2Box", "ClashX Pro"],
}


def render(request: Request, template_name: str, *, force_lang: str = None, status_code: int = 200, **extra_context):
    had_cookie = request.cookies.get(LANG_COOKIE) in SUPPORTED_LANGUAGES
    lang = force_lang or resolve_lang(request)
    other_lang = "fa" if lang == "en" else "en"

    # localized_page=True on the /{lang}/... routes (see index_localized
    # etc. below) — the language switch there is a straight link to the
    # same path under the other language prefix, not a cookie flip, so
    # Google (which doesn't carry cookies) can actually discover and index
    # both language versions of every marketing page independently.
    is_localized_page = extra_context.pop("localized_page", False)
    path = request.url.path
    segments = path.split("/")
    if is_localized_page and len(segments) > 1 and segments[1] in SUPPORTED_LANGUAGES:
        alt_segments = list(segments)
        alt_segments[1] = other_lang
        lang_switch_url = "/".join(alt_segments) or "/"
    else:
        lang_switch_url = f"/set-language?lang={other_lang}&next={path}"

    # Rendered server-side (instead of fetched client-side after paint) so
    # the nav's logged-in/out state is correct in the very first response
    # and never has to grow into place — that growth was a measured
    # ~0.11 CLS regression (an empty #navAuthSlot snapping to its real
    # size once /api/auth/me resolved).
    nav_user = None
    if request.session.get("customer_id"):
        nav_db = SessionLocal()
        try:
            customer = session_customer(request, nav_db)
            if customer:
                nav_user = customer.username
        finally:
            nav_db.close()

    context = {
        "request": request,
        "site_name": settings.SITE_NAME,
        "lang": lang,
        "dir": "rtl" if lang == "fa" else "ltr",
        "t": lambda key, **kw: i18n.t(lang, key, **kw),
        "asset_version": ASSET_VERSION,
        "nav_user": nav_user,
        "GUIDE_OS_SLUGS": GUIDE_OS_SLUGS,
        "GUIDE_APPS": GUIDE_APPS,
        # Every template can link to a marketing page in the visitor's
        # current language via {{ lang_prefix }}/plans etc., whether the
        # current page itself is a localized one or not (e.g. /pay/{id}
        # linking to /guide).
        "lang_prefix": f"/{lang}",
        "lang_switch_url": lang_switch_url,
        "site_base_url": settings.SITE_BASE_URL,
        "ga_measurement_id": settings.GA_MEASUREMENT_ID,
        "gsc_verification": settings.GSC_VERIFICATION,
        "bing_verification": settings.BING_VERIFICATION,
        "google_ads_conversion_id": settings.GOOGLE_ADS_CONVERSION_ID,
        "google_ads_conversion_label": settings.GOOGLE_ADS_CONVERSION_LABEL,
        "reddit_pixel_id": settings.REDDIT_PIXEL_ID,
        **extra_context,
    }
    response = templates.TemplateResponse(template_name, context, status_code=status_code)
    if is_localized_page:
        # Explicitly visiting /en/... or /fa/... (typed, bookmarked, or
        # clicked from a Google result) is a stronger signal than the
        # original auto-detect-once cookie, so it always wins.
        response.set_cookie(LANG_COOKIE, lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    elif not force_lang and not had_cookie:
        response.set_cookie(LANG_COOKIE, lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response

app.include_router(auth.router)
app.include_router(plans.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(support.router)
app.include_router(admin.router)
app.include_router(banners.router)
app.include_router(banners.admin_router)
app.include_router(blog_admin.router)
app.include_router(integrations.router)
app.include_router(tracking.router)


def _seed_plans() -> None:
    db = SessionLocal()
    try:
        if db.query(Plan).count() == 0:
            db.add_all([
                Plan(name="Free Trial", price_usdt=0, data_limit_gb=1, duration_days=1, max_devices=1),
                Plan(name="Basic", price_usdt=5, data_limit_gb=10, duration_days=30, max_devices=2),
                Plan(name="Standard", price_usdt=9, data_limit_gb=30, duration_days=30, max_devices=3),
                Plan(name="Unlimited", price_usdt=15, data_limit_gb=100, duration_days=30, max_devices=5),
            ])
            db.commit()
    finally:
        db.close()


@app.on_event("startup")
async def on_startup():
    # Under Docker/Postgres, schema setup runs once as its own process
    # BEFORE gunicorn starts (see scripts/init_db.py + Dockerfile) — running
    # multiple gunicorn workers through create_all() concurrently races on
    # creating the Postgres enum types and crashes. This call stays here
    # only for convenience when running locally without Docker (single
    # process, SQLite, no race); it's a harmless no-op once tables already
    # exist, and any leftover race is swallowed defensively either way.
    try:
        Base.metadata.create_all(bind=engine)
        _seed_plans()
    except Exception:
        logging.exception("Schema setup on startup failed — continuing, assuming another worker handled it")
    asyncio.create_task(telegram_link_loop())


# ---- Pages (server just serves the shell; JS in each page calls the API) ----

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# path (relative to /{lang}), changefreq, priority — used to build sitemap.xml
SITEMAP_PAGES = [
    ("", "weekly", "1.0"),
    ("plans", "weekly", "0.9"),
    ("how-it-works", "monthly", "0.7"),
    ("features", "monthly", "0.7"),
    ("guide", "monthly", "0.6"),
    ("guide/ios", "monthly", "0.6"),
    ("guide/android", "monthly", "0.6"),
    ("guide/windows", "monthly", "0.6"),
    ("guide/macos", "monthly", "0.6"),
    ("terms", "yearly", "0.3"),
    ("blog", "weekly", "0.7"),
    ("faq", "monthly", "0.6"),
    ("about", "yearly", "0.4"),
    ("contact", "yearly", "0.4"),
    ("privacy", "yearly", "0.3"),
    ("refund-policy", "yearly", "0.3"),
    ("cookies", "yearly", "0.3"),
]


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    site = settings.SITE_BASE_URL.rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /dashboard",
        "Disallow: /billing",
        "Disallow: /account",
        "Disallow: /support",
        "Disallow: /pay/",
        "Disallow: /admin",
        "Disallow: /api/",
        "Disallow: /set-language",
        # Transactional/utility pages, same reasoning as the ones above —
        # no unique content to rank on, and none currently emit a meta
        # description (see _seo_head.html) since they were never meant to
        # be indexed. Marketing/conversion content lives on /plans and the
        # home page, which link to these, not the other way around.
        "Disallow: /login",
        "Disallow: /signup",
        "Disallow: /forgot-password",
        "",
        f"Sitemap: {site}/sitemap.xml",
    ]
    return "\n".join(lines)


# llms.txt (https://llmstxt.org) — a curated, plain-language summary of the
# site for AI assistants/crawlers, distinct from robots.txt/sitemap.xml
# which are about crawl permissions and page discovery, not content. Kept
# static (like the SEO meta descriptions elsewhere) rather than pulled from
# the DB — this is a stable "what is this site" summary, not live pricing.
@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    site = settings.SITE_BASE_URL.rstrip("/")
    name = settings.SITE_NAME
    lines = [
        f"# {name}",
        "",
        f"> {name} is a fast, no-log VPN service (V2Ray/VLESS/Xray-based) for bypassing "
        "internet censorship, protecting online privacy, and streaming without restrictions. "
        "Plans start at $2.99/month, payable by card or crypto (USDT on Tron/Polygon). "
        "Available in English and Persian, with support for iOS, Android, Windows, and macOS.",
        "",
        "## Key pages",
        f"- [Plans & pricing]({site}/en/plans): compare solo, family, and team VPN plans.",
        f"- [How it works]({site}/en/how-it-works): sign up, choose a plan, connect in minutes.",
        f"- [Setup guides]({site}/en/guide): step-by-step connection guides per device (iOS, Android, Windows, macOS).",
        f"- [Features]({site}/en/features): no-log policy, server speed, 24/7 support.",
        f"- [FAQ]({site}/en/faq): pricing, payment methods, refunds, device limits, logging policy.",
        f"- [Blog]({site}/en/blog): guides on VPN protocols, encryption, and online privacy.",
        f"- [About]({site}/en/about): why {name} was built and how it stays no-log.",
        f"- [Contact]({site}/en/contact): support contact information.",
        "",
        "## Optional",
        f"- [Terms of service]({site}/en/terms)",
        f"- [Privacy policy]({site}/en/privacy)",
        f"- [Refund policy]({site}/en/refund-policy)",
        f"- [Cookie policy]({site}/en/cookies)",
    ]
    return "\n".join(lines)


# Required by the IndexNow protocol so a search engine can confirm this
# site actually controls the key it's pinging with — only registered at
# all once an operator sets INDEXNOW_KEY, same "empty means not set up
# yet" convention as the other search-engine settings.
if settings.INDEXNOW_KEY:
    @app.get(f"/{settings.INDEXNOW_KEY}.txt", response_class=PlainTextResponse)
    def indexnow_key_file():
        return settings.INDEXNOW_KEY


@app.get("/sitemap.xml")
def sitemap_xml():
    site = settings.SITE_BASE_URL.rstrip("/")
    entries = []
    for path, changefreq, priority in SITEMAP_PAGES:
        suffix = f"/{path}" if path else "/"
        en_url = f"{site}/en{suffix}"
        fa_url = f"{site}/fa{suffix}"
        for loc in (en_url, fa_url):
            entries.append(f"""  <url>
    <loc>{loc}</loc>
    <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>
    <xhtml:link rel="alternate" hreflang="fa" href="{fa_url}"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="{en_url}"/>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    db = SessionLocal()
    try:
        posts = db.query(BlogPost).filter(BlogPost.status == BlogPostStatus.published).all()
        for p in posts:
            en_url = f"{site}/en/blog/{p.slug}"
            fa_url = f"{site}/fa/blog/{p.slug}"
            lastmod = p.updated_at.strftime("%Y-%m-%d")
            for loc in (en_url, fa_url):
                entries.append(f"""  <url>
    <loc>{loc}</loc>
    <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>
    <xhtml:link rel="alternate" hreflang="fa" href="{fa_url}"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="{en_url}"/>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")
    finally:
        db.close()

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(entries) +
        "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@app.get("/set-language")
def set_language(request: Request, lang: str, next: str = "/"):
    lang = lang if lang in SUPPORTED_LANGUAGES else settings.DEFAULT_LANGUAGE
    # Browsers treat "\" like "/", so "/\evil.com" would leave the site
    # just like "//evil.com" does.
    safe_next = next if next.startswith("/") and not next.startswith("//") and "\\" not in next else "/"
    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(LANG_COOKIE, lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


SITE_URL = settings.SITE_BASE_URL.rstrip("/")


def _localized(request: Request, lang: str, template_name: str, **extra_context):
    if lang not in SUPPORTED_LANGUAGES:
        raise StarletteHTTPException(404)
    return render(request, template_name, force_lang=lang, localized_page=True, **extra_context)


def _redirect_to_localized(request: Request, path: str, status_code: int) -> RedirectResponse:
    # Preserve the query string (UTM/campaign params, etc.) — a bare
    # redirect target would silently drop anything after "?".
    target = f"/{resolve_lang(request)}{path}"
    if request.url.query:
        target += f"?{request.url.query}"
    return RedirectResponse(url=target, status_code=status_code)


# ---- Marketing pages — localized under /en/... and /fa/... so Google can
# crawl and index each language independently (it never carries the cookie
# the old single-URL, cookie-switched pages relied on). The old bare paths
# below 301-redirect to whichever language the visitor would have gotten
# before, preserving any existing bookmarks/backlinks/search rankings
# instead of just breaking them.

@app.get("/{lang}/", response_class=HTMLResponse)
def index_localized(request: Request, lang: str):
    return _localized(request, lang, "home.html")


@app.get("/{lang}/plans", response_class=HTMLResponse)
def plans_page_localized(request: Request, lang: str):
    db = SessionLocal()
    try:
        active_plans = db.query(Plan).filter(Plan.is_active == True).order_by(Plan.price_usdt).all()  # noqa: E712
        # Plain dicts, not ORM objects: the template renders the plan cards
        # server-side (for SEO/no-JS reliability — see plans_page.html) AND
        # embeds this same list as JSON for the client-side pagination
        # script, so it needs to be both Jinja-attribute-accessible and
        # JSON-serializable without any extra conversion in the template.
        plans = [
            {
                "id": p.id, "name": p.name, "price_usdt": p.price_usdt,
                "data_limit_gb": p.data_limit_gb, "duration_days": p.duration_days,
                "max_devices": p.max_devices,
            }
            for p in active_plans
        ]
    finally:
        db.close()
    return _localized(request, lang, "plans_page.html", plans=plans)


@app.get("/{lang}/how-it-works", response_class=HTMLResponse)
def how_it_works_page_localized(request: Request, lang: str):
    return _localized(request, lang, "how_it_works.html")


@app.get("/{lang}/features", response_class=HTMLResponse)
def features_page_localized(request: Request, lang: str):
    return _localized(request, lang, "features.html")


@app.get("/{lang}/guide", response_class=HTMLResponse)
def guide_page_localized(request: Request, lang: str):
    return _localized(request, lang, "guide.html")


@app.get("/{lang}/guide/{os_slug}", response_class=HTMLResponse)
def guide_os_page_localized(request: Request, lang: str, os_slug: str):
    if os_slug not in GUIDE_OS_SLUGS:
        raise StarletteHTTPException(404)
    return _localized(request, lang, "guide_os.html", os=os_slug)


@app.get("/{lang}/terms", response_class=HTMLResponse)
def terms_page_localized(request: Request, lang: str):
    return _localized(request, lang, "terms.html", updated_at="July 30, 2026")


@app.get("/{lang}/faq", response_class=HTMLResponse)
def faq_page_localized(request: Request, lang: str):
    return _localized(request, lang, "faq.html")


@app.get("/{lang}/about", response_class=HTMLResponse)
def about_page_localized(request: Request, lang: str):
    return _localized(request, lang, "about.html")


@app.get("/{lang}/contact", response_class=HTMLResponse)
def contact_page_localized(request: Request, lang: str):
    return _localized(request, lang, "contact.html")


@app.get("/{lang}/privacy", response_class=HTMLResponse)
def privacy_page_localized(request: Request, lang: str):
    return _localized(request, lang, "privacy.html")


@app.get("/{lang}/refund-policy", response_class=HTMLResponse)
def refund_policy_page_localized(request: Request, lang: str):
    return _localized(request, lang, "refund_policy.html")


@app.get("/{lang}/cookies", response_class=HTMLResponse)
def cookies_page_localized(request: Request, lang: str):
    return _localized(request, lang, "cookies.html")


BLOG_PAGE_SIZE = 9


def _blog_post_view(post: BlogPost, lang: str) -> dict:
    is_fa = lang == "fa"
    return {
        "slug": post.slug,
        "title": post.title_fa if is_fa else post.title_en,
        "excerpt": post.excerpt_fa if is_fa else post.excerpt_en,
        "content": post.content_fa if is_fa else post.content_en,
        "featured_image": post.featured_image,
        "og_image": post.og_image,
        "author": post.author,
        "category_name": (post.category.name_fa if is_fa else post.category.name_en) if post.category else None,
        "tags": [t.name_fa if is_fa else t.name_en for t in post.tags],
        "reading_time_min": post.reading_time_min,
        "published_display": post.published_at.strftime("%B %d, %Y") if post.published_at else "",
        "published_iso": (post.published_at or post.created_at).isoformat() + "Z",
        "modified_iso": post.updated_at.isoformat() + "Z",
    }


@app.get("/{lang}/blog", response_class=HTMLResponse)
def blog_list_localized(request: Request, lang: str, page: int = 1):
    if lang not in SUPPORTED_LANGUAGES:
        raise StarletteHTTPException(404)
    page = max(1, page)
    db = SessionLocal()
    try:
        query = (
            db.query(BlogPost)
            .options(selectinload(BlogPost.category))
            .filter(BlogPost.status == BlogPostStatus.published)
            .order_by(BlogPost.published_at.desc())
        )
        total = query.count()
        rows = query.offset((page - 1) * BLOG_PAGE_SIZE).limit(BLOG_PAGE_SIZE).all()
        posts = [_blog_post_view(p, lang) for p in rows]
    finally:
        db.close()
    total_pages = max(1, -(-total // BLOG_PAGE_SIZE))
    return _localized(request, lang, "blog_list.html", posts=posts, page=page, total_pages=total_pages)


@app.get("/{lang}/blog/{slug}", response_class=HTMLResponse)
def blog_detail_localized(request: Request, lang: str, slug: str):
    if lang not in SUPPORTED_LANGUAGES:
        raise StarletteHTTPException(404)
    db = SessionLocal()
    try:
        post = (
            db.query(BlogPost)
            .options(selectinload(BlogPost.category), selectinload(BlogPost.tags))
            .filter(BlogPost.slug == slug, BlogPost.status == BlogPostStatus.published)
            .first()
        )
        if not post:
            raise StarletteHTTPException(404)
        related_query = db.query(BlogPost).options(selectinload(BlogPost.category)).filter(
            BlogPost.status == BlogPostStatus.published, BlogPost.id != post.id
        )
        if post.category_id:
            related_query = related_query.filter(BlogPost.category_id == post.category_id)
        related_rows = related_query.order_by(BlogPost.published_at.desc()).limit(3).all()
        related_posts = [_blog_post_view(p, lang) for p in related_rows]
        post_view = _blog_post_view(post, lang)
    finally:
        db.close()
    return _localized(
        request, lang, "blog_detail.html", post=post_view, related_posts=related_posts
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # Root is the one URL where visitor-preferred-language detection still
    # makes sense — a 302 (not 301) since the "right" target differs per
    # visitor/cookie and must never be treated as a permanent alias for one
    # specific language.
    return _redirect_to_localized(request, "/", 302)


@app.get("/plans", response_class=HTMLResponse)
def plans_page(request: Request):
    return _redirect_to_localized(request, "/plans", 301)


@app.get("/how-it-works", response_class=HTMLResponse)
def how_it_works_page(request: Request):
    return _redirect_to_localized(request, "/how-it-works", 301)


@app.get("/features", response_class=HTMLResponse)
def features_page(request: Request):
    return _redirect_to_localized(request, "/features", 301)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html")


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return render(request, "signup.html")


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return render(request, "forgot_password.html")


# All four logged-in app pages share one template (a sidebar shell) — the
# route only decides which section starts active; switching sections after
# that happens client-side (see app_shell.html) with no further navigation.
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return render(request, "app_shell.html", active_section="overview", page_title_key="dashboard_page_title")


@app.get("/billing", response_class=HTMLResponse)
def billing_page(request: Request):
    return render(request, "app_shell.html", active_section="billing", page_title_key="billing_page_title")


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    return render(request, "app_shell.html", active_section="account", page_title_key="account_page_title")


@app.get("/support", response_class=HTMLResponse)
def support_page(request: Request):
    return render(request, "app_shell.html", active_section="support", page_title_key="support_page_title")


@app.get("/pay/{order_id}", response_class=HTMLResponse)
def pay_page(request: Request, order_id: str):
    return render(request, "pay.html")


@app.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return _redirect_to_localized(request, "/terms", 301)


@app.get("/guide", response_class=HTMLResponse)
def guide_page(request: Request):
    return _redirect_to_localized(request, "/guide", 301)


@app.get("/guide/{os_slug}", response_class=HTMLResponse)
def guide_os_page(request: Request, os_slug: str):
    if os_slug not in GUIDE_OS_SLUGS:
        raise StarletteHTTPException(404)
    return _redirect_to_localized(request, f"/guide/{os_slug}", 301)


@app.get("/blog", response_class=HTMLResponse)
def blog_page(request: Request):
    return _redirect_to_localized(request, "/blog", 301)


@app.get("/faq", response_class=HTMLResponse)
def faq_page(request: Request):
    return _redirect_to_localized(request, "/faq", 301)


@app.get("/about", response_class=HTMLResponse)
def about_page(request: Request):
    return _redirect_to_localized(request, "/about", 301)


@app.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return _redirect_to_localized(request, "/contact", 301)


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return _redirect_to_localized(request, "/privacy", 301)


@app.get("/refund-policy", response_class=HTMLResponse)
def refund_policy_page(request: Request):
    return _redirect_to_localized(request, "/refund-policy", 301)


@app.get("/cookies", response_class=HTMLResponse)
def cookies_page(request: Request):
    return _redirect_to_localized(request, "/cookies", 301)


@app.get("/blog/{slug}", response_class=HTMLResponse)
def blog_post_page(request: Request, slug: str):
    return _redirect_to_localized(request, f"/blog/{slug}", 301)


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return render(request, "admin.html", force_lang="en", no_ga=True)
