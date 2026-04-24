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
from .routers import auth, documents, chat, public

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
print(f"DEBUG: Allowed CORS origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Global Exception Handler ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_msg = str(exc)
    print(f"CRITICAL ERROR: {error_msg}")
    traceback.print_exc()
    
    # On Vercel, write to /tmp or just print
    dump_path = "/tmp/error_dump.txt" if "VERCEL" in os.environ else "error_dump.txt"
    try:
        with open(dump_path, "w") as f:
            f.write(traceback.format_exc())
    except Exception:
        pass
    
    # Manually inject CORS headers so the browser can read the error response.
    # FastAPI's CORSMiddleware does NOT wrap exception handler responses,
    # so a 500 crash would appear as a CORS error to the browser.
    origin = request.headers.get("origin", "")
    allowed = settings.cors_origin_list
    cors_origin = origin if origin in allowed else (allowed[0] if allowed else "*")

    return JSONResponse(
        status_code=500,
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
        },
        content={
            "detail": {
                "message": error_msg,
                "type": type(exc).__name__
            }
        }
    )

# ---------- Health ----------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/test_db")
def test_db():
    from .db import get_session
    from .models import User
    from sqlmodel import select
    import traceback
    try:
        session = next(get_session())
        user = session.exec(select(User).limit(1)).first()
        return {"status": "ok", "user": user}
    except Exception as e:
        return {"status": "error", "traceback": traceback.format_exc()}



# ---------- Routers ----------
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(public.router)
