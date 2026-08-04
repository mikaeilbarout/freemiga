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
        "title_fa": "پروتکل‌های VPN چیست؟ مقایسه کامل OpenVPN، WireGuard، Shadowsocks و VLESS",
        "excerpt_en": "A plain-English guide to the main VPN protocol types — OpenVPN, WireGuard, Shadowsocks, and VLESS — and how to pick the right one for speed, security, and bypassing censorship.",
        "excerpt_fa": "راهنمای جامع و رسمی پروتکل‌های VPN شامل OpenVPN، WireGuard، Shadowsocks و VLESS؛ بررسی تفاوت‌های امنیتی، سرعت اتصال و توانایی عبور از سانسور برای انتخاب مناسب‌ترین گزینه.",
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
<p>هر برنامه VPN بر پایه یک <strong>پروتکل VPN</strong> ساخته می‌شود؛ مجموعه‌ای از قواعد فنی که تعیین می‌کند ترافیک اینترنتی کاربر چگونه رمزنگاری، بسته‌بندی و به سرور مقصد ارسال شود. انتخاب پروتکل تأثیر مستقیمی بر تجربه کاربری دارد: سرعت اتصال، میزان مصرف باتری، پایداری در شبکه‌های ناپایدار و، برای کاربرانی که با محدودیت‌های اینترنتی و سانسور مواجه‌اند، حتی امکان برقراری اتصال. در این مقاله، مهم‌ترین پروتکل‌های VPN رایج بررسی می‌شوند تا انتخابی آگاهانه و متناسب با نیاز خود داشته باشید.</p>

<h2>پروتکل VPN چیست و چرا اهمیت دارد؟</h2>
<p>پروتکل VPN، زیرساخت فنی تونل رمزنگاری‌شده میان دستگاه کاربر و سرور VPN را تشکیل می‌دهد. دو سرویس VPN ممکن است از نظر ظاهری کاملاً مشابه به نظر برسند، اما به دلیل استفاده از پروتکل‌های متفاوت، تجربه‌ای کاملاً متفاوت ارائه دهند؛ یکی ممکن است اتصالی فوری و پایدار فراهم کند و دیگری دچار تأخیر، افت سرعت یا قطعی مکرر شود. به همین دلیل، هنگام مقایسه سرویس‌های VPN، بررسی پروتکل مورد استفاده معمولاً معیار دقیق‌تری نسبت به شعارهای تبلیغاتی درباره «رمزنگاری نظامی» یا «امنیت مطلق» است.</p>

<h2>OpenVPN: پروتکلی استاندارد و دیرینه</h2>
<p>OpenVPN از سال ۲۰۰۱ میلادی فعال است و همچنان یکی از پرکاربردترین و پشتیبانی‌شده‌ترین پروتکل‌های VPN در جهان محسوب می‌شود. این پروتکل متن‌باز است، بارها مورد ارزیابی و ممیزی امنیتی مستقل قرار گرفته و تقریباً روی تمامی سیستم‌عامل‌ها و دستگاه‌ها به‌صورت پایدار عمل می‌کند. با این حال، مهم‌ترین نقطه ضعف آن سرعت است؛ سربار رمزنگاری در OpenVPN باعث می‌شود این پروتکل، به‌ویژه در اتصالات موبایل، محسوساً کندتر از پروتکل‌های جدیدتر عمل کند. به‌طور خلاصه، OpenVPN گزینه‌ای امن، شناخته‌شده و قابل‌اعتماد است، اما امروزه به‌ندرت سریع‌ترین انتخاب ممکن به شمار می‌رود.</p>

<h2>WireGuard: پروتکلی سریع و مدرن</h2>
<p>WireGuard پروتکلی نسبتاً جدید است که بر پایه کدی به‌مراتب کوچک‌تر و ساده‌تر از OpenVPN طراحی شده است؛ ویژگی‌ای که هم ممیزی امنیتی آن را آسان‌تر می‌کند و هم در عمل سرعت به‌مراتب بالاتری به همراه دارد. این پروتکل پس از تغییر شبکه دستگاه (برای نمونه، جابه‌جایی از وای‌فای به اینترنت همراه) تقریباً به‌صورت آنی مجدداً متصل می‌شود؛ ویژگی‌ای که آن را به گزینه‌ای مناسب برای کاربران موبایل تبدیل کرده است. با این حال، الگوی ترافیکی WireGuard نسبتاً قابل‌شناسایی است و شبکه‌هایی که به‌طور فعال به دنبال شناسایی و مسدودسازی ترافیک VPN هستند، می‌توانند آن را با دقت بیشتری تشخیص دهند.</p>

