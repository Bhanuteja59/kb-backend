"""
Lightweight embedding service using fastembed.
No huge PyTorch dependencies. Fast, CPU-friendly (ONNX).
"""
from fastembed import TextEmbedding
import numpy as np

_model = None

def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        import os
        # Vercel has a read-only filesystem except for /tmp
        cache_dir = "/tmp/fastembed_cache" if "VERCEL" in os.environ else None
        if cache_dir and not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except Exception:
                pass
        
        # Use a lightweight, high-performance model
        # Using "sentence-transformers/all-MiniLM-L6-v2" for compatibility
        _model = TextEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            cache_dir=cache_dir
        )
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    model = get_model()
    # model.embed returns a generator, convert to list
    embeddings = list(model.embed(texts))
    # Ensure they are lists of floats
    return [e.tolist() for e in embeddings]

def embed_query(q: str) -> list[float]:
    """Generate embedding for a single query."""
    return embed_texts([q])[0]

def get_embedding_dimension() -> int:
    """Return the dimension of embeddings for this model."""
    return 384  # all-MiniLM-L6-v2 is 384 dim
