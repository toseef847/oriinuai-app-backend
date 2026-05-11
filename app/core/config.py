from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "ORIINU.AI"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"
    STRIPE_CHECKOUT_SUCCESS_PATH: str = "/billing/success"
    STRIPE_CHECKOUT_CANCEL_PATH: str = "/billing/cancel"
    STRIPE_PORTAL_RETURN_PATH: str = "/account/billing"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return bool(value)

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    PROFILE_IMAGE_BUCKET: str = "profile-images"

    # LLM — google_ai_studio | openai (no ollama)
    LLM_PROVIDER: str = "google_ai_studio"
    GOOGLE_AI_STUDIO_KEY: str = ""
    GEMMA_FREE_MODEL: str = "gemma-4-e4b-it"
    GEMMA_PRO_MODEL: str = "gemma-4-27b-it"
    GEMMA_ELITE_MODEL: str = "gemma-4-31b-it"
    OPENAI_API_KEY: str = ""
    OPENAI_MINI_MODEL: str = "gpt-4o-mini"
    OPENAI_FULL_MODEL: str = "gpt-4o"

    # Embeddings — google | openai (no local/sentence-transformers)
    EMBEDDING_PROVIDER: str = "google"
    EMBEDDING_DIMENSIONS: int = 768   # 768=google | 1536=openai

    # Plan limits
    FOUNDATION_DAILY_MESSAGES: int = 5
    CORE_DAILY_MESSAGES: int = 50
    INNER_CIRCLE_DAILY_MESSAGES: int = 500
    FOUNDATION_RAG_CHUNKS: int = 2
    CORE_RAG_CHUNKS: int = 5
    INNER_CIRCLE_RAG_CHUNKS: int = 10

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CORE_MONTHLY_PRICE_ID: str = ""
    STRIPE_CORE_YEARLY_PRICE_ID: str = ""
    STRIPE_INNER_MONTHLY_PRICE_ID: str = ""
    STRIPE_INNER_YEARLY_PRICE_ID: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"


settings = Settings()
