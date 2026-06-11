"""Resolve a Rightmove ``locationIdentifier`` from a place name, and optionally
scaffold a new per-location config file.

Rightmove's search URLs are keyed by a ``locationIdentifier`` like ``REGION^85282``
or ``STATION^2162``. Finding one normally means loading the site and digging
through the network tab. This queries Rightmove's public autocomplete endpoint
instead.

Examples:
    # Look up identifiers for a place
    uv run python find_area.py "clapham"

    # Scaffold config/clapham.json from the 1st match, as a rent search
    uv run python find_area.py "clapham south" --scaffold --pick 1 \\
        --area ClaphamSouth --channel rent
"""
import argparse
import json
import sys
from dataclasses import dataclass

import requests

from config_models import Channel, LocationConfig
from settings import get_storage_settings

_TYPEAHEAD_URL = "https://los.rightmove.co.uk/typeahead"
_HEADERS = {"User-Agent": "Mozilla/5.0 (property-scraper find_area)"}


@dataclass
class Match:
    location_identifier: str  # e.g. "REGION^85282"
    display_name: str


def search_locations(query: str, limit: int = 8) -> list[Match]:
    """Query Rightmove's autocomplete endpoint for matching locations."""
    response = requests.get(
        _TYPEAHEAD_URL, params={"query": query, "limit": limit}, headers=_HEADERS, timeout=15
    )
    response.raise_for_status()
    matches = response.json().get("matches", [])
    return [
        Match(location_identifier=f"{m['type']}^{m['id']}", display_name=m["displayName"])
        for m in matches
    ]


def build_search_url(location_identifier: str, channel: Channel) -> str:
    """Build a Rightmove results URL for the given location and channel.

    Adds a sensible default radius and no price/bed filters — edit the generated
    config to taste. Always includes ``&index=0`` (required for pagination).
    """
    path = "property-to-rent" if channel is Channel.RENT else "property-for-sale"
    rm_channel = "RENT" if channel is Channel.RENT else "BUY"
    encoded = location_identifier.replace("^", "%5E")
    parts = [
        f"locationIdentifier={encoded}",
        "numberOfPropertiesPerPage=24",
        "radius=1.0",
        "sortType=6",
        "index=0",
    ]
    if channel is Channel.RENT:
        parts.append("includeLetAgreed=false")
    parts += ["viewType=LIST", f"channel={rm_channel}", "areaSizeUnit=sqft",
              "currencyCode=GBP", "isFetching=false", "viewport="]
    return f"https://www.rightmove.co.uk/{path}/find.html?" + "&".join(parts)


def scaffold_config(match: Match, area: str, channel: Channel) -> LocationConfig:
    """Build and validate a LocationConfig from a chosen match."""
    return LocationConfig.model_validate(
        {
            "area": area,
            "channel": channel.value,
            "search_url": build_search_url(match.location_identifier, channel),
            "email": {"subject_tag": match.display_name, "to_addr": [], "bcc_addr": []},
        }
    )


def _print_matches(query: str, matches: list[Match]) -> None:
    if not matches:
        print(f"No matches for '{query}'.")
        return
    print(f"Matches for '{query}':")
    width = max(len(m.location_identifier) for m in matches)
    for i, m in enumerate(matches, start=1):
        print(f"  {i}. {m.location_identifier:<{width}}  {m.display_name}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", help="Place name to search for, e.g. 'clapham'")
    parser.add_argument("--limit", type=int, default=8, help="Max matches to show (default 8)")
    parser.add_argument("--scaffold", action="store_true", help="Write a config file for the picked match")
    parser.add_argument("--pick", type=int, metavar="N", help="1-based match index to scaffold")
    parser.add_argument("--area", help="Area / table name for the scaffolded config (e.g. ClaphamSouth)")
    parser.add_argument("--channel", choices=[c.value for c in Channel], help="rent or buy")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing config file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        matches = search_locations(args.query, limit=args.limit)
    except requests.RequestException as e:
        print(f"Lookup failed: {e}", file=sys.stderr)
        return 1

    _print_matches(args.query, matches)
    if not matches:
        return 1

    if not args.scaffold:
        return 0

    # --- scaffold mode ---
    if args.pick is None or not args.area or not args.channel:
        print("\n--scaffold requires --pick N, --area NAME and --channel rent|buy", file=sys.stderr)
        return 2
    if not (1 <= args.pick <= len(matches)):
        print(f"\n--pick {args.pick} out of range (1..{len(matches)})", file=sys.stderr)
        return 2

    match = matches[args.pick - 1]
    config = scaffold_config(match, args.area, Channel(args.channel))

    out_path = get_storage_settings().config_dir / f"{args.area}.json"
    if out_path.exists() and not args.force:
        print(f"\n{out_path} already exists (use --force to overwrite)", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(config.model_dump(mode="json"), indent=4) + "\n", encoding="utf-8"
    )
    print(f"\nWrote {out_path}")
    print("Edit it to set bcc/to recipients and any price/bedroom filters in the search_url.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
