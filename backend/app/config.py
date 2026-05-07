from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Runtime
    app_env: str = "dev"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Secrets
    master_key: str = Field(default="", description="Base64 32-byte key for Fernet")
    jwt_secret: str = Field(default="dev-only-jwt-secret-please-change")
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30
    jwt_algorithm: str = "HS256"

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Logging
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_to_stdout: bool = True

    # Uploads
    upload_dir: str = "./uploads"
    upload_max_image_mb: int = 10
    upload_max_file_mb: int = 25

    # Rate limits
    rate_limit_chat_per_min: int = 60
    rate_limit_chat_per_hour: int = 1000
    rate_limit_mutate_per_min: int = 30

    # Sandbox
    sandbox_python: str = "python"
    sandbox_allow_private_net: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        for d in (self.log_dir, self.upload_dir):
            Path(d).mkdir(parents=True, exist_ok=True)
        db_path = self.database_url.replace("sqlite:///", "", 1)
        if db_path and not db_path.startswith(":"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
