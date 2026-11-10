"""Environment-based configuration. Secrets can come from *_FILE (Docker secrets)."""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL, make_url


def _secret(name: str, default: str | None = None) -> str | None:
    """Read NAME_FILE (preferred, Docker secret) or NAME from the environment."""
    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: URL
    jwt_secret: str
    seed_password: str
    seed_on_start: bool
    token_ttl_minutes: int
    pbkdf2_iterations: int
    log_level: str
    app_version: str


def load_settings() -> Settings:
    explicit_url = os.environ.get("DATABASE_URL")
    if explicit_url:
        database_url = make_url(explicit_url)
    else:
        database_url = URL.create(
            "postgresql+psycopg",
            username=os.environ.get("DB_USER", "school"),
            password=_secret("DB_PASSWORD"),
            host=os.environ.get("DB_HOST", "db"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "school"),
        )

    jwt_secret = _secret("JWT_SECRET")
    if not jwt_secret or len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET (or JWT_SECRET_FILE) must be set, at least 32 characters")

    seed_password = _secret("SEED_PASSWORD") or ""
    seed_on_start = os.environ.get("SEED_ON_START", "true").lower() == "true"
    if seed_on_start and len(seed_password) < 8:
        raise RuntimeError("SEED_PASSWORD (or _FILE) must be >= 8 chars when SEED_ON_START=true")

    return Settings(
        database_url=database_url,
        jwt_secret=jwt_secret,
        seed_password=seed_password,
        seed_on_start=seed_on_start,
        token_ttl_minutes=int(os.environ.get("TOKEN_TTL_MINUTES", "60")),
        pbkdf2_iterations=int(os.environ.get("PBKDF2_ITERATIONS", "200000")),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        app_version=os.environ.get("APP_VERSION", "dev"),
    )


settings = load_settings()
