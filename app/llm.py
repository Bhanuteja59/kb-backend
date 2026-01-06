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

    # ---------- Safe fallback (extractive) ----------
    bullets = []
    for c in contexts[:3]:
        t = c["text"].strip().replace("\n", " ")
        bullets.append(
            f"- {t[:350]}{'…' if len(t) > 350 else ''} "
            f"(source: {c['filename']} #chunk {c['chunk_index']})"
        )

    return "I found the following relevant excerpts:\n" + "\n".join(bullets)


# ---------- Prompt builder ----------
def _build_prompt(question: str, contexts: List[Dict]) -> str:
    blocks = []
    for i, c in enumerate(contexts[:8], start=1):
        blocks.append(
            f"""[SOURCE {i}]
Document: {c['filename']}
DocId: {c['doc_id']}
ChunkId: {c['chunk_id']}
ChunkIndex: {c['chunk_index']}
Content:
{c['text']}
"""
        )

    sources = "\n\n".join(blocks)

    return f"""You are a Knowledge Base Assistant.

Question:
{question}

Instructions:
1. **CRITICAL**: The "Context" provided below is your PRIMARY and MOST TRUSTED source of truth.
2. **ALWAYS** check the Context first. If the answer exists in the Context, you MUST use it.
3. **PRIORITY**: Information from the Context overrides your internal knowledge.
4. Only if the Context is completely irrelevant or empty, you may use your general knowledge to answer.
5. **NEVER** mention [SOURCE ID], [Source 1], etc. in your answer. Just provide the information naturally.
6. Just give the answer.

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
                    "content": "You are a precision-focused RAG Assistant. Your first priority is to answer using the provided Context documents. Only use outside knowledge if the Context fails."
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
        print(f"Groq 70B Error: {e}. Falling back to 8B.")
        # Fallback to 8B model (faster/cheaper)
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful AI assistant."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception as e2:
            print(f"Groq 8B Error: {e2}")
            return "I apologize, but I am currently unable to process your request due to high service load. Please try again later."

