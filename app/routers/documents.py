from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlmodel import Session, select
from datetime import datetime
import uuid

from ..db import get_session
from ..models import User, Role, Document, Chunk, Organization
from ..deps import get_current_user, require_roles
from ..schemas import DocumentOut, DriveIngestRequest, DocumentDetail, ChunkOut
from ..utils import audit
from ..text_extractors import extract_text
from ..tokenizer_chunking import chunk_text_tokens
from ..embedding import embed_texts
from ..vectorstore import ensure_collection, upsert_points
from ..drive_client import download_drive_file

router = APIRouter(tags=["documents"])

@router.post("/ingest", response_model=DocumentOut)
async def ingest_file(
    file: UploadFile = File(...),
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
        .where(Document.is_deleted == False) # noqa
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
    
    # Validation: Max 10MB
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")
    
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
    
    try:
        # 4. Chunk text
        chunks = chunk_text_tokens(text)
        
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
                "filename": file.filename,
                "org_id": user.org_id,
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
        audit(session, actor=user.email, action="upload", target=doc.filename)
        
    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        session.add(doc)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return DocumentOut(
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
    )

@router.post("/ingest/drive", response_model=DocumentOut)
async def ingest_drive_file(
    body: DriveIngestRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        filename, content = await download_drive_file(body.file_id, body.access_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download from Drive: {e}")

    text, file_type = extract_text(filename, content)

    # 1. Check if document exists (Update vs Create)
    existing_doc = session.exec(
        select(Document)
        .where(Document.org_id == user.org_id)
        .where(Document.source_id == body.file_id)
        .where(Document.is_deleted == False) # noqa
    ).first()

    if existing_doc:
        # --- UPDATE FLOW ---
        doc_id = existing_doc.doc_id
        doc = existing_doc
        doc.filename = filename 
        doc.size_bytes = len(content)
        doc.status = "indexing"
        doc.uploaded_by = user.email # Update uploader? Optional
        doc.created_at = datetime.utcnow() # Update timestamp? Or add updated_at?
        
        # Cleanup old data
        # 1. Delete old chunks from SQL
        session.exec(
            select(Chunk).where(Chunk.doc_id == doc_id)
        ) # This just selects, need to delete
        # Proper delete:
        from sqlmodel import delete
        session.exec(delete(Chunk).where(Chunk.doc_id == doc_id))
        
        # 2. Delete old vectors from Qdrant
        from ..vectorstore import delete_vectors
        delete_vectors(doc_id)
        
        session.add(doc)
        session.commit()
        
    else:
        # --- CREATE FLOW ---
        
        # 0. Check Usage Limits (Only for new docs)
        from ..pricing import PRICING_PLANS, DEFAULT_PLAN
        from sqlalchemy import func

        current_count = session.exec(
            select(func.count()).select_from(Document)
            .where(Document.org_id == user.org_id)
            .where(Document.is_deleted == False) # noqa
        ).one()

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

        doc_id = str(uuid.uuid4())
        doc = Document(
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            source="drive",
            source_id=body.file_id, # Store Drive ID
            size_bytes=len(content),
            uploaded_by=user.email,
            status="indexing",
            org_id=user.org_id,
        )
        session.add(doc)
        session.commit()

    try:
        chunks = chunk_text_tokens(text)
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

        vectors = embed_texts(chunks)

        points = []
        for i, vec in enumerate(vectors):
            payload = {
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunks[i],
                "filename": filename,
                "org_id": user.org_id,
            }
            points.append((chunk_records[i].chunk_id, vec, payload))

        if points:
            ensure_collection(vector_size=len(vectors[0]))
            upsert_points(points)

        doc.status = "indexed"
        session.add(doc)
        session.commit()

        audit(session, actor=user.email, action="upload_drive", target=doc.filename)

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        session.add(doc)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return DocumentOut(
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
    )

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

    stmt = select(Document).where(Document.org_id == user.org_id).order_by(Document.created_at.desc())
    if not include_deleted:
        stmt = stmt.where(Document.is_deleted == False)  # noqa

    docs = session.exec(stmt).all()
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
        )
        for d in docs
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
