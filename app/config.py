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

    # ---------- Auth / Security ----------
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # ---------- CORS ----------
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:8000,https://kb-frontend-plum.vercel.app,https://kb-backend-21p3.onrender.com",
        alias="CORS_ORIGINS",
    )

    # ---------- Embeddings ----------
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL_NAME",
    )
    tokenizer_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="TOKENIZER_MODEL_NAME",
    )

    # ---------- LLM Providers ----------
    ollama_url: Optional[str] = Field(default=None, alias="OLLAMA_URL")
    ollama_model: Optional[str] = Field(default=None, alias="OLLAMA_MODEL")

    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: Optional[str] = Field(default=None, alias="OPENAI_MODEL")

    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")

    # ---------- Google Auth ----------
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(default=None, alias="GOOGLE_REDIRECT_URI")

    # ---------- Frontend ----------
    frontend_url: str = Field(default="http://localhost:3000,https://kb-frontend-plum.vercel.app", alias="FRONTEND_URL")

    # ---------- Seed flags ----------
    seed_default_users: bool = Field(default=True, alias="SEED_DEFAULT_USERS")

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
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