<h2>Shadowsocks: طراحی‌شده برای عبور از سانسور</h2>
<p>Shadowsocks به‌طور خاص برای دور زدن فایروال‌هایی طراحی شده که ترافیک متعارف VPN را مسدود می‌کنند. این پروتکل به‌جای رفتار مانند یک VPN آشکار، اتصال را در قالب ترافیک وب رمزنگاری‌شده معمولی پنهان می‌کند و همین امر شناسایی و مسدودسازی آن را برای سامانه‌های فیلترینگ در سطح شبکه دشوارتر می‌سازد. Shadowsocks در مناطقی با محدودیت‌های شدید اینترنتی از محبوبیت بالایی برخوردار است، هرچند پروتکل‌های جدیدتر با تکیه بر همین ایده، سطح پنهان‌سازی (obfuscation) قوی‌تری ارائه می‌دهند.</p>

<h2>VLESS و Xray: فناوری زیرساخت فریمیگا</h2>
<p>VLESS پروتکلی سبک است که بر بستر پروژه Xray-core توسعه یافته؛ تکاملی مدرن از اکوسیستم V2Ray که از ابتدا برای مقاومت در برابر بازرسی عمیق بسته‌ها (Deep Packet Inspection یا DPI) طراحی شده است. DPI روشی است که برخی شبکه‌ها برای شناسایی و مسدودسازی ترافیک VPN از طریق تحلیل الگوهای آن به کار می‌برند. VLESS با حذف سربارهای غیرضروری موجود در پروتکل‌های قدیمی‌تر همین خانواده، تأخیر کمتری ایجاد می‌کند بدون آنکه توانایی شبیه‌سازی ترافیک عادی HTTPS را از دست بدهد. فریمیگا دقیقاً به همین دلیل بر بستر این پروتکل فعالیت می‌کند؛ زیرا در محیط‌هایی که سایر پروتکل‌های VPN به‌طور کامل مسدود می‌شوند، همچنان کارایی خود را حفظ می‌کند.</p>

<h2>مقایسه کلی پروتکل‌های VPN</h2>
<ul>
<li><strong>OpenVPN:</strong> امنیت بالا و پشتیبانی گسترده، اما سرعت پایین‌تر نسبت به گزینه‌های جدیدتر.</li>
<li><strong>WireGuard:</strong> سرعت بسیار بالا و اتصال مجدد سریع، اما قابلیت شناسایی نسبتاً بیشتر توسط سامانه‌های فیلترینگ.</li>
<li><strong>Shadowsocks:</strong> توانایی مناسب در عبور از سانسور پایه، اما مقاومت کمتر در برابر فیلترینگ پیشرفته امروزی.</li>
<li><strong>VLESS بر بستر Xray:</strong> ترکیبی از سرعت بالا و مقاومت قوی در برابر DPI، مناسب‌ترین گزینه برای شبکه‌های با محدودیت شدید.</li>
</ul>

<h2>چگونه پروتکل مناسب خود را انتخاب کنید؟</h2>
<p>اگر تنها به دنبال رمزنگاری سریع و پایدار در یک شبکه باز هستید، WireGuard انتخابی دشوار برای رقابت است. اما اگر در شبکه‌ای قرار دارید که به‌طور فعال ترافیک VPN را مسدود می‌کند، پروتکلی که مشخصاً برای پنهان‌سازی طراحی شده — مانند VLESS بر بستر Xray — تنها گزینه‌ای است که عملاً امکان اتصال را فراهم می‌کند. در چنین شرایطی، سرعت اتصال اهمیتی ندارد اگر اساساً اتصالی برقرار نشود.</p>

