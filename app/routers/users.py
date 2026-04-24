from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import User, Organization
from ..deps import get_current_user
from ..schemas import UserProfileUpdate, OrgUpdate
from ..utils import audit

router = APIRouter(prefix="/users", tags=["users"])

@router.patch("/me")
def update_me(
    body: UserProfileUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    user.full_name = body.full_name
    session.add(user)
    session.commit()
    audit(session, actor=user.email, action="profile_update", target="self")
    return {"ok": True}

@router.patch("/organizations/me")
def update_my_org(
    body: OrgUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    org = session.exec(select(Organization).where(Organization.org_id == user.org_id)).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.name = body.name
    session.add(org)
    session.commit()
    audit(session, actor=user.email, action="org_update", target=org.org_id)
    return {"ok": True}

