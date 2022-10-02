from typing import Dict, Union
from app import manage_database, send_email, DATABASE_TABLE

def format_email_data(house_ids)->Union[Dict, Dict]:
    new_house = []
    updated_house = []
    for new_id in house_ids:
        house_data = manage_database.get_record(DATABASE_TABLE, new_id[0])
        if len(house_data) > 1:
            updated_house.append(
                _gen_update_dict(house_data)
            )
        else:
            new_house.append(
                _gen_new_dict(house_data)
            )
    
    return new_house, updated_house

def _gen_new_dict(house_data)-> Dict:
    return {
        'timestamp': house_data[0][0],
        'price': house_data[0][1],
        'bedroom': house_data[0][2],
        'link': house_data[0][3],
        'address': house_data[0][4],
        'description': house_data[0][5],
        'image': house_data[0][6]
    }

def _gen_update_dict(house_data)-> Dict:
    updated_price = house_data[0][1]
    old_price = house_data[1][1]
    price_history = [(house_data[i][0], house_data[i][1]) for i in range(len(house_data))]
    # TODO: Assumed DESC order, enforce this in sql query
    return {
        'timestamp': house_data[0][0],
        'updated_price': updated_price,
        'old_price': old_price,
        'price_change': ((old_price - updated_price)/old_price)*100,
        'price_history': price_history,
        'bedroom': house_data[0][2],
        'link': house_data[0][3],
        'address': house_data[0][4],
        'description': house_data[0][5],
        'image': house_data[0][6]
    }

if __name__ == '__main__':
    house_ids = manage_database.get_record_n_hours(DATABASE_TABLE, hour=24)
    new_property, updated_property = format_email_data(house_ids)

    send_email.update_property = updated_property
    send_email.new_property = new_property
    send_email.send_email()
