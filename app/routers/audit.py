from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from typing import Optional

from ..db import get_session
from ..models import AuditEvent, User
from ..deps import get_current_user
from ..schemas import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("", response_model=list[AuditOut])
def list_audit(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    actor_email: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    stmt = (
        select(AuditEvent)
        .join(User, AuditEvent.actor_email == User.email)
        .where(User.org_id == user.org_id)
        .order_by(AuditEvent.created_at.desc())
    )
    if actor_email:
        stmt = stmt.where(AuditEvent.actor_email == actor_email)
    if action:
        stmt = stmt.where(AuditEvent.action == action)

    events = session.exec(stmt.limit(limit)).all()
    return [
        AuditOut(
            actor_email=e.actor_email,
            action=e.action,
            target=e.target,
            created_at=e.created_at.isoformat(),
            details=e.details,
        )
        for e in events
    ]
