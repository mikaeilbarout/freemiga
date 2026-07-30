"""
Transactional email via Resend — signup verification and password reset codes.
"""
import httpx

from app.config import settings


def is_configured() -> bool:
    return bool(settings.RESEND_API_KEY)


async def send_email(to: str, subject: str, html: str) -> None:
    if not is_configured():
        return
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": settings.RESEND_FROM_EMAIL,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
        resp.raise_for_status()


async def send_verification_email(to: str, verify_url: str) -> None:
    await send_email(
        to,
        "Verify your email — Freemiga",
        f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Verify your email</h2>
          <p>Thanks for signing up for Freemiga. Confirm your email address to activate your account:</p>
          <p style="margin:24px 0">
            <a href="{verify_url}" style="background:#7c5cff;color:#fff;padding:12px 24px;
              border-radius:8px;text-decoration:none;font-weight:600">Verify email</a>
          </p>
          <p style="color:#888;font-size:13px">If the button doesn't work, copy this link:<br>{verify_url}</p>
          <p style="color:#888;font-size:13px">This link expires in 24 hours.</p>
        </div>
        """,
    )


async def send_password_reset_email(to: str, code: str) -> None:
    await send_email(
        to,
        "Your password reset code — Freemiga",
        f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Password reset code</h2>
          <p>Use this code to reset your Freemiga password:</p>
          <p style="margin:24px 0;font-size:32px;font-weight:700;letter-spacing:4px;
            background:#f4f4f6;padding:16px 24px;border-radius:8px;text-align:center">{code}</p>
          <p style="color:#888;font-size:13px">This code expires in 15 minutes. If you didn't request this, ignore this email.</p>
        </div>
        """,
    )
