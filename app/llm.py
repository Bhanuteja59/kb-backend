from __future__ import annotations
from typing import List, Dict
from groq import Groq
from .config import settings


# ---------- Client ----------
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured")
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ---------- Feature flag ----------
def llm_enabled() -> bool:
    return bool(settings.GROQ_API_KEY)


# ---------- Public API ----------
async def generate_answer(question: str, contexts: List[Dict]) -> str:
    """
    Return an answer grounded in contexts.
    Context items include:
    {doc_id, filename, chunk_id, chunk_index, text}
    """

    if settings.GROQ_API_KEY:
        return _groq_answer(question, contexts)

        bullets.append(
            f"- {t[:350]}{'…' if len(t) > 350 else ''} "
            f"(source: {c['filename']} #chunk {c['chunk_index']})"
        )

    return "I found the following relevant excerpts:\n" + "\n".join(bullets)


# ---------- Prompt builder ----------
def _build_prompt(question: str, contexts: List[Dict]) -> str:
    blocks = []
    for i, c in enumerate(contexts[:5], 1): # Limit to 5 chunks
        blocks.append(f"Content: {c['text']}")

    sources = "\n\n".join(blocks)

    return f"""You are a Knowledge Base Assistant.

Question:
{question}

Instructions:
1. **Context Usage**: The "Context" below is from the user's knowledge base. Use it if relevant.
2. **Fallback**: If the Context matches the question, use it to answer.
3. **General Knowledge**: If the Context is NOT relevant or doesn't answer the question, **IGNORE the Context** and answer using your own general knowledge/training.
4. **Tone**: Be helpful and direct.
5. **Restriction**: Do NOT say "The context does not contain information about..." or "I cannot find this in the documents". Just answer the question directly.

Context:
{sources}
"""


# ---------- Groq implementation ----------
def _groq_answer(question: str, contexts: List[Dict]) -> str:
    client = _get_client()
    prompt = _build_prompt(question, contexts)

    # Try 70B model first (better reasoning)
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a helpful AI assistant. You have access to a Knowledge Base (Context). Use the Context if it helps answer the user's question. If the Context is irrelevant, ignore it and answer from your general knowledge."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq 70B Error: {e}. Returning error message.")
        return "I apologize, but I am currently unable to process your request due to high service load. Please try again later."
