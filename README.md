# SF-Housing-Prices

Data pipeline and web app behind **SF Rent Atlas**, a San Francisco apartment **rent**
estimator and map. The pipeline pulls unit-level rents from public, licensed, and scraped
sources (2022 onward), normalizes them onto one schema with amenities and geography, fits a
hedonic rent model, and publishes aggregates that the static app in [`web/`](web/) serves
without any raw data. The plan this implements is in [`docs/DATA_PLAN.md`](docs/DATA_PLAN.md).

<img width="1440" height="760" alt="image" src="https://github.com/user-attachments/assets/cf45f53a-d991-4d3e-89eb-25f803ebbaf8" />


## Sources

| Source | What it gives | Cadence | Redistributable |
| --- | --- | --- | --- |
| DataSF Rent Board Housing Inventory | ~110k unit-tenancies started 2022+: banded rent/sqft, beds, baths, year built, building size, block-level point, neighborhood | monthly | yes (open data) |
| Zillow ZORI (zip + city) | monthly rent index from 2022-01, used as a deflator (`rent_adj`) | monthly | yes (attribution, non-commercial) |
| RentCast API | exact-geocoded asking rents with listing/removal dates and price history | weekly (active), one-off backfill (inactive) | no, raw stays private |
| Craigslist `sfc/apa` (home IP only) | asking rents plus laundry, parking, pets, kitchen, and building amenities | weekly | no, raw HTML stays private |
| DataSF Analysis Neighborhoods | 42 polygons for point-in-polygon assignment and map layers | on demand | yes |

## Setup

```bash
uv sync --all-extras
cp .env.example .env        # add RENTCAST_API_KEY when you have one
```

`SFRENT_ENV` controls behavior: `dev` (default) caps collectors to small pulls unless
`--limit`/`--max-pages` is passed, `test` is used by pytest with recorded fixtures, `prod`
runs full pulls (set by the launchd jobs).

## Commands

```bash
uv run sfrent pull rent-board            # Socrata -> data/raw -> data/processed/rent_board.parquet
uv run sfrent pull zori                  # ZORI csvs -> data/processed/zori.parquet (deflator table)
uv run sfrent pull neighborhoods         # polygons -> data/reference/analysis_neighborhoods.geojson
uv run sfrent pull rentcast --check-only # 2 billed requests: X-Total-Count for Active and 2022+ Inactive
uv run sfrent pull rentcast --status active   # ~6 requests; RENTCAST_REQUEST_BUDGET is a lifetime cap
uv run sfrent pull craigslist            # dev: 2 search pages, 5 postings; prod: full weekly crawl
uv run sfrent build                      # merge -> listings.parquet, flags, rent_adj, model, data/public/*
uv run sfrent commute --hub financial_district --bedrooms 1   # or --lat/--lng
uv run sfrent runlog                     # row counts per run
```

Every run appends a line to `data/runlog.jsonl`.

## Data layout

- `data/raw/` (private, gitignored): gzip'd JSON lines per pull, Craigslist posting HTML, RentCast budget counter, Craigslist seen-state.
- `data/processed/` (private, gitignored): one Parquet per source plus `listings.parquet`, the merged frame with `h3_r9`, `analysis_neighborhood`, `is_duplicate`, `is_suspicious`, `is_modelable`, `rent_adj`.
- `data/public/` (committed): everything the hosted app needs, written by `sfrent build` and mirrored into `web/public/data/`:
  - `neighborhood_bedroom_stats.{json,parquet}`, `hex_bedroom_stats.parquet`, `hexes.json` (H3 r9 cells with boundaries and per-bedroom medians)
  - `analysis_neighborhoods.geojson` (simplified polygons with label points), `zori.json` (monthly index per zip and city)
  - `model.json` (hedonic coefficients, see below) and `summary.json` (counts, citywide medians, fit stats)

The canonical record is `sfrent.normalize.schema.Listing`. Missing values stay null; nothing is imputed at collection time. Banded Rent Board values fill `rent_low`/`rent_high` (and `sqft_low`/`sqft_high`) with the midpoint as the point value.

## Rent model

`sfrent.model` fits `log(rent_adj)` on modelable listings with a baseline per analysis neighborhood plus bedroom, bathroom, log-size, year-built-bucket and building-size-bucket effects (plain OLS, ~1 s on 108k rows). It reports R² and a 20% holdout MAE, and publishes the coefficients with residual quantiles so the app can compute `rent = exp(neighborhood + Σ effects)` and an 80% range client-side. Amenity effects are added once the Craigslist collector has enough postings.

## Web app (`web/`)

Next.js static export with MapLibre (OpenFreeMap tiles) and Recharts; no server, no keys. It reads the JSON in `web/public/data/` at build time.

```bash
cd web && npm install
npm run dev          # http://localhost:3000
npm run build        # static site in web/out
```

Deployed on Vercel with the project root set to `web/`; every push to `main` redeploys. After changing data, run `uv run sfrent build` and commit the refreshed `data/public/` and `web/public/data/` files.

## Scheduling (macOS launchd)

```bash
./scripts/launchd/install.sh                          # renders plists for this repo path and loads all jobs
./scripts/launchd/install.sh rent-board zori craigslist   # load a subset (e.g. skip rentcast)
./scripts/launchd/install.sh --uninstall
```

Jobs: Rent Board monthly (2nd, 03:00), ZORI monthly (18th, 03:15), RentCast active snapshot weekly (Mon 04:00), Craigslist weekly (Sun 10:00). Each job runs `scripts/launchd/run.sh`, which pulls in prod mode, rebuilds, and logs to `logs/`.

## Scraper conduct

The Craigslist collector identifies itself with a real User-Agent (`CRAIGSLIST_USER_AGENT`), waits at least 4 s between requests, runs weekly, and halts at the first HTTP 403. Run it only from a residential connection. Raw HTML, text, photos, and contact details never leave `data/raw/`; only derived fields (rent, beds, amenities, coarse location) are kept. Anyone running this code inherits these limits.

## Commute layer

Stage A (implemented): great-circle distance from every listing to any work point at query time. Stage B (planned): driving/cycling/walking minutes per H3 hex via OSRM locally or OpenRouteService from the app. Stage C (planned): transit minutes precomputed with r5py from every hex to the hubs in `sfrent.geo.commute.HUBS`. Details in that module's docstring.

## Development

```bash
SFRENT_ENV=test uv run pytest
uv run ruff check src tests && uv run ruff format src tests
```
