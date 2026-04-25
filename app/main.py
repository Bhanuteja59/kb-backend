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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import create_db_and_tables

from .vectorstore import ensure_collection

# Import Routers
from .routers import auth, documents, chat, public, users, analytics, audit

app = FastAPI(title="KB RAG API", version="2.0.0")

@app.on_event("startup")
async def startup():
    """Initialize database and Qdrant on startup."""
    # Skip on Vercel/production — tables already exist, this DB round-trip
    # on every cold start consumes 3–5 s and causes OAuth code expiry issues.
    if os.getenv("ENV", "dev") == "dev":
        try:
            create_db_and_tables()
        except Exception:
            pass
    
    # Initialize Qdrant in background (non-blocking)
    import asyncio
    async def init_qdrant_background():
        try:
            from .vectorstore import ensure_collection as init_collection
            from .vectorstore import sync_all_vectors_from_sql, get_collection_count
            from .embedding import get_embedding_dimension
            
            dim = get_embedding_dimension()
            init_collection(vector_size=dim)
            
            # Only sync if the collection is empty to avoid cold-start timeouts
            qdrant_count = get_collection_count()
            if qdrant_count == 0:
                print("Vector store is empty. Running startup vector check...")
                # Run sync in threadpool to avoid blocking event loop
                await asyncio.to_thread(sync_all_vectors_from_sql, batch_size=50, log_func=print)
            else:
                print(f"Vector store already contains {qdrant_count} vectors. Skipping sync.")
            
        except Exception as e:
            print(f"Startup background task failed: {e}")
            # Log error but continue - vector features may be unavailable
            pass
    
    asyncio.create_task(init_qdrant_background())

# ---------- CORS ----------
origins = settings.cors_origin_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ---------- Global Exception Handler ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_msg = str(exc)
    print(f"UNHANDLED ERROR [{type(exc).__name__}]: {error_msg}")
    traceback.print_exc()

    # Inject CORS headers — CORSMiddleware does not wrap exception-handler responses
    origin = request.headers.get("origin", "")
    allowed = settings.cors_origin_list
    cors_origin = origin if origin in allowed else (allowed[0] if allowed else "*")

    return JSONResponse(
        status_code=500,
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
        },
        content={"detail": error_msg},
    )

# ---------- Health ----------
@app.get("/")
def read_root():
    return {"message": "KB RAG API is running. Visit /docs for documentation."}

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- Routers ----------
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(public.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(audit.router)
