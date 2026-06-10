"""Application settings loaded from environment / .env files via pydantic-settings.

Env files are loaded in layers: the shared ``.env`` first, then an
environment-specific overlay chosen by ``APP_ENV`` (defaults to ``dev``):
  - ``APP_ENV=dev``  -> ``.env`` then ``.env.dev``
  - ``APP_ENV=prod`` -> ``.env`` then ``.env.prod``
Values in the overlay override the base, so shared vars (e.g. Gmail creds) live
only in ``.env`` and the overlays carry just per-environment overrides (paths,
log level). Process environment variables override everything.

Three groups of settings:
  - ``Settings``         secrets (GMAIL_*)
  - ``LoggingSettings``  logging config (LOG_*)
  - ``StorageSettings``  on-disk locations (DB_PATH) — kept outside the repo in
                         prod so a ``git reset --hard`` during deploy can't nuke them.
"""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent


def _env_files() -> tuple[str, ...]:
    """Base .env plus the APP_ENV overlay, in load order (later overrides earlier)."""
    files = []
    base = _ROOT / ".env"
    if base.exists():
        files.append(str(base))
    overlay = _ROOT / f".env.{os.environ.get('APP_ENV', 'dev')}"
    if overlay.exists():
        files.append(str(overlay))
    return tuple(files)


_ENV_FILES = _env_files()
_BASE_CONFIG = dict(env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore")


class Settings(BaseSettings):
    """Secrets — required; raises ValidationError if missing."""
    model_config = SettingsConfigDict(**_BASE_CONFIG)

    gmail_user: str
    gmail_password: str
    gmail_from_addr: str


class LoggingSettings(BaseSettings):
    """Logging config, all overridable via LOG_* env vars."""
    model_config = SettingsConfigDict(env_prefix="LOG_", **_BASE_CONFIG)

    level: str = "INFO"
    dir: Path = _ROOT / "logs"
    filename: str = "property_scraper.log"
    max_bytes: int = 1_000_000
    backup_count: int = 5


class StorageSettings(BaseSettings):
    """On-disk locations. DB_PATH should point outside the repo in prod."""
    model_config = SettingsConfigDict(**_BASE_CONFIG)

    db_path: Path = _ROOT / "database" / "rightmove.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()
