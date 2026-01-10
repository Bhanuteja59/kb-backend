from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, func
from datetime import datetime
import uuid

from ..db import get_session
from ..config import settings
from ..security import verify_password, hash_password, create_access_token, decode_token
from ..google_auth import get_google_auth_url, get_google_user_info
from ..models import User, Role, Organization, VerificationCode
from ..deps import get_current_user
from ..schemas import LoginRequest, LoginResponse, SignupRequest, MeResponse, OnboardingRequest, EmailRequest, OtpRequest, ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest
from ..utils import audit
from ..mailer import send_verification_email, send_welcome_email, send_password_reset_email
from fastapi import BackgroundTasks
import random
from datetime import timedelta


router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=user.email, role=user.role.value)
    audit(session, actor=user.email, action="login")
    return LoginResponse(access_token=token)

@router.post("/send-verification")
async def send_verification(payload: EmailRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.email == payload.email)).first():
        # Ideally we should not reveal if user exists, but for this specific flow "Signup", we want to block duplicates early.
        raise HTTPException(status_code=409, detail="Email already registered")

    # Generate 6-digit code
    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Upsert code
    verification = session.exec(select(VerificationCode).where(VerificationCode.email == payload.email)).first()
    if verification:
        verification.code = code
        verification.expires_at = expires_at
    else:
        verification = VerificationCode(email=payload.email, code=code, expires_at=expires_at)
        session.add(verification)
    
    session.commit()

    # Send email
    background_tasks.add_task(send_verification_email, payload.email, code)
    return {"message": "Verification code sent"}

@router.post("/verify-otp", response_model=LoginResponse)
def verify_otp(payload: OtpRequest, session: Session = Depends(get_session)):
    verification = session.exec(select(VerificationCode).where(VerificationCode.email == payload.email)).first()
    
    if not verification:
        raise HTTPException(status_code=400, detail="No verification code found")
    
    if verification.code != payload.code:
        raise HTTPException(status_code=400, detail="Invalid code")
        
    if verification.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Code expired")

    # Generate "verification token" - basically a temporary access token with a special scope/role
    # We can reuse the standard token structure but maybe use a special subject or role?
    # Or just use a short lived token with "email_verified" role/scope.
    # Let's use role="guest_verified" or similar, or just trust the client keeps it securely? 
    # Better: Signed token that says "this email is verified".
    token = create_access_token(subject=payload.email, role="email_verified", expires_minutes=60)
    
    # Clean up code
    session.delete(verification)
    session.commit()
    
    return LoginResponse(access_token=token)


