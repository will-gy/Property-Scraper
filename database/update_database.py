import sqlite3

class ManageDatabase:
    def __init__(self, db_name) -> None:
        self._db_name = db_name

    def create_db(self):
        sqlite3.connect(f"{self._db_name}.db")

    def create_table(self, table_name):
        connection_obj = sqlite3.connect(f"{self._db_name}.db")
        cursor = connection_obj.cursor()
        cursor.execute(f"DROP TABLE {table_name}")
        table = (
            f"CREATE TABLE {table_name}"
            f"(ID INT NOT NULL,"
            f"PRICE FLOAT NOT NULL,"
            f"BEDS CHAR,"
            f"LINK CHAR"
            f"ADDRESS CHAR,"
            f"DESCRIPTION CHAR,"
            f"IMAGE CHAR,"
            f"UNIQUE(ID,PRICE))"
            )
        cursor.execute(table)

    def update_house(self, table_name, data):
        connection_obj = sqlite3.connect(f"{self._db_name}.db")
        cursor = connection_obj.cursor()
        for house in data:
            # house_str = (f"INSERT INTO {table_name} "
            #     f"(ID, PRICE, BEDS, ADDRESS, DESCRIPTION, IMAGE)"
            #     f"VALUES (:id, :price, :beds, :address, :description, :image);"),
            #     f"{house}"
            cursor.execute(
                (f"INSERT INTO {table_name} "
                f"(ID, PRICE, BEDS, ADDRESS, DESCRIPTION, IMAGE)"
                f"VALUES (:id, :price, :beds, :address, :description, :image);"),
                house
            )


