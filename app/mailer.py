from typing import List
from pydantic import EmailStr
from .config import settings

try:
    from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
    _fastmail_available = True
except ImportError:
    _fastmail_available = False

fast_mail = None

def _is_configured() -> bool:
    return bool(settings.mail_username and settings.mail_password and settings.mail_server)

if _fastmail_available and _is_configured():
    use_ssl = settings.mail_port == 465
    _conf = ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_FROM=settings.mail_from,
        MAIL_PORT=settings.mail_port,
        MAIL_SERVER=settings.mail_server,
        MAIL_FROM_NAME=settings.mail_from_name,
        MAIL_STARTTLS=not use_ssl,
        MAIL_SSL_TLS=use_ssl,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=False,
        TIMEOUT=60,
    )
    fast_mail = FastMail(_conf)
elif not _fastmail_available:
    print("WARNING: fastapi-mail is not installed. Email sending is disabled.")
else:
    missing = [k for k, v in {
        "MAIL_USERNAME": settings.mail_username,
        "MAIL_PASSWORD": settings.mail_password,
        "MAIL_SERVER": settings.mail_server,
    }.items() if not v]
    print(f"WARNING: Email not configured. Missing: {', '.join(missing)}")


async def send_email(recipients: List[EmailStr], subject: str, html_body: str) -> None:
    if not fast_mail:
        print(f"MOCK EMAIL: To={recipients} Subject={subject!r}")
        return

    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=html_body,
        subtype=MessageType.html,
    )
    try:
        await fast_mail.send_message(message)
    except Exception as e:
        print(f"ERROR: Failed to send email to {recipients}: {e}")




