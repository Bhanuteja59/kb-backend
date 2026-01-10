import google.generativeai as genai
from .config import settings
import time

# Configure Gemini
genai.configure(api_key=settings.google_api_key)

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embeds a list of texts using Google Gemini Text Embedding model.
    """
    embeddings = []
    # Gemini has a limit on batch size and rate limits, so we process carefully or let the library handle it.
    # For simplicity and robustness with free tier, we loop or send in small batches.
    # The 'embed_content' method supports a 'content' argument which can be a list or string.
    
    # Using 'models/text-embedding-004' for best performance/size ratio.
    model = 'models/text-embedding-004'

    for text in texts:
        # Simple retry logic could be added here if needed
        try:
            result = genai.embed_content(
                model=model,
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(result['embedding'])
        except Exception as e:
            print(f"Error embedding text '{text[:20]}...': {e}")
            # Fallback or empty embedding? Better to raise or skip.
            # For now, appending a zero-vector if failure to avoid breaking the list alignment?
            # Or just raise.
            embeddings.append([0.0] * 768) 

    return embeddings

def embed_query(q: str) -> list[float]:
    """
    Embeds a single query string.
    """
    model = 'models/text-embedding-004'
    try:
        result = genai.embed_content(
            model=model,
            content=q,
            task_type="retrieval_query"
        )
        return result['embedding']
    except Exception as e:
        print(f"Error embedding query '{q}': {e}")
        return [0.0] * 768
