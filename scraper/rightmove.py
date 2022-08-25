import requests
import json
from collections import namedtuple
from bs4 import BeautifulSoup
from typing import List, NamedTuple
from house_scraper import HouseScraper

class RightMoveScraper(HouseScraper):
    def __init__(self, url) -> None:
        super().__init__(url)
        self._url_page_list

        self._property_info = namedtuple(
            'House', 
            ['id', 'price', 'link', 'beds', 'address', 'description', 'img']
            )
        # Initialise bs4
        # self._soup = None

    def _page_total(self):
        """Retrieve page total
        """        
        page_html = requests.get(
            self._url
        )
        try:
            page_json = json.loads(page_html.content)
        except ValueError as e:
            print(e)
        try:
            return page_json.get('pagination').get('total')
        except KeyError as e:
            print(e)
        
    
    def _iterate_page(self, page_num):
        return f"{self._url}&index={24*page_num}"

    def _parse_property_info(self, listing) -> NamedTuple:
        try:
            return self._property_info(
                int(listing.get('id').replace('property-', '')), # ID
                float(
                    listing.find('span', 'propertyCard-priceValue').
                    text.replace('pcm', '').replace('£', '').replace(',', '').strip() # Price
                    ),
                listing.find('a', class_='propertyCard-link').get('href'), # Link
                listing.find('h2', 'propertyCard-title').text.strip(), # Beds
                listing.find('address', class_='propertyCard-address').text.strip(), # Address
                listing.find('div', class_='propertyCard-description').text.strip(), # Description
                listing.find('div', class_='propertyCard-img').find('img').get('src') # Image
                )
        except ValueError as e:
                    print(f"could not find property: {e}")

    
    def get_page_list(self) -> List:
        # cookies={"pwv":"2",
        # "pws":"functional|analytics|content_recommendation|targeted_advertising|social_media"
        # }
        # page = requests.get(self._url)

        # soup = BeautifulSoup(page.content, 'html.parser')
        # page_nums = soup.find_all('span', 'pagination-pageInfo')

        # print("page_nums")
        # print(page_nums[-1].text)
        # last_page_num = page_nums[-1].text

        # print(f"page nums {page_nums}")
        last_page_num = self._page_total()

        for i in range(1, int(last_page_num)):
            self._url_page_list.append(self._iterate_page(i))

    def get_property_info(self):
        super().get_property_info()
        for url in self._url_page_list:
            page = requests.get(url)

            soup = BeautifulSoup(page.content, 'html.parser')
            property_list = soup.find('div', class_='l-searchResults')

            property_list_items = property_list.find_all('div', class_='l-searchResult')

            for listing in property_list_items:
                house = self._parse_property_info(listing)

                # Assumption that top result will always be a paid promoted house
                if house.id != 0:
                    self._property_list.append({
                        'id': house.id,
                        'price': house.price,
                        'link': f'https://www.rightmove.co.uk{house.link}',
                        'beds': house.beds,
                        'address': house.address,
                        'description': house.description,
                        'image': house.img
                        })
        

        self._property_list = [dict(t) for t in {tuple(d.items()) for d in self._property_list}]

    def run(self) -> List:
        self.get_page_list()
        self.get_property_info()
        return self._property_list

rightmove_scraper = RightMoveScraper(
    'https://www.rightmove.co.uk/api/_search?locationIdentifier=STATION%5E2162&minBedrooms=1&maxPrice=1750\
        &numberOfPropertiesPerPage=24&radius=3.0&sortType=6&index=0&includeLetAgreed=false&viewType=LIST&\
            channel=RENT&areaSizeUnit=sqft&currencyCode=GBP&isFetching=false&viewport='
)

rightmove_scraper.retrieve_data()