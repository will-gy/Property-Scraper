from typing import Tuple
import argparse
import json

from app import manage_database
from scraper_email.send_email import SendEmail


# Parse cmd line args
parser = argparse.ArgumentParser(description='Send Scraper email')
parser.add_argument(
    '--config_path', type=str, help='config file path to load',
    default='scraper_email/config/gmail_info.json'
    )
args = parser.parse_args()


def load_config(config_file: str) -> Tuple[str, str, int]:
    with open(config_file) as f:
        config = json.load(f)
        table_name = config.get('table_name', '')
        search_type = config.get('search_type', ''),
        time_period = config.get('time_period_hours', 24)
    return table_name, search_type, time_period


def format_email_data(house_ids: list, database_table: str) -> Tuple[list, list]:
    new_house = []
    updated_house = []
    for new_id in house_ids:
        house_data = manage_database.get_record(database_table, new_id[0])
        if len(house_data) > 1:
            updated_house.append(
                _gen_update_dict(house_data)
            )
        else:
            new_house.append(
                _gen_new_dict(house_data)
            )
    return new_house, updated_house

def _gen_new_dict(house_data: list) -> dict:
    return {
        'timestamp': house_data[0][0],
        'price': house_data[0][1],
        'bedroom': house_data[0][2],
        'link': house_data[0][3],
        'address': house_data[0][4],
        'description': house_data[0][5],
        'image': house_data[0][6],
        'distance': house_data[0][7],
    }

def _gen_update_dict(house_data: list) -> dict:
    updated_price = house_data[0][1]
    old_price = house_data[1][1]
    price_history = [(house_data[i][0], house_data[i][1]) for i in range(len(house_data))]

    return {
        'timestamp': house_data[0][0],
        'updated_price': updated_price,
        'old_price': old_price,
        'price_change': ((updated_price - old_price)/old_price)*100,
        'price_history': price_history,
        'bedroom': house_data[0][2],
        'link': house_data[0][3],
        'address': house_data[0][4],
        'description': house_data[0][5],
        'image': house_data[0][6],
        'distance': house_data[0][7],
    }

if __name__ == '__main__':
    # Load config
    database_table, search_type, time_period = load_config(args.config_path)
    house_ids = manage_database.get_record_n_hours(database_table, hour=time_period)
    new_property, updated_property = format_email_data(house_ids, database_table)

    send_email = SendEmail(
        args.config_path, 'Rightmove', True if search_type == 'rent' else False
        )
    send_email.update_property = updated_property
    send_email.new_property = new_property
    send_email.send_email()
