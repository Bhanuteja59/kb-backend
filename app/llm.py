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
1. **Context Usage**: The "Context" below is from the user's knowledge base. Use it to answer the question.
2. **Strict Grounding**: If the Context is empty or does not contain the answer, you MUST say "I could not find the answer in the provided documents."
3. **Exceptions**: You may answer general greetings (Hi, Hello) or simple conversational fillers without context.
4. **No Fabrication**: Do NOT make up facts. Do NOT use outside knowledge to fill gaps unless it is common sense definitions.

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
