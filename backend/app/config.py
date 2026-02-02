from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    mysql_url: str = "mysql+aiomysql://labreportai:labreportai@mysql:3306/labreportai"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # LLM - Multi-provider support (groq, openai, google)
    llm_provider: str = "groq"
    llm_api_key: str = ""
    llm_analysis_model: str = "llama-3.3-70b-versatile"
    llm_validation_model: str = "llama-3.1-8b-instant"
    llm_translation_model: str = "llama-3.1-8b-instant"

    # File Upload
    max_file_size: int = 20_971_520  # 20 MB
    max_pages: int = 30

    # OCR
    ocr_engine: str = "PaddleOCR"

    # Validation
    validation_threshold: float = 0.8

    # Security
    recaptcha_secret_key: str = ""
    recaptcha_site_key: str = ""
    rate_limit_per_ip: int = 10

    # CORS
    cors_origins: str = "http://localhost:3000,http://frontend:3000"

    # Storage
    retention_period: int = 48  # hours
    storage_path: str = "/app/storage"

    # Twilio (WhatsApp)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""

    @property
    def sync_mysql_url(self) -> str:
        """Synchronous MySQL URL for Alembic and Celery tasks."""
        return self.mysql_url.replace("mysql+aiomysql://", "mysql+pymysql://")

    @property
    def uploads_path(self) -> str:
        return f"{self.storage_path}/uploads"

    @property
    def outputs_path(self) -> str:
        return f"{self.storage_path}/outputs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
