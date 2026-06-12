# Property-Scraper

Scrapes Rightmove for a set of saved searches, tracks listings and their price
history in SQLite, and emails a daily digest of **new listings** and **price
changes** per area.

- Reads each search's results page and extracts the embedded `__NEXT_DATA__` JSON.
- Scrapes each area **wide** (whole local market) into one `listings` table; a
  price change is kept as a new row, so full price history is retained.
- Narrows down to what you care about with **Python-side filters** at email time,
  so changing a filter never needs a re-scrape.
- Emails new + price-changed properties over a configurable look-back window.

## How it works

```
config/*.json  ──►  run_all.py ──► scrape (wide) ──► SQLite `listings` table
   (per area)            │                                  │
   .env / .env.prod ─────┘        email ◄── filter ◄────────┘  (new + price-changed)
```

A single entrypoint, `run_all.py`, scrapes and/or emails **every** configured
area. Each area runs in isolation: one failure is logged and reported in the run
summary but never stops the others.

## Project structure

| Path | Purpose |
|------|---------|
| `run_all.py` | CLI entrypoint (`--mode scrape\|email\|both`, `--only`, `--dry-run`) |
| `pipeline.py` | Per-area `scrape_location` / `email_location` operations |
| `config_models.py` | Pydantic models validating each location config |
| `config_loader.py` | Discovers + validates `config/*.json` |
| `filters.py` | Pure bed/price/distance filters applied at email time |
| `analytics.py` | Per-area market stats (pure functions) |
| `email_builder.py` + `templates/email.html.j2` | Renders the HTML digest (Jinja2) |
| `settings.py` | Env/`.env`-backed settings (secrets, logging, storage paths) |
| `logging_setup.py` | Rotating file + console logging |
| `app.py` | Shared `ManageDatabase` instance |
| `database/update_database.py` | SQLite access — normalised `properties` / `property_status` / `prices` tables |
| `scraper/` | `HouseScraper` base + `RightMoveScraper` |
| `scraper_email/send_email.py` | Builds and sends the HTML email via Gmail SMTP |
| `cron.yaml` | Schedule installed on the Pi by pi-deploy |

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python 3.14 and dependencies)

## Local setup

```bash
uv sync                       # install Python + deps from uv.lock
cp .env.example .env          # then fill in your Gmail credentials
mkdir -p config               # create your private per-location configs here
cp config.json.example config/clapham.json   # edit per area
```

Run it:

```bash
uv run python run_all.py --mode both                 # scrape then email all areas
uv run python run_all.py --mode scrape --only ClaphamSouth
uv run python run_all.py --mode email --dry-run      # build emails, don't send
```

## Configuration

### Secrets & environment (`.env`)

Settings come from environment variables / `.env` files (via pydantic-settings).
Files load in **layers**: shared `.env` first, then an overlay chosen by
`APP_ENV` (default `dev`) — `.env.dev` or `.env.prod`. Overlay values win, and
real process env vars override everything. Shared values (Gmail creds) live only
in `.env`; overlays carry just per-environment differences (paths).

| Variable | Default | Notes |
|----------|---------|-------|
| `GMAIL_USER` | – (required) | Gmail address used to send |
| `GMAIL_PASSWORD` | – (required) | Gmail **app password** |
| `GMAIL_FROM_ADDR` | – (required) | `From` header, e.g. `Property Scraper <you@gmail.com>` |
| `LOG_LEVEL` | `INFO` | |
| `LOG_DIR` | `./logs` | |
| `LOG_FILENAME` | `property_scraper.log` | |
| `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` | `1000000` / `5` | Log rotation |
| `DB_PATH` | `./database/rightmove.db` | SQLite file |
| `CONFIG_DIR` | `./config` | Where per-location configs live |

`.env*` files and the `config/` directory are **gitignored** — they hold your
credentials, email address, and the areas you're searching, so they never get
committed. See `.env.example` and `config.json.example` for the shape.

### Per-location configs (`config/*.json`)

One file per area. `area` doubles as the SQLite table name (letters/digits/
underscore only). The config is validated on load — bad URLs, unknown channels,
or stray keys fail immediately.

```json
{
    "area": "ClaphamSouth",
    "channel": "rent",
    "search_url": "https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=STATION%5E2162&...&index=0&...",
    "filters": {
        "min_beds": 1,
        "max_price": 1750
    },
    "email": {
        "subject_tag": "Clapham South",
        "to_addr": [],
        "bcc_addr": ["you@example.com"],
        "time_period_hours": 24,
        "enabled": true
    },
    "scraper": { "enabled": true, "max_pages": 42 }
}
```

- `channel`: `rent` or `buy`.
- `search_url`: a Rightmove results URL — must contain `&index=0` (used for
  pagination). Leave **price/bedroom filters out of the URL** and put them in
  `filters` instead, so the database stores the whole local market (for analytics)
  while emails stay narrowed. Build one by running the search on rightmove.co.uk
  and copying the URL, or use the bundled helper (see below).
