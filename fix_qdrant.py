from qdrant_client import QdrantClient
from app.config import settings
import sys

# Connect to Qdrant
try:
    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    COLLECTION_NAME = settings.QDRANT_COLLECTION
    print(f"Connected to Qdrant at {settings.QDRANT_URL}")
except Exception as e:
    print(f"Failed to connect to Qdrant: {e}")
    sys.exit(1)

# Check and Fix Collection
try:
    print(f"Checking collection '{COLLECTION_NAME}'...")
    try:
        collection = client.get_collection(COLLECTION_NAME)
        current_dim = collection.config.params.vectors.size
        print(f"Current dimension: {current_dim}")
        
        target_dim = 384
        
        if current_dim != target_dim:
            print(f"⚠️ Dimension Mismatch! Found {current_dim}, Expected {target_dim}.")
            print("Deleting incompatible collection...")
            client.delete_collection(COLLECTION_NAME)
            print("✅ Collection deleted. Please restart the backend to recreate it with valid dimensions.")
        else:
            print("✅ Dimension is correct (768). No action needed.")
            
    except Exception as e:
        if "not found" in str(e).lower() or "404" in str(e):
             print(f"Collection '{COLLECTION_NAME}' does not exist. It will be created on startup.")
        else:
            print(f"Error checking collection: {e}")

except Exception as e:
    print(f"Unexpected error: {e}")
