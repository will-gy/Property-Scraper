"""Centralised logging configuration (rotating file + console).

All values come from LoggingSettings (LOG_* env vars): level, directory,
filename, rotation size and backup count.
"""
import logging
from logging.handlers import RotatingFileHandler

from settings import get_logging_settings


def setup_logging() -> None:
    """Configure the root logger"""

    cfg = get_logging_settings()
    cfg.dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        cfg.dir / cfg.filename, maxBytes=cfg.max_bytes, backupCount=cfg.backup_count
    )
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.level.upper(), logging.INFO))
    root.addHandler(file_handler)
    root.addHandler(console)
