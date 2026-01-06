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
client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)

COLLECTION_NAME = settings.qdrant_collection


# ---------- Collection ----------
def ensure_collection(vector_size: int):
    collections = client.get_collections().collections
    if not any(c.name == COLLECTION_NAME for c in collections):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    # Ensure indices exist (required for filtering in recent Qdrant versions)
    # We use "keyword" for exact ID matching
    for field in ["org_id", "doc_id", "filename", "chunk_index"]:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema="keyword" if field != "chunk_index" else "integer",
            )
        except Exception:
            # Ignore if already exists or other minor issue to prevent crash
            pass


# ---------- Upsert ----------
def upsert_points(
    points: List[Tuple[str, List[float], dict]],
):
    """
    points: [(id, vector, payload), ...]
    """
    client.upsert(
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
        return client.search(
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
        client.delete(
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
        print(f"Error deleting vectors for doc_id {doc_id}: {e}")

