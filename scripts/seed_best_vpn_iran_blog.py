"""
One-time content seed — publishes a practical "Best VPN for Iran" guide.

Unlike the existing protocol/encryption explainer posts (seed_vpn_proxy_blog.py,
seed_vpn_technology_encryption_blog.py), this is a high-intent, decision-focused
post aimed at people actively searching for a working VPN in Iran rather than
people researching how VPNs work in general. Links out to the existing
protocol/technology posts for depth instead of re-explaining them.

Reuses the "VPN & Proxy Guides" category (queried by slug, never duplicated)
and the existing "VPN" tag; adds one new "Iran" tag.

Created directly with status=published (not draft, unlike the other seed
scripts) since the published_at-on-publish behavior in
routers/blog_admin.py:236 is replicated here rather than requiring a manual
admin-panel publish step afterward.

Idempotent by slug: safe to re-run, existing posts are left untouched.

Run once, after the app's tables already exist:
    python -m scripts.seed_best_vpn_iran_blog
or, in the Docker deployment:
    docker compose exec app python -m scripts.seed_best_vpn_iran_blog
"""
from datetime import datetime

from app.database import SessionLocal
from app.models import BlogCategory, BlogPost, BlogPostStatus, BlogTag
from app.services.blog import reading_time_minutes, slugify

CATEGORY = {"name_en": "VPN & Proxy Guides", "name_fa": "راهنمای VPN و پروکسی"}

TAGS = [
    {"name_en": "VPN", "name_fa": "VPN"},
    {"name_en": "Iran", "name_fa": "ایران"},
]

