import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from .config import settings

# Helper to check if email is configured
def is_email_configured():
    return bool(settings.mail_username and settings.mail_password)


if is_email_configured():
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_FROM=settings.mail_from,
        MAIL_PORT=settings.mail_port,
        MAIL_SERVER=settings.mail_server,
        MAIL_FROM_NAME=settings.mail_from_name,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True
    )
    fast_mail = FastMail(conf)
else:
    fast_mail = None
    missing = []
    if not settings.mail_username: missing.append("MAIL_USERNAME")
    if not settings.mail_password: missing.append("MAIL_PASSWORD")
    print(f"WARNING: Email not configured. Missing: {', '.join(missing)}")


async def send_email(recipients: list[EmailStr], subject: str, html_body: str):
    """
    Generic function to send emails, acting like a Nodemailer transporter.
    """
    if not fast_mail:
        print(f"MOCK EMAIL: To: {recipients}, Subject: {subject}")
        return

    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=html_body,
        subtype=MessageType.html
    )

    await fast_mail.send_message(message)


async def send_verification_email(email: EmailStr, code: str):
    html = f"""
    <html>
        <body>
            <h1>Verify your email</h1>
            <p>Your verification code is: <strong>{code}</strong></p>
            <p>This code expires in 10 minutes.</p>
        </body>
    </html>
    """
    await send_email([email], "Your Verification Code", html)


async def send_welcome_email(email: EmailStr, name: str):
    html = f"""
    <html>
        <body>
            <h1>Welcome, {name}!</h1>
            <p>Thanks for signing up for KB RAG Platform.</p>
            <p>We are excited to have you on board.</p>
        </body>
    </html>
    """
    await send_email([email], "Welcome to KB RAG Platform", html)


async def send_password_reset_email(email: EmailStr, token: str):
    # Retrieve frontend URL from settings to form the link
    # We need to import settings here, or use the one already imported if available
    # It seems settings is imported at the top of mailer.py
    
    reset_link = f"{settings.frontend_url}/reset-password?token={token}"
    
    html = f"""
    <html>
        <body>
            <h1>Reset Your Password</h1>
            <p>You have requested to reset your password.</p>
            <p>Click the link below to set a new password:</p>
            <p><a href="{reset_link}">Reset Password</a></p>
            <p>This link expires in 30 minutes.</p>
            <p>If you did not request this, please ignore this email.</p>
        </body>
    </html>
    """
    await send_email([email], "Reset Your Password", html)
