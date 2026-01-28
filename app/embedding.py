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
        # Use a lightweight, high-performance model
        # fastembed supports "BAAI/bge-small-en-v1.5" or "sentence-transformers/all-MiniLM-L6-v2"
        # Using "sentence-transformers/all-MiniLM-L6-v2" for compatibility with previous Qdrant vectors
        _model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
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
