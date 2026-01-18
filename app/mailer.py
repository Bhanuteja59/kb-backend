import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from .config import settings

# Helper to check if email is configured
def is_email_configured():
    return bool(settings.mail_username and settings.mail_password and settings.mail_server)


if is_email_configured():
    # Auto-configure SSL vs STARTTLS based on port
    use_ssl = (settings.mail_port == 465)
    
    conf = ConnectionConfig(
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
        TIMEOUT=60 
    )
    fast_mail = FastMail(conf)
else:
    fast_mail = None
    missing = []
    if not settings.mail_username: missing.append("MAIL_USERNAME")
    if not settings.mail_password: missing.append("MAIL_PASSWORD")
    if not settings.mail_server: missing.append("MAIL_SERVER")
    print(f"WARNING: Email not configured. Missing: {', '.join(missing)}")


async def send_email(recipients: list[EmailStr], subject: str, html_body: str):
    """
    Generic function to send emails via SMTP.
    """
    if not fast_mail:
        print(f"MOCK EMAIL (SMTP Not Configured): To: {recipients}, Subject: {subject}")
        return

    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=html_body,
        subtype=MessageType.html
    )

    try:
        await fast_mail.send_message(message)
    except Exception as e:
        print(f"ERROR: Failed to send email to {recipients}: {e}")
        # Re-raise if you want it to fail explicitly, or suppress if background task
        # Usually for background tasks, we just want to log it.




