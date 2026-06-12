"""SQLite access for the normalised listings schema.

Three tables, linked by the composite key (area, listing_id):
  - ``properties``      static facts about a listing (write-once)
  - ``property_status`` mutable metadata, one row per listing, updated in place
                        (status, availability, last_seen, let_agreed_at)
  - ``prices``          price history — one row per distinct price seen

``get_area_rows`` joins them back into one flat row per price point (newest
first), which is what analytics and the email pipeline consume.
"""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)
#TODO: Migrate to pydantic
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS properties (
        area          TEXT    NOT NULL,
        listing_id    INTEGER NOT NULL,
        channel       TEXT    NOT NULL DEFAULT 'rent',
        beds          TEXT,
        bathrooms     INTEGER,
        property_type TEXT,
        sqft          REAL,
        link          TEXT,
        address       TEXT,
        description   TEXT,
        image         TEXT,
        latitude      REAL,
        longitude     REAL,
        distance      REAL,
        first_listed  DATETIME,
        key_features  TEXT,
        PRIMARY KEY (area, listing_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS property_status (
        area           TEXT    NOT NULL,
        listing_id     INTEGER NOT NULL,
        status         TEXT,
        available_date TEXT,
        last_seen      DATETIME,
        let_agreed_at  DATETIME,
        PRIMARY KEY (area, listing_id),
        FOREIGN KEY (area, listing_id) REFERENCES properties(area, listing_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS prices (
        area       TEXT    NOT NULL,
        listing_id INTEGER NOT NULL,
        price      REAL    NOT NULL,
        timestamp  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (area, listing_id, price),
        FOREIGN KEY (area, listing_id) REFERENCES properties(area, listing_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_prices_area_ts ON prices(area, timestamp);",
)

_PROPERTY_COLUMNS = (
    "area", "listing_id", "channel", "beds", "bathrooms", "property_type", "sqft",
    "link", "address", "description", "image", "latitude", "longitude", "distance",
    "first_listed", "key_features",
)

# Columns returned by get_area_rows, denormalised back to one row per price point.
_AREA_ROWS_SQL = """
    SELECT p.listing_id AS id, pr.price, pr.timestamp,
           p.channel, p.beds, p.bathrooms, p.property_type, p.sqft,
           p.link, p.address, p.description, p.image,
           p.latitude, p.longitude, p.distance, p.first_listed, p.key_features,
           s.status, s.available_date, s.last_seen, s.let_agreed_at
    FROM prices pr
    JOIN properties p USING (area, listing_id)
    LEFT JOIN property_status s USING (area, listing_id)
    WHERE pr.area = ?
    ORDER BY pr.timestamp DESC;
"""


class ManageDatabase:
    def __init__(self, db_path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _cursor(self):
        """Yield a cursor, committing on success and always closing the connection."""
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
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
            for statement in _SCHEMA:
                cursor.execute(statement)

    def insert_listings(self, area: str, channel: str, rows: list[dict]) -> None:
        """Persist a scrape: static facts (once), mutable status (upsert), price (if new).

        A re-sighting updates ``last_seen``/``status`` and stamps ``let_agreed_at``
        the first time a listing is observed flipping to 'let_agreed'. A new price
        adds a row to ``prices``, preserving history.
        """
        if not rows:
            return
        seen_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        payload = [
            {**row, "listing_id": row["id"], "area": area, "channel": channel, "last_seen": seen_at}
            for row in rows
        ]
        prop_cols = ", ".join(_PROPERTY_COLUMNS)
        prop_vals = ", ".join(f":{c}" for c in _PROPERTY_COLUMNS)

        with self._cursor() as cursor:
            cursor.executemany(
                f"INSERT OR IGNORE INTO properties ({prop_cols}) VALUES ({prop_vals});",
                payload,
            )
            cursor.executemany(
                "INSERT INTO property_status (area, listing_id, status, available_date, last_seen) "
                "VALUES (:area, :listing_id, :status, :available_date, :last_seen) "
                "ON CONFLICT(area, listing_id) DO UPDATE SET "
                "  status = excluded.status, "
                "  available_date = excluded.available_date, "
                "  last_seen = excluded.last_seen, "
                "  let_agreed_at = CASE "
                "    WHEN COALESCE(property_status.status, '') != 'let_agreed' "
                "         AND excluded.status = 'let_agreed' "
                "    THEN excluded.last_seen ELSE property_status.let_agreed_at END;",
                payload,
            )
            cursor.executemany(
                "INSERT OR IGNORE INTO prices (area, listing_id, price) "
                "VALUES (:area, :listing_id, :price);",
                payload,
            )

    def get_area_rows(self, area: str) -> list[sqlite3.Row]:
        """Every stored price point for an area, joined with property facts + status,
        newest first. One fetch powers analytics, new/updated detection and history."""
        with self._cursor() as cursor:
            cursor.execute(_AREA_ROWS_SQL, (area,))
            return cursor.fetchall()
