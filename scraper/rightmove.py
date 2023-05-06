import json

import requests

from scraper.house_scraper import HouseScraper


class RightMoveScraper(HouseScraper):
    def __init__(self, url: str) -> None:
        super().__init__(url)
        self._url_page_list

    @staticmethod
    def __get_page(url) -> dict:
        try:
            page_html = requests.get(url)
            return json.loads(page_html.content)
        except ValueError as e:
            print(e)
            return {}

    def _page_total(self) -> int:
        """Retrieve page total
        """
        page_dict = self.__get_page(self._url)
        try:
            return page_dict.get('pagination').get('total')
        except KeyError as e:
            print(e)
            raise e

    def _iterate_page(self, page_num: int) -> str:
        url = self._url.split('&index=0')
        return f"{url[0]}&index={24*page_num}{url[1]}"

    @staticmethod
    def _get_pcm(price: dict) -> float:
        if price.get('frequency') == 'weekly':
            return round((price.get('amount', 0) *52) / 12, 2)
        return price.get('amount', 0)

    def _parse_property_info(self, listing: dict) -> dict[str, int |float | str | None] | None:
        try:
            return {
                'id': int(listing.get('id')),
                'price': self._get_pcm(listing.get('price')),
                'link': f"https://www.rightmove.co.uk{listing.get('propertyUrl')}",
                'beds': listing.get('bedrooms'),
                'address': listing.get('displayAddress'),
                'description': listing.get('summary'),
                'image': listing.get('propertyImages').get('mainImageSrc')
                }
        except ValueError as e:
            print(f"could not find property: {e}")
            return None


    def get_property_info(self):
        super().get_property_info()

        last_page_num = self._page_total()

        for i in range(0, int(last_page_num)):
            try:
                page_dict = self.__get_page(self._iterate_page(i)).get('properties', [])
            except KeyError as e:
                print(e)
                continue
            for listing in page_dict:
                self._property_list.append(
                    self._parse_property_info(listing)
                    )

        self._property_list = [
            dict(t) for t in {tuple(d.items()) for d in self._property_list}
            ]

    def run(self) -> list:
        self.get_property_info()
        return self._property_list
