import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


class ManageDatabase:
    def __init__(self, db_path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _cursor(self):
        """Yield a cursor, committing on success and always closing the connection."""
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_table(self, table_name: str) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE IF NOT EXISTS "{table_name}" ('
                "ID INT NOT NULL,"
                "TIMESTAMP DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                "PRICE FLOAT NOT NULL,"
                "BEDS TEXT,"
                "LINK TEXT,"
                "ADDRESS TEXT,"
                "DESCRIPTION TEXT,"
                "IMAGE TEXT,"
                "LATTITUDE FLOAT,"
                "LONGITUDE FLOAT,"
                "DISTANCE FLOAT,"
                "UNIQUE(ID,PRICE))"
            )

    def update_house(self, table_name: str, data: list) -> None:
        with self._cursor() as cursor:
            cursor.executemany(
                f'INSERT OR IGNORE INTO "{table_name}" '
                "(ID, PRICE, BEDS, LINK, ADDRESS, DESCRIPTION, IMAGE, LATTITUDE, LONGITUDE, DISTANCE)"
                " VALUES (:id, :price, :beds, :link, :address, :description, :image,"
                " :latitude, :longitude, :distance);",
                data,
            )

    def get_record_n_hours(self, table_name: str, hour: int = 24) -> list:
        with self._cursor() as cursor:
            cursor.execute(
                f'SELECT DISTINCT ID FROM "{table_name}" '
                "WHERE TIMESTAMP >= datetime('now', ?) AND TIMESTAMP < datetime('now');",
                (f"-{int(hour)} hours",),
            )
            return cursor.fetchall()

    def get_record(self, table_name: str, house_id: int) -> list:
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT TIMESTAMP, PRICE, BEDS, LINK, ADDRESS, DESCRIPTION, IMAGE, DISTANCE "
                f'FROM "{table_name}" WHERE ID=? ORDER BY TIMESTAMP DESC;',
                (house_id,),
            )
            return cursor.fetchall()