POST = {
    "slug": "best-vpn-for-iran",
    "title_en": "Best VPN for Iran in 2026: What Actually Works and Why",
    "title_fa": "بهترین VPN برای ایران در ۲۰۲۶: چه چیزی واقعاً کار می‌کند و چرا",
    "excerpt_en": "Most VPNs stop working in Iran within days. Here's what actually separates a VPN that keeps a stable connection from one that gets blocked — and how to get set up.",
    "excerpt_fa": "اغلب VPNها ظرف چند روز در ایران از کار می‌افتند. در این مقاله بررسی می‌شود چه چیزی یک VPN پایدار را از یک VPN مسدودشونده متمایز می‌کند و چگونه می‌توان شروع به کار کرد.",
    "content_en": """
<p>A VPN that works perfectly in most countries can stop connecting entirely within days of being used in Iran. This isn't random bad luck — it's the direct result of active, ongoing network filtering that specifically targets VPN traffic, not just individual websites. Here's what actually determines whether a VPN keeps working, and what to look for.</p>

<h2>Why Regular VPNs Get Blocked in Iran</h2>
<p>Most consumer VPNs (including the free ones bundled into browsers) use protocols like plain OpenVPN or IKEv2 with a small, static pool of server IPs. Iran's filtering infrastructure uses deep packet inspection (DPI) to recognize the distinctive "signature" of these protocols, and maintains blocklists of known VPN server IPs — both of which are straightforward to detect and block once a provider's server range becomes known. A VPN that isn't specifically built to resist this gets progressively slower or fully blocked as its servers get identified, often within days of a spike in usage.</p>

<h2>What to Look for in a VPN for Iran</h2>

<h3>A Protocol Built to Resist DPI</h3>
<p>The single biggest factor is protocol choice. VLESS over Xray, run behind TLS, is built specifically to make VPN traffic indistinguishable from ordinary encrypted web browsing (HTTPS) — rather than having a detectable pattern DPI can flag. This is covered in depth in <a href="/en/blog/v2ray-xray-vless-explained">our breakdown of V2Ray, Xray, and VLESS</a> and <a href="/en/blog/vpn-protocols-explained">our full protocol comparison</a>.</p>

<h3>Frequent Server and IP Rotation</h3>
<p>Even a well-obfuscated protocol eventually gets flagged if the same server IPs stay in use indefinitely. A provider that actively rotates and adds new server IPs keeps ahead of blocklisting instead of going quiet once existing servers get caught.</p>

<h3>A Genuine No-Logs Policy</h3>
<p>Encryption hides the contents of traffic, but the provider itself can still see connection metadata unless it has a real no-logs policy — not just a marketing claim. This matters more in a high-censorship context than almost anywhere else.</p>

<h3>Payment Options That Actually Work</h3>
<p>International card payments frequently fail for users in Iran due to banking sanctions, which rules out most VPNs' checkout flow before the technical side even matters. A provider needs to support payment methods that are actually reachable — locally-friendly card processing and cryptocurrency, at minimum.</p>

<h3>Support for Multiple Devices</h3>
<p>A single subscription that only covers one device forces a choice between phone and laptop. Look for a plan that covers a household's real device count, not just one.</p>

<h2>Getting Connected: Step by Step</h2>
<ol>
<li><strong>Create an account.</strong> No personal ID or phone verification should be required to sign up.</li>
<li><strong>Start with a free trial if one is available.</strong> A real trial (not just a time-limited demo of a slower tier) lets you confirm the connection is stable on your specific network before paying anything.</li>
<li><strong>Install a compatible client app.</strong> VLESS/Xray-based services work with clients such as v2rayNG (Android) or V2rayTun (iOS) — the provider should give you a ready-made config or QR code rather than requiring manual setup.</li>
<li><strong>Import the config and connect.</strong> With a proper client and config, this is normally a single tap.</li>
</ol>

<h2>How Freemiga Is Built for This</h2>
<p>Freemiga runs on VLESS over Xray with TLS by default (see <a href="/en/blog/understanding-vpn-technology">our overview of how the protocol, encryption, and feature layers fit together</a>), rotates server IPs to stay ahead of blocklisting, and keeps a strict no-logs policy. Signup takes no personal ID, payment works by card or crypto, and every new account gets a free 30&nbsp;GB / 30-day trial — enough to genuinely test the connection before committing to a plan.</p>

<h2>Frequently Asked Questions</h2>
<h3>Why did my old VPN stop working after a few days?</h3>
<p>This almost always means the provider's server IPs got added to a blocklist, or its protocol's traffic signature got flagged by DPI. Providers that don't actively rotate server IPs or use DPI-resistant protocols are the most exposed to this.</p>
<h3>Will a VPN work during a full internet shutdown?</h3>
<p>No. A VPN routes existing internet traffic through an encrypted tunnel — it cannot restore connectivity if the underlying internet access itself is cut off entirely. VPNs help against filtering and throttling, not a total shutdown.</p>
<h3>Is a free trial actually useful, or just a limited demo?</h3>
<p>It depends entirely on the provider. A trial worth using gives full access to the same servers and protocol as a paid plan, just for a limited time or data amount — enough to confirm real-world stability on your own network before paying.</p>

<h2>Get Started</h2>
<p>Every new Freemiga account includes a free 30&nbsp;GB / 30-day trial, no card required. <a href="/en/plans">Compare Freemiga's VPN plans</a> and test the connection for yourself.</p>
""",
    "content_fa": """
<p>یک VPN که در اغلب کشورها بی‌نقص کار می‌کند، ممکن است ظرف چند روز پس از استفاده در ایران به‌طور کامل از اتصال بازبماند. این موضوع تصادفی نیست، بلکه نتیجه مستقیم فیلترینگ فعال و مستمر شبکه است که مشخصاً ترافیک VPN را هدف قرار می‌دهد، نه صرفاً وب‌سایت‌های خاص. در این مقاله بررسی می‌شود چه عاملی واقعاً تعیین می‌کند یک VPN پایدار بماند، و به چه مواردی باید توجه کرد.</p>

<h2>چرا VPNهای معمولی در ایران مسدود می‌شوند؟</h2>
<p>اغلب VPNهای مصرفی (از جمله نسخه‌های رایگان داخل مرورگرها) از پروتکل‌هایی مانند OpenVPN ساده یا IKEv2 همراه با مجموعه‌ای کوچک و ثابت از آی‌پی‌های سرور استفاده می‌کنند. زیرساخت فیلترینگ ایران از بازرسی عمیق بسته‌ها (DPI) برای شناسایی «امضای» متمایز این پروتکل‌ها استفاده می‌کند و فهرست‌هایی از آی‌پی‌های شناخته‌شده سرورهای VPN نگه می‌دارد؛ هر دوی این روش‌ها، پس از شناخته‌شدن محدوده سرورهای یک ارائه‌دهنده، به‌سادگی قابل شناسایی و مسدودسازی هستند. VPN‌ای که مشخصاً برای مقاومت در برابر این روند طراحی نشده باشد، به‌تدریج کندتر می‌شود یا کاملاً مسدود می‌شود؛ اغلب ظرف چند روز پس از افزایش استفاده.</p>

<h2>به چه مواردی باید در انتخاب VPN برای ایران توجه کرد؟</h2>

<h3>پروتکلی مقاوم در برابر DPI</h3>
<p>مهم‌ترین عامل، انتخاب پروتکل است. VLESS بر بستر Xray و همراه با TLS، مشخصاً برای شبیه‌سازی ترافیک VPN به مرور عادی و رمزنگاری‌شده وب (HTTPS) طراحی شده است، به‌جای داشتن الگویی قابل‌شناسایی برای DPI. بررسی کامل این موضوع در <a href="/fa/blog/v2ray-xray-vless-explained">مقاله V2Ray، Xray و VLESS</a> و <a href="/fa/blog/vpn-protocols-explained">مقایسه کامل پروتکل‌ها</a> ارائه شده است.</p>

<h3>چرخش مکرر سرور و آی‌پی</h3>
<p>حتی یک پروتکل به‌خوبی مبهم‌سازی‌شده نیز در نهایت شناسایی می‌شود اگر همان آی‌پی‌های سرور به‌طور نامحدود در استفاده باقی بمانند. ارائه‌دهنده‌ای که به‌طور فعال آی‌پی‌های سرور را چرخش داده و جدید اضافه می‌کند، از فرآیند فهرست‌سازی مسدودی جلوتر می‌ماند، به‌جای آنکه پس از شناسایی سرورهای موجود، از کار بیفتد.</p>

<h3>سیاست بدون‌لاگ واقعی</h3>
<p>رمزنگاری محتوای ترافیک را پنهان می‌کند، اما خودِ ارائه‌دهنده همچنان قادر به مشاهده متادیتای اتصال است، مگر آنکه سیاست بدون‌لاگ واقعی داشته باشد — نه صرفاً یک ادعای تبلیغاتی. این موضوع در شرایط فیلترینگ شدید، بیش از تقریباً هر جای دیگری اهمیت دارد.</p>

<h3>روش‌های پرداخت که واقعاً کار می‌کنند</h3>
<p>پرداخت با کارت‌های بین‌المللی، به دلیل تحریم‌های بانکی، اغلب برای کاربران ایرانی با شکست مواجه می‌شود؛ این موضوع پیش از آنکه جنبه فنی اصلاً مطرح شود، فرآیند خرید اغلب VPNها را غیرقابل‌استفاده می‌کند. یک ارائه‌دهنده باید روش‌های پرداختی را پشتیبانی کند که واقعاً در دسترس باشند؛ حداقل، پرداخت کارتی متناسب با شرایط محلی و ارز دیجیتال.</p>

<h3>پشتیبانی از چند دستگاه</h3>
<p>یک اشتراک که فقط یک دستگاه را پوشش می‌دهد، کاربر را مجبور به انتخاب میان گوشی و لپ‌تاپ می‌کند. به‌دنبال پلنی باشید که تعداد واقعی دستگاه‌های یک خانواده را پوشش دهد، نه فقط یکی.</p>

<h2>مراحل اتصال</h2>
<ol>
<li><strong>ساخت حساب کاربری.</strong> نباید نیازی به مدرک شناسایی یا تأیید شماره تلفن برای ثبت‌نام باشد.</li>
<li><strong>در صورت وجود، از پلن آزمایشی رایگان شروع کنید.</strong> یک پلن آزمایشی واقعی (نه صرفاً یک نسخه محدود و کندتر) امکان می‌دهد پیش از هرگونه پرداخت، پایداری اتصال روی شبکه خاص خودتان را بررسی کنید.</li>
<li><strong>نصب یک اپلیکیشن سازگار.</strong> سرویس‌های مبتنی بر VLESS/Xray با اپلیکیشن‌هایی مانند v2rayNG (اندروید) یا V2rayTun (آی‌او‌اس) کار می‌کنند؛ ارائه‌دهنده باید یک کانفیگ آماده یا کد QR در اختیار بگذارد، نه آنکه نیاز به تنظیم دستی باشد.</li>
<li><strong>وارد کردن کانفیگ و اتصال.</strong> با یک اپلیکیشن و کانفیگ مناسب، این مرحله معمولاً تنها یک ضربه است.</li>
</ol>

<h2>فریمیگا چگونه برای این شرایط ساخته شده است؟</h2>
<p>فریمیگا به‌طور پیش‌فرض بر بستر VLESS و Xray همراه با TLS فعالیت می‌کند (نگاه کنید به <a href="/fa/blog/understanding-vpn-technology">نگاهی جامع به لایه‌های پروتکل، رمزنگاری و ویژگی‌ها</a>)، آی‌پی سرورها را برای جلوتر ماندن از فهرست‌سازی مسدودی چرخش می‌دهد و سیاست بدون‌لاگ سخت‌گیرانه‌ای دارد. ثبت‌نام بدون نیاز به مدرک شناسایی است، پرداخت با کارت یا ارز دیجیتال امکان‌پذیر است، و هر حساب جدید یک پلن آزمایشی رایگان ۳۰ گیگابایتی و ۳۰ روزه دریافت می‌کند؛ کافی برای بررسی واقعی اتصال پیش از تعهد به یک پلن.</p>

<h2>پرسش‌های متداول</h2>
<h3>چرا VPN قبلی من پس از چند روز از کار افتاد؟</h3>
<p>این موضوع تقریباً همیشه به این معناست که آی‌پی‌های سرور ارائه‌دهنده به یک فهرست مسدودی اضافه شده‌اند، یا امضای ترافیک پروتکل آن توسط DPI شناسایی شده است. ارائه‌دهندگانی که به‌طور فعال آی‌پی سرور را چرخش نمی‌دهند یا از پروتکل‌های مقاوم در برابر DPI استفاده نمی‌کنند، بیشترین آسیب‌پذیری را دارند.</p>
<h3>آیا VPN در زمان قطعی کامل اینترنت کار می‌کند؟</h3>
<p>خیر. یک VPN، ترافیک اینترنتی موجود را از طریق یک تونل رمزنگاری‌شده مسیریابی می‌کند و در صورتی که دسترسی زیرساختی به اینترنت به‌طور کامل قطع شود، قادر به بازگرداندن اتصال نیست. VPN در برابر فیلترینگ و کندسازی کمک‌کننده است، نه یک قطعی کامل.</p>
<h3>آیا پلن آزمایشی رایگان واقعاً مفید است یا صرفاً یک نسخه محدود؟</h3>
<p>این کاملاً به ارائه‌دهنده بستگی دارد. یک پلن آزمایشی ارزشمند، دسترسی کامل به همان سرورها و پروتکل پلن پولی را فراهم می‌کند، صرفاً برای مدت یا حجم محدود؛ کافی برای بررسی پایداری واقعی روی شبکه خودتان پیش از پرداخت.</p>

<h2>اکنون شروع کنید</h2>
<p>هر حساب جدید فریمیگا شامل یک پلن آزمایشی رایگان ۳۰ گیگابایتی و ۳۰ روزه است، بدون نیاز به کارت بانکی. <a href="/fa/plans">پلن‌های VPN فریمیگا را مقایسه کنید</a> و اتصال را شخصاً امتحان کنید.</p>
""",
}


