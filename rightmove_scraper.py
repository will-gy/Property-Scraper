'''
TODO:
Property scraper to track price movements and new houses given a set criteria.
Run from within summary_email.py

- Have an initialisation mode which creates the csv from scratch, given a certain name
- Add the ability to take the url as an arugment to make it more modular

- When comparing property, first check if the id (in link) is in archive, if not add to archive
  and append to dict of new properties for email
  - Update date of last check of property to ensure it is up to date

- If property is in archive, then check if price has changed:
  - If price has stayed the same then don't add to archive & don't append to email
  - If price has decreased then append to decreased dict and calculate percentage decrease
  - If price has increased then update price in archive and do not email

-Create email that sends updates
-Add functionality to track house prices over time 
-Ensure logging is thorough

'''
import requests
import csv
from tempfile import NamedTemporaryFile
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import pyppdf.patch_pyppeteer
from requests_html import HTMLSession


def get_page_number(soup, url_first_page):
    """Gets urls of every page for a given search

    Args:
        soup (bs4): bs4 web scraper object
        url_first_page (str): url for page 1 of search

    Returns:
        list: list of page urls
    """    
    page_url_list = [url_first_page]
    page_nums = soup.find('select', 'pagination-dropdown')
    last_page_num = page_nums.find_all('option')[-1].text
    for i in range(1, int(last_page_num)):
        url = f'https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=STATION%5E9485&maxBedrooms=2&minBedrooms=2&maxPrice=2000&minPrice=1200&radius=1.0&index={24*i}&propertyTypes=&includeLetAgreed=false&mustHave=&dontShow=&furnishTypes=&keywords='
        page_url_list.append(url)
    
    return page_url_list


def get_property_info(soup, page_url_list):
    """Scrapes property data for each search listing on a given page

    Args:
        soup (bs4): See above
        page_url_list (list): See above

    Returns:
        list: list of dicts. Each dict is an individual property listing
    """    
    property_dict_list = []
    for url in page_url_list:
        page = requests.get(url)

        soup = BeautifulSoup(page.content, 'html.parser')
        property_list = soup.find('div', class_='l-searchResults')

        property_list_items = property_list.find_all('div', class_='l-searchResult')

        for listing in property_list_items:
            try:
                property_id = int(listing.get('id').replace('property-', ''))
                property_price = float(listing.find('span', 'propertyCard-priceValue').text.replace('pcm', '').replace('£', '').replace(',', '').strip())
                property_link = listing.find('a', class_='propertyCard-link').get('href')
                num_beds = listing.find('h2', 'propertyCard-title').text.strip()
                property_address = listing.find('address', class_='propertyCard-address').text.strip()
                property_description= listing.find('div', class_='propertyCard-description').text.strip()
                property_img = listing.find('div', class_='propertyCard-img').find('img').get('src')

                if property_id != 0:
                    property_dict_list.append({
                        'id': property_id,
                        'price': property_price,
                        'link': f'https://www.rightmove.co.uk{property_link}',
                        'beds': num_beds,
                        'address': property_address,
                        'description': property_description,
                        'image': property_img
                        })
                    
            except ValueError as e:
                print(f"could not find property: {e}")
    
    property_dict_list = [dict(t) for t in {tuple(d.items()) for d in property_dict_list}]
    return property_dict_list
    

def create_file(file_name):
    """Creates csv file to store property data

    Args:
        file_name (str): File name for csv archive
    """    
    with open(fr'F:\house_scraper\archive\{file_name}.csv', mode='w') as csv_file:
        property_file = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        property_file.writerow(['id', 'pcm','address', 'link', 'updated'])


def manage_csv(property_dict_list, csv_name):
    """Opens property archive csv and manages both the entry of new listings
    and updating existing listing prices

    Args:
        property_dict_list (list): See above
        csv_name (str): Name of csv archive

    Returns:
        list: lists containing updated and new listings formatted for email
    """    
    with open(fr'/home/pi/house_scraper/archive/{csv_name}.csv', newline='') as csv_file:
        reader = csv.reader(csv_file, delimiter=',', quotechar='"')

        archive_property_list = []
        property_id_list = []
        for row in reader:
            try:
                print(row)
                archived_id = int(row[0])
                archived_price = float(row[1])
                property_id_list.append(archived_id)
                archive_property_list.append(
                    {'id':int(archived_id),
                    'price': float(archived_price)})
            except IndexError as e:
                print(f"could not find index {e}")

        updated_property_list = []
        for property_dict in property_dict_list:
            try:
                scraped_id = int(property_dict['id'])
                scraped_price = float(property_dict['price'])
            except ValueError as e:
                print(f"error finding id or price: {e}")
            for archived_property in archive_property_list:
                try:
                    if scraped_id == archived_property['id']:
                        if scraped_price < archived_property['price']:
                            updated_property_list.append({
                                'id': scraped_id,
                                'price_change': abs(float((scraped_price - archived_property['price'])/archived_property['price']*100)),
                                'updated_price': scraped_price,
                                'old_price': archived_property['price'],
                                'address': property_dict['address'],
                                'link': property_dict['link'],
                                'image': property_dict['image'],
                                'description' : property_dict['description']
                            }
                                )
                except ValueError as e:
                    print(f"error finding id or price: {e}")

        new_property_list = []
        for property_dict in property_dict_list:
            scraped_id = int(property_dict['id'])
            if scraped_id not in property_id_list:
                new_property_list.append(property_dict)

        return updated_property_list, new_property_list


