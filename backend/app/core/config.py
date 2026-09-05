from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PRAMAN AI"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/praman"
    backend_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    # Authentication & Security
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    trusted_proxies: list[str] = ["127.0.0.1", "::1"]

    # Initial Admin Bootstrap (Optional environment injection)
    first_superuser_email: str | None = None
    first_superuser_password: str | None = None
    first_superuser_name: str | None = "System Administrator"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("backend_cors_origins", "trusted_proxies", mode="before")
    @classmethod
    def parse_comma_separated_list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        env_norm = (self.app_env or "development").strip().lower()
        if env_norm in ("production", "prod", "staging") and not (self.jwt_secret_key and self.jwt_secret_key.strip()):
            raise RuntimeError(
                "JWT_SECRET_KEY must be explicitly configured in production and staging environments. "
                "Silent random fallback is strictly prohibited."
            )
        return self

    @property
    def effective_jwt_secret(self) -> str:
        if self.jwt_secret_key and self.jwt_secret_key.strip():
            return self.jwt_secret_key.strip()

        env_norm = (self.app_env or "development").strip().lower()
        if env_norm in ("production", "prod", "staging"):
            raise RuntimeError(
                "JWT_SECRET_KEY must be explicitly configured in production and staging environments. "
                "Silent random fallback is strictly prohibited."
            )
        return "praman-dev-secret-do-not-use-in-production-09418a"



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