- `filters` (all optional): `min_beds`, `max_beds`, `min_price`, `max_price`,
  `max_distance`. Applied in Python at email time — change them any time, no
  re-scrape needed. Omit the block to email everything scraped.
- `time_period_hours`: how far back the email looks for new/changed listings.
- `scraper.max_pages`: caps pages fetched per scrape (Rightmove tops out ~42).

### Finding a location / scaffolding a config

`find_area.py` resolves a place name to a `locationIdentifier` via Rightmove's
autocomplete endpoint, and can write a starter config:

```bash
# List matching locations and their identifiers
uv run python find_area.py "clapham"

# Scaffold config/ClaphamSouth.json from the 1st match, as a rent search
uv run python find_area.py "clapham south" --scaffold --pick 1 \
    --area ClaphamSouth --channel rent
```

The scaffolded file is written to `CONFIG_DIR` with a sensible default search URL
(no price/bed filters) — edit it to add recipients and filters.

## The email digest

Each digest is a modern HTML report (built from `templates/email.html.j2`) with:

- **Market snapshot** for the whole area: median asking price by bedroom band
  (Studio/1/2/3/4+) with range and sample count, median £/bed (and £/sqft where
  floor area exists), and average days-on-market.
- **Trend charts** (CSS bar charts): median asking price over recent weeks (with
  % vs 30 days ago) and new-listings-per-week velocity. These fill in as history
  accumulates.
- **Renter-edge signals**: % of listings reduced, and **let-pace** ("typically let
  in ~N days") — inferred from observed "Let agreed" status flips (needs
  `includeLetAgreed=true` in the `search_url`).
- A **0–100 deal score** (colour-coded pill by the price) ranking each listing:
  ~70% price vs comparable homes, plus size (sqft vs band median), garden /
  en-suite / extra bath. Listings are sorted by it.
- **Price changes** and **new listings** matching your filters, as cards with: a
  value badge (vs the area median for that bed count), £ vs median, "cheaper than
  X% of comparable", and badges for **Just listed**, **Just reduced** (with
  "reduced after N days"), **Cheapest in 30 days**, **🌳 Garden** and **Large
  space**; plus £/bed, days-on-market, beds/baths/type, distance, available date,
  and **View** / **Map**.

House-shares are excluded at the search-URL level (e.g. `&dontShow=houseShare`) so
they don't skew the medians.

Renderable standalone for previewing: build the HTML with `email_builder.build_email_html(...)`
and write it to a file (see the verification snippet in the dev notes).

## Deployment (Raspberry Pi via pi-deploy)

Deployment is **pull-based** through the
[`pi-deploy`](../pi-deploy) system: every 10 minutes the Pi checks the repo's
remote, and on a new commit it `git reset --hard`s, runs `uv sync`, and installs
this repo's `cron.yaml`.

Because deploys hard-reset the working tree, **private files and data live
outside the repo** so they survive and are never committed:

1. On the Pi, create a data directory, e.g. `/home/pi/property-scraper-data/`,
   containing your `config/` directory.
2. Place `.env` (shared, with Gmail creds) and `.env.prod` (overrides) in the
   **deployed repo dir** (`~/projects/Property-Scraper/`). They're untracked, so
   `git reset --hard` leaves them; they're never pulled, so you add them once.
3. In `.env.prod`, point storage outside the repo:
   ```
   LOG_DIR=/home/pi/property-scraper-data/logs
   DB_PATH=/home/pi/property-scraper-data/rightmove.db
   CONFIG_DIR=/home/pi/property-scraper-data/config
   ```
4. Register the repo in `pi-deploy/repos.conf` (deploy key + SSH alias), then
   force the first deploy:
   ```bash
   bash ~/deploy/deploy.sh --repo Property-Scraper --force
   ```

### Schedule (`cron.yaml`)

`cron.yaml` is installed automatically on each deploy. Cron fields are
`minute hour day-of-month month day-of-week`, in the Pi's **local timezone**
(check with `timedatectl`).

| When | Cron | Action |
|------|------|--------|
| Every 2h, 08:00–18:00 | `0 8-18/2 * * *` | `run_all.py --mode scrape` (08,10,…,18) |
| 10:30 daily | `30 10 * * *` | `run_all.py --mode email` |

`8-18/2` is a stepped range (08:00, 10:00, 12:00, 14:00, 16:00, 18:00). Each
command is prefixed with `APP_ENV=prod` so the run loads `.env` + `.env.prod`. The
10:30 email follows the 10:00 scrape, so it reflects fresh data.

To run manually on the Pi:

```bash
APP_ENV=prod ~/projects/Property-Scraper/.venv/bin/python \
    ~/projects/Property-Scraper/run_all.py --mode both
```

## Logging

Logs go to both the console and a rotating file at `LOG_DIR/LOG_FILENAME`. Every
run ends with a summary table of listings scraped / new / updated / errors per
area; `run_all.py` exits non-zero if any area errored, so the scheduler surfaces
failures.
