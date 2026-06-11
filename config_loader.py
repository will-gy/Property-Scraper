"""Discover and validate per-location config files in ``config/``."""
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from config_models import LocationConfig

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent / "config"


class ConfigError(Exception):
    """Raised when a config file is missing, malformed, or invalid."""


def load_config_file(path: Path) -> LocationConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path.name}: invalid JSON: {e}") from e
    try:
        return LocationConfig.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"{path.name}: invalid config:\n{e}") from e


def load_configs(config_dir: Path = DEFAULT_CONFIG_DIR) -> list[LocationConfig]:
    """Load and validate every ``*.json`` in ``config_dir``.

    Raises ConfigError on the first malformed file, on an empty directory, or on
    duplicate ``area`` values (which would collide on the same DB table).
    """
    if not config_dir.is_dir():
        raise ConfigError(f"Config directory not found: {config_dir}")

    paths = sorted(config_dir.glob("*.json"))
    if not paths:
        raise ConfigError(f"No config files found in {config_dir}")

    configs = [load_config_file(p) for p in paths]

    seen: set[str] = set()
    for cfg in configs:
        if cfg.area in seen:
            raise ConfigError(f"Duplicate area '{cfg.area}' across config files")
        seen.add(cfg.area)

    logger.info("Loaded %d location config(s) from %s", len(configs), config_dir)
    return configs
