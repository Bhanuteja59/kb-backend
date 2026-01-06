from __future__ import annotations
from typing import List
from transformers import AutoTokenizer
from .config import settings

_tok = None

def get_tokenizer():
    global _tok
    if _tok is None:
        _tok = AutoTokenizer.from_pretrained(settings.tokenizer_model_name)
    return _tok

def chunk_text_tokens(text: str, chunk_tokens: int = 500, overlap_tokens: int = 80) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    tok = get_tokenizer()
    ids = tok.encode(text, add_special_tokens=False)
    if not ids:
        return []

    chunks = []
    start = 0
    n = len(ids)
    while start < n:
        end = min(n, start + chunk_tokens)
        piece_ids = ids[start:end]
        chunk = tok.decode(piece_ids, skip_special_tokens=True).strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap_tokens)
    return chunks
