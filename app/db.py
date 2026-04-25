from sqlmodel import SQLModel, create_engine, Session
from .config import settings

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        if not url:
            # On Vercel, we don't want to crash at import time.
            # We only crash if someone actually tries to use the DB.
            raise ValueError("DATABASE_URL is not set. Please configure it in your environment variables.")
        from sqlmodel import create_engine
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine

def create_db_and_tables() -> None:
    try:
        engine = get_engine()
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f"DB Error: {e}")
        # Don't re-raise in startup to allow health checks
        pass

def get_session():
    engine = get_engine()
    with Session(engine) as session:
        yield session
