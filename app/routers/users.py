from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import User, Role, Organization
from ..deps import get_current_user, require_roles
from ..schemas import UserCreate, UserUpdate, UserProfileUpdate, OrgUpdate, InviteRequest
from ..security import hash_password
from ..utils import audit

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", dependencies=[Depends(require_roles(Role.ADMIN, Role.MANAGER))])
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

@router.delete("/me")
def delete_me(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    from ..models import Document, Chunk
    from sqlmodel import delete
    from ..vectorstore import delete_vectors

    # CASCADE DELETE DOCUMENTS
    # 1. Find all user docs
    user_docs = session.exec(select(Document).where(Document.uploaded_by == user.email)).all()
    
    deleted_count = 0
    for doc in user_docs:
        try:
            # 2. Delete Chunks
            session.exec(delete(Chunk).where(Chunk.doc_id == doc.doc_id))
            
            # 3. Delete Vectors
            delete_vectors(doc.doc_id)
            
            # 4. Delete Document
            session.delete(doc)
            deleted_count += 1
        except Exception as e:
            print(f"Error cascade deleting doc {doc.doc_id}: {e}")

    # 5. Delete User
    session.delete(user)
    session.commit()
    
    audit(session, actor=user.email, action="user_delete_self", target=user.email)
    
    return {"ok": True, "deleted_docs": deleted_count}

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

@router.post("/invite", dependencies=[Depends(require_roles(Role.ADMIN))])
async def invite_user(
    body: InviteRequest,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
):
    # from ..services.email import send_invite_email
    from sqlalchemy import func
    
    # 1. Check if user exists (Global Check)
    existing_user = session.exec(select(User).where(User.email == body.email)).first()
    if existing_user:
        if existing_user.org_id == actor.org_id:
            raise HTTPException(
                status_code=409, 
                detail="User already exists in your organization."
            )
        else:
            raise HTTPException(
                status_code=409, 
                detail="User is already in another organization."
            )

    # 2. Check Role Limits in THIS Organization
    current_role_count = session.exec(
        select(func.count())
        .select_from(User)
        .where(User.org_id == actor.org_id)
        .where(User.role == body.role)
    ).one()

    # Enforce Limits
    if body.role == Role.ADMIN and current_role_count >= 3:
        raise HTTPException(status_code=403, detail="Role Limit Reached: Maximum 3 Admins allowed per organization.")
    
    if body.role == Role.MANAGER and current_role_count >= 10:
        raise HTTPException(status_code=403, detail="Role Limit Reached: Maximum 10 Managers allowed per organization.")
        
    if body.role == Role.USER and current_role_count >= 20:
        raise HTTPException(status_code=403, detail="Role Limit Reached: Maximum 20 Users allowed per organization.")

    # 3. Create User (No Password yet, will use Google Auth)
    u = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        is_active=True,
        org_id=actor.org_id,
        password_hash="google_auth_placeholder" # Ensure field isn't null if DB requires it
    )
    session.add(u)
    session.commit()
    
    # 4. Email Sending Removed (User Request)
    # email_sent = await send_invite_email(body.email, body.role)
    email_sent = False
    print("INFO: Email invite skipped (SMTP disabled)")
    
    audit(session, actor=actor.email, action="user_invite", target=body.email)
    return {"ok": True, "email_sent": email_sent}

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
    if body.password is not None:
        u.password_hash = hash_password(body.password)

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
            delete_vectors(doc.doc_id)
            
            # 4. Delete Document
            session.delete(doc)
            deleted_count += 1
        except Exception as e:
            print(f"Error cascade deleting doc {doc.doc_id}: {e}")

    # 5. Delete User
    session.delete(u)
    session.commit()
    
    audit(session, actor=actor.email, action="user_delete_cascade", target=email)
    
    return {"ok": True, "deleted_docs": deleted_count}
