"""
One-off content seed: publishes a starter batch of hyper-local blog posts
targeting censorship-circumvention search intent (see SEO audit — topical
authority around Iran-specific access problems was the one real content gap;
meta tags, hreflang, FAQ/HowTo schema, and heading structure were already in
place). Idempotent by slug, like init_db.py's seed_plans() — safe to re-run.

Reuses the existing "VPN & Proxy Guides" category and "VPN"/"Iran" tags
(same ones seed_best_vpn_iran_blog.py uses, queried by slug, never
duplicated) instead of a new standalone category — a post in its own
category never turns up in another post's category-filtered "related
posts" section (see app/main.py:blog_detail_localized), which is why an
earlier version of this post, seeded into its own "guides" category, had
no related-post links to the rest of the blog. Also links out to the
existing protocol and "best VPN for Iran" posts inline, matching how
those posts already cross-link to each other.

Run once on the server after a deploy:
    docker compose exec app python -m scripts.seed_blog_posts
"""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import BlogCategory, BlogPost, BlogPostStatus, BlogTag
from app.services.blog import reading_time_minutes, slugify

CATEGORY = {"name_en": "VPN & Proxy Guides", "name_fa": "راهنمای VPN و پروکسی"}
TAGS = [
    {"name_en": "VPN", "name_fa": "VPN"},
    {"name_en": "Iran", "name_fa": "ایران"},
]


def _get_or_create_category(db, name_en: str, name_fa: str) -> BlogCategory:
    slug = slugify(name_en)
    category = db.query(BlogCategory).filter(BlogCategory.slug == slug).first()
    if category:
        return category
    category = BlogCategory(slug=slug, name_en=name_en, name_fa=name_fa)
    db.add(category)
    db.flush()
    return category


def _get_or_create_tags(db, tags: list[dict]) -> list[BlogTag]:
    result = []
    for t in tags:
        slug = slugify(t["name_en"])
        tag = db.query(BlogTag).filter(BlogTag.slug == slug).first()
        if not tag:
            tag = BlogTag(slug=slug, name_en=t["name_en"], name_fa=t["name_fa"])
            db.add(tag)
            db.flush()
        result.append(tag)
    return result


