"""
Base class for housing web scrapers

codeauthor::William Yelverton
"""
from abc import ABC, abstractmethod
from typing import List

class HouseScraper(ABC):
    def __init__(self, url):
        self._url = url
        self._url_page_list = [url]
        self._property_list = []

    # @abstractmethod
    # def get_page_list(self) -> List:
    #     pass

    @abstractmethod
    def get_property_info(self):
        pass
