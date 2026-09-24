"""
The interactive Telegram bot experience — language selection, browsing
plans, creating an account entirely in-chat (username + email), and paying
(via a button that opens the same hosted Stripe/NowPayments checkout page
the website uses). A purchase can't be completed until the account's email
is verified — the same rule the website enforces in routers/orders.py.

Conversation state for flows that span multiple messages (choosing a
username, entering an email, writing a support message) is kept in an
in-memory dict keyed by chat_id. It's ephemeral by design — if the process
restarts mid-flow, the customer just sends /start again. Nothing valuable
is lost since no Order or Customer row is written until username+email are
both collected.
"""
import logging
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.auth import hash_password
from app.config import settings
from app.models import (
    Customer, Order, OrderStatus, PaymentMethod, Plan, SupportTicket, TelegramLinkToken, TicketMessage,
)
from app.services import order_service, polygon_gateway, stripe_gateway, telegram, tron_gateway, verification

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _crypto_configured() -> bool:
    return tron_gateway.is_configured() or polygon_gateway.is_configured()


def _stars_for_plan(plan: Plan) -> int:
    return max(1, round(plan.price_usdt * settings.TELEGRAM_STARS_PER_USD))

logger = logging.getLogger("telegram_bot")

# chat_id -> {"lang": "en"|"fa", "state": "...", "plan_id": "...", ...}
_sessions: dict[str, dict] = {}

