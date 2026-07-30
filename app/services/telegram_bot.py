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

from app.auth import hash_password
from app.config import settings
from app.models import Customer, Order, OrderStatus, PaymentMethod, Plan, SupportTicket, TicketMessage
from app.services import order_service, polygon_gateway, stripe_gateway, telegram, tron_gateway, verification

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _crypto_configured() -> bool:
    return tron_gateway.is_configured() or polygon_gateway.is_configured()

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
        "choose_payment": "How would you like to pay for {plan_name} (${price})?",
        "pay_card": "💳 Pay with card",
        "pay_crypto": "🪙 Pay with crypto",
        "no_payment_methods": "No payment method is available on this deployment yet — please contact support.",
        "checkout_ready": "Please tap below to complete your ${price} payment for {plan_name}. "
        "This page updates automatically, and we'll let you know here as soon as it's confirmed.",
        "pay_now": "Pay now →",
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
        "choose_payment": "پلن {plan_name} (${price}) رو چطور مایلید پرداخت کنید؟",
        "pay_card": "💳 پرداخت با کارت",
        "pay_crypto": "🪙 پرداخت با کریپتو",
        "no_payment_methods": "با عرض پوزش، در حال حاضر روش پرداختی روی این سرویس فعال نشده — لطفاً با پشتیبانی تماس بگیرید.",
        "checkout_ready": "برای تکمیل پرداخت ${price} پلن {plan_name}، لطفاً روی دکمه‌ی زیر بزنید. "
        "این صفحه به‌صورت خودکار به‌روزرسانی میشه و به‌محض تأیید پرداخت، همینجا بهتون اطلاع می‌دیم.",
        "pay_now": "پرداخت →",
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


async def _show_payment_choice(chat_id: str, lang: str, plan: Plan, customer: Customer | None = None) -> None:
    if customer and not customer.email_verified:
        await telegram.send_message(
            chat_id,
            _t(lang, "verify_email_first", email=customer.email or ""),
            reply_markup=_verify_email_kb(lang),
        )
        return
    if not stripe_gateway.is_configured() and not _crypto_configured():
        await telegram.send_message(chat_id, _t(lang, "no_payment_methods"))
        return
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
        amount_due=plan.price_usdt,
        status=OrderStatus.pending,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ORDER_EXPIRY_MINUTES),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    checkout_url = await order_service.create_checkout(db, order, plan)
    # Crypto has no external checkout page anymore (self-hosted USDT wallet,
    # see app/services/tron_gateway.py) — send them to our own pay page,
    # which shows the wallet address and takes their transaction hash.
    pay_url = checkout_url or f"{settings.SITE_BASE_URL}/pay/{order.id}"

    await telegram.send_message(
        chat_id,
        _t(lang, "checkout_ready", price=plan.price_usdt, plan_name=plan.name),
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
        target_id = parts[1].strip()
        target = db.query(Customer).filter(Customer.id == target_id).first()
        if target:
            target.telegram_chat_id = chat_id
            db.commit()
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
    db.commit()
    db.refresh(customer)

    await telegram.send_message(chat_id, _t(lang, "account_created", username=username))
    await verification.send_verification_email(db, customer)
    await telegram.send_message(chat_id, _t(lang, "verification_sent", email=customer.email))

    session["state"] = None
    plan_id = session.get("plan_id")
    if plan_id:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if plan:
            await _show_payment_choice(chat_id, lang, plan, customer)
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
                await _show_payment_choice(chat_id, lang, plan, customer)
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
            await _show_payment_choice(chat_id, lang, plan, customer)
        return


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
        elif "message" in update:
            message = update["message"]
            chat_id = str(message.get("chat", {}).get("id", ""))
            text = message.get("text", "")
            if chat_id:
                await _handle_text_message(db, chat_id, text)
    except Exception:
        logger.exception("Failed to handle Telegram update")
