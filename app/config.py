from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
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
    max_upload_size_mb: int = Field(default=50, alias="MAX_UPLOAD_SIZE_MB")

    # ---------- Auth / Security ----------
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # ---------- CORS ----------
    cors_origins: str = Field(
        default="http://localhost:3000,https://kb-frontend-plum.vercel.app",
        alias="CORS_ORIGINS",
    )

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
    


    # ---------- Frontend ----------
    frontend_url: str = Field(default="https://kb-frontend-plum.vercel.app", alias="FRONTEND_URL")

    # ---------- Email ----------



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

    @property
    def FRONTEND_URL(self) -> str:
        return self.frontend_url



    # ---------- Helpers ----------
    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
