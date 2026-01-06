from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Organization
from typing import Optional

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/org/{org_identifier}")
def get_public_org_info(org_identifier: str, session: Session = Depends(get_session)):
    # Try looking up by slug first (common for public embeds)
    org = session.exec(select(Organization).where(Organization.slug == org_identifier)).first()
    
    # If not found, try by ID
    if not org:
        org = session.exec(select(Organization).where(Organization.org_id == org_identifier)).first()
        
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    return {
        "name": org.name,
        "welcome_message": f"Hi! Welcome to {org.name}. Ask me anything."
    }
