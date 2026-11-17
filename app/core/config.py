"""Application settings, loaded from environment variables (prefix ``APP_``)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DISCORD_WEBHOOK_HOSTS = frozenset(
    {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "ERP Maintenance Tickets"
    environment: Literal["development", "test", "production"] = "development"
    docs_enabled: bool = True
    api_prefix: str = "/api/v1"

    # --- Database -------------------------------------------------------------------------
    database_url: str = "sqlite:///./maintenance.db"
    auto_create_tables: bool = False  # dev convenience only, use Alembic otherwise

    # --- Authentication / sessions -----------------------------------------------------
    secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "erp-maintenance"
    jwt_audience: str = "erp-maintenance-api"
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_ttl_days: int = Field(default=7, ge=1, le=30)
    password_min_length: int = Field(default=12, ge=8)
    login_max_attempts: int = Field(default=5, ge=1)
    login_window_seconds: int = Field(default=300, ge=1)

    # --- HTTP ---------------------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=list)

    # --- Uploads ------------------------------------------------------------------------
    upload_dir: Path = Path("./var/uploads")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)

    # --- Notifications ------------------------------------------------------------------
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True
    smtp_from: str = "maintenance@example.com"
    discord_webhook_url: SecretStr | None = None
    notification_timeout_seconds: float = Field(default=5.0, gt=0, le=30)

    @field_validator("discord_webhook_url")
    @classmethod
    def _validate_discord_webhook(cls, value: SecretStr | None) -> SecretStr | None:
        """Only Discord webhook URLs are accepted: prevents using the notifier for SSRF."""
        if value is None or not value.get_secret_value():
            return None
        parsed = urlparse(value.get_secret_value())
        if (
            parsed.scheme != "https"
            or parsed.hostname not in _DISCORD_WEBHOOK_HOSTS
            or not parsed.path.startswith("/api/webhooks/")
        ):
            raise ValueError(
                "discord_webhook_url must be an https://discord.com/api/webhooks/... URL"
            )
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.environment == "production":
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origin is forbidden in production")
            if self.auto_create_tables:
                raise ValueError("auto_create_tables must be disabled in production (use Alembic)")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # secret_key comes from the environment
