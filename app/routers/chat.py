from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional

from ..db import get_session
from ..models import User, Organization, Chunk, Document
from ..deps import get_current_user_optional
from ..schemas import ChatRequest, ChatResponse
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
    # 1. Validation
    org_id = user.org_id if user else None
    if not org_id and body.org_id:
        # Simple lookup: check if slug or id matches
        org = session.exec(select(Organization).where((Organization.slug == body.org_id) | (Organization.org_id == body.org_id))).first()
        if org: org_id = org.org_id

    if not org_id:
        # Security: If the Org ID provided doesn't exist in our DB, reject the request immediately.
        # This prevents unauthorized usage with fake IDs.
        raise HTTPException(status_code=404, detail="Invalid Organization ID. Please check your configuration.")

    # 2. Search (Embed + Vector DB)
    qv = embed_query(body.query)
    hits = vs_search(qv, top_k=body.top_k, filters={"org_id": org_id})
    
    score_map = {str(h.id): h.score for h in hits} if hits else {}
    ids = list(score_map.keys())

    # 3. Retrieve Content
    contexts = []
    if ids:
        chunks = session.exec(
            select(Chunk, Document)
            .where(Chunk.chunk_id.in_(ids))
            .where(Chunk.doc_id == Document.doc_id)
            .where(Document.org_id == org_id)
        ).all()

        for c, d in chunks:
            contexts.append({
                "text": c.text,
                "filename": d.filename,
                "score": score_map.get(c.chunk_id, 0.0),
            })

    # 4. Generate Answer
    answer = await generate_answer(body.query, contexts)

    # 5. Return (No citations, just answer)
    return ChatResponse(
        query=body.query,
        answer=answer,
        citations=[] 
    )
