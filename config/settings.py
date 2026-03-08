"""
Configuration settings for HealthLink using Pydantic Settings.
All settings loaded from environment variables with sensible defaults.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # LLM Configuration
    # Keep defaults in code; only secrets should be in .env / GitHub Secrets.
    llm_provider: str = "openai"  # supported: openai, gemini
    llm_model_name: str = "gpt-4o"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # Embedding Configuration
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Pinecone Configuration
    pinecone_api_key: str = ""
    pinecone_environment: str = ""  # e.g., "us-east-1-aws"
    pinecone_index_name: str = "healthlink"

    # RAG Configuration
    rag_top_k: int = 5
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Database Configuration
    database_url: str = "sqlite:///./data/healthlink.db"
    db_echo: bool = False

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8501"]

    # Logging Configuration
    log_level: str = "INFO"

    # Security
    # Not currently used by auth middleware, but kept for future JWT/session use.
    secret_key: str = "dev-secret-key-change-in-production"

    # Google Cloud Configuration
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    cloud_run_service_name: str = "healthlink"

    # Feature Flags
    enable_metrics: bool = True
    auto_seed_doctors_on_startup: bool = True
    auto_load_kb_on_startup: bool = False

    def validate_config(self) -> None:
        """Validate required configuration is present."""
        provider = self.llm_provider.lower()
        if provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required for llm_provider=openai")
        elif provider == "gemini":
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required for llm_provider=gemini")
        else:
            raise ValueError("LLM_PROVIDER must be one of: openai, gemini")
        if not self.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is required")


# Singleton instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    FastAPI dependency for getting application settings.
    Returns singleton instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.validate_config()
    return _settings
