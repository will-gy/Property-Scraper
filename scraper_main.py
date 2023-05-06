import argparse
import json
from typing import Tuple

from app import manage_database
from scraper.rightmove import RightMoveScraper

# Parse cmd line args
parser = argparse.ArgumentParser(description='Scrape rightmove')
parser.add_argument(
    '--config_path', type=str, help='config file path to load',
    default='scraper/config/scraper_config.json'
    )
args = parser.parse_args()


def load_config(config_file: str) -> Tuple[str, str]:
    with open(config_file) as f:
        config = json.load(f)
        url = config.get('url', '')
        table_name = config.get('table_name', '')
    return url, table_name


if __name__ == '__main__':
    # Load config
    url, database_table = load_config(args.config_path)
    rightmove_scraper = RightMoveScraper(url)
    # Scrape rightmove
    data = rightmove_scraper.run()
    try:
        manage_database.create_db()
    except:
        pass
    try:
        manage_database.create_table(database_table)
    except:
        pass
    manage_database.update_house(database_table, data)
