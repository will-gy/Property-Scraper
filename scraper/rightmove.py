import json
import logging
import random
import re
import time

import requests

from scraper.house_scraper import HouseScraper

logger = logging.getLogger(__name__)

_MIN_DELAY = 2.0
_MAX_DELAY = 5.0


class RightMoveScraper(HouseScraper):
    def _get_page(self, url: str) -> dict:
        """Fetch a search page and return its ``searchResults`` payload."""
        try:
            response = self._session.get(url, timeout=30)
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                response.text,
                re.DOTALL,
            )
            if not match:
                logger.warning(
                    "No __NEXT_DATA__ found for %s (status %s)", url, response.status_code
                )
                return {}
            data = json.loads(match.group(1))
            return data["props"]["pageProps"]["searchResults"]
        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse page %s: %s", url, e)
            return {}
        except requests.RequestException as e:
            logger.warning("Request failed for %s: %s", url, e)
            return {}

    def _page_total(self) -> int:
        page_dict = self._get_page(self._url)
        pagination = page_dict.get("pagination") if page_dict else None
        if not pagination or pagination.get("total") is None:
            logger.warning("No pagination found for %s; assuming 0 pages", self._url)
            return 0
        return pagination.get("total")

    def _iterate_page(self, page_num: int) -> str:
        url = self._url.split("&index=0")
        return f"{url[0]}&index={24 * page_num}{url[1]}"

    @staticmethod
    def _get_price(price: dict) -> float:
        if not price:
            return 0
        if price.get("frequency") == "weekly":
            return round((price.get("amount", 0) * 52) / 12, 2)
        return price.get("amount", 0)

    def _parse_property_info(self, listing: dict) -> dict | None:
        try:
            images = listing.get("propertyImages") or {}
            location = listing.get("location") or {}
            return {
                "id": int(listing.get("id")),
                "price": self._get_price(listing.get("price")),
                "link": f"https://www.rightmove.co.uk{listing.get('propertyUrl')}",
                "beds": listing.get("bedrooms"),
                "address": listing.get("displayAddress"),
                "description": listing.get("summary"),
                "image": images.get("mainImageSrc"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "distance": listing.get("distance") if listing.get("distance") else "N/A",
            }
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("Could not parse property: %s", e)
            return None

    def get_property_info(self) -> None:
        super().get_property_info()

        last_page_num = self._page_total()

        for i in range(0, int(last_page_num)):
            if i > 0:
                time.sleep(random.uniform(_MIN_DELAY, _MAX_DELAY))
            properties = self._get_page(self._iterate_page(i)).get("properties", [])
            for listing in properties:
                parsed = self._parse_property_info(listing)
                if parsed is not None:
                    self._property_list.append(parsed)

        self._property_list = [
            dict(t) for t in {tuple(d.items()) for d in self._property_list}
        ]

    def run(self) -> list:
        self.get_property_info()
        return self._property_list