TEXT = {
    "en": {
        "choose_language": "Please choose your language:",
        "welcome_back": "How can I help you today?",
        "main_menu_title": "Main menu — how can I help you today?",
        "plans_title": "Please choose a plan:",
        "no_plans": "No plans are available right now — please check back soon.",
        "ask_username": "Let's set up your account. Please choose a username (3-20 letters/numbers, no spaces):",
        "username_taken": "That username is already taken. Please try a different one:",
        "username_invalid": "Usernames may only contain 3-20 letters/numbers, with no spaces. Please try again:",
        "ask_email": "Almost done — please enter your email address. We'll send you a verification link, "
        "and you'll need to verify it before you can complete a purchase:",
        "email_invalid": "That doesn't look like a valid email address. Please try again:",
        "email_taken": "An account with this email already exists. Please enter a different email address:",
        "account_created": "✅ Your account has been created! Your username is \"{username}\". "
        "Whenever you'd like, you can set a password from the website (Account → \"Forgot password\").",
        "verification_sent": "📧 We've sent a verification link to {email}. Please check your inbox (and spam "
        "folder) and tap the link. We'll let you know right here as soon as it's verified — then you can "
        "complete your purchase.",
        "verify_email_first": "✉️ Please verify your email before completing a purchase. We sent a link to "
        "{email} — check your inbox (and spam folder), or tap below to resend it.",
        "resend_verification": "📧 Resend verification email",
        "verification_resent": "✅ A new verification email has been sent — please check your inbox.",
        "already_verified": "Your email is already verified.",
        "email_verified_notice": "✅ Your email has been verified! You can now complete your purchase.",
        "terms_prompt": "Before you can purchase, please read and agree to our Acceptable Use Policy "
        "(covers prohibited activity, device limits, and automated abuse enforcement): "
        "{site_base_url}/terms#acceptable-use\n\nTap below once you've read it to continue.",
        "terms_agree_btn": "✅ I agree, continue",
        "terms_not_accepted": "Please agree to the Acceptable Use Policy first — use /plans to try again.",
        "choose_payment": "How would you like to pay for {plan_name} (${price})?",
        "pay_card": "💳 Pay with card",
        "pay_crypto": "🪙 Pay with crypto",
        "pay_stars": "⭐ Pay with Telegram Stars",
        "pay_card_to_card": "🏦 Card-to-card transfer",
        "card_to_card_instructions": "For a card-to-card transfer, please message our support with the plan you want "
        "({plan_name} — ${price}). They'll send you the account details and confirm your order once the transfer "
        "is received.\n\nSupport: @{support_username}",
        "card_to_card_no_support": "Card-to-card transfer isn't available right now — please contact support from the site instead.",
        "checkout_ready": "Please tap below to complete your ${price} payment for {plan_name}. "
        "This page updates automatically, and we'll let you know here as soon as it's confirmed.",
        "pay_now": "Pay now →",
        "free_plan_claimed": "✅ Your free trial ({plan_name}) has been activated!",
        "free_plan_already_used": "Your free plan is still active — you can claim it again once it expires or its data runs out.",
        "banned": "⚠️ Your account has been suspended.\nReason: {reason}\n"
        "Please contact support if you believe this is a mistake.",
        "pending_order_exists": "You already have a payment in progress. You're welcome to cancel it below to "
        "choose a different plan or payment method, or complete it from the website (Billing tab).",
        "cancel_and_choose": "🔁 Cancel & choose again",
        "order_cancelled": "Your order has been cancelled.",
        "ask_support_message": "Please write your message below and our support team will get back to you here:",
        "support_sent": "✅ Thank you — your message has been sent to support. We'll reply here shortly.",
        "support_title": "You're welcome to reach us here:",
        "chat_telegram": "💬 Chat on Telegram",
        "email_us": "📧 Email us",
        "orders_title": "📦 Your orders:",
        "no_orders": "You don't have any orders yet.",
        "not_understood": "Sorry, I didn't quite understand that — please choose from the menu below:",
        "menu_plans": "🛒 Plans & Pricing",
        "menu_orders": "📦 My Orders",
        "menu_support": "💬 Contact Support",
        "menu_language": "🌍 Change language",
        "menu_website": "🌐 Website",
        "menu_guide": "📖 Setup Guide",
        "back": "← Back",
        "invalid_link": "That connection link appears to be invalid or expired. Please use the menu below instead:",
        "linked": "✅ Your Telegram account has been linked to your site account.",
        "relink_notice": "⚠️ Your account's Telegram connection was just moved to a different chat. "
        "If this wasn't you, please contact support and consider changing your password right away.",
    },
    "fa": {
        "choose_language": "لطفاً زبان مورد نظرتون رو انتخاب کنید:",
        "welcome_back": "چه کمکی از دستم برمیاد؟",
        "main_menu_title": "منوی اصلی — چه کمکی از دستم برمیاد؟",
        "plans_title": "لطفاً یکی از پلن‌ها رو انتخاب کنید:",
        "no_plans": "با عرض پوزش، فعلاً پلنی موجود نیست — لطفاً بعداً سر بزنید.",
        "ask_username": "بریم حسابتون رو بسازیم. لطفاً یه یوزرنیم انتخاب کنید (۳ تا ۲۰ حرف/عدد انگلیسی، بدون فاصله):",
        "username_taken": "این یوزرنیم قبلاً انتخاب شده. لطفاً یوزرنیم دیگه‌ای وارد کنید:",
        "username_invalid": "یوزرنیم فقط می‌تونه شامل ۳ تا ۲۰ حرف/عدد انگلیسی باشه، بدون فاصله. لطفاً دوباره امتحان کنید:",
        "ask_email": "یک قدم دیگه مونده — لطفاً ایمیل‌تون رو وارد کنید. یک لینک تأیید براتون می‌فرستیم و "
        "قبل از تکمیل خرید باید تأییدش کنید:",
        "email_invalid": "این یک آدرس ایمیل معتبر به نظر نمی‌رسه. لطفاً دوباره امتحان کنید:",
        "email_taken": "حسابی با این ایمیل قبلاً وجود داره. لطفاً یک ایمیل دیگه وارد کنید:",
        "account_created": "✅ حساب شما با موفقیت ساخته شد! یوزرنیم‌تون «{username}» هست. "
        "هر وقت مایل بودید، می‌تونید از سایت (Account → Forgot password) یه رمز عبور تنظیم کنید.",
        "verification_sent": "📧 یک لینک تأیید به {email} فرستادیم. لطفاً صندوق ایمیل‌تون (و پوشه اسپم) رو "
        "چک کنید و روی لینک بزنید. به‌محض تأیید، همین‌جا بهتون خبر می‌دیم — بعدش می‌تونید خریدتون رو تکمیل کنید.",
        "verify_email_first": "✉️ لطفاً قبل از تکمیل خرید، ایمیل‌تون رو تأیید کنید. یک لینک به {email} فرستادیم — "
        "صندوق ایمیل (و پوشه اسپم) رو چک کنید، یا پایین بزنید تا دوباره ارسال بشه.",
        "resend_verification": "📧 ارسال دوباره ایمیل تأیید",
        "verification_resent": "✅ یک ایمیل تأیید جدید فرستاده شد — لطفاً صندوقتون رو چک کنید.",
        "already_verified": "ایمیل شما قبلاً تأیید شده.",
        "email_verified_notice": "✅ ایمیل شما تأیید شد! حالا می‌تونید خریدتون رو تکمیل کنید.",
        "terms_prompt": "قبل از خرید، لطفاً قوانین استفاده صحیح رو بخونید و بپذیرید "
        "(شامل فعالیت‌های ممنوع، محدودیت دستگاه، و اجرای خودکار در برابر سوءاستفاده):\n"
        "{site_base_url}/terms#acceptable-use\n\nبعد از خوندنش، دکمه‌ی زیر رو بزنید تا ادامه بدیم.",
        "terms_agree_btn": "✅ می‌پذیرم، ادامه",
        "terms_not_accepted": "لطفاً اول قوانین استفاده صحیح رو بپذیرید — با /plans دوباره امتحان کنید.",
        "choose_payment": "پلن {plan_name} (${price}) رو چطور مایلید پرداخت کنید؟",
        "pay_card": "💳 پرداخت با کارت",
        "pay_crypto": "🪙 پرداخت با کریپتو",
        "pay_stars": "⭐ پرداخت با Telegram Stars",
        "pay_card_to_card": "🏦 کارت به کارت",
        "card_to_card_instructions": "برای پرداخت کارت به کارت، لطفاً به پشتیبانی ما پیام بدید و پلن مورد نظرتون رو "
        "بگید ({plan_name} — ${price}). شماره کارت رو براتون می‌فرستن و بعد از واریز، سفارشتون رو تأیید می‌کنن.\n\n"
        "پشتیبانی: @{support_username}",
        "card_to_card_no_support": "پرداخت کارت به کارت الان در دسترس نیست — لطفاً از طریق سایت با پشتیبانی تماس بگیرید.",
        "checkout_ready": "برای تکمیل پرداخت ${price} پلن {plan_name}، لطفاً روی دکمه‌ی زیر بزنید. "
        "این صفحه به‌صورت خودکار به‌روزرسانی میشه و به‌محض تأیید پرداخت، همینجا بهتون اطلاع می‌دیم.",
        "pay_now": "پرداخت →",
        "free_plan_claimed": "✅ پلن آزمایشی رایگان شما ({plan_name}) فعال شد!",
        "free_plan_already_used": "پلن رایگان شما هنوز فعال است — بعد از تمام شدن زمان یا حجم آن، می‌توانید دوباره دریافتش کنید.",
        "banned": "⚠️ حساب شما مسدود شده است.\nدلیل: {reason}\n"
        "اگر فکر می‌کنید این یک اشتباهه، لطفاً با پشتیبانی تماس بگیرید.",
        "pending_order_exists": "شما یک سفارش نیمه‌کاره دارید. می‌تونید پایین لغوش کنید تا پلن یا روش پرداخت "
        "دیگه‌ای انتخاب کنید، یا از سایت (تب Billing) تکمیلش کنید.",
        "cancel_and_choose": "🔁 لغو و انتخاب دوباره",
        "order_cancelled": "سفارش شما لغو شد.",
        "ask_support_message": "لطفاً پیام‌تون رو بنویسید، تیم پشتیبانی همینجا پاسخ می‌ده:",
        "support_sent": "✅ ممنون — پیام شما به پشتیبانی ارسال شد. به‌زودی همینجا پاسخ می‌گیرید.",
        "support_title": "می‌تونید از این راه‌ها با ما در ارتباط باشید:",
        "chat_telegram": "💬 چت در تلگرام",
        "email_us": "📧 ایمیل به ما",
        "orders_title": "📦 سفارش‌های شما:",
        "no_orders": "شما هنوز سفارشی ثبت نکرده‌اید.",
        "not_understood": "متأسفانه متوجه نشدم — لطفاً از منوی زیر انتخاب کنید:",
        "menu_plans": "🛒 پلن‌ها و قیمت‌ها",
        "menu_orders": "📦 سفارش‌های من",
        "menu_support": "💬 تماس با پشتیبانی",
        "menu_language": "🌍 تغییر زبان",
        "menu_website": "🌐 وبسایت",
        "menu_guide": "📖 راهنمای اتصال",
        "back": "← بازگشت",
        "invalid_link": "این لینک اتصال نامعتبر یا منقضی شده است. لطفاً از منوی زیر استفاده کنید:",
        "linked": "✅ حساب تلگرام شما به حساب سایت‌تون متصل شد.",
        "relink_notice": "⚠️ اتصال تلگرام حساب شما همین الان به یک چت دیگه منتقل شد. "
        "اگه این کار شما نبوده، لطفاً با پشتیبانی تماس بگیرید و رمز عبورتون رو هم عوض کنید.",
    },
}


