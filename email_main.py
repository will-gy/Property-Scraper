from typing import Tuple
import argparse
import json
import logging

from app import manage_database
from logging_setup import setup_logging
from scraper_email.send_email import SendEmail

logger = logging.getLogger(__name__)


def load_config(config_file: str) -> Tuple[str, str, int, str]:
    with open(config_file) as f:
        config = json.load(f)
        table_name = config.get('table_name', '')
        search_type = config.get('search_type', '')
        time_period = config.get('time_period_hours', 24)
        subject_tag = config.get('subject_tag', '')
    return table_name, search_type, time_period, subject_tag


def format_email_data(house_ids: list, database_table: str) -> Tuple[list, list]:
    new_house = []
    updated_house = []
    for new_id in house_ids:
        house_data = manage_database.get_record(database_table, new_id['ID'])
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
    row = house_data[0]
    return {
        'timestamp': row['TIMESTAMP'],
        'price': row['PRICE'],
        'bedroom': row['BEDS'],
        'link': row['LINK'],
        'address': row['ADDRESS'],
        'description': row['DESCRIPTION'],
        'image': row['IMAGE'],
        'distance': row['DISTANCE'],
    }


def _gen_update_dict(house_data: list) -> dict:
    latest = house_data[0]
    previous = house_data[1]
    updated_price = latest['PRICE']
    old_price = previous['PRICE']
    price_history = [(row['TIMESTAMP'], row['PRICE']) for row in house_data]

    return {
        'timestamp': latest['TIMESTAMP'],
        'updated_price': updated_price,
        'old_price': old_price,
        'price_change': ((updated_price - old_price) / old_price) * 100,
        'price_history': price_history,
        'bedroom': latest['BEDS'],
        'link': latest['LINK'],
        'address': latest['ADDRESS'],
        'description': latest['DESCRIPTION'],
        'image': latest['IMAGE'],
        'distance': latest['DISTANCE'],
    }


def _gen_subject(subject_tag: str, new_property: list, updated_property: list) -> str:
    new_count = len(new_property) if new_property else 0
    update_count = len(updated_property) if updated_property else 0
    return f'{subject_tag} Property Scraper: {new_count} New & {update_count} Price Updates'


if __name__ == '__main__':
    setup_logging()

    parser = argparse.ArgumentParser(description='Send Scraper email')
    parser.add_argument(
        '--config_path', type=str, help='config file path to load',
        default='scraper_email/config/gmail_info.json'
    )
    args = parser.parse_args()

    database_table, search_type, time_period, subject_tag = load_config(args.config_path)
    house_ids = manage_database.get_record_n_hours(database_table, hour=time_period)
    new_property, updated_property = format_email_data(house_ids, database_table)

    send_email = SendEmail(
        args.config_path, 'Rightmove', search_type == 'rent'
    )
    send_email.update_property = updated_property
    send_email.new_property = new_property
    send_email.subject = _gen_subject(subject_tag, new_property, updated_property)
    send_email.send_email()
    logger.info(
        "Email sent for %s: %s new, %s updated",
        database_table, len(new_property), len(updated_property)
    )
