"""
One-time content seed — publishes four blog posts covering VPN and proxy
types (protocols, proxy types, VPN-vs-proxy, and the V2Ray/Xray/VLESS stack
Freemiga itself runs on), each ending with a link to /plans.

Idempotent by slug: safe to re-run (e.g. after a fresh DB) since existing
posts are left untouched and only missing ones are created — same pattern
as scripts/init_db.py's seed_plans().

Run once, after the app's tables already exist:
    python -m scripts.seed_vpn_proxy_blog
or, in the Docker deployment:
    docker compose exec app python -m scripts.seed_vpn_proxy_blog
"""
from datetime import datetime

from app.database import SessionLocal
from app.models import BlogCategory, BlogPost, BlogPostStatus, BlogTag
from app.services.blog import reading_time_minutes, slugify

CATEGORY = {"name_en": "VPN & Proxy Guides", "name_fa": "راهنمای VPN و پروکسی"}

TAGS = [
    {"name_en": "VPN", "name_fa": "VPN"},
    {"name_en": "Proxy", "name_fa": "پروکسی"},
    {"name_en": "Protocols", "name_fa": "پروتکل‌ها"},
]

POSTS = [
    {
        "slug": "vpn-protocols-explained",
        "title_en": "VPN Protocols Explained: OpenVPN, WireGuard, Shadowsocks & VLESS",
        "title_fa": "پروتکل‌های VPN چیستند؟ مقایسه OpenVPN، WireGuard، Shadowsocks و VLESS",
        "excerpt_en": "A plain-English guide to the main VPN protocol types — OpenVPN, WireGuard, Shadowsocks, and VLESS — and how to pick the right one for speed, security, and bypassing censorship.",
        "excerpt_fa": "راهنمای ساده انواع پروتکل‌های VPN — OpenVPN، WireGuard، Shadowsocks و VLESS — و اینکه برای سرعت، امنیت و عبور از سانسور کدومشون مناسب‌تره.",
        "content_en": """
<p>Every VPN app is built on top of a <strong>VPN protocol</strong> — the set of rules that decides how your traffic gets encrypted, packaged, and sent to a server. The protocol a VPN uses affects almost everything that matters to you: connection speed, battery life, how well it holds up on unstable networks, and — for anyone dealing with internet censorship — whether it actually gets through in the first place. This guide walks through the VPN protocol types you'll actually run into, in plain English.</p>

<h2>What Is a VPN Protocol?</h2>
<p>A VPN protocol is the technical foundation of your encrypted tunnel. Two apps can look identical on the surface while using completely different protocols underneath, and that difference is often the reason one connection feels instant while another lags or drops. When you're comparing VPN services, the protocol is usually a better predictor of real-world performance than marketing claims about "military-grade encryption."</p>

<h2>OpenVPN: The Long-Standing Standard</h2>
<p>OpenVPN has been around since 2001 and is still one of the most widely supported VPN protocols. It's open-source, has been audited extensively, and works reliably across almost every platform. Its main downside is speed: OpenVPN's encryption overhead makes it noticeably slower than newer protocols, especially on mobile connections. It's a safe, well-understood choice, but it's rarely the fastest option available today.</p>

<h2>WireGuard: Fast and Modern</h2>
<p>WireGuard is a newer protocol built around a much smaller, leaner codebase than OpenVPN — which makes it easier to audit and, in practice, significantly faster. It reconnects almost instantly after your device switches networks (say, from Wi-Fi to mobile data), which makes it a strong choice for phones. Its one limitation: WireGuard's traffic pattern is relatively easy to detect and block, which matters if you're on a network actively trying to identify and throttle VPN connections.</p>

<h2>Shadowsocks: Built for Bypassing Censorship</h2>
<p>Shadowsocks was designed specifically to get around firewalls that block conventional VPN traffic. Instead of behaving like an obvious VPN, it disguises your connection as ordinary encrypted web traffic, which makes it much harder for network-level filtering to single out and block. It's a popular choice in regions with aggressive internet restrictions, though newer protocols have since built on its ideas with even stronger obfuscation.</p>

<h2>VLESS and Xray: The Protocol Behind Freemiga</h2>
<p>VLESS is a lightweight protocol built on the Xray-core project — a modern evolution of the V2Ray ecosystem, designed from the ground up to resist deep packet inspection (DPI), the technique some networks use to detect and block VPN traffic by analyzing its patterns. VLESS strips out unnecessary overhead compared to older protocols in the same family, which means less latency without giving up the ability to blend in with normal HTTPS traffic. This is the protocol Freemiga runs on, specifically because it holds up well in environments where other VPN protocols get blocked outright.</p>

<h2>Which VPN Protocol Should You Choose?</h2>
<p>If you just want fast, reliable encryption on an open network, WireGuard is hard to beat. If you're on a network that actively blocks VPN traffic, a protocol built for obfuscation — like VLESS over Xray — is the one that actually gets you connected in the first place. Speed doesn't matter much if the connection never establishes.</p>

<h2>Get Connected With Freemiga</h2>
<p>Freemiga runs on VLESS/Xray specifically so it keeps working where basic VPN protocols get blocked, without sacrificing speed. <a href="/en/plans">Compare Freemiga's VPN plans</a> and get connected on any device in a few minutes.</p>
""",
        "content_fa": """
<p>هر اپ VPN رو یه <strong>پروتکل VPN</strong> می‌سازه — مجموعه‌ای از قوانین که تعیین می‌کنه ترافیک شما چطور رمزنگاری، بسته‌بندی و به سرور فرستاده بشه. پروتکلی که یه VPN استفاده می‌کنه تقریباً روی همه‌چیزی که براتون مهمه تأثیر می‌ذاره: سرعت اتصال، مصرف باتری، پایداری روی شبکه‌های ناپایدار، و برای کسایی که با سانسور اینترنت سروکار دارن — اینکه اصلاً وصل میشه یا نه. تو این مقاله انواع پروتکل‌های VPN که واقعاً باهاشون سروکار دارید رو ساده توضیح می‌دیم.</p>

<h2>پروتکل VPN چیه؟</h2>
<p>پروتکل VPN، پایه‌ی فنی تونل رمزنگاری‌شده‌ی شماست. دو تا اپ ممکنه از بیرون شبیه هم به‌نظر برسن ولی از پروتکل کاملاً متفاوتی استفاده کنن، و همین تفاوت معمولاً دلیل اینه که چرا یه اتصال فوری کار می‌کنه و اون یکی کند یا قطع میشه. وقتی دارید سرویس‌های VPN رو مقایسه می‌کنید، پروتکل معمولاً پیش‌بینی‌کننده‌ی بهتری برای عملکرد واقعی نسبت به ادعاهای تبلیغاتی درباره‌ی «رمزنگاری نظامی» هست.</p>

<h2>OpenVPN: استاندارد قدیمی و شناخته‌شده</h2>
<p>OpenVPN از سال ۲۰۰۱ وجود داره و هنوز یکی از پشتیبانی‌شده‌ترین پروتکل‌های VPN هست. متن‌بازه، خیلی زیاد ممیزی امنیتی شده، و رو تقریباً همه پلتفرم‌ها قابل‌اعتماد کار می‌کنه. نقطه‌ضعف اصلیش سرعته: overhead رمزنگاری OpenVPN باعث میشه به‌طور محسوسی از پروتکل‌های جدیدتر کندتر باشه، به‌خصوص رو اتصال‌های موبایل. یه انتخاب امن و شناخته‌شده‌ست، ولی امروزه به‌ندرت سریع‌ترین گزینه‌ی موجوده.</p>

<h2>WireGuard: سریع و مدرن</h2>
<p>WireGuard یه پروتکل جدیدتره که رو یه کدبیس خیلی کوچیک‌تر و ساده‌تر از OpenVPN ساخته شده — که ممیزی‌کردنش رو راحت‌تر می‌کنه و در عمل، به‌طور قابل‌توجهی سریع‌تره. تقریباً فوری بعد از عوض‌شدن شبکه‌ی دستگاهتون (مثلاً از وای‌فای به دیتای موبایل) دوباره وصل میشه، که باعث میشه انتخاب خوبی برای گوشی‌ها باشه. یه محدودیت داره: الگوی ترافیک WireGuard نسبتاً راحت قابل‌شناسایی و مسدودسازیه، که اگه رو یه شبکه‌ای باشید که فعالانه دنبال شناسایی و کندکردن اتصالات VPNه، مهم میشه.</p>

<h2>Shadowsocks: ساخته‌شده برای عبور از سانسور</h2>
<p>Shadowsocks مخصوصاً برای دور زدن فایروال‌هایی طراحی شده که ترافیک VPN معمولی رو مسدود می‌کنن. به‌جای رفتار کردن مثل یه VPN آشکار، اتصالتون رو شبیه ترافیک وب رمزنگاری‌شده‌ی عادی جا می‌زنه، که باعث میشه فیلترینگ در سطح شبکه خیلی سخت‌تر بتونه تشخیصش بده و مسدودش کنه. تو مناطقی با محدودیت‌های شدید اینترنتی محبوبه، هرچند پروتکل‌های جدیدتر رو ایده‌هاش ساخته شدن و obfuscation قوی‌تری هم دارن.</p>

<h2>VLESS و Xray: پروتکلی که فریمیگا روش کار می‌کنه</h2>
<p>VLESS یه پروتکل سبک‌وزنه که رو پروژه‌ی Xray-core ساخته شده — یه تکامل مدرن از اکوسیستم V2Ray، که از پایه برای مقاومت در برابر Deep Packet Inspection (DPI) طراحی شده؛ همون تکنیکی که بعضی شبکه‌ها برای شناسایی و مسدودکردن ترافیک VPN با تحلیل الگوهاش استفاده می‌کنن. VLESS overhead غیرضروری نسبت به پروتکل‌های قدیمی‌تر همون خانواده رو حذف می‌کنه، یعنی تأخیر کمتر بدون از دست دادن توانایی جا زدن خودش به‌عنوان ترافیک عادی HTTPS. فریمیگا دقیقاً به همین دلیل رو این پروتکل کار می‌کنه — چون تو محیط‌هایی که پروتکل‌های دیگه‌ی VPN کاملاً مسدود میشن، همچنان پایداره.</p>

<h2>کدوم پروتکل VPN رو انتخاب کنید؟</h2>
<p>اگه فقط دنبال رمزنگاری سریع و پایدار رو یه شبکه‌ی بازید، WireGuard خیلی سخت شکست می‌خوره. ولی اگه رو یه شبکه‌ای هستید که فعالانه ترافیک VPN رو مسدود می‌کنه، یه پروتکل ساخته‌شده برای obfuscation — مثل VLESS رو Xray — همونیه که واقعاً وصلتون می‌کنه. سرعت وقتی اتصال اصلاً برقرار نمیشه، اهمیتی نداره.</p>

<h2>با فریمیگا وصل شید</h2>
<p>فریمیگا دقیقاً به همین دلیل رو VLESS/Xray کار می‌کنه — تا جایی که پروتکل‌های ساده‌ی VPN مسدود میشن، همچنان کار کنه، بدون اینکه از سرعت بزنه. <a href="/fa/plans">پلن‌های VPN فریمیگا رو مقایسه کنید</a> و تو چند دقیقه رو هر دستگاهی وصل شید.</p>
""",
    },
    {
        "slug": "what-is-a-proxy-server-types-explained",
        "title_en": "What Is a Proxy Server? HTTP, SOCKS5 & Residential Proxies Explained",
        "title_fa": "پروکسی سرور چیست؟ توضیح انواع پروکسی HTTP، SOCKS5 و رزیدنشیال",
        "excerpt_en": "Learn what a proxy server actually does, the difference between HTTP, SOCKS5, datacenter, and residential proxies, and why most people are better off with a VPN.",
        "excerpt_fa": "پروکسی سرور واقعاً چیکار می‌کنه، تفاوت پروکسی HTTP، SOCKS5، دیتاسنتر و رزیدنشیال چیه، و چرا برای بیشتر افراد VPN گزینه‌ی بهتریه.",
        "content_en": """
<p>"Proxy" is one of those words that gets used loosely — proxy server, proxy site, proxy extension — without much explanation of what's actually happening underneath. Here's a straightforward breakdown of what a proxy server is, the main types of proxies you'll encounter, and where they fall short compared to a VPN.</p>

<h2>What Is a Proxy Server?</h2>
<p>A proxy server sits between your device and the websites you visit. Instead of connecting directly, your request goes to the proxy first, which then forwards it on your behalf. To the website, the request appears to come from the proxy's IP address, not yours — which is why proxies are commonly used to change your apparent location or hide your real IP from a specific site or service.</p>

<h2>HTTP and HTTPS Proxies</h2>
<p>HTTP proxies handle web traffic specifically — they understand HTTP requests and can do things like cache pages or filter content, which is why they're common in offices and schools. HTTPS proxies extend this to encrypted web traffic. The catch: a basic HTTP proxy only routes browser traffic, not the rest of your device's internet activity, and it typically doesn't encrypt the connection between your device and the proxy itself.</p>

<h2>SOCKS5 Proxies</h2>
<p>SOCKS5 is a more general-purpose proxy protocol — it doesn't care what kind of traffic it's handling, so it works for torrenting, gaming, and apps beyond just your browser, not just web pages. It's more flexible than an HTTP proxy, but like HTTP proxies, standard SOCKS5 doesn't encrypt your traffic by default, which is an important distinction from a VPN.</p>

<h2>Datacenter vs. Residential Proxies</h2>
<p>Datacenter proxies run on IP addresses owned by cloud hosting providers — they're fast and cheap, but easy for websites to detect and block since datacenter IP ranges are well known. Residential proxies route your traffic through real IP addresses assigned by home internet providers, which makes them much harder to detect but significantly more expensive and often slower.</p>

<h2>Proxy vs VPN: Why Encryption Matters</h2>
<p>This is the core difference that gets lost in most proxy discussions: a proxy typically changes your apparent IP address but doesn't encrypt your traffic end-to-end. A VPN encrypts everything between your device and the VPN server, protecting your data even on untrusted networks like public Wi-Fi — and, unlike most proxies, it covers your entire device's traffic, not just one browser or app.</p>

<h2>When a Proxy Isn't Enough</h2>
<p>If your goal is genuinely private, secure browsing — not just swapping your IP address for one request — a proxy alone doesn't get you there. That's especially true on networks where your ISP or network administrator can see unencrypted traffic. For anything involving personal accounts, payments, or sensitive browsing, encryption isn't optional.</p>

<h2>Choose a Freemiga Plan</h2>
<p>Freemiga gives you a fully encrypted VPN connection, not just an IP swap — with fast VLESS/Xray servers built to stay reliable even on restrictive networks. <a href="/en/plans">See Freemiga's VPN plans</a> and get set up on any device in minutes.</p>
""",
        "content_fa": """
<p>«پروکسی» یکی از اون کلمه‌هاییه که خیلی راحت و بدون توضیح دقیق استفاده میشه — پروکسی سرور، سایت پروکسی، اکستنشن پروکسی — بدون اینکه خیلی روشن باشه واقعاً زیرش چه اتفاقی می‌افته. این مقاله یه توضیح ساده از اینکه پروکسی سرور چیه، انواع اصلی پروکسی که باهاشون مواجه میشید، و کجاها نسبت به VPN کم میارن رو می‌ده.</p>

<h2>پروکسی سرور چیه؟</h2>
<p>یه پروکسی سرور بین دستگاه شما و سایت‌هایی که بازدید می‌کنید قرار می‌گیره. به‌جای اتصال مستقیم، درخواست شما اول میره سراغ پروکسی، که بعد از طرف شما اون رو ارسال می‌کنه. از دید سایت، درخواست انگار از آی‌پی پروکسی میاد، نه آی‌پی شما — به همین خاطر پروکسی‌ها معمولاً برای تغییر موقعیت مکانی ظاهری یا پنهان‌کردن آی‌پی واقعی از یه سایت یا سرویس خاص استفاده میشن.</p>

<h2>پروکسی‌های HTTP و HTTPS</h2>
<p>پروکسی‌های HTTP مخصوص ترافیک وب کار می‌کنن — درخواست‌های HTTP رو می‌فهمن و می‌تونن کارهایی مثل کش‌کردن صفحات یا فیلترکردن محتوا انجام بدن، به همین خاطره که تو ادارات و مدارس رایجن. پروکسی‌های HTTPS این رو به ترافیک وب رمزنگاری‌شده هم گسترش میدن. نکته‌ی مهم: یه پروکسی HTTP ساده فقط ترافیک مرورگر رو مسیریابی می‌کنه، نه بقیه فعالیت اینترنتی دستگاهتون، و معمولاً اتصال بین دستگاهتون و خودِ پروکسی رو رمزنگاری نمی‌کنه.</p>

<h2>پروکسی‌های SOCKS5</h2>
<p>SOCKS5 یه پروتکل پروکسی همه‌منظوره‌تره — براش مهم نیست چه نوع ترافیکی رو داره جابه‌جا می‌کنه، پس برای تورنت، گیمینگ و اپ‌های دیگه هم کار می‌کنه، نه فقط صفحات وب. از پروکسی HTTP انعطاف‌پذیرتره، ولی مثل پروکسی‌های HTTP، SOCKS5 استاندارد هم به‌طور پیش‌فرض ترافیکتون رو رمزنگاری نمی‌کنه، که یه تفاوت مهم با VPN هست.</p>

<h2>پروکسی دیتاسنتر در برابر رزیدنشیال</h2>
<p>پروکسی‌های دیتاسنتر رو آی‌پی‌هایی اجرا میشن که متعلق به شرکت‌های هاستینگ ابری هستن — سریع و ارزون‌ان، ولی سایت‌ها راحت می‌تونن شناسایی و مسدودشون کنن چون رنج آی‌پی‌های دیتاسنتر شناخته‌شده‌ست. پروکسی‌های رزیدنشیال ترافیک شما رو از آی‌پی‌های واقعی که ارائه‌دهنده‌های اینترنت خانگی اختصاص دادن رد می‌کنن، که شناساییشون خیلی سخت‌تره ولی به‌طور قابل‌توجهی گرون‌تر و اغلب کندترن.</p>

<h2>پروکسی در برابر VPN: چرا رمزنگاری مهمه</h2>
<p>این تفاوت اصلیه که تو بیشتر بحث‌های پروکسی گم میشه: یه پروکسی معمولاً آی‌پی ظاهریتون رو عوض می‌کنه ولی ترافیکتون رو سرتاسر رمزنگاری نمی‌کنه. یه VPN همه‌چیز بین دستگاهتون و سرور VPN رو رمزنگاری می‌کنه و داده‌هاتون رو حتی رو شبکه‌های نامطمئن مثل وای‌فای عمومی محافظت می‌کنه — و برخلاف بیشتر پروکسی‌ها، کل ترافیک دستگاهتون رو پوشش میده، نه فقط یه مرورگر یا اپ.</p>

<h2>وقتی پروکسی کافی نیست</h2>
<p>اگه هدفتون واقعاً مرورگری خصوصی و امنه — نه فقط عوض‌کردن آی‌پی برای یه درخواست — یه پروکسی به‌تنهایی بهتون نمی‌رسونه. این به‌خصوص رو شبکه‌هایی درسته که ISP یا مدیر شبکه می‌تونه ترافیک رمزنگاری‌نشده رو ببینه. برای هرچیزی که شامل حساب‌های شخصی، پرداخت یا مرور اطلاعات حساس میشه، رمزنگاری اختیاری نیست.</p>

<h2>یه پلن فریمیگا انتخاب کنید</h2>
<p>فریمیگا بهتون یه اتصال VPN کاملاً رمزنگاری‌شده میده، نه فقط عوض‌کردن آی‌پی — با سرورهای سریع VLESS/Xray که طوری ساخته شدن که حتی رو شبکه‌های محدودکننده هم پایدار بمونن. <a href="/fa/plans">پلن‌های VPN فریمیگا رو ببینید</a> و تو چند دقیقه رو هر دستگاهی راه‌اندازیش کنید.</p>
""",
    },
    {
        "slug": "vpn-vs-proxy-differences",
        "title_en": "VPN vs Proxy: Key Differences and Which One You Actually Need",
        "title_fa": "تفاوت VPN و پروکسی: کدوم رو واقعاً لازم دارید؟",
        "excerpt_en": "VPN vs proxy, explained simply: how each one works, what they protect (and don't), and why most people end up choosing a VPN over a proxy.",
        "excerpt_fa": "تفاوت VPN و پروکسی به زبان ساده: هرکدوم چطور کار می‌کنن، چی رو محافظت می‌کنن (و چی رو نه)، و چرا بیشتر افراد آخرش VPN رو به پروکسی ترجیح میدن.",
        "content_en": """
<p>VPN and proxy get lumped together constantly, and it's easy to see why — both can change the IP address a website sees, and both are marketed as ways to "hide" your location online. But under the hood, they solve different problems, and picking the wrong one for what you actually need can leave you with a false sense of privacy. Here's the difference, without the jargon.</p>

<h2>The Short Answer</h2>
<p>A proxy reroutes specific traffic through another IP address. A VPN encrypts and reroutes <em>all</em> of your device's internet traffic through a secure tunnel. If all you need is to appear to browse from a different location for one site, a proxy might do the job. If you care about privacy, security, or getting a full, reliable connection on a restricted network, you need a VPN.</p>

<h2>How a Proxy Works</h2>
<p>A proxy sits between your browser (or a specific app) and the internet, forwarding your requests under its own IP address. It's typically configured per-app or per-browser, which means the rest of your device's traffic — other apps, background services, system-level connections — goes out through your normal, unprotected connection. Most proxies also don't encrypt the traffic between you and the proxy server itself.</p>

<h2>How a VPN Works</h2>
<p>A VPN creates an encrypted tunnel between your entire device and a VPN server, at the operating-system level rather than the app level. Every app on your device routes through that same encrypted connection, and your ISP or anyone else monitoring the network only sees encrypted traffic headed to the VPN server — not what you're actually doing.</p>

<h2>Speed, Security, and Privacy Compared</h2>
<p>Proxies are often marginally faster for the one thing they're doing, since there's no encryption overhead — but that speed comes at the direct cost of security. A VPN adds a small amount of encryption overhead, but a well-run VPN with fast protocols (like VLESS over Xray) keeps that difference barely noticeable, while giving you real protection instead of just an IP swap.</p>

<h2>Which One Do You Actually Need?</h2>
<p>Reach for a proxy only if you have a narrow, low-stakes need — like checking how a website looks from another country — and nothing sensitive is involved. Reach for a VPN for anything involving personal accounts, banking, public Wi-Fi, or a network that's actively restricting your access to the open internet.</p>

<h2>Why Most People Choose a VPN</h2>
<p>In practice, most people who start out looking for "a proxy" actually want what a VPN provides: privacy from their ISP, protection on public networks, and a way to reliably get online when a network is blocking access. A VPN covers the proxy use case (changing your apparent location) while also solving the problems a proxy can't.</p>

<h2>Get Started</h2>
<p>Freemiga is a full VPN — encrypted, device-wide, and built on VLESS/Xray to stay reliable on restrictive networks. <a href="/en/plans">Compare Freemiga's plans</a> and get connected in a few minutes.</p>
""",
        "content_fa": """
<p>VPN و پروکسی مدام با هم قاطی میشن، و دلیلشم مشخصه — هر دو می‌تونن آی‌پی‌ای که یه سایت می‌بینه رو عوض کنن، و هر دو به‌عنوان راهی برای «پنهان‌کردن» موقعیتتون آنلاین تبلیغ میشن. ولی زیر پوسته، این دو مشکل متفاوتی رو حل می‌کنن، و انتخاب اشتباه بین این دو می‌تونه یه حس امنیت کاذب بهتون بده. این‌جا تفاوتشون رو بدون اصطلاحات پیچیده توضیح می‌دیم.</p>

<h2>جواب کوتاه</h2>
<p>یه پروکسی ترافیک خاصی رو از یه آی‌پی دیگه رد می‌کنه. یه VPN <em>همه‌ی</em> ترافیک اینترنتی دستگاهتون رو رمزنگاری و از یه تونل امن رد می‌کنه. اگه فقط می‌خواید برای یه سایت به‌نظر برسه از یه موقعیت دیگه دارید مرور می‌کنید، شاید یه پروکسی کافی باشه. ولی اگه براتون حریم خصوصی، امنیت، یا داشتن یه اتصال کامل و پایدار رو یه شبکه‌ی محدودشده مهمه، به VPN نیاز دارید.</p>

<h2>پروکسی چطور کار می‌کنه</h2>
<p>یه پروکسی بین مرورگر شما (یا یه اپ خاص) و اینترنت قرار می‌گیره و درخواست‌هاتون رو زیر آی‌پی خودش ارسال می‌کنه. معمولاً به‌ازای هر اپ یا مرورگر جداگانه تنظیم میشه، یعنی بقیه‌ی ترافیک دستگاهتون — اپ‌های دیگه، سرویس‌های پس‌زمینه، اتصالات سطح سیستم — از اتصال عادی و بدون محافظت شما رد میشه. بیشتر پروکسی‌ها همچنین ترافیک بین شما و خودِ سرور پروکسی رو رمزنگاری نمی‌کنن.</p>

<h2>VPN چطور کار می‌کنه</h2>
<p>یه VPN یه تونل رمزنگاری‌شده بین کل دستگاهتون و یه سرور VPN می‌سازه، در سطح سیستم‌عامل نه در سطح اپ. هر اپی رو دستگاهتون از همون اتصال رمزنگاری‌شده رد میشه، و ISP یا هرکسی که داره شبکه رو مانیتور می‌کنه فقط ترافیک رمزنگاری‌شده به‌سمت سرور VPN رو می‌بینه — نه اینکه واقعاً چیکار دارید می‌کنید.</p>

<h2>مقایسه سرعت، امنیت و حریم خصوصی</h2>
<p>پروکسی‌ها معمولاً برای همون یه کاری که انجام می‌دن کمی سریع‌ترن، چون overhead رمزنگاری ندارن — ولی این سرعت مستقیماً به قیمت امنیت تموم میشه. یه VPN مقدار کمی overhead رمزنگاری اضافه می‌کنه، ولی یه VPN خوب با پروتکل‌های سریع (مثل VLESS رو Xray) این تفاوت رو تقریباً نامحسوس نگه می‌داره، در حالی که محافظت واقعی بهتون میده نه فقط عوض‌کردن آی‌پی.</p>

<h2>کدوم رو واقعاً لازم دارید؟</h2>
<p>فقط وقتی سراغ پروکسی برید که یه نیاز محدود و کم‌ریسک دارید — مثل چک‌کردن اینکه یه سایت از یه کشور دیگه چه شکلیه — و هیچ چیز حساسی درگیر نیست. برای هرچیزی که شامل حساب‌های شخصی، بانکداری، وای‌فای عمومی، یا یه شبکه‌ای که فعالانه دسترسیتون به اینترنت آزاد رو محدود می‌کنه، سراغ VPN برید.</p>

<h2>چرا بیشتر افراد VPN رو انتخاب می‌کنن</h2>
<p>در عمل، بیشتر افرادی که دنبال «یه پروکسی» می‌گردن، در واقع دنبال چیزی هستن که یه VPN می‌ده: حریم خصوصی از ISP، محافظت رو شبکه‌های عمومی، و راهی برای وصل‌شدن پایدار وقتی یه شبکه دسترسی رو مسدود می‌کنه. یه VPN هم کاربرد پروکسی (عوض‌کردن موقعیت ظاهری) رو پوشش میده، هم مشکلاتی که پروکسی نمی‌تونه حلشون کنه رو حل می‌کنه.</p>

<h2>شروع کنید</h2>
<p>فریمیگا یه VPN کامله — رمزنگاری‌شده، سرتاسر دستگاه، و ساخته‌شده رو VLESS/Xray تا رو شبکه‌های محدودکننده هم پایدار بمونه. <a href="/fa/plans">پلن‌های فریمیگا رو مقایسه کنید</a> و تو چند دقیقه وصل شید.</p>
""",
    },
    {
        "slug": "v2ray-xray-vless-explained",
        "title_en": "V2Ray, Xray, and VLESS Explained: The Tech Behind Modern VPNs",
        "title_fa": "V2Ray، Xray و VLESS چیستند؟ فناوری پشت VPN‌های مدرن",
        "excerpt_en": "How V2Ray, Xray, VMess, and VLESS relate to each other, why they resist deep packet inspection, and how Freemiga uses this stack to stay online where basic VPNs get blocked.",
        "excerpt_fa": "ارتباط V2Ray، Xray، VMess و VLESS با هم چیه، چرا در برابر Deep Packet Inspection مقاومن، و فریمیگا چطور از این فناوری برای وصل‌موندن استفاده می‌کنه.",
        "content_en": """
<p>If you've spent any time researching VPNs that actually work in heavily censored regions, you've probably run into the names V2Ray, Xray, VMess, and VLESS — often used almost interchangeably, which makes it genuinely confusing to figure out what each one actually is. Here's how they fit together, and why this specific stack matters for getting a reliable connection.</p>

<h2>What Is V2Ray?</h2>
<p>V2Ray is an open-source networking framework, not a single protocol — it's a platform for building flexible, configurable proxy and VPN tools. It grew out of the earlier Shadowsocks project with a goal of being harder to detect and more customizable. V2Ray introduced VMess, its own protocol for authenticating and encrypting traffic between client and server.</p>

<h2>Xray: The Modern Successor</h2>
<p>Xray started as a fork of V2Ray's core and has since become the more actively developed, higher-performance option. It's largely compatible with V2Ray's configuration and protocols but adds better performance, more transport options, and — critically — stronger tools for disguising VPN traffic as ordinary web traffic. Most modern VLESS-based VPN setups, Freemiga included, run on Xray-core specifically for this reason.</p>

<h2>VMess vs VLESS: What Changed</h2>
<p>VMess, V2Ray's original protocol, encrypts traffic itself in addition to whatever transport-layer encryption (like TLS) is layered on top — which adds processing overhead. VLESS strips this out: it relies entirely on the outer transport layer (typically TLS) for encryption instead of duplicating it, which makes it lighter and faster while remaining just as secure when paired with TLS, which is the standard way it's deployed. This is the main reason VLESS has largely replaced VMess in new deployments.</p>

<h2>Why These Protocols Resist Deep Packet Inspection</h2>
<p>Deep Packet Inspection (DPI) is how some networks identify and block VPN traffic — by analyzing traffic patterns for the fingerprint of a VPN connection, rather than just blocking IP addresses. VLESS over Xray, especially when combined with TLS and a technique called WebSocket or gRPC transport, makes VPN traffic look nearly identical to ordinary encrypted web browsing (the same HTTPS traffic every website uses). That similarity is what lets it get through firewalls that block more obviously "VPN-shaped" traffic, including WireGuard and OpenVPN in some cases.</p>

<h2>How Freemiga Uses VLESS and Xray</h2>
<p>Freemiga's servers run on Xray-core with the VLESS protocol specifically because it holds up in environments with aggressive network filtering. This isn't a marketing choice — it's a practical one: a VPN that's technically "more secure" on paper is worthless if the network blocks it before it can connect. Freemiga is built around staying connectable first, with strong encryption included, not traded off.</p>

<h2>Try It Yourself</h2>
<p>You don't need to understand every layer of this stack to benefit from it — Freemiga handles the configuration, you just need a subscription link and a compatible app. <a href="/en/plans">See Freemiga's VPN plans</a> and get set up in a few minutes.</p>
""",
        "content_fa": """
<p>اگه یه‌مدت درباره‌ی VPN‌هایی که واقعاً تو مناطق با سانسور سنگین کار می‌کنن تحقیق کرده باشید، احتمالاً به اسم‌های V2Ray، Xray، VMess و VLESS برخوردید — که اغلب تقریباً به‌جای هم استفاده میشن، که واقعاً گیج‌کننده‌ست بفهمید هرکدوم دقیقاً چیه. این‌جا توضیح می‌دیم این‌ها چطور به هم مرتبطن، و چرا این فناوری خاص برای داشتن یه اتصال پایدار مهمه.</p>

<h2>V2Ray چیه؟</h2>
<p>V2Ray یه فریم‌ورک شبکه‌ی متن‌بازه، نه یه پروتکل تنها — یه پلتفرمه برای ساختن ابزارهای پروکسی و VPN منعطف و قابل‌تنظیم. از دلِ پروژه‌ی قدیمی‌تر Shadowsocks با هدف سخت‌تر شدن شناسایی و قابل‌شخصی‌سازی‌تر بودن رشد کرد. V2Ray پروتکل VMess خودش رو معرفی کرد، برای احراز هویت و رمزنگاری ترافیک بین کلاینت و سرور.</p>

<h2>Xray: جانشین مدرن</h2>
<p>Xray به‌عنوان یه فورک از هسته‌ی V2Ray شروع شد و از اون موقع به گزینه‌ای با توسعه‌ی فعال‌تر و عملکرد بالاتر تبدیل شده. تا حد زیادی با کانفیگ و پروتکل‌های V2Ray سازگاره ولی عملکرد بهتر، گزینه‌های transport بیشتر، و — مهم‌تر از همه — ابزارهای قوی‌تری برای جا زدن ترافیک VPN به‌عنوان ترافیک عادی وب اضافه می‌کنه. بیشتر تنظیمات مدرن VPN مبتنی‌بر VLESS، از جمله فریمیگا، دقیقاً به همین دلیل رو Xray-core اجرا میشن.</p>

<h2>VMess در برابر VLESS: چی تغییر کرد</h2>
<p>VMess، پروتکل اصلی V2Ray، خودش ترافیک رو رمزنگاری می‌کنه به‌علاوه‌ی هر رمزنگاری لایه‌ی transport (مثل TLS) که روش گذاشته میشه — که overhead پردازشی اضافه می‌کنه. VLESS این رو حذف می‌کنه: کاملاً به لایه‌ی transport بیرونی (معمولاً TLS) برای رمزنگاری تکیه می‌کنه به‌جای تکرارش، که سبک‌تر و سریع‌ترش می‌کنه در حالی که وقتی با TLS جفت بشه — که روش استاندارد پیاده‌سازیشه — همون‌قدر امنه. این دلیل اصلیه که VLESS تا حد زیادی جای VMess رو تو پیاده‌سازی‌های جدید گرفته.</p>

<h2>چرا این پروتکل‌ها در برابر Deep Packet Inspection مقاومن</h2>
<p>Deep Packet Inspection (DPI) روشیه که بعضی شبکه‌ها ترافیک VPN رو شناسایی و مسدود می‌کنن — با تحلیل الگوهای ترافیک برای پیدا کردن اثر انگشت یه اتصال VPN، نه فقط مسدودکردن آی‌پی‌ها. VLESS رو Xray، به‌خصوص وقتی با TLS و تکنیکی به اسم WebSocket یا gRPC transport ترکیب بشه، ترافیک VPN رو تقریباً شبیه مرور وب رمزنگاری‌شده‌ی عادی می‌کنه (همون ترافیک HTTPSای که هر سایتی استفاده می‌کنه). همین شباهته که باعث میشه از فایروال‌هایی که ترافیک آشکارتر «شکل VPN» رو مسدود می‌کنن رد بشه، از جمله بعضی وقت‌ها WireGuard و OpenVPN.</p>

<h2>فریمیگا چطور از VLESS و Xray استفاده می‌کنه</h2>
<p>سرورهای فریمیگا رو Xray-core با پروتکل VLESS اجرا میشن، دقیقاً چون تو محیط‌های با فیلترینگ شدید شبکه پایداره. این یه انتخاب تبلیغاتی نیست — یه انتخاب کاربردیه: یه VPN که رو کاغذ از نظر فنی «امن‌تره» اگه شبکه قبل از اینکه بتونه وصل بشه مسدودش کنه، بی‌ارزشه. فریمیگا اول حول محور وصل‌ماندن ساخته شده، با رمزنگاری قوی که همراهشه، نه چیزی که باهاش معامله بشه.</p>

<h2>خودتون امتحان کنید</h2>
<p>لازم نیست هر لایه‌ی این فناوری رو بفهمید تا ازش بهره ببرید — فریمیگا کانفیگ رو خودش مدیریت می‌کنه، شما فقط به یه لینک اشتراک و یه اپ سازگار نیاز دارید. <a href="/fa/plans">پلن‌های VPN فریمیگا رو ببینید</a> و تو چند دقیقه راه‌اندازیش کنید.</p>
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
                status=BlogPostStatus.published,
                published_at=datetime.utcnow(),
                reading_time_min=reading_time_minutes(p["content_en"]),
                tags=tags,
            )
            db.add(post)
            created += 1
        db.commit()
        print(f"Done — {created} new post(s) created, {len(POSTS) - created} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