def _t(lang: str, key: str, **kwargs) -> str:
    s = TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"][key])
    return s.format(**kwargs) if kwargs else s


def _lang_for(chat_id: str, customer: Customer | None) -> str:
    if customer and customer.language:
        return customer.language
    return _sessions.get(chat_id, {}).get("lang", "en")


def _get_customer(db, chat_id: str) -> Customer | None:
    return db.query(Customer).filter(Customer.telegram_chat_id == chat_id).first()


# ---------- Keyboards ----------

def _kb(rows: list[list[dict]]) -> dict:
    return {"inline_keyboard": rows}


def _language_kb(lang: str | None = None) -> dict:
    rows = [[
        {"text": "🇬🇧 English", "callback_data": "lang:en"},
        {"text": "🇮🇷 فارسی", "callback_data": "lang:fa"},
    ]]
    if lang:
        rows.append([{"text": _t(lang, "back"), "callback_data": "menu:main"}])
    return _kb(rows)


def _main_menu_kb(lang: str) -> dict:
    return _kb([
        [{"text": _t(lang, "menu_plans"), "callback_data": "menu:plans"}],
        [{"text": _t(lang, "menu_orders"), "callback_data": "menu:orders"}],
        [{"text": _t(lang, "menu_support"), "callback_data": "menu:support"}],
        [{"text": _t(lang, "menu_language"), "callback_data": "menu:language"}],
        [
            {"text": _t(lang, "menu_website"), "url": settings.SITE_BASE_URL},
            {"text": _t(lang, "menu_guide"), "url": f"{settings.SITE_BASE_URL}/guide"},
        ],
    ])


