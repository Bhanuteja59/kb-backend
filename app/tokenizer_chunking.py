from __future__ import annotations
from typing import List

def chunk_text_tokens(text: str, chunk_tokens: int = 500, overlap_tokens: int = 80) -> List[str]:
    """
    Lightweight chunker that splits by words instead of tokens.
    Approximation: 1 "token" ~= 1 word (simplification for speed).
    """
    text = (text or "").strip()
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    n = len(words)
    
    # If chunk_tokens is 500, we treat it as 400 words to be safe/conservative
    # or just use it 1:1. Let's use it 1:1 for simplicity.
    limit = chunk_tokens 
    overlap = overlap_tokens

    while start < n:
        end = min(n, start + limit)
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words)
        if chunk:
            chunks.append(chunk)
        
        if end == n:
            break
        
        start = max(0, end - overlap)
        
    return chunks
