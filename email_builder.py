"""Render the HTML digest email from analytics + listings via a Jinja2 template."""
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import analytics as analytics_mod
from analytics import AreaAnalytics
from config_models import LocationConfig

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _gbp(value) -> str:
    if value is None:
        return "N/A"
    return f"£{value:,.0f}"


def _price(value, rent: bool) -> str:
    if value is None:
        return "N/A"
    return f"£{value:,.0f} pcm" if rent else f"£{value:,.0f}"


def _pct(value) -> str:
    if value is None:
        return ""
    return f"{value:+.1f}%"


def _kgbp(value) -> str:
    """Compact money for chart labels: 1875 -> '£1.9k'."""
    if value is None:
        return ""
    if value >= 1000:
        return f"£{value / 1000:.1f}k"
    return f"£{value:.0f}"


def _short_date(value) -> str:
    """ISO/SQLite timestamp -> '4 Jun'."""
    if not value:
        return ""
    text = str(value)[:10]
    try:
        dt = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return text
    return f"{dt.day} {dt.strftime('%b')}"


_env.filters["gbp"] = _gbp
_env.filters["price"] = _price
_env.filters["pct"] = _pct
_env.filters["kgbp"] = _kgbp
_env.filters["short_date"] = _short_date


def _decorate(listing: dict, a: AreaAnalytics) -> dict:
    """Add presentation + edge fields used by the template and for sorting."""
    d = dict(listing)
    d["price_per_bed"] = analytics_mod.price_per_bed(listing)
    d["days_on_market"] = analytics_mod.days_on_market(listing)
    d["value"] = analytics_mod.value_rating(listing, a)
    d["vs_median_gbp"] = analytics_mod.vs_median_gbp(listing, a)
    d["percentile_cheaper"] = analytics_mod.percentile_cheaper_than(listing, a)
    d["cheapest_30d"] = analytics_mod.is_cheapest_30d(listing, a)
    d["just_listed"] = d["days_on_market"] is not None and d["days_on_market"] <= 1
    d["just_reduced"] = bool(listing.get("is_update") and (listing.get("price_change_pct") or 0) < 0)
    d["reduced_after_days"] = _reduced_after_days(listing)
    lat, lng = listing.get("latitude"), listing.get("longitude")
    d["map_url"] = f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else None
    d["deal_score"] = _deal_score(d)
    return d


def _reduced_after_days(listing: dict) -> int | None:
    if not listing.get("is_update"):
        return None
    history = listing.get("price_history") or []
    listed = analytics_mod._parse_dt(listing.get("first_listed"))
    reduced_at = analytics_mod._parse_dt(history[-1][0]) if history else None
    if not listed or not reduced_at:
        return None
    days = (reduced_at - listed).days
    return days if days >= 0 else None


def _deal_score(d: dict) -> float:
    """Higher = better opportunity. Below-median value, plus freshness/reduction."""
    value = d.get("value")
    score = max(0.0, -value[1]) if value else 0.0   # value[1] < 0 means below median
    if d.get("just_listed"):
        score += 15
    if d.get("just_reduced"):
        score += 15
    if d.get("cheapest_30d"):
        score += 10
    return score


def _sort_by_deal(listings: list[dict]) -> list[dict]:
    return sorted(listings, key=lambda l: l.get("deal_score", 0), reverse=True)


def build_email_html(
    config: LocationConfig,
    area_analytics: AreaAnalytics,
    new_listings: list[dict],
    updated_listings: list[dict],
) -> str:
    rent = config.channel.value == "rent"
    context = {
        "area": config.area,
        "subject_tag": config.email.subject_tag or config.area,
        "rent": rent,
        "channel": config.channel.value,
        "now": datetime.now().strftime("%d %b %Y"),
        "analytics": area_analytics,
        "new_listings": _sort_by_deal([_decorate(l, area_analytics) for l in new_listings]),
        "updated_listings": _sort_by_deal([_decorate(l, area_analytics) for l in updated_listings]),
    }
    return _env.get_template("email.html.j2").render(**context)
