from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text
from typing import Optional
from datetime import datetime, timezone

def _utcnow():
    return datetime.now(timezone.utc)

class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: str = Field(index=True, unique=True)
    name: str
    slug: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=_utcnow)
    plan: str = Field(default="free", index=True)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: str
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    org_id: str = Field(index=True)
    auth_provider: str = Field(default="google", index=True)
    password_hash: Optional[str] = Field(default=None)

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str = Field(index=True, unique=True)
    filename: str
    file_type: str
    source: str
    source_id: Optional[str] = Field(default=None, index=True)
    size_bytes: int
    uploaded_by: str
    created_at: datetime = Field(default_factory=_utcnow)
    status: str = Field(default="indexed")
    error_message: Optional[str] = None
    is_deleted: bool = Field(default=False, index=True)
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    org_id: str = Field(index=True)

class Chunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chunk_id: str = Field(index=True, unique=True)
    doc_id: str = Field(index=True)
    chunk_index: int = Field(index=True)
    text: str
    created_at: datetime = Field(default_factory=_utcnow)

class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_email: str = Field(index=True)
    action: str = Field(index=True)
    target: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    details: Optional[str] = None