def _plans_kb(lang: str, plans: list[Plan]) -> dict:
    rows = [[{"text": f"{p.name} — ${p.price_usdt}", "callback_data": f"plan:{p.id}"}] for p in plans]
    rows.append([{"text": _t(lang, "back"), "callback_data": "menu:main"}])
    return _kb(rows)


def _payment_kb(lang: str, plan_id: str) -> dict:
    rows = []
    if stripe_gateway.is_configured():
        rows.append([{"text": _t(lang, "pay_card"), "callback_data": f"pay:card:{plan_id}"}])
    if _crypto_configured():
        rows.append([{"text": _t(lang, "pay_crypto"), "callback_data": f"pay:crypto:{plan_id}"}])
    # Stars need no separate gateway config (unlike Stripe/crypto) — the
    # bot token alone is enough, and we're already inside the bot.
    rows.append([{"text": _t(lang, "pay_stars"), "callback_data": f"pay:stars:{plan_id}"}])
    # Card-to-card has no automated verification — it only makes sense to
    # offer if there's a support contact to actually message about it.
    if settings.TELEGRAM_SUPPORT_USERNAME:
        rows.append([{"text": _t(lang, "pay_card_to_card"), "callback_data": f"cardtocard:{plan_id}"}])
    rows.append([{"text": _t(lang, "back"), "callback_data": "menu:plans"}])
    return _kb(rows)


def _has_direct_support() -> bool:
    return bool(settings.TELEGRAM_SUPPORT_USERNAME or settings.SUPPORT_EMAIL)


def _support_kb(lang: str) -> dict:
    # Telegram inline buttons only accept http(s)/tg:// URLs — "mailto:" is
    # rejected outright (BUTTON_URL_INVALID), so email goes in the message
    # text instead, where Telegram auto-linkifies it.
    rows = []
    if settings.TELEGRAM_SUPPORT_USERNAME:
        rows.append([{
            "text": _t(lang, "chat_telegram"),
            "url": f"https://t.me/{settings.TELEGRAM_SUPPORT_USERNAME}",
        }])
    rows.append([{"text": _t(lang, "back"), "callback_data": "menu:main"}])
    return _kb(rows)


# ---------- Screens ----------

async def _show_main_menu(chat_id: str, lang: str, title_key: str = "main_menu_title") -> None:
    await telegram.send_message(chat_id, _t(lang, title_key), reply_markup=_main_menu_kb(lang))


async def _show_plans(db, chat_id: str, lang: str) -> None:
    plans = db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.price_usdt).all()
    if not plans:
        await telegram.send_message(chat_id, _t(lang, "no_plans"))
        return
    details = "\n".join(
        f"🔹 {p.name} — ${p.price_usdt} ({p.data_limit_gb} GB, {p.duration_days} days)" for p in plans
    )
    await telegram.send_message(
        chat_id, f"{_t(lang, 'plans_title')}\n\n{details}", reply_markup=_plans_kb(lang, plans)
    )


async def _show_support(chat_id: str, lang: str) -> None:
    text = _t(lang, "support_title")
    if settings.SUPPORT_EMAIL:
        text += f"\n{_t(lang, 'email_us')}: {settings.SUPPORT_EMAIL}"
    await telegram.send_message(chat_id, text, reply_markup=_support_kb(lang))


def _verify_email_kb(lang: str) -> dict:
    return _kb([[{"text": _t(lang, "resend_verification"), "callback_data": "resendverify"}]])


def _terms_kb(lang: str, plan_id: str) -> dict:
    return _kb([[{"text": _t(lang, "terms_agree_btn"), "callback_data": f"agreeterms:{plan_id}"}]])


