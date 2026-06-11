"""Pydantic models for per-location scraper configuration.

Strict by design (``extra="forbid"``) so typos in a config file fail loudly at
load time rather than being silently ignored.
"""
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

_AREA_RE = re.compile(r"[A-Za-z0-9_]+")


class Channel(str, Enum):
    RENT = "rent"
    BUY = "buy"


class EmailConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_tag: str = ""
    to_addr: list[str] = Field(default_factory=list)
    bcc_addr: list[str] = Field(default_factory=list)
    time_period_hours: int = Field(default=24, gt=0)
    enabled: bool = True


class ScraperConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class LocationConfig(BaseModel):
    """A single scrape + email target. ``area`` doubles as the SQL table name."""
    model_config = ConfigDict(extra="forbid")

    area: str = Field(min_length=1)
    channel: Channel
    search_url: str
    email: EmailConfig = Field(default_factory=EmailConfig)
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)

    @field_validator("area")
    @classmethod
    def _validate_area(cls, value: str) -> str:
        if not _AREA_RE.fullmatch(value):
            raise ValueError(
                "area must contain only letters, digits and underscores "
                "(it is used as a SQL table name)"
            )
        return value

    @field_validator("search_url")
    @classmethod
    def _validate_search_url(cls, value: str) -> str:
        if not value.startswith("https://www.rightmove.co.uk/"):
            raise ValueError("search_url must be a https://www.rightmove.co.uk/ URL")
        if "&index=0" not in value:
            raise ValueError("search_url must contain '&index=0' so pagination works")
        return value

    @property
    def table_name(self) -> str:
        return self.area
