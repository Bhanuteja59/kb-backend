from sqlmodel import Session
from typing import Optional
import json
from .models import AuditEvent

def audit(
    session: Session,
    actor: str,
    action: str,
    target: Optional[str] = None,
    details: Optional[dict] = None,
):
    ev = AuditEvent(
        actor_email=actor,
        action=action,
        target=target,
        details=json.dumps(details) if details else None,
    )
    session.add(ev)
    session.commit()