async def _claim_free_plan(db, chat_id: str, lang: str, customer: Customer, plan: Plan) -> None:
    """Mirrors routers/orders.py's free-plan branch: can be claimed again
    only once the previous free plan has expired or run out of data,
    provisioned immediately instead of going through a checkout — no payment method involved at all, so this must never fall
    through to _show_payment_choice's payment-method flow (a $0 Stripe
    checkout or a crypto payment with nothing to actually verify)."""
    # _start_order's ban check never runs on this path (free plans skip
    # the payment-method step entirely), so it has to be repeated here.
    if customer.is_banned:
        await telegram.send_message(chat_id, _t(lang, "banned", reason=customer.ban_reason or "—"))
        return

    if await order_service.has_usable_free_plan(db, customer, plan):
        await telegram.send_message(chat_id, _t(lang, "free_plan_already_used"))
        return

    already_has_account = (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.status == OrderStatus.provisioned)
        .first()
        is not None
    )
    order = Order(
        customer_id=customer.id,
        plan_id=plan.id,
        is_renewal=already_has_account,
        payment_method=PaymentMethod.free,
        amount_due=0,
        status=OrderStatus.pending,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ORDER_EXPIRY_MINUTES),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    from app.routers.payments import _mark_paid_and_provision
    await _mark_paid_and_provision(order.id)
    db.refresh(order)

    # _mark_paid_and_provision already sent its own failure notice to this
    # same chat_id (background.py's _provision, on the Marzban-call-failed
    # path) if provisioning didn't actually succeed — sending a hardcoded
    # "activated" message unconditionally here would contradict it.
    if order.status == OrderStatus.provisioned:
        await telegram.send_message(chat_id, _t(lang, "free_plan_claimed", plan_name=plan.name))


async def _show_payment_choice(db, chat_id: str, lang: str, plan: Plan, customer: Customer | None = None) -> None:
    if customer and not customer.email_verified:
        await telegram.send_message(
            chat_id,
            _t(lang, "verify_email_first", email=customer.email or ""),
            reply_markup=_verify_email_kb(lang),
        )
        return
    if customer and not customer.terms_accepted_at:
        await telegram.send_message(
            chat_id,
            _t(lang, "terms_prompt", site_base_url=settings.SITE_BASE_URL),
            reply_markup=_terms_kb(lang, plan.id),
        )
        return
    if plan.price_usdt == 0:
        if customer:
            await _claim_free_plan(db, chat_id, lang, customer, plan)
        return
    # No "are any payment methods configured?" guard here: Stars needs no
    # separate gateway, so a payment option is always available once the
    # bot itself is (which it must be — we're already inside a bot chat).
    await telegram.send_message(
        chat_id,
        _t(lang, "choose_payment", plan_name=plan.name, price=plan.price_usdt),
        reply_markup=_payment_kb(lang, plan.id),
    )


async def _show_orders(db, chat_id: str, lang: str, customer: Customer) -> None:
    orders = (
        db.query(Order)
        .filter(Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )
    if not orders:
        await telegram.send_message(chat_id, _t(lang, "no_orders"))
        return
    status_emoji = {
        "pending": "🟡", "paid": "🟢", "provisioned": "✅",
        "expired": "🔴", "failed": "🔴", "cancelled": "⚪",
    }
    lines = [_t(lang, "orders_title")]
    for o in orders:
        plan = db.query(Plan).filter(Plan.id == o.plan_id).first()
        plan_name = plan.name if plan else "?"
        lines.append(f"{status_emoji.get(o.status.value, '•')} {plan_name} — ${o.amount_due} — {o.status.value}")
    await telegram.send_message(chat_id, "\n".join(lines))


async def _start_order(db, chat_id: str, lang: str, customer: Customer, plan_id: str, method: str) -> None:
    plan = db.query(Plan).filter(Plan.id == plan_id, Plan.is_active.is_(True)).first()
    if not plan:
        await telegram.send_message(chat_id, _t(lang, "no_plans"))
        return

    if customer.is_banned:
        await telegram.send_message(chat_id, _t(lang, "banned", reason=customer.ban_reason or "—"))
        return

    if not customer.email_verified:
        await telegram.send_message(
            chat_id,
            _t(lang, "verify_email_first", email=customer.email or ""),
            reply_markup=_verify_email_kb(lang),
        )
        return

    if not customer.terms_accepted_at:
        # Shouldn't normally happen (_show_payment_choice gates this first),
        # but guard here too rather than let an order slip through.
        await telegram.send_message(chat_id, _t(lang, "terms_not_accepted"))
        return

    order_service.expire_stale_pending(db, customer.id)
    pending = (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.status == OrderStatus.pending)
        .first()
    )
    if pending:
        await telegram.send_message(
            chat_id,
            _t(lang, "pending_order_exists"),
            reply_markup=_kb([[
                {"text": _t(lang, "cancel_and_choose"), "callback_data": f"cancelorder:{pending.id}:{plan_id}"},
            ]]),
        )
        return

    already_has_account = (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.status == OrderStatus.provisioned)
        .first()
        is not None
    )

    order = Order(
        customer_id=customer.id,
        plan_id=plan.id,
        is_renewal=already_has_account,
        payment_method=PaymentMethod(method),
        # Same unique-amount rule as the web checkout (routers/orders.py).
        amount_due=order_service.unique_crypto_amount(db, plan) if method == "crypto" else plan.price_usdt,
        status=OrderStatus.pending,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ORDER_EXPIRY_MINUTES),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    if method == "stars":
        # No hosted checkout page for this one — Telegram renders its own
        # native "Pay" button on the invoice message itself. The order id
        # as payload is how _handle_pre_checkout_query / _handle_successful_
        # payment later find their way back to this exact order.
        await telegram.send_invoice(
            chat_id,
            title=plan.name,
            description=f"{plan.data_limit_gb} GB · {plan.duration_days} days",
            payload=order.id,
            amount_stars=_stars_for_plan(plan),
        )
        return

    checkout_url = await order_service.create_checkout(db, order, plan)
    # Crypto has no external checkout page anymore (self-hosted USDT wallet,
    # see app/services/tron_gateway.py) — send them to our own pay page,
    # which shows the wallet address and takes their transaction hash.
    pay_url = checkout_url or f"{settings.SITE_BASE_URL}/pay/{order.id}"

    await telegram.send_message(
        chat_id,
        _t(lang, "checkout_ready", price=order.amount_due, plan_name=plan.name),
        reply_markup=_kb([[{"text": _t(lang, "pay_now"), "url": pay_url}]]),
    )