def seed() -> None:
    db = SessionLocal()
    try:
        category = db.query(BlogCategory).filter(BlogCategory.slug == slugify(CATEGORY["name_en"])).first()
        if not category:
            category = BlogCategory(
                slug=slugify(CATEGORY["name_en"]),
                name_en=CATEGORY["name_en"],
                name_fa=CATEGORY["name_fa"],
            )
            db.add(category)
            db.commit()
            db.refresh(category)

        tags = []
        for t in TAGS:
            tag = db.query(BlogTag).filter(BlogTag.slug == slugify(t["name_en"])).first()
            if not tag:
                tag = BlogTag(slug=slugify(t["name_en"]), name_en=t["name_en"], name_fa=t["name_fa"])
                db.add(tag)
                db.commit()
                db.refresh(tag)
            tags.append(tag)

        if db.query(BlogPost).filter(BlogPost.slug == POST["slug"]).first():
            print("Already exists — skipped.")
            return

        post = BlogPost(
            slug=POST["slug"],
            category_id=category.id,
            title_en=POST["title_en"],
            title_fa=POST["title_fa"],
            excerpt_en=POST["excerpt_en"],
            excerpt_fa=POST["excerpt_fa"],
            content_en=POST["content_en"].strip(),
            content_fa=POST["content_fa"].strip(),
            status=BlogPostStatus.published,
            published_at=datetime.utcnow(),
            reading_time_min=reading_time_minutes(POST["content_en"]),
            tags=tags,
        )
        db.add(post)
        db.commit()
        print("Done — post created and published.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
