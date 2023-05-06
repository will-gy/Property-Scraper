import sqlite3
from typing import List

class ManageDatabase:
    def __init__(self, db_name) -> None:
        self._db_name = db_name

    def create_db(self):
        sqlite3.connect(f"{self._db_name}.db")

    def _connect_db(self):
        connection_obj = sqlite3.connect(f"{self._db_name}.db")
        cursor = connection_obj.cursor()
        return connection_obj, cursor

    def create_table(self, table_name):
        _, cursor = self._connect_db()
        table = (
            f"CREATE TABLE {table_name}"
            f"(ID INT NOT NULL,"
            f"TIMESTAMP DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            f"PRICE FLOAT NOT NULL,"
            f"BEDS TEXT,"
            f"LINK TEXT,"
            f"ADDRESS TEXT,"
            f"DESCRIPTION TEXT,"
            f"IMAGE TEXT,"
            f"UNIQUE(ID,PRICE))"
            )
        cursor.execute(table)

    def update_house(self, table_name, data):
        connection_obj, cursor = self._connect_db()
        for house in data:
            cursor.execute(
                (f"INSERT OR IGNORE INTO {table_name} "
                f"(ID, PRICE, BEDS, LINK, ADDRESS, DESCRIPTION, IMAGE)"
                f" VALUES (:id, :price, :beds, :link, :address, :description, :image);"),
                house
            )
        connection_obj.commit()

    def get_record_n_hours(self, table_name, hour=24)-> List:
        _, cursor = self._connect_db()

        cursor.execute(
            f"""SELECT DISTINCT ID FROM {table_name}
            WHERE TIMESTAMP >= datetime('now', '-{hour} hours') AND TIMESTAMP < datetime('now');"""
        )
        return cursor.fetchall()

    def get_record(self, table_name, house_id):
        _, cursor = self._connect_db()

        cursor.execute(
            f"""SELECT TIMESTAMP, PRICE, BEDS, LINK, ADDRESS, DESCRIPTION, IMAGE FROM {table_name} 
            WHERE ID={house_id} ORDER BY TIMESTAMP DESC;"""
        )
        return cursor.fetchall()
