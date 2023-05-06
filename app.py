import json
from typing import Tuple

from database.update_database import ManageDatabase
from scraper.rightmove import RightMoveScraper
from scraper_email.send_email import SendEmail


def load_config(config_file: str) -> Tuple[str, str, str]:
    with open(config_file) as f:
        config = json.load(f)
        url = config.get('url', '')
        table_name = config.get('table_name', '')
        search_type = config.get('search_type', '')

    return url, table_name, search_type

URL, DATABASE_TABLE, SEARCH_TYPE = load_config('scraper/scraper_config.json')

manage_database = ManageDatabase("database/rightmove")
rightmove_scraper = RightMoveScraper(URL)
# TODO: move this to a seperate app file as it is not part of the scraper
send_email = SendEmail('scraper_email/gmail_info.json','Rightmove')
