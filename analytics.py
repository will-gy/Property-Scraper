"""Per-area market analytics computed from stored listing rows (pure, no IO).

A single list of rows for an area (every price point, newest first) powers
everything: the active market snapshot (latest *available* row per id), price
distribution by bedroom, trends, value ratings, and let-pace (how fast listings
get let, inferred from observed 'Let agreed' status flips).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# Value rating tiers: fraction above/below the area median for the listing's basis.
_GREAT_VALUE = -0.15
_GOOD_VALUE = -0.05
_PRICEY = 0.05

_TREND_WEEKS = 8
_LET_PACE_WINDOW_DAYS = 60


# coercion / parsing helpers
def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_BAND_ORDER = ["Studio", "1 bed", "2 bed", "3 bed", "4+ bed"]


def _bed_band(beds) -> str | None:
    b = _to_int(beds)
    if b is None:
        return None
    if b <= 0:
        return "Studio"
    if b >= 4:
        return "4+ bed"
    return f"{b} bed"


def _status(row) -> str:
    try:
        return (row["status"] or "available")
    except (IndexError, KeyError):
        return "available"


def _week_start(dt: datetime):
    d = dt.date()
    return d - timedelta(days=d.weekday())


def _fmt_week(week_start) -> str:
    return f"{week_start.day} {week_start.strftime('%b')}"


@dataclass
class BedStat:
    band: str
    count: int
    median: float
    avg: float
    minimum: float
    maximum: float


@dataclass
class Bar:
    label: str
    value: float


@dataclass
class AreaAnalytics:
    channel: str
    active: int = 0
    new_count: int = 0
    reduced_count: int = 0
    increased_count: int = 0
    price_by_bed: list[BedStat] = field(default_factory=list)
    median_by_band: dict[str, float] = field(default_factory=dict)
    prices_by_band: dict[str, list[float]] = field(default_factory=dict)
    median_price_per_bed: float | None = None
    median_price_per_sqft: float | None = None
    band_30d_low: dict[str, float] = field(default_factory=dict)
    pct_reduced: float = 0.0
    price_trend: list[Bar] = field(default_factory=list)
    price_trend_pct_30d: float | None = None
    new_listings_trend: list[Bar] = field(default_factory=list)
    let_pace_days: int | None = None
    let_pace_sample: int = 0

# computation
def _latest_per_listing(rows) -> dict:
    """rows are newest-first, so the first row seen per id is its latest."""
    latest: dict = {}
    for row in rows:
        latest.setdefault(row["id"], row)
    return latest


def _history_by_id(rows) -> dict[int, list]:
    history: dict[int, list] = defaultdict(list)
    for row in rows:  # newest-first preserved
        history[row["id"]].append(row)
    return history


def compute(rows, channel: str, window_hours: int = 24) -> AreaAnalytics:
    latest = _latest_per_listing(rows)
    history = _history_by_id(rows)
    active = {i: r for i, r in latest.items() if _status(r) == "available"}

    a = AreaAnalytics(channel=channel, active=len(active))
    _price_by_bed(active, a)
    a.median_price_per_bed = _median_ratio(active, "beds")
    a.median_price_per_sqft = _median_ratio(active, "sqft")
    a.band_30d_low = _band_30d_low(rows)
    a.pct_reduced = _pct_reduced(active, history)
    _trends(rows, active, a)
    _window_counts(active, history, a, window_hours)
    _let_pace(latest, a)
    return a


def _price_by_bed(active, a: AreaAnalytics) -> None:
    by_band: dict[str, list[float]] = defaultdict(list)
    for row in active.values():
        band = _bed_band(row["beds"])
        price = _to_float(row["price"])
        if band and price:
            by_band[band].append(price)
    for band in _BAND_ORDER:
        prices = sorted(by_band.get(band, []))
        if not prices:
            continue
        a.prices_by_band[band] = prices
        med = statistics.median(prices)
        a.median_by_band[band] = med
        a.price_by_bed.append(
            BedStat(band, len(prices), med, statistics.mean(prices), prices[0], prices[-1])
        )


def _median_ratio(active, denom_field: str) -> float | None:
    ratios = []
    for row in active.values():
        denom = _to_float(row["beds"]) if denom_field == "beds" else _to_float(row["sqft"])
        price = _to_float(row["price"])
        if denom and denom >= 1 and price:
            ratios.append(price / denom)
    return statistics.median(ratios) if ratios else None


def _band_30d_low(rows) -> dict[str, float]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    low: dict[str, float] = {}
    for row in rows:
        dt, price, band = _parse_dt(row["timestamp"]), _to_float(row["price"]), _bed_band(row["beds"])
        if dt and price and band and dt >= cutoff:
            if band not in low or price < low[band]:
                low[band] = price
    return low


def _pct_reduced(active, history) -> float:
    if not active:
        return 0.0
    reduced = 0
    for listing_id in active:
        prices = [p for p in (_to_float(r["price"]) for r in history[listing_id]) if p is not None]
        if len(prices) > 1 and prices[0] < max(prices[1:]):  # current below an earlier price
            reduced += 1
    return round(reduced / len(active) * 100, 1)


def _trends(rows, active, a: AreaAnalytics) -> None:
    price_buckets: dict = defaultdict(list)
    for row in rows:
        dt, price = _parse_dt(row["timestamp"]), _to_float(row["price"])
        if dt and price:
            price_buckets[_week_start(dt)].append(price)
    for ws in sorted(price_buckets)[-_TREND_WEEKS:]:
        a.price_trend.append(Bar(_fmt_week(ws), statistics.median(price_buckets[ws])))
    if len(a.price_trend) >= 5:
        recent, old = a.price_trend[-1].value, a.price_trend[-5].value
        if old:
            a.price_trend_pct_30d = round((recent - old) / old * 100, 1)

    new_buckets: dict = defaultdict(int)
    for row in active.values():
        dt = _parse_dt(row["first_listed"]) or _parse_dt(row["timestamp"])
        if dt:
            new_buckets[_week_start(dt)] += 1
    for ws in sorted(new_buckets)[-_TREND_WEEKS:]:
        a.new_listings_trend.append(Bar(_fmt_week(ws), new_buckets[ws]))


def _window_counts(active, history, a: AreaAnalytics, window_hours: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    for listing_id, latest in active.items():
        dt = _parse_dt(latest["timestamp"])
        if not dt or dt < cutoff:
            continue
        rows = history[listing_id]
        if len(rows) == 1:
            a.new_count += 1
        else:
            new_price, old_price = _to_float(rows[0]["price"]), _to_float(rows[1]["price"])
            if new_price is None or old_price is None:
                continue
            if new_price < old_price:
                a.reduced_count += 1
            elif new_price > old_price:
                a.increased_count += 1


def _let_pace(latest, a: AreaAnalytics) -> None:
    """Median days from first listed to (observed) let-agreed, recent lets only."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_LET_PACE_WINDOW_DAYS)
    paces = []
    for row in latest.values():
        if _status(row) != "let_agreed":
            continue
        let_at, listed = _parse_dt(row["let_agreed_at"]), _parse_dt(row["first_listed"])
        if not let_at or not listed or let_at < cutoff:
            continue
        days = (let_at - listed).days
        if days >= 0:
            paces.append(days)
    if paces:
        a.let_pace_days = round(statistics.median(paces))
        a.let_pace_sample = len(paces)


