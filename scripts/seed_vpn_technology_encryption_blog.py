"""
One-time content seed — publishes two blog posts: a "VPN Technology" pillar
overview and a dedicated "What Is VPN Encryption?" deep dive.

"VPN Technology" deliberately does NOT re-explain individual protocols
(OpenVPN/WireGuard/VLESS) or the V2Ray/Xray/VMess stack in depth — both are
already covered by scripts/seed_vpn_proxy_blog.py's "vpn-protocols-explained"
and "v2ray-xray-vless-explained" posts, and duplicating that content would
just cannibalize the same search terms. Instead it's a higher-level overview
(protocol layer / encryption layer / feature layer) that links out to those
two posts, and to the new encryption post here, for depth — a hub linking to
the existing cluster rather than a rewrite of it.

Reuses the same "VPN & Proxy Guides" category as seed_vpn_proxy_blog.py
(queried by slug, never duplicated) and follows the same structure/formal
Persian register as its posts: intro, H2/H3 sections, an FAQ section, and a
closing CTA linking to /plans.

Idempotent by slug: safe to re-run since existing posts are left untouched
and only missing ones are created — same pattern as scripts/init_db.py's
seed_plans() and scripts/seed_vpn_proxy_blog.py's seed().

Run once, after the app's tables already exist:
    python -m scripts.seed_vpn_technology_encryption_blog
or, in the Docker deployment:
    docker compose exec app python -m scripts.seed_vpn_technology_encryption_blog
"""
from datetime import datetime

from app.database import SessionLocal
from app.models import BlogCategory, BlogPost, BlogPostStatus, BlogTag
from app.services.blog import reading_time_minutes, slugify

CATEGORY = {"name_en": "VPN & Proxy Guides", "name_fa": "راهنمای VPN و پروکسی"}

TAGS = [
    {"name_en": "VPN", "name_fa": "VPN"},
    {"name_en": "Protocols", "name_fa": "پروتکل‌ها"},
    {"name_en": "Encryption", "name_fa": "رمزنگاری"},
]

