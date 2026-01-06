from sentence_transformers import SentenceTransformer
import numpy as np
from .config import settings

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True)
    if isinstance(vecs, np.ndarray):
        vecs = vecs.tolist()
    return vecs

def embed_query(q: str) -> list[float]:
    return embed_texts([q])[0]
