from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, func
from datetime import datetime, timezone
import uuid

from ..db import get_session
from ..config import settings
from ..security import create_access_token, decode_token
from ..google_auth import get_google_auth_url, get_google_user_info
from ..models import User, Organization
from ..deps import get_current_user
from ..schemas import LoginResponse, MeResponse, OnboardingRequest
from ..utils import audit

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/google/login")
def google_login():
    uri = settings.google_redirect_uri
    if not uri:
        raise HTTPException(status_code=500, detail="GOOGLE_REDIRECT_URI is not configured")
    return RedirectResponse(get_google_auth_url(uri))

@router.get("/google/callback")
async def google_callback(code: str, session: Session = Depends(get_session)):
    uri = settings.google_redirect_uri
    if not uri:
        raise HTTPException(status_code=500, detail="GOOGLE_REDIRECT_URI is not configured")

    try:
        user_info = await get_google_user_info(code, uri)
    except Exception as e:
        # invalid_grant = code already used or expired (e.g. user refreshed, or cold-start
        # timeout caused Vercel to retry the request). Send user back to login gracefully.
        error_str = str(e).lower()
        if "invalid_grant" in error_str or "bad request" in error_str:
            return RedirectResponse(f"{settings.frontend_url}/login?error=session_expired")
        return RedirectResponse(f"{settings.frontend_url}/login?error=auth_failed")

    email = user_info.get("email")
    name = user_info.get("name")
    if not email:
        raise HTTPException(status_code=400, detail="No email provided by Google")

    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        token = create_access_token(subject=email, expires_minutes=1440)
        encoded_name = (name or "").replace(" ", "+")
        return RedirectResponse(f"{settings.frontend_url}/onboarding?token={token}&name={encoded_name}")

    audit(session, actor=email, action="login_google")
    token = create_access_token(subject=user.email)
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?token={token}")

@router.post("/google/onboarding", response_model=LoginResponse)
def complete_google_onboarding(payload: OnboardingRequest, session: Session = Depends(get_session)):
    try:
        token_data = decode_token(payload.token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    email = token_data.sub
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=409, detail="User already exists")

    import random
    base_slug = payload.organization_name.lower().replace(" ", "-")
    random_suffix = random.randint(1000, 9999)
    slug = f"{base_slug}-{int(datetime.now(timezone.utc).timestamp())}-{random_suffix}"
    org_id = str(uuid.uuid4())

    org = Organization(org_id=org_id, name=payload.organization_name, slug=slug)
    session.add(org)
    session.commit()
    session.refresh(org)

    user = User(
        email=email,
        full_name=email.split("@")[0],
        is_active=True,
        org_id=org.org_id,
        auth_provider="google",
        password_hash="oauth_user_no_password",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    audit(session, actor=email, action="signup_google_complete", details={"org_id": org.org_id})

    final_token = create_access_token(subject=user.email)
    return LoginResponse(access_token=final_token)

@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    org = session.exec(select(Organization).where(Organization.org_id == user.org_id)).first()

    doc_count = 0
    total_storage_bytes = 0
    plan_name = "free"
    max_docs = 3
    max_file_size = 20 * 1024 * 1024

    if org:
        from ..pricing import PRICING_PLANS, DEFAULT_PLAN
        from ..models import Document

        doc_count = session.exec(
            select(func.count()).select_from(Document)
            .where(Document.org_id == user.org_id)
            .where(Document.is_deleted == False)  # noqa
        ).one()

        total_storage_bytes = session.exec(
            select(func.sum(Document.size_bytes)).select_from(Document)
            .where(Document.org_id == user.org_id)
            .where(Document.is_deleted == False)  # noqa
        ).one() or 0

        plan_name = org.plan
        if plan_name not in PRICING_PLANS:
            plan_name = DEFAULT_PLAN.value

        max_docs = PRICING_PLANS[plan_name]["max_docs"]
        max_file_size = PRICING_PLANS[plan_name].get("max_size_bytes", 20 * 1024 * 1024)

    return MeResponse(
        email=user.email,
        full_name=user.full_name,
        org_id=user.org_id,
        auth_provider=user.auth_provider,
        org_name=org.name if org else None,
        org_slug=org.slug if org else None,
        plan=plan_name,
        max_docs=max_docs,
        max_file_size_bytes=max_file_size,
        doc_count=doc_count,
        total_storage_bytes=int(total_storage_bytes)
    )
