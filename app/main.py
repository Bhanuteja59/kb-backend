import os

# Compatibility: Unset system SSL variables that might point to invalid paths on Windows
# This prevents "OSError: Could not find a suitable TLS CA certificate bundle"
pass_on_env_errors = True
try:
    for var in ["CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"]:
        if var in os.environ:
            del os.environ[var]
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import create_db_and_tables

from .vectorstore import ensure_collection

# Import Routers
from .routers import auth, users, documents, audit, chat, public

app = FastAPI(title="KB RAG API", version="2.0.0")

@app.on_event("startup")
async def startup():
    """Initialize database and Qdrant on startup."""
    try:
        # Initialize database tables
        create_db_and_tables()
    except Exception as e:
        # Log error but continue - app can still serve health checks
        pass
    
    # Initialize Qdrant in background (non-blocking)
    import asyncio
    async def init_qdrant_background():
        try:
            from .vectorstore import ensure_collection as init_collection
            from .embedding import get_embedding_dimension
            dim = get_embedding_dimension()
            init_collection(vector_size=dim)
        except Exception as e:
            # Log error but continue - vector features may be unavailable
            pass
    
    asyncio.create_task(init_qdrant_background())

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,  # Loaded from CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Health ----------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- Routers ----------
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(audit.router)
app.include_router(chat.router)
app.include_router(public.router)
