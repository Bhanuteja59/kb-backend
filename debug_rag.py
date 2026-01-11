from qdrant_client import QdrantClient
from app.config import settings
from app.embedding import embed_query
import sys

# Connect
client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
COLLECTION_NAME = settings.QDRANT_COLLECTION

print(f"--- Debugging RAG Retrieval ({COLLECTION_NAME}) ---")

# 1. Check Count
try:
    count = client.count(COLLECTION_NAME)
    print(f"✅ Collection Count: {count.count} documents")
    if count.count == 0:
        print("⚠️ DATABASE IS EMPTY! Please upload documents via the Admin Portal.")
        sys.exit(0)
except Exception as e:
    print(f"❌ Error getting count: {e}")
    sys.exit(1)

# 2. Test Search
query = "Teja"
print(f"\n--- Searching for '{query}' ---")
try:
    vector = embed_query(query)
    # Search without filter first
    hits = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=3
    )
    
    print(f"Found {len(hits)} hits (Global search):")
    for h in hits:
        print(f" - Score: {h.score:.4f}, DocID: {h.payload.get('doc_id')}, Text: {h.payload.get('text')[:50]}...")

except Exception as e:
    print(f"❌ Error searching: {e}")
