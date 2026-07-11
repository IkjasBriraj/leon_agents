"""
AgentCraft Backend — Application Configuration

Uses Pydantic BaseSettings for environment-aware config management.
All settings can be overridden via environment variables or a .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the AgentCraft backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ──────────────────────────────────────────────────────────
    app_name: str = "AgentCraft"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = "INFO"

    # ─── Server ───────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"

    # ─── Security / JWT ───────────────────────────────────────────────────────
    secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_openssl_rand_hex_32",
        description="JWT signing secret — must be at least 32 chars in production",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Master encryption key for secrets manager (AES-256-GCM)
    encryption_key: str = Field(
        default="CHANGE_ME_32_BYTE_HEX_KEY_PLACEHOLDER00",
        description="Hex-encoded 32-byte key for secret encryption",
    )

    # ─── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://agentcraft:agentcraft@localhost:5432/agentcraft",
        description="Async PostgreSQL connection string",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # ─── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_max_connections: int = 50

    # ─── LLM (Ollama — default provider) ─────────────────────────────────────
    default_llm_provider: str = "ollama"
    default_llm_model: str = "llama3.2"  # Installed Ollama model
    ollama_base_url: str = "http://localhost:11434"

    # Embedding model (used for pgvector)
    embedding_model: str = "nomic-embed-text"  # Ollama embedding model
    embedding_dimensions: int = 768  # nomic-embed-text outputs 768-dim vectors

    # ─── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins",
    )

    # ─── Rate Limiting ────────────────────────────────────────────────────────
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # ─── Docker Sandbox ───────────────────────────────────────────────────────
    sandbox_enabled: bool = True
    sandbox_memory_limit: str = "128m"
    sandbox_cpu_quota: int = 20000   # 20% of one CPU core
    sandbox_timeout_seconds: int = 30
    sandbox_python_image: str = "python:3.11-slim"
    sandbox_node_image: str = "node:20-slim"

    # ─── Websocket ────────────────────────────────────────────────────────────
    ws_heartbeat_interval: int = 30  # seconds

    # ─── Validation ───────────────────────────────────────────────────────────
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("secret_key must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()


# Convenience alias used throughout the app
settings = get_settings()