POSTS = [
    {
        "slug": "understanding-vpn-technology",
        "title_en": "Understanding VPN Technology: How Modern VPNs Actually Work",
        "title_fa": "فناوری VPN چگونه کار می‌کند؟ نگاهی جامع به اجزای یک VPN مدرن",
        "excerpt_en": "A big-picture look at how modern VPN technology actually works — the protocol layer, the encryption layer, and the features that separate a real VPN from a basic one.",
        "excerpt_fa": "نگاهی کلی و رسمی به نحوه عملکرد فناوری VPN مدرن؛ بررسی لایه پروتکل، لایه رمزنگاری و ویژگی‌هایی که یک VPN واقعی را از یک ابزار ابتدایی متمایز می‌کنند.",
        "content_en": """
<p>"VPN technology" covers a lot of ground — protocols, encryption standards, and a long list of features that vary wildly between providers. This is the big-picture view: how the pieces fit together, and what actually separates a serious VPN from a basic IP-changing tool.</p>

<h2>Three Layers That Make Up a VPN</h2>
<p>Every VPN connection is really three things working together: a <strong>protocol</strong> that defines how the encrypted tunnel is built and transported, an <strong>encryption standard</strong> that scrambles data so only the user and the server can read it, and a set of <strong>features</strong> built on top that determine how much real protection and control a person actually gets. Marketing tends to blur these together — understanding them separately makes it much easier to judge what's actually being paid for.</p>

<h2>Layer 1: The Protocol</h2>
<p>The protocol decides how a device and the VPN server talk to each other — and, critically, what that traffic looks like to anyone watching the network in between. Established protocols like OpenVPN and WireGuard prioritize speed and broad compatibility. On networks that actively detect and block VPN traffic, though, a different category of protocol matters more: ones like VLESS, built specifically to make a connection indistinguishable from ordinary encrypted web browsing. This is covered in full detail in <a href="/en/blog/vpn-protocols-explained">our guide to VPN protocols</a>, with an even deeper look at the VLESS/Xray stack Freemiga runs on in <a href="/en/blog/v2ray-xray-vless-explained">this breakdown of V2Ray, Xray, and VLESS</a>.</p>

<h2>Layer 2: Encryption</h2>
<p>Encryption is what actually keeps the contents of traffic private once the tunnel is established — the difference between someone seeing scrambled noise versus real browsing activity. Modern VPNs rely on well-established, publicly audited ciphers (AES-256, ChaCha20), not proprietary "black box" encryption. This is broken down in plain language in <a href="/en/blog/what-is-vpn-encryption">our guide to VPN encryption</a>.</p>

<h2>Layer 3: The Features That Separate a Real VPN From a Basic One</h2>
<h3>Kill Switch</h3>
<p>A kill switch blocks all internet traffic if the VPN connection drops unexpectedly, instead of silently falling back to a normal, unprotected connection. Without one, a brief disconnect can expose traffic that was assumed to be protected the entire time.</p>

<h3>Split Tunneling</h3>
<p>Split tunneling allows choosing which apps go through the VPN and which use the regular connection — useful when a specific app should always route through the VPN while everything else keeps local network speed.</p>

<h3>Obfuscation</h3>
<p>Obfuscation is what makes VPN traffic resistant to deep packet inspection (DPI) — the technique some networks use to detect and block VPN usage itself, not just specific sites. This is the single most important feature for anyone on a network that actively restricts VPN access, and it's a direct result of protocol choice (see Layer 1).</p>

<h3>No-Logs Policy</h3>
<p>Encryption protects traffic in transit, but the VPN provider itself can still see a user's real IP address and connection metadata. A genuine no-logs policy — not just a marketing claim — determines whether that information is ever stored at all.</p>

<h3>Multi-Device, Simultaneous Connections</h3>
<p>How many devices can use one subscription at once is a practical feature with nothing to do with security, but it affects whether a plan actually fits how someone uses it day to day.</p>

<h2>How Freemiga Puts These Layers Together</h2>
<p>Freemiga runs on VLESS over Xray with TLS (protocol layer), AES-256/ChaCha20-grade encryption via that TLS layer (encryption layer), and is built specifically to keep working on networks that actively try to detect and block VPN traffic — the feature that matters most for our users.</p>

<h2>Frequently Asked Questions</h2>
<h3>Is newer VPN technology always better?</h3>
<p>Not necessarily "better" in every sense — newer protocols like VLESS are specifically better at resisting detection on restrictive networks, while established ones like OpenVPN have a longer track record of independent security review. The right choice depends on the network in question, not just the release date of the technology.</p>
<h3>Does stronger encryption mean a slower connection?</h3>
<p>Modern ciphers like AES-256 and ChaCha20 are fast enough on any current device that the difference is negligible in practice. Connection speed is affected far more by protocol choice, server load, and distance to the server than by encryption strength.</p>
<h3>What VPN technology does Freemiga use?</h3>
<p>Freemiga runs on the VLESS protocol over Xray-core with TLS encryption, chosen specifically to stay connectable on networks that actively block conventional VPN traffic.</p>

<h2>Get Started</h2>
<p>Understanding every layer isn't required to benefit from it — Freemiga handles the technology, all that's needed is a plan and a compatible app. <a href="/en/plans">Compare Freemiga's VPN plans</a> and get connected in a few minutes.</p>
""",
        "content_fa": """
<p>عبارت «فناوری VPN» دامنه گسترده‌ای را در بر می‌گیرد: پروتکل‌ها، استانداردهای رمزنگاری و فهرست بلندی از ویژگی‌ها که میان ارائه‌دهندگان مختلف تفاوت قابل‌توجهی دارند. در این مقاله، دیدگاهی کلی نسبت به نحوه ترکیب این اجزا ارائه می‌شود و مشخص می‌شود چه عاملی یک VPN جدی را از یک ابزار ابتدایی تغییر آی‌پی متمایز می‌کند.</p>

<h2>سه لایه تشکیل‌دهنده یک VPN</h2>
<p>هر اتصال VPN در واقع حاصل هم‌کاری سه مؤلفه است: یک <strong>پروتکل</strong> که نحوه ساخت و انتقال تونل رمزنگاری‌شده را تعیین می‌کند، یک <strong>استاندارد رمزنگاری</strong> که داده‌های کاربر را به‌گونه‌ای درهم می‌ریزد که تنها کاربر و سرور مقصد قادر به خواندن آن باشند، و مجموعه‌ای از <strong>ویژگی‌ها</strong> که بر پایه این دو لایه ساخته می‌شوند و میزان محافظت و کنترل واقعی کاربر را تعیین می‌کنند. تبلیغات معمولاً این لایه‌ها را در هم می‌آمیزند؛ درک جداگانه هرکدام، ارزیابی دقیق‌تر آنچه واقعاً پرداخت می‌شود را ممکن می‌سازد.</p>

<h2>لایه اول: پروتکل</h2>
<p>پروتکل تعیین می‌کند دستگاه کاربر و سرور VPN چگونه با یکدیگر ارتباط برقرار کنند و — نکته مهم‌تر — ترافیک کاربر از دید هر ناظری در مسیر شبکه چگونه به نظر برسد. پروتکل‌های شناخته‌شده‌ای مانند OpenVPN و WireGuard اولویت را بر سرعت و سازگاری گسترده می‌گذارند. با این حال، در شبکه‌هایی که به‌طور فعال ترافیک VPN را شناسایی و مسدود می‌کنند، دسته دیگری از پروتکل‌ها اهمیت بیشتری پیدا می‌کند؛ پروتکل‌هایی مانند VLESS که مشخصاً برای شبیه‌سازی ترافیک عادی وب رمزنگاری‌شده طراحی شده‌اند. بررسی کامل این موضوع در <a href="/fa/blog/vpn-protocols-explained">راهنمای پروتکل‌های VPN</a> و بررسی عمیق‌تر زیرساخت VLESS/Xray مورد استفاده فریمیگا در <a href="/fa/blog/v2ray-xray-vless-explained">این مقاله درباره V2Ray، Xray و VLESS</a> ارائه شده است.</p>

<h2>لایه دوم: رمزنگاری</h2>
<p>رمزنگاری همان عاملی است که پس از برقراری تونل، محتوای واقعی ترافیک کاربر را محرمانه نگه می‌دارد؛ تفاوت میان مشاهده داده‌ای بی‌معنا و درهم‌ریخته توسط یک ناظر، در برابر مشاهده فعالیت واقعی مرور کاربر. VPNهای مدرن بر پایه سایفرهای شناخته‌شده و ممیزی‌شده عمومی (مانند AES-256 و ChaCha20) فعالیت می‌کنند، نه رمزنگاری‌های اختصاصی و غیرشفاف. توضیح کامل و ساده این فرآیند در <a href="/fa/blog/what-is-vpn-encryption">راهنمای رمزنگاری VPN</a> ارائه شده است.</p>

<h2>لایه سوم: ویژگی‌هایی که یک VPN واقعی را متمایز می‌کنند</h2>
<h3>کیل سوییچ (Kill Switch)</h3>
<p>کیل سوییچ در صورت قطع ناگهانی اتصال VPN، تمامی ترافیک اینترنتی را مسدود می‌کند، به‌جای آنکه به‌طور خاموش به اتصال عادی و بدون محافظت بازگردد. بدون این ویژگی، یک قطعی کوتاه می‌تواند ترافیکی را که کاربر تصور می‌کرده همواره محافظت‌شده بوده، در معرض دید قرار دهد.</p>
<h3>تونل‌سازی تفکیکی (Split Tunneling)</h3>
<p>این ویژگی امکان انتخاب می‌دهد که کدام برنامه‌ها از طریق VPN و کدام‌یک از طریق اتصال عادی ارسال شوند؛ کاربردی برای مواردی که کاربر می‌خواهد یک برنامه خاص همواره از طریق VPN فعالیت کند، در حالی که سایر برنامه‌ها از سرعت شبکه محلی بهره‌مند باشند.</p>
<h3>مبهم‌سازی ترافیک (Obfuscation)</h3>
<p>مبهم‌سازی، عاملی است که ترافیک VPN را در برابر بازرسی عمیق بسته‌ها (DPI) مقاوم می‌سازد؛ روشی که برخی شبکه‌ها برای شناسایی و مسدودسازی خودِ استفاده از VPN، نه صرفاً سایت‌های خاص، به کار می‌برند. این ویژگی برای کاربرانی که در شبکه‌ای با محدودیت فعال دسترسی به VPN قرار دارند، مهم‌ترین عامل محسوب می‌شود و مستقیماً نتیجه انتخاب پروتکل (لایه اول) است.</p>
<h3>سیاست بدون‌لاگ (No-Logs)</h3>
<p>رمزنگاری از ترافیک کاربر در حین انتقال محافظت می‌کند، اما خودِ ارائه‌دهنده VPN همچنان قادر به مشاهده آدرس آی‌پی واقعی و متادیتای اتصال کاربر است. یک سیاست بدون‌لاگ واقعی — نه صرفاً یک ادعای تبلیغاتی — تعیین می‌کند که آیا این اطلاعات اساساً ذخیره می‌شوند یا خیر.</p>
<h3>پشتیبانی از چند دستگاه هم‌زمان</h3>
<p>تعداد دستگاه‌هایی که می‌توانند به‌طور هم‌زمان از یک اشتراک استفاده کنند، ویژگی‌ای کاربردی است که ارتباطی به سطح امنیت ندارد، اما تعیین می‌کند آیا یک پلن واقعاً متناسب با نحوه استفاده روزانه کاربر است یا خیر.</p>

<h2>فریمیگا چگونه این لایه‌ها را در کنار هم قرار می‌دهد؟</h2>
<p>فریمیگا بر بستر VLESS و Xray همراه با TLS فعالیت می‌کند (لایه پروتکل)، از رمزنگاری در سطح AES-256/ChaCha20 از طریق لایه TLS بهره می‌برد (لایه رمزنگاری)، و مشخصاً برای حفظ عملکرد در شبکه‌هایی که به‌طور فعال به دنبال شناسایی و مسدودسازی ترافیک VPN هستند طراحی شده است؛ ویژگی‌ای که برای کاربران فریمیگا بیش از هر چیز دیگری اهمیت دارد.</p>

<h2>پرسش‌های متداول درباره فناوری VPN</h2>
<h3>آیا فناوری جدیدتر VPN همیشه بهتر است؟</h3>
<p>نه لزوماً به‌معنای مطلق. پروتکل‌های جدیدتری مانند VLESS مشخصاً در مقاومت در برابر شناسایی در شبکه‌های محدودکننده برتری دارند، در حالی که پروتکل‌های شناخته‌شده‌ای مانند OpenVPN سابقه طولانی‌تری در ارزیابی امنیتی مستقل دارند. انتخاب مناسب به شرایط شبکه کاربر بستگی دارد، نه صرفاً تاریخ عرضه فناوری.</p>
<h3>آیا رمزنگاری قوی‌تر به معنای اتصال کندتر است؟</h3>
<p>سایفرهای مدرنی مانند AES-256 و ChaCha20 روی هر دستگاه امروزی به‌قدری سریع هستند که این تفاوت در عمل تقریباً غیرقابل‌احساس است. سرعت اتصال بسیار بیشتر تحت تأثیر انتخاب پروتکل، بار سرور و فاصله تا سرور قرار دارد تا قدرت رمزنگاری.</p>
<h3>فریمیگا از چه فناوری VPN استفاده می‌کند؟</h3>
<p>فریمیگا بر بستر پروتکل VLESS و هسته Xray، همراه با رمزنگاری TLS فعالیت می‌کند؛ انتخابی که مشخصاً برای حفظ قابلیت اتصال در شبکه‌هایی که ترافیک متعارف VPN را مسدود می‌کنند صورت گرفته است.</p>

<h2>اکنون امتحان کنید</h2>
<p>برای بهره‌مندی از این فناوری، نیازی به درک تمامی جزئیات فنی آن نیست؛ فریمیگا این بخش را مدیریت می‌کند و کاربر تنها به یک پلن و یک برنامه سازگار نیاز دارد. <a href="/fa/plans">پلن‌های VPN فریمیگا را مقایسه کنید</a> و در عرض چند دقیقه متصل شوید.</p>
""",
    },
    {
        "slug": "what-is-vpn-encryption",
        "title_en": "What Is VPN Encryption? AES-256, ChaCha20, and How It Actually Protects You",
        "title_fa": "رمزنگاری VPN چیست؟ بررسی AES-256، ChaCha20 و نحوه محافظت واقعی از کاربر",
        "excerpt_en": "How VPN encryption actually works — symmetric vs asymmetric encryption, AES-256 and ChaCha20, and what it does (and doesn't) protect you from.",
        "excerpt_fa": "بررسی رسمی نحوه عملکرد رمزنگاری VPN؛ تفاوت رمزنگاری متقارن و نامتقارن، استانداردهای AES-256 و ChaCha20، و مواردی که این رمزنگاری از آن‌ها محافظت می‌کند و نمی‌کند.",
        "content_en": """
<p>"Military-grade encryption" appears on nearly every VPN's homepage, but the phrase explains almost nothing on its own. Here is what VPN encryption actually is, how it works, and — just as importantly — what it does and doesn't protect against.</p>

<h2>The Basic Idea</h2>
<p>Encryption scrambles data into unreadable ciphertext using a mathematical key, so that only someone holding the matching key can turn it back into readable data. Once a VPN connection is active, everything sent from the device — web requests, app traffic, DNS lookups — is encrypted before it leaves the device and only decrypted once it reaches the VPN server. Anyone observing the connection in between, including an internet provider or another user on the same public Wi-Fi network, sees only scrambled data.</p>

<h2>Symmetric vs. Asymmetric Encryption</h2>
<p>VPN connections rely on two types of encryption working together:</p>
<ul>
<li><strong>Asymmetric encryption</strong> (a public/private key pair) is used briefly at the start of the connection, allowing both sides to agree on a shared secret without ever sending that secret across the network in the clear.</li>
<li><strong>Symmetric encryption</strong> (a single shared key both sides now hold) handles the actual data afterward, since it is significantly faster — this is what encrypts every byte sent and received for the remainder of the session.</li>
</ul>
<p>This handshake — agreeing on a secret asymmetrically, then encrypting everything symmetrically — is the same basic pattern behind HTTPS, and it is what makes strong encryption practical for everyday use rather than just a theoretical security exercise.</p>

<h2>AES-256 and ChaCha20</h2>
<p>These are the two symmetric ciphers responsible for the actual encryption in nearly every modern VPN:</p>
<ul>
<li><strong>AES-256</strong> — the United States government's own standard for classified information, and the most widely deployed encryption cipher in the world. A 256-bit key produces 2<sup>256</sup> possible combinations, a number large enough that brute-forcing it is not a realistic attack for any computer that currently exists or is expected to exist.</li>
<li><strong>ChaCha20</strong> — a newer cipher used by WireGuard and many modern proxy protocols, chosen for being extremely fast in software, including on mobile devices that lack the specialized hardware which makes AES fast on most laptops and servers, without any reduction in security.</li>
</ul>
<p>Both are considered secure under current cryptographic standards. Neither is meaningfully "stronger" in practice — the choice mainly affects speed and battery consumption, not whether the data is genuinely protected.</p>

<h2>What Encryption Actually Protects Against</h2>
<ul>
<li><strong>An internet provider or network operator reading traffic</strong> — without a VPN, an internet provider can see every domain a device connects to and, on unencrypted sites, the content itself.</li>
<li><strong>Interception on public Wi-Fi</strong> — another user on the same network can otherwise intercept unencrypted traffic exchanged with websites that don't use HTTPS.</li>
<li><strong>Content-based traffic analysis</strong> — a network that inspects traffic to block specific sites or content cannot see inside an encrypted VPN tunnel.</li>
</ul>

<h2>What Encryption Doesn't Protect Against</h2>
<p>This is the part most VPN marketing leaves out. Encryption protects the <em>contents</em> of traffic — it does not automatically make a user anonymous.</p>
<ul>
<li>The VPN provider itself can see the user's real IP address and, without a strict no-logs policy, potentially their activity — which is why trust in the provider matters as much as the encryption itself.</li>
<li>Any website a user logs into still knows who they are, regardless of encryption; logging into an email account over a VPN does not hide that identity from the email provider.</li>
<li>Encryption does not prevent a network from detecting <em>that</em> a VPN is in use, even if it cannot see what's inside — that is a separate problem solved by protocol choice, not encryption strength (see our <a href="/en/blog/understanding-vpn-technology">overview of VPN technology</a>).</li>
</ul>

<h2>Frequently Asked Questions</h2>
<h3>Is AES-256 or ChaCha20 more secure?</h3>
<p>Both are considered equally secure under current cryptographic standards. ChaCha20 tends to perform faster on devices without dedicated encryption hardware, such as most phones, while AES-256 benefits from hardware acceleration on many laptops and servers. Security is not the differentiator between the two.</p>
<h3>Can encrypted VPN traffic still be traced back to a user?</h3>
<p>Encryption prevents the contents of traffic from being read, but it does not hide the fact that a device is connecting to a VPN server, nor does it hide activity from the VPN provider itself. Real anonymity depends on the provider's logging practices, not on encryption strength alone.</p>
<h3>Does VPN encryption slow down a connection?</h3>
<p>Modern ciphers like AES-256 and ChaCha20 add only a small, generally imperceptible amount of overhead on current devices. Connection speed is affected far more by server distance, server load, and protocol choice than by encryption itself.</p>

<h2>Get Started</h2>
<p>Freemiga encrypts every connection with modern, independently audited ciphers by default — no configuration required. <a href="/en/plans">Compare Freemiga's VPN plans</a> and get connected in a few minutes.</p>
""",
        "content_fa": """
<p>عبارت «رمزنگاری نظامی» تقریباً روی صفحه اصلی هر VPN دیده می‌شود، اما این عبارت به‌تنهایی توضیح چندانی ارائه نمی‌دهد. در این مقاله، تعریف دقیق رمزنگاری VPN، نحوه عملکرد آن و — به همان اندازه مهم — مواردی که این رمزنگاری از آن‌ها محافظت می‌کند و نمی‌کند، به‌طور کامل بررسی می‌شود.</p>

<h2>اصل بنیادی رمزنگاری</h2>
<p>رمزنگاری داده‌ها را با استفاده از یک کلید ریاضی به متنی غیرقابل‌خواندن (سایفرتکست) تبدیل می‌کند، به‌گونه‌ای که تنها دارنده کلید متناظر قادر به بازگرداندن آن به داده قابل‌خواندن است. پس از فعال شدن اتصال VPN، تمامی داده‌های ارسالی از دستگاه — شامل درخواست‌های وب، ترافیک برنامه‌ها و جستجوهای DNS — پیش از خروج از دستگاه رمزنگاری می‌شوند و تنها پس از رسیدن به سرور VPN رمزگشایی می‌شوند. هر شخصی که اتصال را در این مسیر مشاهده کند، از جمله ارائه‌دهنده خدمات اینترنت یا کاربر دیگری در همان شبکه وای‌فای عمومی، تنها داده‌ای درهم‌ریخته و بی‌معنا مشاهده خواهد کرد.</p>

<h2>رمزنگاری متقارن در برابر نامتقارن</h2>
<p>اتصالات VPN بر پایه هم‌کاری دو نوع رمزنگاری فعالیت می‌کنند:</p>
<ul>
<li><strong>رمزنگاری نامتقارن</strong> (یک جفت کلید عمومی و خصوصی) به‌طور کوتاه‌مدت در ابتدای اتصال به کار می‌رود و امکان توافق دو طرف بر سر یک راز مشترک را فراهم می‌کند، بدون آنکه این راز به‌صورت خام از طریق شبکه ارسال شود.</li>
<li><strong>رمزنگاری متقارن</strong> (یک کلید مشترک واحد که هر دو طرف اکنون در اختیار دارند) داده‌های واقعی را در ادامه مدیریت می‌کند، زیرا به‌مراتب سریع‌تر است؛ همین رمزنگاری است که تمامی داده‌های ارسالی و دریافتی را تا پایان نشست پوشش می‌دهد.</li>
</ul>
<p>این فرآیند دست‌دهی — توافق نامتقارن بر سر یک راز و سپس رمزنگاری متقارن تمامی داده‌ها — همان الگوی پایه‌ای است که HTTPS نیز بر اساس آن عمل می‌کند و همین الگو رمزنگاری قوی را برای استفاده روزمره عملی می‌سازد، نه صرفاً یک تمرین نظری امنیتی.</p>

<h2>AES-256 و ChaCha20</h2>
<p>این دو سایفر متقارن، رمزنگاری واقعی را در تقریباً تمامی VPNهای مدرن انجام می‌دهند:</p>
<ul>
<li><strong>AES-256</strong> — استاندارد رسمی دولت ایالات متحده برای اطلاعات طبقه‌بندی‌شده و پرکاربردترین سایفر رمزنگاری در جهان. کلید ۲۵۶ بیتی، ۲<sup>۲۵۶</sup> ترکیب ممکن ایجاد می‌کند؛ عددی به‌قدری بزرگ که حمله brute-force به آن، با هیچ کامپیوتری که هم‌اکنون وجود دارد یا در آینده قابل‌پیش‌بینی است، عملی نخواهد بود.</li>
<li><strong>ChaCha20</strong> — سایفری جدیدتر که توسط WireGuard و بسیاری از پروتکل‌های پراکسی مدرن استفاده می‌شود؛ این سایفر به دلیل سرعت بسیار بالا در پیاده‌سازی نرم‌افزاری، از جمله روی دستگاه‌های موبایل که فاقد سخت‌افزار تخصصی تسریع‌کننده AES هستند، بدون هیچ کاهشی در سطح امنیت انتخاب شده است.</li>
</ul>
<p>هر دو سایفر طبق استانداردهای رمزنگاری فعلی، امن محسوب می‌شوند. هیچ‌کدام از نظر عملی «قوی‌تر» از دیگری نیستند؛ انتخاب میان آن‌ها عمدتاً بر سرعت و مصرف باتری تأثیر می‌گذارد، نه بر میزان محافظت واقعی از داده‌ها.</p>

<h2>رمزنگاری واقعاً از چه مواردی محافظت می‌کند؟</h2>
<ul>
<li><strong>مشاهده ترافیک توسط ارائه‌دهنده اینترنت یا اپراتور شبکه</strong> — بدون استفاده از VPN، ارائه‌دهنده اینترنت قادر است تمامی دامنه‌هایی که دستگاه به آن‌ها متصل می‌شود را مشاهده کند و، در مورد سایت‌های رمزنگاری‌نشده، حتی به محتوای واقعی نیز دسترسی داشته باشد.</li>
<li><strong>شنود در شبکه‌های وای‌فای عمومی</strong> — کاربر دیگری در همان شبکه می‌تواند ترافیک رمزنگاری‌نشده میان دستگاه کاربر و وب‌سایت‌های فاقد HTTPS را شنود کند.</li>
<li><strong>تحلیل ترافیک مبتنی بر محتوا</strong> — شبکه‌ای که ترافیک را برای مسدودسازی سایت یا محتوای خاصی بازرسی می‌کند، قادر به مشاهده محتوای داخل یک تونل رمزنگاری‌شده VPN نخواهد بود.</li>
</ul>

<h2>رمزنگاری از چه مواردی محافظت نمی‌کند؟</h2>
<p>این بخشی است که اغلب در تبلیغات VPN نادیده گرفته می‌شود. رمزنگاری از <em>محتوای</em> ترافیک محافظت می‌کند، اما به‌طور خودکار کاربر را ناشناس نمی‌سازد.</p>
<ul>
<li>خودِ ارائه‌دهنده VPN همچنان قادر به مشاهده آدرس آی‌پی واقعی کاربر است و، در غیاب یک سیاست بدون‌لاگ سخت‌گیرانه، احتمالاً به فعالیت کاربر نیز دسترسی دارد؛ به همین دلیل، اعتماد به ارائه‌دهنده به‌اندازه خودِ رمزنگاری اهمیت دارد.</li>
<li>هر وب‌سایتی که کاربر در آن وارد حساب کاربری خود شود، صرف‌نظر از رمزنگاری، همچنان هویت او را می‌شناسد؛ ورود به یک حساب ایمیل از طریق VPN، هویت کاربر را از دید ارائه‌دهنده ایمیل پنهان نمی‌کند.</li>
<li>رمزنگاری مانع از تشخیص <em>خودِ استفاده از VPN</em> توسط شبکه نمی‌شود، حتی اگر محتوای داخل آن قابل‌مشاهده نباشد؛ این موضوعی جداگانه است که با انتخاب پروتکل حل می‌شود، نه با قدرت رمزنگاری (نگاه کنید به <a href="/fa/blog/understanding-vpn-technology">نگاهی جامع به فناوری VPN</a>).</li>
</ul>

<h2>پرسش‌های متداول درباره رمزنگاری VPN</h2>
<h3>کدام‌یک امن‌تر است: AES-256 یا ChaCha20؟</h3>
<p>هر دو طبق استانداردهای رمزنگاری فعلی به‌یک‌اندازه امن محسوب می‌شوند. ChaCha20 معمولاً روی دستگاه‌های فاقد سخت‌افزار اختصاصی رمزنگاری، مانند اغلب گوشی‌های هوشمند، عملکرد سریع‌تری دارد، در حالی که AES-256 از شتاب‌دهی سخت‌افزاری روی بسیاری از لپ‌تاپ‌ها و سرورها بهره می‌برد. امنیت، عامل تمایز میان این دو سایفر نیست.</p>
<h3>آیا ترافیک رمزنگاری‌شده VPN همچنان قابل ردیابی است؟</h3>
<p>رمزنگاری از خوانده‌شدن محتوای ترافیک جلوگیری می‌کند، اما این واقعیت را که دستگاه به یک سرور VPN متصل شده پنهان نمی‌سازد و فعالیت کاربر را از دید خودِ ارائه‌دهنده VPN نیز مخفی نمی‌کند. ناشناس بودن واقعی، بیش از آنکه به قدرت رمزنگاری وابسته باشد، به سیاست‌های ثبت لاگ ارائه‌دهنده بستگی دارد.</p>
<h3>آیا رمزنگاری VPN سرعت اتصال را کاهش می‌دهد؟</h3>
<p>سایفرهای مدرنی مانند AES-256 و ChaCha20 روی دستگاه‌های امروزی تنها سربار اندک و معمولاً غیرقابل‌احساسی ایجاد می‌کنند. سرعت اتصال بسیار بیشتر تحت تأثیر فاصله تا سرور، بار سرور و انتخاب پروتکل قرار دارد تا خودِ رمزنگاری.</p>

<h2>اکنون امتحان کنید</h2>
<p>فریمیگا به‌صورت پیش‌فرض تمامی اتصالات را با سایفرهای مدرن و ممیزی‌شده مستقل رمزنگاری می‌کند، بدون نیاز به هیچ پیکربندی اضافه‌ای. <a href="/fa/plans">پلن‌های VPN فریمیگا را مقایسه کنید</a> و در عرض چند دقیقه متصل شوید.</p>
""",
    },
]


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

        created = 0
        for p in POSTS:
            if db.query(BlogPost).filter(BlogPost.slug == p["slug"]).first():
                continue
            post = BlogPost(
                slug=p["slug"],
                category_id=category.id,
                title_en=p["title_en"],
                title_fa=p["title_fa"],
                excerpt_en=p["excerpt_en"],
                excerpt_fa=p["excerpt_fa"],
                content_en=p["content_en"].strip(),
                content_fa=p["content_fa"].strip(),
                status=BlogPostStatus.draft,
                reading_time_min=reading_time_minutes(p["content_en"]),
                tags=tags,
            )
            db.add(post)
            created += 1
        db.commit()
        print(f"Done — {created} new post(s) created as drafts, {len(POSTS) - created} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