<h2>پرسش‌های متداول درباره پروتکل‌های VPN</h2>
<h3>کدام پروتکل VPN امن‌ترین است؟</h3>
<p>از نظر فنی، تمامی پروتکل‌های معرفی‌شده در این مقاله — در صورت پیاده‌سازی صحیح — سطح امنیتی قابل‌قبولی ارائه می‌دهند. تفاوت اصلی میان آن‌ها معمولاً در سرعت، پایداری و توانایی عبور از سانسور است، نه در میزان رمزنگاری.</p>
<h3>چرا فریمیگا از VLESS استفاده می‌کند؟</h3>
<p>فریمیگا به دلیل مقاومت بالای VLESS در برابر بازرسی عمیق بسته‌ها و توانایی آن در شبیه‌سازی ترافیک عادی وب، این پروتکل را برای زیرساخت خود انتخاب کرده تا حتی در شبکه‌های با فیلترینگ شدید، اتصالی پایدار و سریع ارائه دهد.</p>
<h3>آیا می‌توان پروتکل VPN را در طول استفاده تغییر داد؟</h3>
<p>بله؛ اغلب سرویس‌های VPN معتبر، از جمله فریمیگا، امکان استفاده از پیکربندی بهینه‌شده را برای کاربران فراهم می‌کنند تا در صورت بروز مشکل در اتصال، تجربه کاربری بدون وقفه باقی بماند.</p>

