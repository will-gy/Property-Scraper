"""
Base class for housing web scrapers

codeauthor::William Yelverton
"""
from abc import ABC, abstractmethod

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


class HouseScraper(ABC):
    def __init__(self, url):
        self._url = url
        self._url_page_list = [url]
        self._property_list = []
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    @abstractmethod
    def get_property_info(self):
        pass