# per-listing helpers (operate on the email listing dict: 'beds', 'price', ...)
def price_per_bed(listing) -> float | None:
    beds, price = _to_int(listing.get("beds")), _to_float(listing.get("price"))
    if not beds or beds < 1 or not price:
        return None
    return price / beds


def days_on_market(listing) -> int | None:
    listed = _parse_dt(listing.get("first_listed"))
    if not listed:
        return None
    return (datetime.now(timezone.utc) - listed).days


def vs_median_gbp(listing, a: AreaAnalytics) -> float | None:
    """Pounds below (positive) / above (negative) the band median."""
    median = a.median_by_band.get(_bed_band(listing.get("beds")) or "")
    price = _to_float(listing.get("price"))
    if not median or price is None:
        return None
    return median - price


def percentile_cheaper_than(listing, a: AreaAnalytics) -> int | None:
    """% of comparable (same-band) active listings priced above this one."""
    prices = a.prices_by_band.get(_bed_band(listing.get("beds")) or "")
    price = _to_float(listing.get("price"))
    if not prices or price is None or len(prices) < 3:
        return None
    return round(sum(1 for p in prices if p > price) / len(prices) * 100)


def is_cheapest_30d(listing, a: AreaAnalytics) -> bool:
    low = a.band_30d_low.get(_bed_band(listing.get("beds")) or "")
    price = _to_float(listing.get("price"))
    return low is not None and price is not None and price <= low


def value_rating(listing, a: AreaAnalytics) -> tuple[str, float] | None:
    """('great'|'good'|'fair'|'pricey', pct_vs_median) for a listing, or None.

    Buy listings with floor area are judged on £/sqft vs the area median;
    everything else on price vs the median for the listing's bedroom band.
    """
    price = _to_float(listing.get("price"))
    if not price:
        return None

    sqft = _to_float(listing.get("sqft"))
    if a.channel == "buy" and sqft and a.median_price_per_sqft:
        basis, median = price / sqft, a.median_price_per_sqft
    else:
        median = a.median_by_band.get(_bed_band(listing.get("beds")) or "")
        basis = price
    if not median:
        return None

    pct = (basis - median) / median
    if pct <= _GREAT_VALUE:
        rating = "great"
    elif pct <= _GOOD_VALUE:
        rating = "good"
    elif pct < _PRICEY:
        rating = "fair"
    else:
        rating = "pricey"
    return rating, round(pct * 100, 1)
