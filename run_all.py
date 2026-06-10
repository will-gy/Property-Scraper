"""Single entrypoint: scrape and/or email all configured locations.

Usage:
    uv run python run_all.py --mode both
    uv run python run_all.py --mode scrape --only ClaphamSouth
    uv run python run_all.py --mode email --dry-run

Each location runs in isolation: a failure in one is logged and recorded in the
run summary, but does not stop the others. Exit code is non-zero if any
location errored, so a scheduler surfaces failures.
"""
import argparse
import logging
import sys

from app import manage_database
from config_loader import ConfigError, load_configs
from logging_setup import setup_logging
from pipeline import EmailResult, ScrapeResult, email_location, scrape_location
from settings import get_storage_settings

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Rightmove and email property updates for all configured areas."
    )
    parser.add_argument(
        "--mode", choices=["scrape", "email", "both"], default="both",
        help="Which phase(s) to run (default: both).",
    )
    parser.add_argument(
        "--only", metavar="AREA", help="Run only the location with this area name.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Build emails but do not send them (email phase only).",
    )
    return parser.parse_args()


def run(mode: str, only: str | None, dry_run: bool) -> int:
    try:
        configs = load_configs(get_storage_settings().config_dir)
    except ConfigError as e:
        logger.error("Config error: %s", e)
        return 2

    if only:
        configs = [c for c in configs if c.area == only]
        if not configs:
            logger.error("No config matches area '%s'", only)
            return 2

    scrape_results: list[ScrapeResult] = []
    email_results: list[EmailResult] = []

    if mode in ("scrape", "both"):
        for cfg in (c for c in configs if c.scraper.enabled):
            try:
                scrape_results.append(scrape_location(cfg, manage_database))
            except Exception as e:  # isolate: one area's failure must not stop the rest
                logger.exception("Scrape failed for %s", cfg.area)
                scrape_results.append(ScrapeResult(area=cfg.area, error=str(e)))

    if mode in ("email", "both"):
        for cfg in (c for c in configs if c.email.enabled):
            try:
                email_results.append(email_location(cfg, manage_database, dry_run=dry_run))
            except Exception as e:
                logger.exception("Email failed for %s", cfg.area)
                email_results.append(EmailResult(area=cfg.area, error=str(e)))

    _log_summary(scrape_results, email_results)

    errored = [r for r in (*scrape_results, *email_results) if r.error]
    return 1 if errored else 0


def _log_summary(
    scrape_results: list[ScrapeResult], email_results: list[EmailResult]
) -> None:
    logger.info("==== Run summary ====")
    for r in scrape_results:
        if r.error:
            logger.info("  scrape %-22s ERROR: %s", r.area, r.error)
        else:
            logger.info("  scrape %-22s %d listings", r.area, r.scraped)
    for r in email_results:
        if r.error:
            logger.info("  email  %-22s ERROR: %s", r.area, r.error)
        else:
            status = "sent" if r.sent else "dry-run"
            logger.info(
                "  email  %-22s %d new, %d updated (%s)",
                r.area, r.new, r.updated, status,
            )


def main() -> int:
    setup_logging()
    args = _parse_args()
    return run(mode=args.mode, only=args.only, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
