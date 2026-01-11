from fastembed import TextEmbedding
from .config import settings
import numpy as np

_model = None

def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        # caching model
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5") 
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    # fastembed returns a generator of numpy arrays
    embeddings = list(model.embed(texts))
    # Convert numpy arrays to lists
    return [e.tolist() for e in embeddings]

def embed_query(q: str) -> list[float]:
    return embed_texts([q])[0]
