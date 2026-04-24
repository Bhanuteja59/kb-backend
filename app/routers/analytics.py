from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from ..db import get_session
from ..models import User, Document, Chunk, AuditEvent
from ..deps import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/analytics", tags=["analytics"])

class ActivityItem(BaseModel):
    title: str
    desc: str
    time: str
    icon: str
    color: str

class DashboardStats(BaseModel):
    docs_count: int
    chunks_count: int
    storage_size_bytes: int
    avg_response_ms: int
    recent_activity: List[ActivityItem]

def get_time_ago(dt: datetime) -> str:
    now = datetime.utcnow()
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60: return "Just now"
    if seconds < 3600: return f"{int(seconds // 60)} mins ago"
    if seconds < 86400: return f"{int(seconds // 3600)} hours ago"
    return f"{int(seconds // 86400)} days ago"

@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    org_id = user.org_id
    
    # 1. Active Documents
    # 1. Active Documents (Optimized)
    doc_stats = session.exec(
        select(
            func.count(Document.id),
            func.sum(Document.size_bytes)
        )
        .where(Document.org_id == org_id)
        .where(Document.is_deleted == False)
    ).first()
    
    docs_count = doc_stats[0] or 0
    storage_size_bytes = doc_stats[1] or 0
    
    # 2. Vector Chunks
    # This might be slow if huge, but okay for now. Better to track in Org metadata later.
    chunks_count = session.exec(
        select(func.count()).select_from(Chunk)
        .join(Document, Chunk.doc_id == Document.doc_id)
        .where(Document.org_id == org_id)
    ).one()

    # 3. Avg Response Time (ChatLog not implemented yet)
    avg_response_ms = 0

    # 4. Recent Activity (From AuditEvent + ChatLog + Document)
    # Merging streams is complex, let's just pick Audit Events for now + Maybe Chats
    activity_items = []
    
    # Get last 5 audit events
    audits = session.exec(
        select(AuditEvent)
        .where(AuditEvent.actor_email == user.email) # or Org wide? user specific for now
        .order_by(AuditEvent.created_at.desc())
        .limit(5)
    ).all()

    for audit in audits:
        icon = "bi-activity"
        color = "#6b7280"
        if "upload" in audit.action.lower():
            icon = "bi-upload"
            color = "#10b981"
        elif "delete" in audit.action.lower():
            icon = "bi-trash"
            color = "#ef4444"
        elif "login" in audit.action.lower():
            icon = "bi-shield-check"
            color = "#f59e0b"
            
        activity_items.append(ActivityItem(
            title=audit.action.replace('_', ' ').title(),
            desc=audit.target or audit.details or "Action performed",
            time=get_time_ago(audit.created_at),
            icon=icon,
            color=color
        ))
        
    return DashboardStats(
        docs_count=docs_count,
        chunks_count=chunks_count,
        storage_size_bytes=storage_size_bytes,
        avg_response_ms=avg_response_ms,
        recent_activity=activity_items
    )
