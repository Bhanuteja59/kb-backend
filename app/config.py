from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # ---------- Core infrastructure ----------
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v

        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)

        # On Vercel use pg8000 (pure Python) — psycopg2 native extensions are unavailable
        if "VERCEL" in os.environ or "VERCEL_ENV" in os.environ:
            if v.startswith("postgresql://") and "+pg8000" not in v:
                v = v.replace("postgresql://", "postgresql+pg8000://", 1)

            # pg8000 does not accept sslmode or channel_binding in the URL.
            # Strip them and use ssl=true (which pg8000 does support).
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(v)
            params = parse_qs(parsed.query, keep_blank_values=True)
            had_ssl = params.pop("sslmode", None)
            params.pop("channel_binding", None)
            if had_ssl and had_ssl[0] in ("require", "verify-ca", "verify-full"):
                params["ssl"] = ["true"]
            new_query = urlencode({k: vals[0] for k, vals in params.items()})
            v = urlunparse(parsed._replace(query=new_query))

        return v

    qdrant_url: Optional[str] = Field(default=None, validation_alias="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="documents_v2", validation_alias="QDRANT_COLLECTION")

    # ---------- Auth / Security ----------
    jwt_secret: str = Field(default="fallback-secret-change-me-in-prod", validation_alias="JWT_SECRET_KEY") 
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # ---------- CORS ----------
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "https://kb-frontend-plum.vercel.app",
        ],
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            try:
                # Try JSON list first
                if v.startswith("["):
                    return json.loads(v)
                # Fallback to comma-separated
                return [i.strip() for i in v.split(",")]
            except Exception:
                return [v]
        return v

    # ---------- Embeddings ----------
    # FastEmbed uses BAAI/bge-small-en-v1.5 by default in embedding.py
    
    # ---------- LLM Providers ----------
    groq_api_key: Optional[str] = Field(default=None, validation_alias="GROQ_API_KEY")

    # ---------- Google Auth ----------
    google_client_id: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(default=None, validation_alias="GOOGLE_REDIRECT_URI")
    
    # ---------- Mail (SMTP) ----------
    mail_username: Optional[str] = Field(default=None, validation_alias="MAIL_USERNAME")
    mail_password: Optional[str] = Field(default=None, validation_alias="MAIL_PASSWORD")
    mail_from: Optional[str] = Field(default=None, validation_alias="MAIL_FROM")
    mail_port: int = Field(default=587, validation_alias="MAIL_PORT")
    mail_server: Optional[str] = Field(default=None, validation_alias="MAIL_SERVER")
    mail_from_name: str = Field(default="KB RAG Platform", validation_alias="MAIL_FROM_NAME")

    # ---------- Frontend ----------
    frontend_url: str = Field(default="https://kb-frontend-plum.vercel.app", validation_alias="FRONTEND_URL")

    # ---------- Backward-compatible uppercase access ----------
    @property
    def QDRANT_URL(self) -> str:
        return self.qdrant_url

    @property
    def QDRANT_API_KEY(self) -> Optional[str]:
        return self.qdrant_api_key

    @property
    def QDRANT_COLLECTION(self) -> str:
        return self.qdrant_collection

    @property
    def GROQ_API_KEY(self) -> Optional[str]:
        return self.groq_api_key

    @property
    def DATABASE_URL(self) -> Optional[str]:
        return self.database_url

    @property
    def JWT_SECRET(self) -> Optional[str]:
        return self.jwt_secret

    # ---------- Helpers ----------
    @property
    def cors_origin_list(self) -> List[str]:
        return self.cors_origins


settings = Settings()
