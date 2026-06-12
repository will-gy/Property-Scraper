"""SQLite access for the unified ``listings`` table.

One table holds every area's listings, keyed by ``UNIQUE(area, id, price)`` so a
price change for a listing is stored as a new row — preserving full price history
while ignoring unchanged re-scrapes.
"""
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# TODO: Migrate to pydantic
_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    area        TEXT    NOT NULL,
    channel     TEXT    NOT NULL DEFAULT 'rent',
    id          INTEGER NOT NULL,
    timestamp   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    price       REAL    NOT NULL,
    beds        TEXT,
    link        TEXT,
    address     TEXT,
    description TEXT,
    image       TEXT,
    latitude    REAL,
    longitude   REAL,
    distance    REAL,
    UNIQUE(area, id, price)
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_listings_area_ts ON listings(area, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_listings_area_id ON listings(area, id);",
)

_INSERT_COLUMNS = (
    "area", "channel", "id", "price", "beds", "link", "address",
    "description", "image", "latitude", "longitude", "distance",
)


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

    def init_schema(self) -> None:
        with self._cursor() as cursor:
            cursor.execute(_SCHEMA)
            for statement in _INDEXES:
                cursor.execute(statement)

    def insert_listings(self, area: str, channel: str, rows: list[dict]) -> None:
        """Insert scraped listings for an area (ignoring unchanged duplicates)."""
        if not rows:
            return
        placeholders = ", ".join(f":{col}" for col in _INSERT_COLUMNS)
        columns = ", ".join(_INSERT_COLUMNS)
        payload = [{**row, "area": area, "channel": channel} for row in rows]
        with self._cursor() as cursor:
            cursor.executemany(
                f"INSERT OR IGNORE INTO listings ({columns}) VALUES ({placeholders});",
                payload,
            )

    def get_changed_ids(self, area: str, hours: int = 24) -> list[int]:
        """Listing ids for an area with a row recorded in the last ``hours``."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT id FROM listings "
                "WHERE area = ? AND timestamp >= datetime('now', ?);",
                (area, f"-{int(hours)} hours"),
            )
            return [row["id"] for row in cursor.fetchall()]

    def get_listing_history(self, area: str, listing_id: int) -> list[sqlite3.Row]:
        """All stored rows for one listing, newest first (full price history)."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT timestamp, price, beds, link, address, description, image, distance "
                "FROM listings WHERE area = ? AND id = ? ORDER BY timestamp DESC;",
                (area, listing_id),
            )
            return cursor.fetchall()
