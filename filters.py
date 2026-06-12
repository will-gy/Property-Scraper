"""Pure listing filters applied at email time (no DB / IO).

Searches are scraped wide so the database holds the whole local market; these
functions narrow that down to what each digest should include. Because they run
at email time, changing a filter never requires a re-scrape.
"""
from collections.abc import Mapping

from config_models import FilterConfig


def _coerce_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def passes_filters(listing: Mapping, filters: FilterConfig) -> bool:
    """Return True if a listing row satisfies the configured filters.

    The row is expected to expose ``price``, ``beds`` and ``distance``.
    Rules for missing/unparseable values:
      - beds: if a bed bound is set and beds can't be parsed, the listing is
        excluded (we can't confirm it qualifies).
      - distance: if it can't be parsed it is treated as unknown and passes a
        ``max_distance`` bound (radius is already constrained by the search URL).
    """
    price = _coerce_float(listing["price"])
    if price is not None:
        if filters.min_price is not None and price < filters.min_price:
            return False
        if filters.max_price is not None and price > filters.max_price:
            return False

    if filters.min_beds is not None or filters.max_beds is not None:
        beds = _coerce_int(listing["beds"])
        if beds is None:
            return False
        if filters.min_beds is not None and beds < filters.min_beds:
            return False
        if filters.max_beds is not None and beds > filters.max_beds:
            return False

    if filters.max_distance is not None:
        distance = _coerce_float(listing["distance"])
        if distance is not None and distance > filters.max_distance:
            return False

    return True
