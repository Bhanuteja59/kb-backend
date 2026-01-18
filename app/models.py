from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"

class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: str = Field(index=True, unique=True)
    name: str
    slug: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    plan: str = Field(default="free", index=True)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    full_name: str
    role: Role = Field(default=Role.USER, index=True)
    password_hash: str
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    org_id: str = Field(index=True)

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str = Field(index=True, unique=True)
    filename: str
    file_type: str
    source: str
    source_id: Optional[str] = Field(default=None, index=True) # e.g. Google Drive File ID
    size_bytes: int
    uploaded_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="indexed")  # indexed|error
    error_message: Optional[str] = None

    # v2: soft delete
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
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_email: str = Field(index=True)
    action: str = Field(index=True)  # login|upload|delete|restore|user_create|user_update
    target: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[str] = None


class ChatLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: str = Field(index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    query: str
    answer: str
    response_time_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


