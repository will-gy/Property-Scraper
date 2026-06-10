import argparse
import json
import logging
from typing import Tuple

from app import manage_database
from logging_setup import setup_logging
from scraper.rightmove import RightMoveScraper

logger = logging.getLogger(__name__)


def load_config(config_file: str) -> Tuple[str, str]:
    with open(config_file) as f:
        config = json.load(f)
        url = config.get('url', '')
        table_name = config.get('table_name', '')
    return url, table_name


if __name__ == '__main__':
    setup_logging()

    parser = argparse.ArgumentParser(description='Scrape rightmove')
    parser.add_argument(
        '--config_path', type=str, help='config file path to load',
        default='scraper/config/scraper_config.json'
    )
    args = parser.parse_args()

    url, database_table = load_config(args.config_path)
    rightmove_scraper = RightMoveScraper(url)
    data = rightmove_scraper.run()

    manage_database.create_table(database_table)
    manage_database.update_house(database_table, data)
    logger.info("Scraped %s listings into %s", len(data), database_table)
