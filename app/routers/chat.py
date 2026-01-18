from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional

from ..db import get_session
from ..models import User, Organization, Chunk, Document, ChatLog
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
    import time
    t0 = time.time()
    qv = embed_query(body.query)
    t1 = time.time()
    hits = vs_search(qv, top_k=body.top_k, filters={"org_id": org_id})
    t2 = time.time()
    
    if not hits:
        ids = [] 
    else:
        # ... existing logic ...
        pass
    
    ids = [str(h.id) for h in hits] if hits else []

    # 3. Retrieve Content (Simple Query)
    # We just fetch the text content. simpler than mapping objects.
    contexts = []
    if ids:
        chunks = session.exec(
            select(Chunk, Document)
            .where(Chunk.chunk_id.in_(ids))
            .where(Chunk.doc_id == Document.doc_id)
            .where(Document.org_id == org_id)
        ).all()
        
        # Format for LLM
        for c, d in chunks:
            contexts.append({
                "text": c.text,
                "filename": d.filename,
                "score": 0.0 # Placeholder
            })
    else:
        pass # No hits
    t3 = time.time()

    # 4. Generate Answer
    print(f"PERF: Embed={int((t1-t0)*1000)}ms, Qdrant={int((t2-t1)*1000)}ms, Postgres={int((t3-t2)*1000)}ms")
    import time
    start_time = time.time()
    answer = await generate_answer(body.query, contexts)
    duration_ms = int((time.time() - start_time) * 1000)

    # 5. Log Chat
    try:
        chat_log = ChatLog(
            org_id=org_id,
            user_id=user.id if user else None,
            query=body.query,
            answer=answer,
            response_time_ms=duration_ms
        )
        session.add(chat_log)
        session.commit()
    except Exception as e:
        print(f"ERROR: Failed to save chat log: {e}")

    # 6. Return (No citations, just answer)
    return ChatResponse(
        query=body.query,
        answer=answer,
        citations=[] 
    )