<h2>اتصال به فریمیگا</h2>
<p>فریمیگا بر بستر VLESS/Xray فعالیت می‌کند تا حتی در شرایطی که پروتکل‌های پایه VPN مسدود می‌شوند، اتصال بدون افت سرعت برقرار بماند. <a href="/fa/plans">پلن‌های VPN فریمیگا را مقایسه کنید</a> و در عرض چند دقیقه، روی هر دستگاهی متصل شوید.</p>
""",
    },
    {
        "slug": "what-is-a-proxy-server-types-explained",
        "title_en": "What Is a Proxy Server? HTTP, SOCKS5 & Residential Proxies Explained",
        "title_fa": "پروکسی سرور چیست؟ بررسی کامل انواع پروکسی HTTP، SOCKS5 و رزیدنشیال",
        "excerpt_en": "Learn what a proxy server actually does, the difference between HTTP, SOCKS5, datacenter, and residential proxies, and why most people are better off with a VPN.",
        "excerpt_fa": "توضیح رسمی و کامل اینکه پروکسی سرور چگونه عمل می‌کند، تفاوت پروکسی‌های HTTP، SOCKS5، دیتاسنتر و رزیدنشیال با یکدیگر، و دلیل برتری VPN نسبت به پروکسی برای اغلب کاربران.",
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
<p>واژه «پروکسی» بسیار پرکاربرد است — پروکسی سرور، سایت پروکسی، افزونه پروکسی — بی‌آنکه همواره توضیح روشنی از عملکرد واقعی آن ارائه شود. در این مقاله، تعریف دقیق پروکسی سرور، مهم‌ترین انواع آن و محدودیت‌های آن در مقایسه با VPN به‌طور کامل بررسی می‌شود.</p>

<h2>پروکسی سرور چیست؟</h2>
<p>پروکسی سرور واسطه‌ای میان دستگاه کاربر و وب‌سایت‌های مورد بازدید قرار می‌گیرد. به‌جای برقراری اتصال مستقیم، درخواست کاربر ابتدا به پروکسی ارسال می‌شود و سپس این سرور، درخواست را از طرف کاربر به مقصد نهایی منتقل می‌کند. از دیدگاه وب‌سایت مقصد، درخواست از آدرس آی‌پی پروکسی ارسال شده است، نه آدرس واقعی کاربر؛ به همین دلیل، پروکسی‌ها معمولاً برای تغییر موقعیت مکانی ظاهری یا پنهان‌سازی آدرس آی‌پی واقعی در برابر یک سرویس یا وب‌سایت خاص به کار می‌روند.</p>

<h2>پروکسی‌های HTTP و HTTPS</h2>
<p>پروکسی‌های HTTP به‌طور اختصاصی ترافیک وب را مدیریت می‌کنند؛ این پروکسی‌ها قادر به تفسیر درخواست‌های HTTP هستند و می‌توانند اقداماتی مانند ذخیره‌سازی موقت (کش) صفحات یا فیلترینگ محتوا انجام دهند، به همین دلیل در محیط‌های سازمانی و آموزشی کاربرد گسترده‌ای دارند. پروکسی‌های HTTPS این قابلیت را به ترافیک رمزنگاری‌شده وب نیز گسترش می‌دهند. نکته حائز اهمیت این است که یک پروکسی HTTP معمولی تنها ترافیک مرورگر را مسیریابی می‌کند، نه سایر فعالیت‌های اینترنتی دستگاه، و معمولاً اتصال میان دستگاه کاربر و خودِ پروکسی را رمزنگاری نمی‌کند.</p>

<h2>پروکسی‌های SOCKS5</h2>
<p>SOCKS5 پروتکلی عمومی‌تر برای پروکسی است که نسبت به نوع ترافیک بی‌تفاوت عمل می‌کند؛ به همین دلیل برای تورنت، بازی‌های آنلاین و سایر برنامه‌ها، فراتر از مرورگر، قابل استفاده است. این ویژگی، انعطاف‌پذیری بیشتری نسبت به پروکسی HTTP فراهم می‌کند، اما همانند پروکسی‌های HTTP، نسخه استاندارد SOCKS5 نیز به‌طور پیش‌فرض ترافیک را رمزنگاری نمی‌کند؛ تفاوتی اساسی نسبت به VPN.</p>

<h2>پروکسی دیتاسنتر در برابر پروکسی رزیدنشیال</h2>
<p>پروکسی‌های دیتاسنتر بر بستر آدرس‌های آی‌پی متعلق به ارائه‌دهندگان میزبانی ابری فعالیت می‌کنند؛ این پروکسی‌ها سریع و کم‌هزینه‌اند، اما به دلیل شناخته‌شده بودن محدوده آی‌پی دیتاسنترها، وب‌سایت‌ها به‌راحتی قادر به شناسایی و مسدودسازی آن‌ها هستند. در مقابل، پروکسی‌های رزیدنشیال ترافیک کاربر را از طریق آدرس‌های آی‌پی واقعی که توسط ارائه‌دهندگان اینترنت خانگی تخصیص یافته‌اند، مسیریابی می‌کنند؛ ویژگی‌ای که شناسایی آن‌ها را به‌مراتب دشوارتر می‌سازد، اما هزینه بالاتر و سرعت پایین‌تری نیز به همراه دارد.</p>

<h2>پروکسی در برابر VPN: اهمیت رمزنگاری</h2>
<p>این نکته کلیدی است که در بسیاری از توضیحات مربوط به پروکسی نادیده گرفته می‌شود: پروکسی معمولاً تنها آدرس آی‌پی ظاهری را تغییر می‌دهد و ترافیک را به‌صورت سرتاسری رمزنگاری نمی‌کند. در مقابل، VPN تمامی ترافیک میان دستگاه کاربر و سرور VPN را رمزنگاری می‌کند و از داده‌های کاربر حتی در شبکه‌های نامطمئن، مانند وای‌فای عمومی، محافظت می‌کند. همچنین، برخلاف اغلب پروکسی‌ها که تنها یک مرورگر یا برنامه را پوشش می‌دهند، VPN تمامی ترافیک دستگاه را در بر می‌گیرد.</p>

<h2>چه زمانی پروکسی کافی نیست؟</h2>
<p>در صورتی که هدف کاربر مرور خصوصی و امن باشد — نه صرفاً تغییر آدرس آی‌پی برای یک درخواست موقت — استفاده از پروکسی به‌تنهایی کافی نخواهد بود. این موضوع به‌ویژه در شبکه‌هایی که ارائه‌دهنده خدمات اینترنت یا مدیر شبکه امکان مشاهده ترافیک رمزنگاری‌نشده را دارد، اهمیت بیشتری پیدا می‌کند. برای هرگونه فعالیتی که شامل حساب‌های شخصی، تراکنش‌های مالی یا اطلاعات حساس باشد، رمزنگاری یک ضرورت است، نه یک گزینه اختیاری.</p>

<h2>پرسش‌های متداول درباره پروکسی سرور</h2>
<h3>آیا استفاده از پروکسی رایگان امن است؟</h3>
<p>پروکسی‌های رایگان معمولاً فاقد رمزنگاری مناسب هستند و در برخی موارد، اطلاعات کاربران را برای اهداف تجاری ثبت و ذخیره می‌کنند. استفاده از این سرویس‌ها برای فعالیت‌های حساس توصیه نمی‌شود.</p>
<h3>تفاوت اصلی پروکسی و VPN در یک جمله چیست؟</h3>
<p>پروکسی صرفاً آدرس آی‌پی را تغییر می‌دهد، در حالی که VPN علاوه بر تغییر آی‌پی، تمامی ترافیک دستگاه را نیز رمزنگاری می‌کند.</p>
<h3>آیا می‌توان همزمان از پروکسی و VPN استفاده کرد؟</h3>
<p>از نظر فنی امکان‌پذیر است، اما در اغلب موارد استفاده هم‌زمان ضرورتی ندارد و ممکن است سرعت اتصال را به‌طور محسوسی کاهش دهد.</p>

<h2>انتخاب یک پلن فریمیگا</h2>
<p>فریمیگا یک اتصال VPN کاملاً رمزنگاری‌شده ارائه می‌دهد، نه صرفاً تغییر آدرس آی‌پی؛ با سرورهای سریع مبتنی بر VLESS/Xray که برای حفظ پایداری حتی در شبکه‌های محدودکننده طراحی شده‌اند. <a href="/fa/plans">پلن‌های VPN فریمیگا را مشاهده کنید</a> و در عرض چند دقیقه، روی هر دستگاهی راه‌اندازی کنید.</p>
""",
    },
    {
        "slug": "vpn-vs-proxy-differences",
        "title_en": "VPN vs Proxy: Key Differences and Which One You Actually Need",
        "title_fa": "تفاوت VPN و پروکسی: کدام یک را واقعاً نیاز دارید؟",
        "excerpt_en": "VPN vs proxy, explained simply: how each one works, what they protect (and don't), and why most people end up choosing a VPN over a proxy.",
        "excerpt_fa": "بررسی رسمی و دقیق تفاوت VPN و پروکسی؛ نحوه عملکرد هرکدام، سطح محافظتی که ارائه می‌دهند و دلیل اینکه چرا اغلب کاربران در نهایت VPN را به پروکسی ترجیح می‌دهند.",
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
<p>VPN و پروکسی اغلب به‌اشتباه معادل یکدیگر در نظر گرفته می‌شوند؛ دلیل این موضوع کاملاً روشن است، چراکه هر دو قادرند آدرس آی‌پی قابل مشاهده برای یک وب‌سایت را تغییر دهند و هر دو به‌عنوان روشی برای «پنهان‌سازی» موقعیت مکانی آنلاین معرفی می‌شوند. با این حال، این دو فناوری در سطح فنی مسائل کاملاً متفاوتی را حل می‌کنند و انتخاب نادرست میان آن‌ها می‌تواند حس کاذبی از امنیت و حریم خصوصی ایجاد کند. در این مقاله، تفاوت‌های اصلی این دو فناوری بدون استفاده از اصطلاحات پیچیده فنی تشریح می‌شود.</p>

<h2>پاسخ کوتاه</h2>
<p>یک پروکسی، بخش مشخصی از ترافیک را از طریق یک آدرس آی‌پی دیگر مسیریابی می‌کند. در مقابل، یک VPN تمامی ترافیک اینترنتی دستگاه را رمزنگاری کرده و از طریق یک تونل امن ارسال می‌کند. اگر تنها نیاز کاربر نمایش موقعیت مکانی متفاوت برای یک وب‌سایت خاص باشد، پروکسی ممکن است کافی باشد؛ اما در صورتی که حریم خصوصی، امنیت اطلاعات یا برقراری اتصالی کامل و پایدار در یک شبکه محدودشده اهمیت داشته باشد، استفاده از VPN ضروری است.</p>

<h2>پروکسی چگونه عمل می‌کند؟</h2>
<p>پروکسی میان مرورگر کاربر (یا یک برنامه خاص) و اینترنت قرار می‌گیرد و درخواست‌ها را زیر آدرس آی‌پی خود ارسال می‌کند. این پیکربندی معمولاً به‌صورت جداگانه برای هر برنامه یا مرورگر انجام می‌شود، به این معنا که سایر ترافیک دستگاه — شامل برنامه‌های دیگر، سرویس‌های پس‌زمینه و اتصالات سطح سیستم‌عامل — از طریق اتصال عادی و بدون محافظت ارسال می‌شود. علاوه بر این، اغلب پروکسی‌ها ترافیک میان کاربر و خودِ سرور پروکسی را نیز رمزنگاری نمی‌کنند.</p>

<h2>VPN چگونه عمل می‌کند؟</h2>
<p>یک VPN تونلی رمزنگاری‌شده میان کل دستگاه کاربر و سرور VPN ایجاد می‌کند؛ این فرآیند در سطح سیستم‌عامل انجام می‌شود، نه در سطح یک برنامه منفرد. تمامی برنامه‌های نصب‌شده روی دستگاه از همین اتصال رمزنگاری‌شده استفاده می‌کنند و ارائه‌دهنده خدمات اینترنت یا هر شخص دیگری که ترافیک شبکه را رصد می‌کند، تنها ترافیک رمزنگاری‌شده به‌سمت سرور VPN را مشاهده می‌کند، بدون اطلاع از محتوای واقعی فعالیت کاربر.</p>

<h2>مقایسه سرعت، امنیت و حریم خصوصی</h2>
<p>پروکسی‌ها معمولاً به دلیل نبود سربار رمزنگاری، اندکی سریع‌تر از VPN عمل می‌کنند، اما این افزایش سرعت مستقیماً با کاهش سطح امنیت همراه است. VPN مقدار محدودی سربار رمزنگاری ایجاد می‌کند، اما یک VPN با کیفیت و مجهز به پروتکل‌های سریع — مانند VLESS بر بستر Xray — این تفاوت را تقریباً غیرقابل‌احساس نگه می‌دارد، در حالی که محافظتی واقعی ارائه می‌دهد، نه صرفاً یک جابه‌جایی آدرس آی‌پی.</p>

<h2>کدام یک را واقعاً نیاز دارید؟</h2>
<p>استفاده از پروکسی تنها برای نیازهای محدود و کم‌ریسک توصیه می‌شود؛ برای نمونه، بررسی ظاهر یک وب‌سایت از کشوری دیگر، بدون درگیر بودن اطلاعات حساس. در مقابل، برای هرگونه فعالیتی که شامل حساب‌های شخصی، بانکداری آنلاین، استفاده از وای‌فای عمومی یا اتصال در شبکه‌ای باشد که دسترسی آزاد به اینترنت را به‌طور فعال محدود می‌کند، استفاده از VPN توصیه می‌شود.</p>

<h2>چرا اغلب کاربران در نهایت VPN را انتخاب می‌کنند؟</h2>
<p>در عمل، بسیاری از کاربرانی که در ابتدا به دنبال «یک پروکسی» هستند، در واقع به چیزی نیاز دارند که تنها VPN فراهم می‌کند: حریم خصوصی در برابر ارائه‌دهنده اینترنت، محافظت در شبکه‌های عمومی و امکان اتصال پایدار در شرایطی که یک شبکه دسترسی را مسدود کرده است. VPN، علاوه بر پوشش کاربرد پروکسی (تغییر موقعیت مکانی ظاهری)، مسائلی را نیز حل می‌کند که از عهده پروکسی خارج است.</p>

<h2>پرسش‌های متداول درباره VPN و پروکسی</h2>
<h3>آیا پروکسی رایگان می‌تواند جایگزین VPN شود؟</h3>
<p>خیر. پروکسی‌های رایگان معمولاً فاقد رمزنگاری مناسب هستند و پوشش کاملی برای ترافیک دستگاه ارائه نمی‌دهند؛ بنابراین جایگزین مناسبی برای VPN محسوب نمی‌شوند.</p>
<h3>آیا VPN سرعت اینترنت را کاهش می‌دهد؟</h3>
<p>استفاده از VPN ممکن است سربار اندکی ایجاد کند، اما با انتخاب پروتکل‌های مدرن مانند VLESS، این افت سرعت معمولاً ناچیز و در عمل غیرقابل‌احساس است.</p>
<h3>آیا استفاده از VPN قانونی است؟</h3>
<p>استفاده از VPN در بیشتر کشورهای جهان قانونی است، هرچند مقررات مربوط به آن می‌تواند بسته به کشور متفاوت باشد. توصیه می‌شود کاربران از قوانین محلی مطلع باشند.</p>

<h2>شروع کنید</h2>
<p>فریمیگا یک VPN کامل است؛ رمزنگاری‌شده، پوشش‌دهنده تمامی ترافیک دستگاه و مبتنی بر VLESS/Xray برای حفظ پایداری در شبکه‌های محدودکننده. <a href="/fa/plans">پلن‌های فریمیگا را مقایسه کنید</a> و در عرض چند دقیقه متصل شوید.</p>
""",
    },
    {
        "slug": "v2ray-xray-vless-explained",
        "title_en": "V2Ray, Xray, and VLESS Explained: The Tech Behind Modern VPNs",
        "title_fa": "V2Ray، Xray و VLESS چیستند؟ فناوری پشت VPN‌های مدرن",
        "excerpt_en": "How V2Ray, Xray, VMess, and VLESS relate to each other, why they resist deep packet inspection, and how Freemiga uses this stack to stay online where basic VPNs get blocked.",
        "excerpt_fa": "توضیح رسمی و فنی ارتباط میان V2Ray، Xray، VMess و VLESS، دلیل مقاومت این فناوری‌ها در برابر بازرسی عمیق بسته‌ها (DPI) و نحوه استفاده فریمیگا از این زیرساخت برای حفظ اتصال در شبکه‌های محدودکننده.",
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
<p>کاربرانی که به بررسی VPNهای کارآمد در مناطق با سانسور شدید پرداخته‌اند، به‌احتمال زیاد با نام‌های V2Ray، Xray، VMess و VLESS مواجه شده‌اند؛ نام‌هایی که اغلب تقریباً به‌جای یکدیگر به کار می‌روند و همین موضوع درک دقیق کارکرد هرکدام را دشوار می‌سازد. در این مقاله، ارتباط این فناوری‌ها با یکدیگر و دلیل اهمیت این زیرساخت خاص برای برقراری اتصالی پایدار، به‌طور کامل تشریح می‌شود.</p>

<h2>V2Ray چیست؟</h2>
<p>V2Ray یک چارچوب شبکه‌ای متن‌باز است، نه یک پروتکل منفرد؛ بلکه بستری برای ساخت ابزارهای پروکسی و VPN منعطف و قابل‌پیکربندی محسوب می‌شود. این پروژه از دل پروژه قدیمی‌تر Shadowsocks و با هدف افزایش دشواری شناسایی و ارتقای قابلیت شخصی‌سازی توسعه یافت. V2Ray پروتکل اختصاصی خود، موسوم به VMess، را برای احراز هویت و رمزنگاری ترافیک میان کلاینت و سرور معرفی کرد.</p>

<h2>Xray: جانشین مدرن V2Ray</h2>
<p>Xray در ابتدا به‌صورت یک فورک (نسخه مشتق‌شده) از هسته V2Ray آغاز شد و از آن زمان تاکنون به گزینه‌ای با توسعه فعال‌تر و عملکرد بالاتر تبدیل شده است. این پروژه تا حد زیادی با پیکربندی و پروتکل‌های V2Ray سازگار است، اما عملکرد بهتر، گزینه‌های انتقال (transport) بیشتر و — از همه مهم‌تر — ابزارهای قوی‌تری برای پنهان‌سازی ترافیک VPN در قالب ترافیک عادی وب ارائه می‌دهد. اکثر پیاده‌سازی‌های مدرن VPN مبتنی بر VLESS، از جمله فریمیگا، دقیقاً به همین دلیل بر بستر Xray-core اجرا می‌شوند.</p>

<h2>VMess در برابر VLESS: تفاوت اصلی چیست؟</h2>
<p>VMess، پروتکل اصلی V2Ray، علاوه بر رمزنگاری لایه انتقال (مانند TLS)، ترافیک را به‌صورت مستقل نیز رمزنگاری می‌کند؛ فرآیندی که سربار پردازشی اضافی ایجاد می‌کند. VLESS این رمزنگاری تکراری را حذف می‌کند و به‌طور کامل به رمزنگاری لایه انتقال بیرونی (معمولاً TLS) تکیه می‌کند. نتیجه این رویکرد، سبک‌تر و سریع‌تر شدن پروتکل است، بدون کاهش سطح امنیت، مشروط بر آنکه — طبق روش استاندارد پیاده‌سازی — با TLS ترکیب شود. همین ویژگی دلیل اصلی جایگزینی گسترده VMess با VLESS در پیاده‌سازی‌های جدید است.</p>

<h2>چرا این پروتکل‌ها در برابر بازرسی عمیق بسته‌ها مقاوم‌اند؟</h2>
<p>بازرسی عمیق بسته‌ها (Deep Packet Inspection یا DPI) روشی است که برخی شبکه‌ها برای شناسایی و مسدودسازی ترافیک VPN به کار می‌برند؛ این روش با تحلیل الگوهای ترافیکی، اثر انگشت یک اتصال VPN را شناسایی می‌کند، نه صرفاً با مسدودسازی آدرس‌های آی‌پی. VLESS بر بستر Xray، به‌ویژه در ترکیب با TLS و روش‌های انتقال مانند WebSocket یا gRPC، ترافیک VPN را تقریباً غیرقابل‌تشخیص از مرور عادی وب رمزنگاری‌شده (همان ترافیک HTTPS که تمامی وب‌سایت‌ها از آن استفاده می‌کنند) می‌سازد. همین شباهت، عامل اصلی عبور موفق این فناوری از فایروال‌هایی است که ترافیک به‌وضوح «شبیه VPN» را مسدود می‌کنند؛ فایروال‌هایی که در برخی موارد حتی WireGuard و OpenVPN را نیز شناسایی و مسدود می‌کنند.</p>

<h2>فریمیگا چگونه از VLESS و Xray استفاده می‌کند؟</h2>
<p>سرورهای فریمیگا بر بستر Xray-core و با پروتکل VLESS فعالیت می‌کنند؛ انتخابی که مشخصاً به دلیل پایداری این فناوری در محیط‌های با فیلترینگ شدید شبکه صورت گرفته است. این تصمیم، انتخابی تبلیغاتی نیست، بلکه رویکردی کاملاً کاربردی است: یک VPN که از نظر فنی «امنیت بالاتری» روی کاغذ دارد، در صورتی که شبکه پیش از برقراری اتصال آن را مسدود کند، عملاً بی‌ارزش خواهد بود. فریمیگا در وهله نخست بر پایه حفظ قابلیت اتصال طراحی شده، همراه با رمزنگاری قوی، بدون هیچ‌گونه مصالحه‌ای میان این دو.</p>

<h2>پرسش‌های متداول درباره V2Ray، Xray و VLESS</h2>
<h3>آیا لازم است کاربر جزئیات فنی این فناوری‌ها را بداند؟</h3>
<p>خیر. فریمیگا تمامی پیکربندی‌های لازم را مدیریت می‌کند؛ کاربر تنها به یک لینک اشتراک و یک برنامه سازگار نیاز دارد تا از مزایای این زیرساخت بهره‌مند شود.</p>
<h3>تفاوت اصلی Xray با V2Ray در چیست؟</h3>
<p>Xray نسخه‌ای توسعه‌یافته‌تر و پرکارایی‌تر از V2Ray است که با حفظ سازگاری، عملکرد بهتر و ابزارهای پیشرفته‌تری برای پنهان‌سازی ترافیک ارائه می‌دهد.</p>
<h3>چرا VLESS از WireGuard در برابر سانسور مقاوم‌تر است؟</h3>
<p>VLESS بر بستر Xray برای شبیه‌سازی دقیق ترافیک عادی HTTPS طراحی شده، در حالی که WireGuard الگوی ترافیکی نسبتاً قابل‌شناسایی‌تری دارد؛ همین تفاوت باعث می‌شود VLESS در شبکه‌های با فیلترینگ پیشرفته عملکرد بهتری داشته باشد.</p>

<h2>اکنون امتحان کنید</h2>
<p>برای بهره‌مندی از این فناوری، نیازی به درک تمامی جزئیات فنی آن نیست؛ فریمیگا پیکربندی را به‌طور کامل مدیریت می‌کند. <a href="/fa/plans">پلن‌های VPN فریمیگا را مشاهده کنید</a> و در عرض چند دقیقه، راه‌اندازی را تکمیل کنید.</p>
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