def write_updated_entry(csv_name, updated_property_list):
    """Updates existing entries in archive csv. Updates property price and last updated date

    Args:
        csv_name (str): See above
        updated_property_list (list): See above
    """    
    today_date = datetime.now()
    day_str = today_date.strftime("%d/%m/%Y, %H:%M")
    file_path = fr'/home/pi/house_scraper/archive/{csv_name}.csv'

    if len(updated_property_list):
        tempfile = NamedTemporaryFile(mode='w', delete=False, newline='')
        with open(file_path, 'r', newline='') as csvfile, tempfile:
            reader = csv.reader(csvfile, delimiter=',')
            writer = csv.writer(tempfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            written_row_updates = []
            written_rows = []
            try:
                for row in reader:
                    for property_dict in updated_property_list:
                    
                        if property_dict['id'] == int(row[0]):
                            writer.writerow(
                                [int(property_dict['id']), 
                                float((property_dict['updated_price'])),
                                property_dict['address'],
                                property_dict['link'], 
                                day_str]
                                )
                            written_row_updates.append(int(property_dict['id']))
                        else:
                            if int(row[0]) not in written_row_updates:
                                if int(row[0]) not in written_rows:
                                    written_rows.append(int(row[0]))
                                    writer.writerow(row)
            except IndexError as e:
                print(f'error finding index {e}')
        if len(updated_property_list):
            shutil.move(tempfile.name, file_path)


def write_new_entry(csv_name, new_property_list):
    """Adds new entries to archive csv

    Args:
        csv_name (str): See above
        new_property_list (list): See above
    """    
    today_date = datetime.now()
    day_str = today_date
    if len(new_property_list):
        with open(fr'/home/pi/house_scraper/archive/{csv_name}.csv', mode='a', newline='') as csv_file:
            property_file = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            for property_dict in new_property_list:
                property_file.writerow(
                    [str(property_dict['id']), 
                    str(property_dict['price']),
                    property_dict['address'],
                    property_dict['link'], day_str])


def clean_csv(csv_name):
    """Removes any duplicate entries from archive csv due to bug.
    Janky workaround to prevent summary email from listing duplicates.

    Args:
        csv_name (str): See above
    """    
    file_name = fr'/home/pi/house_scraper/archive/{csv_name}.csv'
    cleaned_file = fr'/home/pi/house_scraper/archive/{csv_name}_cleaned.csv'
    
    df = pd.read_csv(file_name, index_col=0, names=['price', 'address', 'link', 'date'])

    duplicate_indexes = df[df.index.duplicated()].index
    dup_list = list(set(duplicate_indexes.tolist()))

    df_dup_dropped = df.drop(duplicate_indexes)
    df_dup_dropped['date'] = pd.to_datetime(df_dup_dropped.date)

    countvar = 0
    df_dup = df[df.index.duplicated(keep=False)]
    df_dup['date'] = pd.to_datetime(df_dup.date)
    df_dup = df_dup.sort_values(by=['date'])
 
    df_dup_removed = pd.DataFrame()
    for prop_id in dup_list:
        df_dup_subset = df_dup.loc[int(prop_id)]
        print(df_dup_subset)
        df_dup_removed = df_dup_removed.append(df_dup_subset[-1:])
    
    df_output = df_dup_dropped.append(df_dup_removed)
    df_output.to_csv(cleaned_file, index=True, header=False)

    shutil.move(cleaned_file, file_name)


def manage_rightmove(csv_name, new_file_name=None):
    """Main function to manage property scraping

    Args:
        csv_name (str): See above
        new_file_name (csv property archive if not already existing, optional): [description]. Defaults to None.

    Returns:
        list: lists containing updated and new listings formatted for email
    """    
    clean_csv(csv_name)

    url_first_page = 'https://www.rightmove.co.uk/property-to-rent/find.html?minBedrooms=2&keywords=&dontShow=houseShare%2Cretirement&channel=RENT&index=0&mustHave=garden&retirement=false&houseFlatShare=false&maxBedrooms=2&letFurnishType=furnished&sortType=6&minPrice=1500&viewType=LIST&maxPrice=2000&radius=0.0&propFeature=Garden&locationIdentifier=USERDEFINEDAREA%5E%7B%22id%22%3A6403162%7D'

    session = HTMLSession()
    r = session.get(url_first_page)
    r.html.render(sleep=5)

    soup = BeautifulSoup(r.html.raw_html, 'html.parser')

    # Remove featured property
    page_url_list = get_page_number(soup, url_first_page)

    property_dict_list = get_property_info(soup, page_url_list)

    if new_file_name is not None:
        create_file(new_file_name)
        csv_name = new_file_name

    updated_property_list, new_property_list = manage_csv(property_dict_list, csv_name)
    
    write_updated_entry(csv_name, updated_property_list)
    write_new_entry(csv_name, new_property_list)

    return updated_property_list, new_property_list

