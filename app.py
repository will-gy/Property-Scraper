from database.update_database import ManageDatabase
from scraper.rightmove import RightMoveScraper
from scraper_email.send_email import SendEmail

# TODO: Put all this in config
manage_database = ManageDatabase("database/rightmove")

rightmove_scraper = RightMoveScraper(
    'https://www.rightmove.co.uk/api/_search?locationIdentifier=STATION%5E2162&minBedrooms=1&maxPrice=1750'\
        '&numberOfPropertiesPerPage=24&radius=3.0&sortType=6&index=0&includeLetAgreed=false&viewType=LIST&'\
            'channel=RENT&areaSizeUnit=sqft&currencyCode=GBP&isFetching=false&viewport='
)

send_email = SendEmail('scraper_email/gmail_info.json','Rightmove')

DATABASE_TABLE = 'Clapham3Mile'