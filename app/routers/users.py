from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import User, Role
from ..deps import get_current_user, require_roles
from ..schemas import UserCreate, UserUpdate
from ..security import hash_password
from ..utils import audit

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", dependencies=[Depends(require_roles(Role.ADMIN))])
def list_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return [
        {
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]

@router.post("", dependencies=[Depends(require_roles(Role.ADMIN))])
def create_user(
    body: UserCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
):
    if session.exec(select(User).where(User.email == body.email)).first():
        raise HTTPException(status_code=409, detail="Email already exists")

    u = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    session.add(u)
    session.commit()
    audit(session, actor=actor.email, action="user_create", target=body.email)
    return {"ok": True}

@router.patch("/{email}", dependencies=[Depends(require_roles(Role.ADMIN))])
def update_user(
    email: str,
    body: UserUpdate,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
):
    u = session.exec(select(User).where(User.email == email)).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    if body.full_name is not None:
        u.full_name = body.full_name
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password is not None:
        u.password_hash = hash_password(body.password)

    session.add(u)
    session.commit()
    audit(session, actor=actor.email, action="user_update", target=email)
    return {"ok": True}
