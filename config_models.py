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
    max_pages: int = Field(default=42, gt=0)  # Rightmove caps results at ~42 pages


class FilterConfig(BaseModel):
    """Filters applied (in Python) to decide which stored listings get emailed.

    Searches are scraped wide (all prices/beds in the area) so the database holds
    the whole market for analytics; these narrow it down per email digest. Change
    them any time — no re-scrape needed.
    """
    model_config = ConfigDict(extra="forbid")

    min_beds: int | None = None
    max_beds: int | None = None
    min_price: float | None = None
    max_price: float | None = None
    max_distance: float | None = None


class LocationConfig(BaseModel):
    """A single scrape + email target. ``area`` doubles as the listings key."""
    model_config = ConfigDict(extra="forbid")

    area: str = Field(min_length=1)
    channel: Channel
    search_url: str
    filters: FilterConfig = Field(default_factory=FilterConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)

    @field_validator("area")
    @classmethod
    def _validate_area(cls, value: str) -> str:
        if not _AREA_RE.fullmatch(value):
            raise ValueError(
                "area must contain only letters, digits and underscores"
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
