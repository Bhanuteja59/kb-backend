from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional

from ..db import get_session
from ..models import User, Organization, Chunk, Document
from ..deps import get_current_user_optional
from ..schemas import ChatRequest, ChatResponse, Citation
from ..embedding import embed_query
from ..vectorstore import search as vs_search
from ..llm import generate_answer

router = APIRouter(prefix="/rag", tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def rag_chat(
    body: ChatRequest, 
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional)
):
    # Determine Org ID
    org_id = None
    if user:
        org_id = user.org_id
    elif body.org_id:   
        # Check by slug first (more user friendly for embed), then ID
        # For simplicity, we assume the frontend passes the org SLUG as org_id
        # or we check both.
        org_q = select(Organization).where((Organization.slug == body.org_id) | (Organization.org_id == body.org_id))
        org = session.exec(org_q).first()
        if org:
            org_id = org.org_id
        else:
             raise HTTPException(status_code=404, detail="Organization not found")
    
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Login or valid Org ID required")

    qv = embed_query(body.query)
    # Fetch more candidates to allow for post-filtering
    # We filter by org_id at the vector store level for efficiency and security
    search_filters = {"org_id": org_id}
    if body.doc_id:
        search_filters["doc_id"] = body.doc_id

    hits = vs_search(qv, top_k=body.top_k * 3, filters=search_filters)

    # Optimization: Batch fetch chunks to avoid N+1 DB queries
    if not hits:
        # Fallback early if no hits
        answer = await generate_answer(body.query, [])
        return ChatResponse(query=body.query, answer=answer, citations=[])

    chunk_ids = [str(h.id) for h in hits]
    
    # Fetch all chunks and related documents in one query
    rows = session.exec(
        select(Chunk, Document)
        .where(Chunk.chunk_id.in_(chunk_ids))
        .where(Chunk.doc_id == Document.doc_id)
        .where(Document.org_id == org_id)  # Security: Enforce Org ID at DB level too
        .where(Document.is_deleted == False)
    ).all()

    # Map chunks by ID for preserving rank order from vector search
    chunk_map = {row[0].chunk_id: row for row in rows}

    contexts = []
    citations = []

    for h in hits:
        chunk_id = str(h.id)
        if chunk_id not in chunk_map:
            continue
            
        c, d = chunk_map[chunk_id]
        
        # Deduplication: Optional, but good to avoid same doc flooding context? 
        # For now, we allow multiple chunks from same doc, as they might be different parts.

        excerpt = c.text.strip().replace("\n", " ")
        excerpt = (excerpt[:240] + "…") if len(excerpt) > 240 else excerpt

        citations.append(Citation(
            filename=d.filename,
            doc_id=d.doc_id,
            chunk_id=c.chunk_id,
            chunk_index=c.chunk_index,
            excerpt=excerpt,
        ))

        contexts.append({
            "filename": d.filename,
            "doc_id": d.doc_id,
            "chunk_id": c.chunk_id,
            "chunk_index": c.chunk_index,
            "text": c.text,
            "source": "document"
        })
        
        if len(contexts) >= body.top_k:
            break

    # --- Fallback Logic ---
    try:
        # We always call generate_answer. If no contexts, the LLM will fall back to general knowledge.
        answer = await generate_answer(body.query, contexts)
    except Exception as e:
        # Final safety net for chat
        print(f"Chat Error: {e}")
        answer = "I'm having trouble connecting to the AI service right now. Please try again in a moment."

    return ChatResponse(
        query=body.query,
        answer=answer,
        citations=citations[: min(len(citations), 8)],
    )