# ---------- Message (text) handling ----------

async def _handle_text_message(db, chat_id: str, text: str) -> None:
    customer = _get_customer(db, chat_id)
    lang = _lang_for(chat_id, customer)
    session = _sessions.setdefault(chat_id, {"lang": lang})

    if text.startswith("/start"):
        await _handle_start(db, chat_id, text, customer)
        return

    state = session.get("state")

    if state == "awaiting_username":
        await _handle_username_reply(db, chat_id, lang, text.strip())
        return

    if state == "awaiting_email":
        await _handle_email_reply(db, chat_id, lang, text.strip())
        return

    if state == "awaiting_support":
        await _handle_support_reply(db, chat_id, lang, customer, text.strip())
        return

    if customer:
        await _show_main_menu(chat_id, lang, "not_understood")
    else:
        await telegram.send_message(chat_id, _t(lang, "choose_language"), reply_markup=_language_kb())


async def _handle_start(db, chat_id: str, text: str, customer: Customer | None) -> None:
    parts = text.split(maxsplit=1)
    lang = _lang_for(chat_id, customer)

    if len(parts) >= 2:
        # Deep link from the website's "Connect Telegram bot" button — link an
        # EXISTING web account to this chat (doesn't create a new one).
        link = (
            db.query(TelegramLinkToken)
            .filter(
                TelegramLinkToken.token == parts[1].strip(),
                TelegramLinkToken.used.is_(False),
                TelegramLinkToken.expires_at > datetime.utcnow(),
            )
            .first()
        )
        target = db.query(Customer).filter(Customer.id == link.customer_id).first() if link else None
        if target and not target.is_deleted:
            link.used = True
            previous_chat_id = target.telegram_chat_id
            target.telegram_chat_id = chat_id
            try:
                db.commit()
            except IntegrityError:
                # chat_id is already linked to a DIFFERENT customer account
                # (telegram_chat_id is unique) — treat like an invalid link
                # rather than letting the exception bubble up silently.
                db.rollback()
                await telegram.send_message(chat_id, _t(lang, "invalid_link"))
                return
            if previous_chat_id and previous_chat_id != chat_id:
                # Tripwire: if this account's Telegram link is ever moved by
                # someone other than its owner (e.g. a leaked/guessed deep
                # link — see telegram.deep_link), the real owner still
                # holding the OLD chat finds out immediately, since that
                # chat is also where password-reset codes get sent.
                await telegram.send_message(previous_chat_id, _t(target.language or "en", "relink_notice"))
            await telegram.send_message(chat_id, _t(target.language or "en", "linked"))
            await _show_main_menu(chat_id, target.language or "en", "welcome_back")
            return
        # Invalid/expired id — fall through to the normal menu below.
        await telegram.send_message(chat_id, _t(lang, "invalid_link"))

    if customer:
        await _show_main_menu(chat_id, lang, "welcome_back")
    else:
        await telegram.send_message(chat_id, _t(lang, "choose_language"), reply_markup=_language_kb())


async def _handle_username_reply(db, chat_id: str, lang: str, username: str) -> None:
    session = _sessions[chat_id]
    normalized = username.strip().lower()

    if not normalized.isalnum() or not (3 <= len(normalized) <= 20):
        await telegram.send_message(chat_id, _t(lang, "username_invalid"))
        return

    if db.query(Customer).filter(Customer.username == normalized).first():
        await telegram.send_message(chat_id, _t(lang, "username_taken"))
        return

    session["username"] = normalized
    session["state"] = "awaiting_email"
    await telegram.send_message(chat_id, _t(lang, "ask_email"))


