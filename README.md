# Property-Scraper

Scrapes Rightmove for a set of saved searches, tracks listings and their price
history in SQLite, and emails a daily digest of **new listings** and **price
changes** per area.

- Reads each search's results page and extracts the embedded `__NEXT_DATA__` JSON.
- Stores listings per area; a price change is kept as a new row, so full price
  history is retained.
- Emails new + price-changed properties over a configurable look-back window.

## How it works

```
config/*.json  ──►  run_all.py ──► scrape ──► SQLite (one table per area)
   (per area)            │                         │
   .env / .env.prod ─────┘            email ◄──────┘  (new + price-changed)
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
| `settings.py` | Env/`.env`-backed settings (secrets, logging, storage paths) |
| `logging_setup.py` | Rotating file + console logging |
| `app.py` | Shared `ManageDatabase` instance |
| `database/update_database.py` | SQLite access (context-managed connections) |
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
    "email": {
        "subject_tag": "Clapham South",
        "to_addr": [],
        "bcc_addr": ["you@example.com"],
        "time_period_hours": 24,
        "enabled": true
    },
    "scraper": { "enabled": true }
}
```

- `channel`: `rent` or `buy`.
- `search_url`: a Rightmove results URL — must contain `&index=0` (used for
  pagination). Build one by running the search on rightmove.co.uk and copying the
  URL, or look up a `locationIdentifier` via the autocomplete endpoint:
  `https://los.rightmove.co.uk/typeahead?query=clapham` → combine `type` and `id`
  as `TYPE^ID` (e.g. `REGION^85282`, URL-encoded `%5E`).
- `time_period_hours`: how far back the email looks for new/changed listings.

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
| Hourly, 08:00–18:00 daily | `0 8-18 * * *` | `run_all.py --mode scrape` |
| 09:30 daily | `30 9 * * *` | `run_all.py --mode email` |

`8-18` is an hourly range (08:00, 09:00, … 18:00). Each command is prefixed with
`APP_ENV=prod` so the run loads `.env` + `.env.prod`. The 09:30 email follows the
08:00 and 09:00 scrapes, so it reflects fresh data.

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
