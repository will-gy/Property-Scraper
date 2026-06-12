"""Per-location scrape and email operations used by the orchestrator.

Each function operates on a single :class:`LocationConfig` and returns a result
object describing the outcome. They never swallow exceptions — fault isolation
is the orchestrator's job (so it can record a failure per location and carry on).
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import analytics
from config_models import LocationConfig
from database.update_database import ManageDatabase
from email_builder import build_email_html
from filters import passes_filters
from scraper.rightmove import RightMoveScraper
from scraper_email.send_email import SendEmail

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    area: str
    scraped: int = 0
    error: str | None = None


@dataclass
class EmailResult:
    area: str
    new: int = 0
    updated: int = 0
    sent: bool = False
    error: str | None = None


def scrape_location(config: LocationConfig, db: ManageDatabase) -> ScrapeResult:
    """Scrape one location (whole market) and persist its listings."""
    logger.info("Scraping %s", config.area)
    listings = RightMoveScraper(config.search_url, max_pages=config.scraper.max_pages).run()
    db.insert_listings(config.area, config.channel.value, listings)
    logger.info("Scraped %d listings for %s", len(listings), config.area)
    return ScrapeResult(area=config.area, scraped=len(listings))


def email_location(
    config: LocationConfig, db: ManageDatabase, dry_run: bool = False
) -> EmailResult:
    """Build and (unless ``dry_run``) send the digest email for one location."""
    rows = db.get_area_rows(config.area)
    area_analytics = analytics.compute(
        rows, config.channel.value, config.email.time_period_hours
    )
    new_listings, updated_listings = _split_changed(rows, config)

    html = build_email_html(config, area_analytics, new_listings, updated_listings)
    subject = _build_subject(config.email.subject_tag, new_listings, updated_listings)

    if dry_run:
        logger.info(
            "[dry-run] %s: %d new, %d updated (%d bytes of HTML, not sent)",
            config.area, len(new_listings), len(updated_listings), len(html),
        )
        return EmailResult(
            area=config.area, new=len(new_listings), updated=len(updated_listings), sent=False
        )

    SendEmail(config.email.to_addr, config.email.bcc_addr).send(subject, html)
    logger.info(
        "Emailed %s: %d new, %d updated",
        config.area, len(new_listings), len(updated_listings),
    )
    return EmailResult(
        area=config.area, new=len(new_listings), updated=len(updated_listings), sent=True
    )


def _split_changed(rows, config: LocationConfig) -> tuple[list[dict], list[dict]]:
    """Listings whose latest row falls in the digest window, passing filters,
    split into new (single price) and updated (price history)."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=config.email.time_period_hours)
    ).strftime("%Y-%m-%d %H:%M:%S")

    history: dict[int, list] = defaultdict(list)
    for row in rows:  # newest-first preserved
        history[row["id"]].append(row)

    new_listings: list[dict] = []
    updated_listings: list[dict] = []
    for listing_history in history.values():
        latest = listing_history[0]
        if str(latest["timestamp"]) < cutoff:
            continue
        if (latest["status"] or "available") != "available":  # hide let-agreed/gone
            continue
        if not passes_filters(latest, config.filters):
            continue
        listing = _listing_dict(listing_history)
        (updated_listings if listing["is_update"] else new_listings).append(listing)
    return new_listings, updated_listings


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _listing_dict(history: list) -> dict:
    latest = history[0]
    listing = {
        "id": latest["id"],
        "price": latest["price"],
        "beds": latest["beds"],
        "bathrooms": latest["bathrooms"],
        "property_type": latest["property_type"],
        "address": latest["address"],
        "description": latest["description"],
        "image": latest["image"],
        "link": latest["link"],
        "distance": latest["distance"],
        "sqft": latest["sqft"],
        "available_date": latest["available_date"],
        "first_listed": latest["first_listed"],
        "latitude": latest["latitude"],
        "longitude": latest["longitude"],
        "timestamp": latest["timestamp"],
        "is_update": len(history) > 1,
    }
    if len(history) > 1:
        new_price = _to_float(latest["price"])
        old_price = _to_float(history[1]["price"])
        listing["old_price"] = old_price
        listing["price_change_pct"] = (
            round((new_price - old_price) / old_price * 100, 1)
            if new_price is not None and old_price
            else None
        )
        # oldest -> newest for display
        listing["price_history"] = [(r["timestamp"], r["price"]) for r in reversed(history)]
    return listing


def _build_subject(subject_tag: str, new_listings: list, updated_listings: list) -> str:
    return (
        f"{subject_tag} Property Scraper: "
        f"{len(new_listings)} New & {len(updated_listings)} Price Updates"
    )