async def _handle_email_reply(db, chat_id: str, lang: str, email: str) -> None:
    session = _sessions[chat_id]
    normalized = email.strip().lower()

    if not _EMAIL_RE.match(normalized):
        await telegram.send_message(chat_id, _t(lang, "email_invalid"))
        return

    if db.query(Customer).filter(Customer.email == normalized).first():
        await telegram.send_message(chat_id, _t(lang, "email_taken"))
        return

    username = session.get("username")
    if not username or db.query(Customer).filter(Customer.username == username).first():
        # Username got taken by someone else meanwhile (or the session lost
        # it, e.g. process restart) — restart the signup from the top.
        session["state"] = "awaiting_username"
        await telegram.send_message(chat_id, _t(lang, "ask_username"))
        return

    customer = Customer(
        username=username,
        email=normalized,
        email_verified=False,
        password_hash=hash_password(secrets.token_urlsafe(16)),
        telegram_chat_id=chat_id,
        language=lang,
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent signup grabbed the same username/email/chat link a
        # moment ago (e.g. a double-tap) — restart from the username step
        # rather than leaving this chat stuck with no response.
        db.rollback()
        session["state"] = "awaiting_username"
        await telegram.send_message(chat_id, _t(lang, "username_taken"))
        return
    db.refresh(customer)

    await telegram.send_message(chat_id, _t(lang, "account_created", username=username))
    await verification.send_verification_email(db, customer)
    await telegram.send_message(chat_id, _t(lang, "verification_sent", email=customer.email))

    session["state"] = None
    plan_id = session.get("plan_id")
    if plan_id:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if plan:
            await _show_payment_choice(db, chat_id, lang, plan, customer)
            return
    await _show_main_menu(chat_id, lang, "welcome_back")


async def _handle_support_reply(db, chat_id: str, lang: str, customer: Customer | None, message: str) -> None:
    if not message:
        return
    if customer:
        ticket = SupportTicket(customer_id=customer.id, subject="Telegram support request")
        db.add(ticket)
        db.flush()
        db.add(TicketMessage(ticket_id=ticket.id, sender="customer", body=message))
        db.commit()
        who = customer.username
    else:
        ticket = SupportTicket(
            guest_username=f"tg_{chat_id}",
            guest_contact=chat_id,
            subject="Telegram support request",
        )
        db.add(ticket)
        db.flush()
        db.add(TicketMessage(ticket_id=ticket.id, sender="customer", body=message))
        db.commit()
        who = f"telegram guest {chat_id}"

    await telegram.notify_admin(f"📩 Telegram support request from {who}: {message}")
    _sessions[chat_id]["state"] = None
    await telegram.send_message(chat_id, _t(lang, "support_sent"))


# ---------- Callback query (button press) handling ----------

async def _handle_callback(db, callback_query: dict) -> None:
    data = callback_query.get("data", "")
    message = callback_query.get("message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    callback_id = callback_query.get("id", "")
    if not chat_id:
        return

    await telegram.answer_callback_query(callback_id)

    customer = _get_customer(db, chat_id)
    session = _sessions.setdefault(chat_id, {})
    lang = _lang_for(chat_id, customer)

    if data.startswith("lang:"):
        lang = data.split(":", 1)[1]
        session["lang"] = lang
        if customer:
            customer.language = lang
            db.commit()
        await _show_main_menu(chat_id, lang, "welcome_back")
        return

    if data == "menu:main":
        await _show_main_menu(chat_id, lang, "welcome_back")
        return

    if data == "menu:language":
        await telegram.send_message(chat_id, _t(lang, "choose_language"), reply_markup=_language_kb(lang))
        return

    if data == "menu:plans":
        await _show_plans(db, chat_id, lang)
        return

    if data == "menu:orders":
        if not customer:
            await telegram.send_message(chat_id, _t(lang, "no_orders"))
            return
        await _show_orders(db, chat_id, lang, customer)
        return

    if data == "menu:support":
        if _has_direct_support():
            await _show_support(chat_id, lang)
        else:
            # No direct contact configured on this deployment — fall back
            # to the in-bot ticket flow so the button never dead-ends.
            session["state"] = "awaiting_support"
            await telegram.send_message(chat_id, _t(lang, "ask_support_message"))
        return

    if data.startswith("plan:"):
        plan_id = data.split(":", 1)[1]
        if customer:
            plan = db.query(Plan).filter(Plan.id == plan_id).first()
            if plan:
                await _show_payment_choice(db, chat_id, lang, plan, customer)
        else:
            session["state"] = "awaiting_username"
            session["plan_id"] = plan_id
            await telegram.send_message(chat_id, _t(lang, "ask_username"))
        return

    if data == "resendverify":
        if customer and customer.email and not customer.email_verified:
            await verification.send_verification_email(db, customer)
            await telegram.send_message(chat_id, _t(lang, "verification_resent"))
        elif customer and customer.email_verified:
            await telegram.send_message(chat_id, _t(lang, "already_verified"))
        return

    if data.startswith("agreeterms:"):
        plan_id = data.split(":", 1)[1]
        if customer:
            if not customer.terms_accepted_at:
                customer.terms_accepted_at = datetime.utcnow()
                db.commit()
            plan = db.query(Plan).filter(Plan.id == plan_id).first()
            if plan:
                await _show_payment_choice(db, chat_id, lang, plan, customer)
        return

    if data.startswith("cardtocard:"):
        plan_id = data.split(":", 1)[1]
        if not settings.TELEGRAM_SUPPORT_USERNAME:
            await telegram.send_message(chat_id, _t(lang, "card_to_card_no_support"))
            return
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if plan:
            await telegram.send_message(
                chat_id,
                _t(
                    lang, "card_to_card_instructions",
                    plan_name=plan.name, price=plan.price_usdt,
                    support_username=settings.TELEGRAM_SUPPORT_USERNAME,
                ),
                reply_markup=_kb([[{
                    "text": _t(lang, "chat_telegram"),
                    "url": f"https://t.me/{settings.TELEGRAM_SUPPORT_USERNAME}",
                }]]),
            )
        return

    if data.startswith("pay:"):
        _, method, plan_id = data.split(":", 2)
        if not customer:
            # Shouldn't normally happen (payment menu only shown post-signup),
            # but guard anyway rather than crash.
            session["state"] = "awaiting_username"
            session["plan_id"] = plan_id
            await telegram.send_message(chat_id, _t(lang, "ask_username"))
            return
        await _start_order(db, chat_id, lang, customer, plan_id, method)
        return

    if data.startswith("cancelorder:"):
        _, order_id, plan_id = data.split(":", 2)
        if customer:
            order = (
                db.query(Order)
                .filter(Order.id == order_id, Order.customer_id == customer.id, Order.status == OrderStatus.pending)
                .first()
            )
            if order:
                order_service.cancel_pending_order(db, order)
                await telegram.send_message(chat_id, _t(lang, "order_cancelled"))
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if plan:
            await _show_payment_choice(db, chat_id, lang, plan, customer)
        return


# ---------- Telegram Stars payment handling ----------

async def _handle_pre_checkout_query(db, pre_checkout_query: dict) -> None:
    """Telegram requires an answer within 10 seconds of a customer tapping
    Pay on a Stars invoice, before it actually charges them — the only
    check that matters here is that the order this invoice's payload
    points at is still a real, pending order (not already paid, cancelled,
    or expired out from under it)."""
    query_id = pre_checkout_query.get("id", "")
    order_id = pre_checkout_query.get("invoice_payload", "")
    order = db.query(Order).filter(Order.id == order_id, Order.status == OrderStatus.pending).first()
    if not order:
        await telegram.answer_pre_checkout_query(
            query_id, ok=False, error_message="This order is no longer available — please choose a plan again."
        )
        return
    await telegram.answer_pre_checkout_query(query_id, ok=True)


async def _handle_successful_payment(db, message: dict) -> None:
    """Fires after Telegram has already charged the customer's Stars
    balance — the payment itself can't be declined from here, only
    recorded and provisioned. telegram_payment_charge_id is set in its own
    commit first, same reasoning as verify_payment's tx_hash in
    routers/orders.py: the column's unique constraint (see
    scripts/add_stars_payment_support.py) is what actually prevents a
    replayed update from crediting the same Stars payment twice, not the
    order-status check above it."""
    sp = message.get("successful_payment") or {}
    order_id = sp.get("invoice_payload", "")
    charge_id = sp.get("telegram_payment_charge_id", "")
    if not order_id or not charge_id:
        return

    # Telegram has already taken the Stars at this point, so the order is
    # credited even if it expired or was cancelled since the invoice was
    # sent — see payments._mark_paid_and_provision.
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.status.in_(order_service.PAYABLE_STATUSES))
        .first()
    )
    if not order:
        return

    order.telegram_charge_id = charge_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return

    from app.routers.payments import _mark_paid_and_provision
    await _mark_paid_and_provision(order.id, payment_received=True)


# ---------- Entry point ----------

async def notify_email_verified(customer: Customer) -> None:
    """Called from the web /api/auth/verify-email route once a customer's
    email is confirmed, so a bot signup that's mid-flow (paused waiting on
    verification) hears about it and can go complete their purchase."""
    if not customer.telegram_chat_id:
        return
    lang = customer.language or "en"
    await telegram.send_message(
        customer.telegram_chat_id,
        _t(lang, "email_verified_notice"),
        reply_markup=_kb([[{"text": _t(lang, "menu_plans"), "callback_data": "menu:plans"}]]),
    )


async def handle_update(update: dict, db) -> None:
    try:
        if "callback_query" in update:
            await _handle_callback(db, update["callback_query"])
        elif "pre_checkout_query" in update:
            await _handle_pre_checkout_query(db, update["pre_checkout_query"])
        elif "message" in update:
            message = update["message"]
            if "successful_payment" in message:
                await _handle_successful_payment(db, message)
                return
            chat_id = str(message.get("chat", {}).get("id", ""))
            text = message.get("text", "")
            if chat_id:
                await _handle_text_message(db, chat_id, text)
    except Exception:
        logger.exception("Failed to handle Telegram update")
