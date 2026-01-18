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
from sqlmodel import Session, select

from .config import settings
from .db import create_db_and_tables, get_session
from .models import User, Role

from .vectorstore import ensure_collection

# Import Routers
from .routers import auth, users, documents, audit, chat, public, analytics

app = FastAPI(title="KB RAG API", version="2.0.0")

@app.on_event("startup")
async def startup_event():
    # Initialize Qdrant collection and indexes on startup
    try:
        # Avoid loading the heavy ML model at startup to save memory on Render (Free Tier)
        dim = 384 
        ensure_collection(vector_size=dim)
        print(f"INFO:    Qdrant collection '{settings.QDRANT_COLLECTION}' verified with dimension {dim}")
    except Exception as e:
        print(f"WARNING: Failed to initialize Qdrant on startup: {e}")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kb-frontend-plum.vercel.app",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ---------- Startup ----------
@app.on_event("startup")
def on_startup():
    try:
        create_db_and_tables()
    except Exception as e:
        pass

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
app.include_router(analytics.router)
