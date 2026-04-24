from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Optional


class Settings(BaseSettings):
    # Pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # ---------- Core infrastructure ----------
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")

    qdrant_url: str = Field(alias="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="documents_v2", alias="QDRANT_COLLECTION")

    # ---------- Auth / Security ----------
    jwt_secret: str = Field(alias="JWT_SECRET_KEY") # Changed from JWT_SECRET to match .env
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # ---------- CORS ----------
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "https://kb-frontend-plum.vercel.app",
        ],
        alias="CORS_ORIGINS",
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
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")

    # ---------- Google Auth ----------
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(default=None, alias="GOOGLE_REDIRECT_URI")
    
    # ---------- Google Gemini ----------
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    

    # ---------- Mail (SMTP) ----------
    mail_username: Optional[str] = Field(default=None, alias="MAIL_USERNAME")
    mail_password: Optional[str] = Field(default=None, alias="MAIL_PASSWORD")
    mail_from: Optional[str] = Field(default=None, alias="MAIL_FROM")
    mail_port: int = Field(default=587, alias="MAIL_PORT")
    mail_server: Optional[str] = Field(default=None, alias="MAIL_SERVER")
    mail_from_name: str = Field(default="KB RAG Platform", alias="MAIL_FROM_NAME")

    # ---------- Frontend ----------
    frontend_url: str = Field(default="https://kb-frontend-plum.vercel.app", alias="FRONTEND_URL")

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
