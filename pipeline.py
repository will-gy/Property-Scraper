"""Per-location scrape and email operations used by the orchestrator.

Each function operates on a single :class:`LocationConfig` and returns a result
object describing the outcome. They never swallow exceptions — fault isolation
is the orchestrator's job (so it can record a failure per location and carry on).
"""
import logging
import sqlite3
from dataclasses import dataclass

from config_models import Channel, LocationConfig
from database.update_database import ManageDatabase
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
    """Scrape one location and persist its listings."""
    logger.info("Scraping %s", config.area)
    listings = RightMoveScraper(config.search_url).run()
    db.create_table(config.table_name)
    db.update_house(config.table_name, listings)
    logger.info("Scraped %d listings for %s", len(listings), config.area)
    return ScrapeResult(area=config.area, scraped=len(listings))


def email_location(
    config: LocationConfig, db: ManageDatabase, dry_run: bool = False
) -> EmailResult:
    """Build and (unless ``dry_run``) send the update email for one location."""
    changed_ids = db.get_record_n_hours(
        config.table_name, hour=config.email.time_period_hours
    )
    new_props, updated_props = _split_new_and_updated(db, config.table_name, changed_ids)

    email = SendEmail(
        to_addr=config.email.to_addr,
        bcc_addr=config.email.bcc_addr,
        rent=config.channel is Channel.RENT,
    )
    email.new_property = new_props
    email.update_property = updated_props
    email.subject = _build_subject(config.email.subject_tag, new_props, updated_props)

    if dry_run:
        html = email.build_html()
        logger.info(
            "[dry-run] %s: %d new, %d updated (%d bytes of HTML, not sent)",
            config.area, len(new_props), len(updated_props), len(html),
        )
        return EmailResult(
            area=config.area, new=len(new_props), updated=len(updated_props), sent=False
        )

    email.send_email()
    logger.info(
        "Emailed %s: %d new, %d updated", config.area, len(new_props), len(updated_props)
    )
    return EmailResult(
        area=config.area, new=len(new_props), updated=len(updated_props), sent=True
    )


def _split_new_and_updated(
    db: ManageDatabase, table_name: str, changed_ids: list[sqlite3.Row]
) -> tuple[list[dict], list[dict]]:
    new_house: list[dict] = []
    updated_house: list[dict] = []
    for row in changed_ids:
        history = db.get_record(table_name, row["ID"])
        if len(history) > 1:
            updated_house.append(_updated_dict(history))
        else:
            new_house.append(_new_dict(history))
    return new_house, updated_house


def _new_dict(history: list[sqlite3.Row]) -> dict:
    latest = history[0]
    return {
        "timestamp": latest["TIMESTAMP"],
        "price": latest["PRICE"],
        "bedroom": latest["BEDS"],
        "link": latest["LINK"],
        "address": latest["ADDRESS"],
        "description": latest["DESCRIPTION"],
        "image": latest["IMAGE"],
        "distance": latest["DISTANCE"],
    }


def _updated_dict(history: list[sqlite3.Row]) -> dict:
    latest, previous = history[0], history[1]
    updated_price = latest["PRICE"]
    old_price = previous["PRICE"]
    return {
        "timestamp": latest["TIMESTAMP"],
        "updated_price": updated_price,
        "old_price": old_price,
        "price_change": ((updated_price - old_price) / old_price) * 100,
        "price_history": [(row["TIMESTAMP"], row["PRICE"]) for row in history],
        "bedroom": latest["BEDS"],
        "link": latest["LINK"],
        "address": latest["ADDRESS"],
        "description": latest["DESCRIPTION"],
        "image": latest["IMAGE"],
        "distance": latest["DISTANCE"],
    }


def _build_subject(subject_tag: str, new_props: list, updated_props: list) -> str:
    return (
        f"{subject_tag} Property Scraper: "
        f"{len(new_props)} New & {len(updated_props)} Price Updates"
    )
