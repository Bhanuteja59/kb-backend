"""
Simple Groq-only LLM service for RAG responses.
No fallback providers - clean and fast.
"""
from __future__ import annotations
from typing import List, Dict
from groq import Groq
from .config import settings

# ---------- Groq Client ----------
_groq_client: Groq | None = None

def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        if settings.GROQ_API_KEY:
            _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client

# ---------- Feature flag ----------
def llm_enabled() -> bool:
    return bool(settings.GROQ_API_KEY)

# ---------- Public API ----------
async def generate_answer(question: str, contexts: List[Dict]) -> str:
    """
    Generate answer using Groq LLM.
    Uses context from documents if available, otherwise uses general knowledge.
    """
    if not settings.GROQ_API_KEY:
        return "Error: GROQ_API_KEY not configured. Please add it to your .env file."

    try:
        return _groq_answer(question, contexts)
    except Exception as e:
        return f"Error generating response: {str(e)}"

# ---------- Prompt builder ----------
def _build_prompt(question: str, contexts: List[Dict]) -> str:
    """Build prompt with context from retrieved documents."""
    if contexts:
        blocks = []
        for i, c in enumerate(contexts[:5], 1):  # Limit to top 5 chunks
            blocks.append(f"Content {i}: {c['text']}")
        sources = "\n\n".join(blocks)
        
        return f"""You are an advanced Knowledge Base Assistant designed to provide comprehensive and detailed answers.

Question: {question}

Instructions:
1.  **PRIORITIZE CONTEXT:** Use the provided 'Context from Documents' as the primary source of truth.
2.  **BE DETAILED:** If the answer is found in the context, provide a thorough, deep explanation. Do not summarize briefly; expand on the details found in the documents.
3.  **FALLBACK:** If the provided context is not relevant to the user's question, IGNORE the context and answer using your internal general knowledge.
4.  **Integration:** You may combine context with general knowledge to provide a better answer, but always give precedence to the context for specific facts.

Context from Documents:
{sources}
"""
    else:
        return f"""You are a helpful and knowledgeable AI assistant.

Question: {question}

Instructions:
- No relevant internal documents were found for this query.
- Please answer the question comprehensively using your general knowledge.
- Be detailed and helpful.
"""

# ---------- Groq implementation ----------
def _groq_answer(question: str, contexts: List[Dict]) -> str:
    """Call Groq API to generate answer."""
    client = _get_groq_client()
    if not client:
        raise Exception("Groq client not initialized")

    prompt = _build_prompt(question, contexts)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system", 
                "content": "You are a helpful AI assistant with access to a knowledge base. Answer questions accurately and concisely."
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()
