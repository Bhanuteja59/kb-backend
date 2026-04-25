from typing import List, Tuple, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
)
from .config import settings

# ---------- Client ----------
_client = None

def get_client():
    global _client
    if _client is None:
        url = settings.QDRANT_URL
        if not url:
            # We allow it to be None during import but fail when used
            raise ValueError("QDRANT_URL is not set. Please configure it in your environment variables.")
        _client = QdrantClient(
            url=url,
            api_key=settings.QDRANT_API_KEY,
        )
    return _client

COLLECTION_NAME = settings.qdrant_collection


# ---------- Collection ----------
def ensure_collection(vector_size: int = 384):
    """
    Ensure Qdrant collection exists with correct vector dimensions.
    Default: 384 dimensions for all-MiniLM-L6-v2 model.
    """
    collections = get_client().get_collections().collections
    if not any(c.name == COLLECTION_NAME for c in collections):
        get_client().create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    # Create indices for fast filtering
    for field in ["org_id", "doc_id", "filename", "chunk_index"]:
        try:
            get_client().create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema="keyword" if field != "chunk_index" else "integer",
            )
        except Exception:
            # Index already exists
            pass


# ---------- Upsert ----------
def upsert_points(
    points: List[Tuple[str, List[float], dict]],
):
    """
    points: [(id, vector, payload), ...]
    """
    get_client().upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=pid,
                vector=vector,
                payload=payload,
            )
            for pid, vector, payload in points
        ],
    )


# ---------- Search ----------
from qdrant_client.http.exceptions import UnexpectedResponse

# ... (imports)

# ... (ensure_collection and upsert_points unchanged)

# ---------- Search ----------
def search(
    query_vector: List[float],
    top_k: int = 5,
    filters: Optional[dict] = None,
):
    qdrant_filter = None
    if filters:
        qdrant_filter = Filter(
            must=[
                {
                    "key": k,
                    "match": {"value": v},
                }
                for k, v in filters.items()
            ]
        )

    try:
        return get_client().search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
        )
    except UnexpectedResponse as e:
        if "Not found: Collection" in str(e) or e.status_code == 404:
            return []
        raise e

def delete_vectors(doc_id: str):
    """
    Delete all vectors for a given doc_id.
    """
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        get_client().delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id),
                    )
                ]
            ),
        )
    except Exception as e:
        # Silently fail - vectors may not exist
        pass


# ---------- Management ----------
def get_collection_count() -> int:
    """Get total number of vectors in the collection."""
    try:
        return get_client().count(COLLECTION_NAME).count
    except Exception:
        return 0

def sync_all_vectors_from_sql(batch_size: int = 50, log_func=print):
    """
    Synchronize all vectors from SQL chunks to Qdrant.
    """
    from .db import get_engine
    from sqlmodel import Session, select
    from sqlalchemy import func
    from .models import Chunk, Document
    from .embedding import embed_texts
    
    log_func("--- Starting Vector Synchronization ---")
    
    engine = get_engine()
    # Check if we need to sync
    with Session(engine) as session:
        # Check counts
        total_chunks = session.exec(select(func.count()).select_from(Chunk)).one()
        
        if total_chunks == 0:
            log_func("No chunks in SQL to sync.")
            return

        log_func("Verifying vector store consistency...")

        ensure_collection()
        
        # Paginate to avoid OOM
        offset = 0
        limit = batch_size
        count_synced = 0
        
        while offset < total_chunks:
            # log_func(f"Processing batch...") # Optional: minimize noise further
            # Fetch batch from SQL
            # Join with Document to get metadata in one query if possible, or just lazy load
            # Lazy loading in loop is N+1 but low memory. 
            # Eager loading (select(Chunk, Document)) is better for DB performance.
            # Let's keep it simple: Fetch Chunks, then metadata.
            
            chunks = session.exec(select(Chunk).offset(offset).limit(limit)).all()
            if not chunks:
                break
                
            _process_sync_batch(chunks, session)
            
            count_synced += len(chunks)
            offset += limit
            
    log_func("--- Vector Synchronization Check Complete. ---")

def _process_sync_batch(chunk_objs, session):
    from .models import Document
    from sqlmodel import select
    from .embedding import embed_texts
    
    texts = [c.text for c in chunk_objs]
    vectors = embed_texts(texts)
    points = []
    
    for i, chunk_obj in enumerate(chunk_objs):
        # We need doc metadata
        doc = session.exec(select(Document).where(Document.doc_id == chunk_obj.doc_id)).first()
        if doc:
            payload = {
                "doc_id": chunk_obj.doc_id,
                "chunk_index": chunk_obj.chunk_index,
                "text": chunk_obj.text,
                "filename": doc.filename,
                "org_id": doc.org_id,
            }
            points.append((chunk_obj.chunk_id, vectors[i], payload))
    
    if points:
        upsert_points(points)

