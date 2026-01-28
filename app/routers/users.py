from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import User, Role, Organization
from ..deps import get_current_user, require_roles
from ..schemas import UserCreate, UserUpdate, UserProfileUpdate, OrgUpdate
from ..utils import audit

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", dependencies=[Depends(require_roles(Role.ADMIN))])
def list_users(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    # Security: Only list users in the same organization
    users = session.exec(select(User).where(User.org_id == user.org_id)).all()
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
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Only Admins can update Organization")
    
    org = session.exec(select(Organization).where(Organization.org_id == user.org_id)).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    org.name = body.name
    session.add(org)
    session.commit()
    audit(session, actor=user.email, action="org_update", target=org.org_id)
    return {"ok": True}

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
        is_active=True,
        org_id=actor.org_id, # Admins create users in THEIR org
        auth_provider="google"
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
        
    # Security: Ensure Admin can only edit users in their own Org
    if u.org_id != actor.org_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to user")

    if body.full_name is not None:
        u.full_name = body.full_name
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active

    session.add(u)
    session.commit()
    audit(session, actor=actor.email, action="user_update", target=email)
    return {"ok": True}

@router.delete("/{email}", dependencies=[Depends(require_roles(Role.ADMIN))])
def delete_user(
    email: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
):
    from ..models import Document, Chunk
    from sqlmodel import delete
    from ..vectorstore import delete_vectors

    u = session.exec(select(User).where(User.email == email)).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Security: Ensure Admin can only delete users in their own Org
    if u.org_id != actor.org_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to user")

    # CASCADE DELETE DOCUMENTS
    # 1. Find all user docs
    user_docs = session.exec(select(Document).where(Document.uploaded_by == email)).all()
    
    deleted_count = 0
    for doc in user_docs:
        try:
            # 2. Delete Chunks
            session.exec(delete(Chunk).where(Chunk.doc_id == doc.doc_id))
            
            # 3. Delete Vectors
            # delete_vectors(doc.doc_id) # Using direct call or background?
            # Safe to call directly if short, but we should wrap in try/except around vector store call to avoid transaction rollback if Qdrant down
            try:
                delete_vectors(doc.doc_id)
            except:
                pass
            
            # 4. Delete Document
            session.delete(doc)
            deleted_count += 1
        except Exception as e:
            pass

    # 5. Delete User
    session.delete(u)
    session.commit()
    
    audit(session, actor=actor.email, action="user_delete_cascade", target=email)
    
    return {"ok": True, "deleted_docs": deleted_count}
