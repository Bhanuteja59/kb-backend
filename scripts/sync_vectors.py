import sys
import os

# Ensure app is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.db import engine
from app.models import Chunk, Document
from app.vectorstore import ensure_collection, upsert_points, client, COLLECTION_NAME, sync_all_vectors_from_sql
from app.embedding import embed_texts
import time

def sync_vectors():
    print("--- Starting Vector Synchronization (Script) ---")
    
    # Use the optimized, paginated sync function from vectorstore
    sync_all_vectors_from_sql(batch_size=50)
    
    print("--- Synchronization Complete (Script) ---")

if __name__ == "__main__":
    sync_vectors()

if __name__ == "__main__":
    sync_vectors()