POSTS = [
    {
        "slug": "access-blocked-messaging-apps-iran",
        "title_en": "How to Access Blocked Messaging Apps in Iran",
        "title_fa": "چطور به اپ‌های پیام‌رسان مسدودشده در ایران دسترسی داشته باشیم",
        "excerpt_en": (
            "WhatsApp, Telegram, and Instagram are routinely blocked or throttled "
            "inside Iran. Here's how a VPN restores access, and what actually "
            "makes some VPN protocols work better than others on filtered networks."
        ),
        "excerpt_fa": (
            "واتس‌اپ، تلگرام و اینستاگرام معمولاً در ایران مسدود یا کندشده‌اند. "
            "این‌جا توضیح می‌دهیم که یک VPN چطور دسترسی را برمی‌گرداند و چرا بعضی "
            "پروتکل‌های VPN روی شبکه‌های فیلترشده بهتر از بقیه کار می‌کنند."
        ),
        "content_en": """
<p>Messaging apps like WhatsApp, Telegram, and Instagram have faced repeated
blocking and heavy throttling inside Iran over the past several years,
usually during periods of unrest or around specific events. When that
happens, the apps don't just get slow — they often stop connecting
entirely, even though the same apps work fine for friends and family
outside the country.</p>

<h2>Why these apps get blocked</h2>
<p>Blocking usually happens at the network level: internet providers are
ordered to filter traffic to specific app servers or IP ranges. The app
itself isn't broken — the connection between your device and its servers
is being intercepted or dropped before it gets there. That's why simply
reinstalling the app or switching Wi-Fi networks rarely helps for long.</p>

<h2>How a VPN restores access</h2>
<p>A VPN routes your traffic through an encrypted tunnel to a server
outside the filtered network, then out to the internet from there. To the
local network, it looks like you're just talking to one destination (the
VPN server) — it can't see or block the messaging traffic riding inside
that tunnel. That's the basic mechanism behind restoring access to
WhatsApp, Telegram, Instagram, and any other blocked service.</p>

<h2>Why protocol choice matters</h2>
<p>Not every VPN protocol handles heavily filtered networks equally well.
Older protocols are relatively easy for deep packet inspection to
fingerprint and block outright, which is why connections can fail even
with a VPN turned on. Freemiga is built on V2Ray/VLESS/Xray — protocols
designed specifically to blend in with ordinary encrypted web traffic
rather than announcing themselves as VPN traffic, which is why they tend
to keep working on networks where older protocols get flagged. See
<a href="/en/blog/v2ray-xray-vless-explained">our breakdown of V2Ray, Xray, and VLESS</a>
for how that actually works under the hood.</p>

<h2>Setting it up</h2>
<p>Getting messaging apps working again takes three steps: sign up, pick a
plan (a free trial plan is available if you want to test speed and
compatibility first), and follow the <a href="/en/guide">setup guide</a>
for your device — Windows, macOS, iOS, and Android are all covered.
Freemiga runs a strict no-log policy, and plans can be paid by card or
with USDT (Tron or Polygon network) if you'd rather not use a card.</p>

<p>Once connected, messaging apps typically reconnect within moments —
no reinstall or account changes needed. If messaging apps aren't the only
thing you're fighting with, see our full guide to
<a href="/en/blog/best-vpn-for-iran">what actually keeps a VPN working in Iran</a>.</p>
""".strip(),
        "content_fa": """
<p>اپ‌های پیام‌رسانی مثل واتس‌اپ، تلگرام و اینستاگرام در چند سال اخیر، معمولاً
در دوره‌های ناآرامی یا هم‌زمان با رویدادهای خاص، بارها در ایران مسدود یا به‌شدت
کندشده‌اند. در این حالت‌ها اپ‌ها فقط کند نمی‌شوند — اغلب اصلاً وصل نمی‌شوند،
درحالی‌که همان اپ‌ها برای دوستان و خانواده خارج از کشور به‌خوبی کار می‌کنند.</p>

<h2>چرا این اپ‌ها مسدود می‌شوند</h2>
<p>مسدودسازی معمولاً در سطح شبکه اتفاق می‌افتد: به ارائه‌دهنده‌های اینترنت
دستور داده می‌شود ترافیک به سمت سرورها یا بازه‌های IP خاصی را فیلتر کنند.
خود اپ خراب نیست — اتصال بین دستگاه تو و سرورهایش قبل از رسیدن، رهگیری یا قطع
می‌شود. به همین دلیل نصب دوباره اپ یا عوض کردن وای‌فای معمولاً کمک زیادی
نمی‌کند.</p>

<h2>یک VPN چطور دسترسی را برمی‌گرداند</h2>
<p>یک VPN ترافیک تو را از یک تونل رمزنگاری‌شده به سمت سروری خارج از شبکه
فیلترشده هدایت می‌کند و از آن‌جا به اینترنت وصل می‌شود. از دید شبکه محلی،
تو فقط داری با یک مقصد (سرور VPN) صحبت می‌کنی — نمی‌تواند ترافیک پیام‌رسانی
داخل آن تونل را ببیند یا مسدود کند. این همان مکانیزم اصلی برگرداندن دسترسی
به واتس‌اپ، تلگرام، اینستاگرام و هر سرویس مسدودشده دیگری‌ست.</p>

<h2>چرا انتخاب پروتکل مهم است</h2>
<p>همه پروتکل‌های VPN به یک اندازه روی شبکه‌های شدیداً فیلترشده خوب کار
نمی‌کنند. پروتکل‌های قدیمی‌تر نسبتاً راحت توسط بازرسی عمیق بسته‌ها (DPI)
شناسایی و کاملاً مسدود می‌شوند، و به همین دلیل ممکن است حتی با روشن بودن
VPN هم اتصال قطع شود. فریمیگا روی V2Ray/VLESS/Xray ساخته شده — پروتکل‌هایی
که مخصوصاً طوری طراحی شده‌اند که شبیه ترافیک وب رمزنگاری‌شده معمولی به‌نظر
برسند، نه این‌که خودشان را به‌عنوان ترافیک VPN اعلام کنند، و به همین دلیل
معمولاً روی شبکه‌هایی که پروتکل‌های قدیمی‌تر شناسایی می‌شوند، همچنان کار
می‌کنند. برای جزئیات فنی بیشتر، <a href="/fa/blog/v2ray-xray-vless-explained">نگاهی به V2Ray، Xray و VLESS</a> را ببین.</p>

<h2>راه‌اندازی</h2>
<p>برگرداندن اپ‌های پیام‌رسان به کار سه مرحله دارد: ثبت‌نام، انتخاب یک پلن
(یک پلن آزمایشی رایگان هم موجود است اگر بخواهی اول سرعت و سازگاری را تست
کنی)، و دنبال‌کردن <a href="/fa/guide">راهنمای نصب</a> برای دستگاهت —
ویندوز، مک، آیفون و اندروید همه پوشش داده شده‌اند. فریمیگا سیاست سخت‌گیرانه
بدون لاگ دارد، و پلن‌ها را می‌توان با کارت یا با USDT (شبکه ترون یا پالیگان)
پرداخت کرد اگر ترجیح می‌دهی از کارت استفاده نکنی.</p>

<p>بعد از وصل شدن، اپ‌های پیام‌رسان معمولاً در عرض چند لحظه دوباره وصل
می‌شوند — بدون نیاز به نصب دوباره یا تغییر حساب کاربری. اگر فقط پیام‌رسان‌ها
مسئله نیستند، <a href="/fa/blog/best-vpn-for-iran">راهنمای کامل چه چیزی یک VPN را در ایران پایدار نگه می‌دارد</a> را هم ببین.</p>
""".strip(),
    },
]


def seed_blog_posts() -> None:
    db = SessionLocal()
    try:
        category = _get_or_create_category(db, CATEGORY["name_en"], CATEGORY["name_fa"])
        tags = _get_or_create_tags(db, TAGS)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for data in POSTS:
            if db.query(BlogPost).filter(BlogPost.slug == data["slug"]).first():
                continue
            db.add(BlogPost(
                slug=slugify(data["slug"]),
                category_id=category.id,
                title_en=data["title_en"],
                title_fa=data["title_fa"],
                excerpt_en=data["excerpt_en"],
                excerpt_fa=data["excerpt_fa"],
                content_en=data["content_en"],
                content_fa=data["content_fa"],
                og_image=None,
                reading_time_min=reading_time_minutes(data["content_en"]),
                status=BlogPostStatus.published,
                published_at=now,
                updated_at=now,
                tags=tags,
            ))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_blog_posts()
    print("Blog posts seeded.")
