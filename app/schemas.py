from pydantic import BaseModel
from typing import Optional, List
from .models import Role

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MeResponse(BaseModel):
    email: str
    full_name: str
    role: Role
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    org_slug: Optional[str] = None
    auth_provider: str = "email"
    plan: str = "free"
    max_docs: int = 3
    max_file_size_bytes: int = 20 * 1024 * 1024
    doc_count: int = 0
    total_storage_bytes: int = 0

class UserCreate(BaseModel):
    email: str
    full_name: str
    role: Role

class OnboardingRequest(BaseModel):
    token: str
    organization_name: str
    role: Role

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None

class UserProfileUpdate(BaseModel):
    full_name: str

class OrgUpdate(BaseModel):
    name: str

class DocumentOut(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    source: str
    size_bytes: int
    uploaded_by: str
    created_at: str
    status: str
    error_message: Optional[str] = None
    chunk_count: int = 0
    is_deleted: bool = False
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None

class ChunkOut(BaseModel):
    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str

class DocumentDetail(BaseModel):
    document: DocumentOut
    chunks: List[ChunkOut]

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    doc_id: Optional[str] = None

class QueryHit(BaseModel):
    score: float
    chunk: ChunkOut
    document: DocumentOut

class QueryResponse(BaseModel):
    query: str
    hits: List[QueryHit]

class ChatRequest(BaseModel):
    query: str
    top_k: int = 5
    doc_id: Optional[str] = None
    org_id: Optional[str] = None

class Citation(BaseModel):
    filename: str
    doc_id: str
    chunk_id: str
    chunk_index: int
    excerpt: str

class ChatResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation]

class AuditOut(BaseModel):
    actor_email: str
    action: str
    target: Optional[str]
    created_at: str
    details: Optional[str]

class UploadResponse(BaseModel):
    status: str