@router.post("/signup", response_model=LoginResponse)
def signup(payload: SignupRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    # 0. Verify Token
    try:
        token_data = decode_token(payload.verification_token)
        if token_data.role != "email_verified" or token_data.sub != payload.email:
             raise HTTPException(status_code=403, detail="Invalid verification token")
    except Exception as e:
        print(f"DEBUG: Signup token verification failed: {e}")
        raise HTTPException(status_code=403, detail=f"Invalid or expired verification token. Details: {str(e)}")

    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    # 1. Create Organization
    base_slug = payload.organization_name.lower().replace(" ", "-")
    slug = f"{base_slug}-{int(datetime.utcnow().timestamp())}"
    org_id = str(uuid.uuid4())
    
    org = Organization(
        org_id=org_id,
        name=payload.organization_name,
        slug=slug,
    )
    session.add(org)
    session.commit()
    session.refresh(org)

    # 2. Create User
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
        org_id=org.org_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(subject=user.email, role=user.role.value)
    audit(session, actor=user.email, action="signup", details={"role": user.role.value, "org_id": org.org_id})
    
    # 3. Send Welcome Email
    background_tasks.add_task(send_welcome_email, user.email, user.full_name)
    
    return LoginResponse(access_token=token)

@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    org = session.exec(select(Organization).where(Organization.org_id == user.org_id)).first()
    
    # Calculate usage
    doc_count = 0
    plan_name = "free"
    max_docs = 3
    
    if org:
        from ..pricing import PRICING_PLANS, DEFAULT_PLAN
        from ..models import Document
        
        # Get count of non-deleted documents
        doc_count = session.exec(
            select(func.count()).select_from(Document)
            .where(Document.org_id == user.org_id)
            .where(Document.is_deleted == False) # noqa
        ).one()
        
        plan_name = org.plan
        if plan_name not in PRICING_PLANS:
            plan_name = DEFAULT_PLAN.value
            
        max_docs = PRICING_PLANS[plan_name]["max_docs"]

    return MeResponse(
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        org_id=user.org_id,
        org_name=org.name if org else None,
        org_slug=org.slug if org else None,
        plan=plan_name,
        max_docs=max_docs,
        doc_count=doc_count
    )

@router.get("/google/login")
def google_login():
    redirect_uri = settings.google_redirect_uri or f"{settings.cors_origin_list[0]}/auth/google/callback"
    if not settings.google_redirect_uri:
        pass

    uri = settings.google_redirect_uri
    if not uri:
         raise HTTPException(status_code=500, detail="GOOGLE_REDIRECT_URI is not configured.")

    auth_url = get_google_auth_url(uri)
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_callback(code: str, session: Session = Depends(get_session)):
    uri = settings.google_redirect_uri
    if not uri:
         raise HTTPException(status_code=500, detail="GOOGLE_REDIRECT_URI is not configured.")

    try:
        user_info = await get_google_user_info(code, uri)
    except Exception as e:
         raise HTTPException(status_code=400, detail=f"Google Auth failed: {str(e)}")

    email = user_info.get("email")
    name = user_info.get("name")
    
    if not email:
        raise HTTPException(status_code=400, detail="No email provided by Google")

    # Find or Create User
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        # User doesn't exist. Issue a temporary "onboarding" token.
        token = create_access_token(subject=email, role="onboarding", expires_minutes=1440)
        
        encoded_name = (name or "").replace(" ", "+")
        
        # Redirect to Onboarding Page
        frontend_onboarding = f"{settings.frontend_url}/onboarding?token={token}&name={encoded_name}"
        return RedirectResponse(frontend_onboarding)

    else:
        audit(session, actor=email, action="login_google")
        # Issue Standard Token
        token = create_access_token(subject=user.email, role=user.role.value)
        # Redirect to callback
        frontend_redirect = f"{settings.frontend_url}/auth/callback?token={token}"
        return RedirectResponse(frontend_redirect)

@router.post("/google/onboarding", response_model=LoginResponse)
def complete_google_onboarding(payload: OnboardingRequest, session: Session = Depends(get_session)):
    # 1. Verify Token
    print(f"DEBUG: Received Onboarding Token: {payload.token}")
    try:
        token_data = decode_token(payload.token)
    except Exception as e:
        print(f"DEBUG: Token decode failed in main: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    if token_data.role != "onboarding":
        raise HTTPException(status_code=403, detail="Invalid token scope")

    email = token_data.sub
    if session.exec(select(User).where(User.email == email)).first():
         raise HTTPException(status_code=409, detail="User already exists")

    # 2. Create Organization
    base_slug = payload.organization_name.lower().replace(" ", "-")
    slug = f"{base_slug}-{int(datetime.utcnow().timestamp())}"
    org_id = str(uuid.uuid4())
    
    org = Organization(
        org_id=org_id,
        name=payload.organization_name,
        slug=slug,
    )
    session.add(org)
    session.commit()
    session.refresh(org)

    # 3. Create User
    user = User(
        email=email,
        full_name=email.split("@")[0], 
        role=payload.role,
        password_hash=hash_password(str(uuid.uuid4())),
        is_active=True,
        org_id=org.org_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    audit(session, actor=email, action="signup_google_complete", details={"org_id": org.org_id})

    # 4. Issue Final Token
    final_token = create_access_token(subject=user.email, role=user.role.value)
    return LoginResponse(access_token=final_token)


# ---------- Password Reset & Change ----------

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not user.is_active:
        # For security, we do not reveal if the email exists.
        # But we should simulate a delay to prevent timing attacks? 
        # For now, just return success.
        return {"message": "If an account exists, a reset email has been sent."}

    # Generate a reset token (valid for 30 mins)
    token = create_access_token(subject=user.email, role="password_reset", expires_minutes=30)
    
    from ..mailer import send_password_reset_email
    background_tasks.add_task(send_password_reset_email, user.email, token)
    
    return {"message": "If an account exists, a reset email has been sent."}


@router.post("/reset-password", response_model=LoginResponse)
def reset_password(payload: ResetPasswordRequest, session: Session = Depends(get_session)):
    # Verify Token
    try:
        token_data = decode_token(payload.token)
        if token_data.role != "password_reset":
             raise HTTPException(status_code=403, detail="Invalid token scope")
    except Exception as e:
        raise HTTPException(status_code=403, detail="Invalid or expired reset token")

    email = token_data.sub
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update Password
    user.password_hash = hash_password(payload.new_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    
    audit(session, actor=user.email, action="password_reset")

    # Log them in automatically
    token = create_access_token(subject=user.email, role=user.role.value)
    return LoginResponse(access_token=token)


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    # Verify Old Password
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    # Update Password
    user.password_hash = hash_password(payload.new_password)
    session.add(user)
    session.commit()
    
@router.get("/test-email")
async def test_email(email: str):
    """
    Debug endpoint to test email sending synchronously.
    """
    from ..mailer import send_email
    try:
        # Try sending a simple email
        await send_email([email], "Test Email from KB RAG", "<h1>It Works!</h1><p>Your email configuration is correct.</p>")
        return {"message": "Email sent successfully!"}
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return {
            "status": "failed",
            "error": str(e),
            "trace": error_trace
        }
