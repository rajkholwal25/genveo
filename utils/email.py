"""Transactional email via the Resend API and signed reset tokens."""
import json
import os
import urllib.request

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

RESET_SALT = "genveo-password-reset"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_SALT)


def make_reset_token(email: str) -> str:
    return _serializer().dumps(email)


def verify_reset_token(token: str, max_age: int = 3600):
    """Return the email if the token is valid and unexpired, else None."""
    try:
        return _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email through Resend. Returns True on success."""
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        print("[email] RESEND_API_KEY not set — cannot send")
        return False

    sender = os.environ.get("MAIL_FROM", "Genveo <onboarding@resend.dev>")
    payload = json.dumps({"from": sender, "to": [to], "subject": subject, "html": html}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    # Cloudflare in front of the Resend API blocks the default urllib agent.
    req.add_header("User-Agent", "Genveo/1.0 (+https://genveo.app)")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status in (200, 201):
                return True
            print(f"[email] Resend HTTP {resp.status}")
    except Exception as exc:  # noqa: BLE001
        body = exc.read().decode()[:200] if hasattr(exc, "read") else str(exc)[:200]
        print(f"[email] send failed: {body}")
    return False


def password_reset_html(name: str, reset_url: str) -> str:
    return f"""\
<div style="font-family:Arial,Helvetica,sans-serif;background:#070b09;padding:40px 0;">
  <div style="max-width:480px;margin:0 auto;background:#0e1512;border:1px solid #1c2a24;
              border-radius:16px;padding:36px;color:#f1f6f3;">
    <h1 style="margin:0 0 6px;font-size:22px;">Reset your password</h1>
    <p style="color:#8ba099;margin:0 0 24px;font-size:14px;">
      Hi {name}, we received a request to reset your Genveo password.
    </p>
    <a href="{reset_url}"
       style="display:inline-block;background:linear-gradient(135deg,#10b981,#2dd4bf);
              color:#04130d;font-weight:700;text-decoration:none;padding:13px 26px;
              border-radius:11px;">Reset password</a>
    <p style="color:#8ba099;margin:24px 0 0;font-size:12.5px;line-height:1.6;">
      This link expires in 1 hour. If you didn't request this, you can safely ignore this email.<br>
      If the button doesn't work, paste this link into your browser:<br>
      <span style="color:#34d399;word-break:break-all;">{reset_url}</span>
    </p>
  </div>
</div>"""
