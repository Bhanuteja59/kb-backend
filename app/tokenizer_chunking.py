"""
Adaptive text chunking optimized for file size and fast RAG retrieval.
Automatically adjusts chunk size and overlap based on document characteristics.
"""
from typing import List, Tuple

def calculate_optimal_chunking(file_size_bytes: int, total_words: int) -> Tuple[int, int]:
    """
    Calculate optimal chunk size and overlap based on file size and content.
    
    Strategy:
    - Tiny files (<10KB, <500 words): Large chunks, preserve all context
    - Small files (10-50KB, 500-2000 words): Medium-large chunks
    - Medium files (50-200KB, 2000-10000 words): Standard chunks
    - Large files (200KB-1MB, 10000-50000 words): Smaller chunks, precise retrieval
    - Huge files (>1MB, >50000 words): Very small chunks, maximum precision
    
    Returns: (chunk_size_in_words, overlap_in_words)
    """
    # File size brackets (in KB)
    size_kb = file_size_bytes / 1024
    
    if size_kb < 10 or total_words < 500:
        # Tiny: Keep most context together
        return 800, 150
    elif size_kb < 50 or total_words < 2000:
        # Small: Balance context and retrieval
        return 600, 120
    elif size_kb < 200 or total_words < 10000:
        # Medium: Standard chunking
        return 500, 100
    elif size_kb < 1024 or total_words < 50000:
        # Large: Favor precision
        return 350, 70
    else:
        # Huge: Maximum precision for needle-in-haystack queries
        return 250, 50


def chunk_text_tokens(text: str, chunk_tokens: int = 500, overlap_tokens: int = 80, 
                      file_size_bytes: int = 0) -> List[str]:
    """
    Intelligent chunking that splits text into optimal-sized chunks.
    
    Auto-adjusts based on file size AND content length for best RAG performance:
    - Preserves context in small documents
    - Enables precise retrieval in large documents
    - Optimizes overlap to prevent information loss at boundaries
    
    Args:
        text: The text to chunk
        chunk_tokens: Default chunk size (used for medium files)
        overlap_tokens: Default overlap (used for medium files)
        file_size_bytes: Original file size in bytes (for optimization)
    
    Returns:
        List of text chunks optimized for semantic search
    """
    text = (text or "").strip()
    if not text:
        return []

    words = text.split()
    total_words = len(words)
    
    if total_words == 0:
        return []
    
    # Auto-calculate optimal chunking based on file size
    if file_size_bytes > 0:
        chunk_size, overlap = calculate_optimal_chunking(file_size_bytes, total_words)
    else:
        # Fallback: word-count-based optimization
        if total_words < 500:
            chunk_size, overlap = 800, 150
        elif total_words < 2000:
            chunk_size, overlap = 600, 120
        elif total_words < 10000:
            chunk_size, overlap = chunk_tokens, overlap_tokens  # Use default
        elif total_words < 50000:
            chunk_size, overlap = 350, 70
        else:
            chunk_size, overlap = 250, 50
    
    chunks = []
    start = 0
    
    while start < total_words:
        end = min(total_words, start + chunk_size)
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words)
        
        if chunk.strip():  # Only add non-empty chunks
            chunks.append(chunk)
        
        if end == total_words:
            break
        
        # Move forward with overlap to prevent context loss
        start = end - overlap
        
        # Safety: prevent infinite loop
        if start <= 0 or start >= end:
            break
    
    return chunks
