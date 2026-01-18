from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form, BackgroundTasks
from sqlmodel import Session, select
from datetime import datetime
import uuid

from ..db import get_session
from ..models import User, Role, Document, Chunk, Organization
from ..deps import get_current_user, require_roles
from ..schemas import DocumentOut, DocumentDetail, ChunkOut
from ..utils import audit
from ..text_extractors import extract_text
from ..tokenizer_chunking import chunk_text_tokens
from ..embedding import embed_texts
from ..vectorstore import ensure_collection, upsert_points

router = APIRouter(tags=["documents"])

@router.post("/ingest", response_model=DocumentOut)
async def ingest_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chunk_tokens: int = Form(500),
    overlap_tokens: int = Form(80),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    from ..pricing import PRICING_PLANS, DEFAULT_PLAN
    from sqlalchemy import func

    # 0. Check Usage Limits
    # Get current doc count
    current_count = session.exec(
        select(func.count()).select_from(Document)
        .where(Document.org_id == user.org_id)
    ).one()

    # Get Plan Limit
    org = session.exec(select(Organization).where(Organization.org_id == user.org_id)).first()
    plan_name = org.plan if org else DEFAULT_PLAN.value
    if plan_name not in PRICING_PLANS:
        plan_name = DEFAULT_PLAN.value
    
    max_docs = PRICING_PLANS[plan_name]["max_docs"]
    
    if current_count >= max_docs:
         raise HTTPException(
            status_code=403, 
            detail={
                "error_code": "LIMIT_EXCEEDED",
                "message": f"Upgrade your plan to upload more documents. Limit: {max_docs}",
                "current_usage": current_count,
                "max_limit": max_docs
            }
        )

    # 1. Read file
    content = await file.read()
    new_size = len(content)
    
    # Validation: Max Size from Settings (Per File Hard Limit)
    from ..config import settings
    max_bytes_file = settings.max_upload_size_mb * 1024 * 1024
    if new_size > max_bytes_file:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB.")

    # Validation: Organization Storage Limit (Cumulative)
    # Re-fetch plan details to get storage limit
    max_storage_mb = PRICING_PLANS[plan_name].get("max_storage_mb", 30) # Default to 30 if missing
    max_storage_bytes = max_storage_mb * 1024 * 1024
    
    current_storage_bytes = session.exec(
        select(func.sum(Document.size_bytes)).select_from(Document)
        .where(Document.org_id == user.org_id)
        .where(Document.is_deleted == False) # noqa
    ).one() or 0
    
    if (current_storage_bytes + new_size) > max_storage_bytes:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "STORAGE_LIMIT_EXCEEDED",
                "message": f"Storage limit exceeded. Free limit is {max_storage_mb} MB per org.",
                "current_usage_mb": round(current_storage_bytes / (1024 * 1024), 2),
                "limit_mb": max_storage_mb
            }
        )
    
    # 2. Extract text
    text, file_type = extract_text(file.filename, content)
    
    # 3. Create Document record
    doc_id = str(uuid.uuid4())
    doc = Document(
        doc_id=doc_id,
        filename=file.filename,
        file_type=file_type,
        source="upload",
        size_bytes=len(content),
        uploaded_by=user.email,
        status="indexing",
        org_id=user.org_id,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    
    # 4. Offload to Background Task
    background_tasks.add_task(
        process_ingestion_background,
        doc_id=doc_id,
        text=text,
        filename=file.filename,
        user_email=user.email,
        org_id=user.org_id,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens
    )

    return DocumentOut(
        doc_id=doc.doc_id,
        filename=doc.filename,
        file_type=doc.file_type,
        source=doc.source,
        size_bytes=doc.size_bytes,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at.isoformat(),
        status=doc.status,
        chunk_count=0, # Initially 0
        error_message=doc.error_message,
        is_deleted=doc.is_deleted,
        deleted_at=doc.deleted_at.isoformat() if doc.deleted_at else None,
        deleted_by=doc.deleted_by,
    )

def process_ingestion_background(
    doc_id: str,
    text: str,
    filename: str,
    user_email: str,
    org_id: str,
    chunk_tokens: int,
    overlap_tokens: int
):
    """
    Background worker to handle chunking, embedding, and vector storage.
    """
    from ..db import engine
    from ..models import Chunk
    
    # Create a NEW session for the background task
    # We cannot use the dependency injection session as it closes when the request finishes
    with Session(engine) as session:
        try:
            # Re-fetch document to ensure we have it attached to this session
            doc = session.exec(select(Document).where(Document.doc_id == doc_id)).first()
            if not doc:
                print(f"Background Error: Document {doc_id} not found")
                return

            # 4. Chunk text
            chunks = chunk_text_tokens(text, chunk_tokens=chunk_tokens, overlap_tokens=overlap_tokens)
            
            # 5. Create Chunk records
            chunk_records = []
            for i, chunk_text in enumerate(chunks):
                cid = str(uuid.uuid4())
                c = Chunk(
                    chunk_id=cid,
                    doc_id=doc_id,
                    chunk_index=i,
                    text=chunk_text,
                )
                chunk_records.append(c)
            session.add_all(chunk_records)
            session.commit()
            
            # 6. Embed texts
            vectors = embed_texts(chunks)
            
            # 7. Upsert to Qdrant
            points = []
            for i, vec in enumerate(vectors):
                payload = {
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "text": chunks[i],
                    "filename": filename,
                    "org_id": org_id,
                }
                points.append((chunk_records[i].chunk_id, vec, payload))
                
            if points:
                ensure_collection(vector_size=len(vectors[0]))
                upsert_points(points)
                
            # 8. Update Document status
            doc.status = "indexed"
            session.add(doc)
            session.commit()
            
            # 9. Audit
            audit(session, actor=user_email, action="upload", target=filename)
            
        except Exception as e:
            print(f"Background Ingestion Failed for {doc_id}: {e}")
            # Try to update status to error
            try:
                doc.status = "error"
                doc.error_message = str(e)
                session.add(doc)
                session.commit()
            except:
                pass



@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document_details(
    doc_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # 1. Fetch Document
    doc = session.exec(
        select(Document)
        .where(Document.doc_id == doc_id)
        .where(Document.org_id == user.org_id)
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. Fetch Chunks
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.doc_id == doc_id)
        .order_by(Chunk.chunk_index)
    ).all()

    return DocumentDetail(
        document=DocumentOut(
            doc_id=doc.doc_id,
            filename=doc.filename,
            file_type=doc.file_type,
            source=doc.source,
            size_bytes=doc.size_bytes,
            uploaded_by=doc.uploaded_by,
            created_at=doc.created_at.isoformat(),
            status=doc.status,
            error_message=doc.error_message,
            is_deleted=doc.is_deleted,
            deleted_at=doc.deleted_at.isoformat() if doc.deleted_at else None,
            deleted_by=doc.deleted_by,
        ),
        chunks=[
            ChunkOut(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                chunk_index=c.chunk_index,
                text=c.text
            ) for c in chunks
        ]
    )

@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    include_deleted: bool = Query(default=False),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if user.role == Role.USER:
        include_deleted = False

    from sqlalchemy import func
    # Optimized Loop-free extraction with Scalar Subquery
    # Instead of JOIN + GROUP BY (which explodes rows), use a correlated subquery
    chunk_count_subq = (
        select(func.count(Chunk.chunk_id))
        .where(Chunk.doc_id == Document.doc_id)
        .scalar_subquery()
    )

    stmt = (
        select(Document, chunk_count_subq.label("chunk_count"))
        .where(Document.org_id == user.org_id)
        .order_by(Document.created_at.desc())
    )
    
    results = session.exec(stmt).all()
    
    return [
        DocumentOut(
            doc_id=d.doc_id,
            filename=d.filename,
            file_type=d.file_type,
            source=d.source,
            size_bytes=d.size_bytes,
            uploaded_by=d.uploaded_by,
            created_at=d.created_at.isoformat(),
            status=d.status,
            error_message=d.error_message,
            is_deleted=d.is_deleted,
            deleted_at=d.deleted_at.isoformat() if d.deleted_at else None,
            deleted_by=d.deleted_by,
            chunk_count=count
        )
        for d, count in results
    ]

@router.delete("/documents/{doc_id}", dependencies=[Depends(require_roles(Role.ADMIN, Role.MANAGER))])
def delete_document(
    doc_id: str,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
):
    d = session.exec(
        select(Document)
        .where(Document.doc_id == doc_id)
        .where(Document.org_id == actor.org_id)
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")

    # HARD DELETE LOGIC
    try:
        # 1. Delete Chunks from SQL
        from sqlmodel import delete
        session.exec(delete(Chunk).where(Chunk.doc_id == doc_id))
        
        # 2. Delete Vectors from Qdrant
        from ..vectorstore import delete_vectors
        delete_vectors(doc_id)
        
        # 3. Delete Document from SQL
        session.delete(d)
        session.commit()
        
        audit(session, actor=actor.email, action="hard_delete", target=doc_id)
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e}")

    return {"ok": True}
