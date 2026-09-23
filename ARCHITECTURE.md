# How Bureau's code works

This is a technical tour of the repository: the overall architecture, then
what every individual file does. `README.md` is the pitch, setup steps,
and Tailscale/launchd operations guide; this document is the one to read
to understand the *code* — how a lead actually gets from a public API or
a Firecrawl scrape onto your screen, and which file is responsible for
which part of that.

## The big picture

Bureau is one FastAPI process serving two things from the same port:

1. A **JSON API** under `/api/*` — authentication, region metadata, lead
   listing/filtering/export, and the ingestion triggers that pull in new
   leads.
2. The **built React frontend** (`frontend/dist/`, produced by `npm run
   build`) mounted as static files at `/`. There's no separate frontend
   server in production — `backend/app/main.py` serves both, which is why
   only one `launchd` service and one Tailscale Serve port are needed.

Leads come from two families of source, both normalized into one `leads`
SQLite table:

- **Job leads**: three keyless public APIs (Remotive, Arbeitnow,
  RemoteOK) refreshed automatically every few hours by a background
  asyncio loop, plus Firecrawl-based company-careers-page discovery
  triggered manually (it spends Firecrawl credits, so it's never
  automatic).
- **Business-opportunity leads**: Firecrawl web/news search per
  industry+region, then a structured-JSON scrape of each matched page to
  pull out a company's name, location, size, funding stage, and the
  specific signal that makes it a live lead — triggered manually from the
  "Discover businesses" bar on the Business Opportunities tab.

Every source module — regardless of which family — produces plain
dicts in the same shape and hands them to one shared function,
`ingest.upsert_leads()`, which is what actually knows how to write to the
database and dedupe. This is why adding a new source later (e.g. Adzuna)
only means writing one new file that produces that dict shape, not
touching the database or API layer at all.

Auth is deliberately minimal: one username/password (bcrypt-hashed),
one signed session cookie, no user table, no roles — this is a
single-operator tool, not a multi-tenant product.

## Repository layout

```
backend/            FastAPI app, SQLite storage, all lead sources
  app/
    routers/         the three API routers (auth, leads, ingest)
    sources/          one module per lead source, plus shared helpers
      jobs/            job-board sources
      business/        business-opportunity sources
  scripts/          one-off CLI scripts (set password, seed/clear mock data)
  data/             SQLite DB + auth.json + secret key (gitignored, created at runtime)
frontend/           React + Tailwind SPA (Vite), built to frontend/dist/
  src/
    components/      one file per UI piece
deploy/             launchd unit for running the backend as a service
scripts/            repo-root dev convenience scripts (not backend/scripts/)
.claude/            launch.json — lets the Claude Code browser tool preview
                    the dev servers by name
```

---

## `backend/` — the FastAPI app

### `backend/app/main.py`
The entry point. Builds the `FastAPI` app, registers the three routers
(`auth`, `leads`, `ingest`), and — if `frontend/dist/` exists — mounts it
as static files at `/` so the built SPA and the API are served from the
same port. The `lifespan` context manager runs `init_db()` and starts
`scheduler.background_loop()` as an asyncio task when the app boots, and
cancels it on shutdown.

### `backend/app/config.py`
All environment-driven settings in one place, loaded from `backend/.env`
via `python-dotenv`. Resolves the data directory (`backend/data/` by
default), the SQLite path, the bcrypt-auth file path, and generates (or
loads) the `SECRET_KEY` used to sign session cookies — if you don't set
`BUREAU_SECRET_KEY` yourself, one is created on first run and cached in
`data/.secret_key` so sessions survive restarts (but not a wipe of
`data/`). Also reads `FIRECRAWL_API_KEY` and the background-ingest
interval.

### `backend/app/db.py`
The SQLAlchemy setup: one `Lead` table with every field either family of
source might populate (job-only fields like `remote_type`/`seniority`,
business-only fields like `industry`/`contact_path`, and shared fields
like `signal`/`company_size`/`funding_stage`). A unique constraint on
`(source, external_id)` is what makes re-running a source idempotent —
see `ingest.py`. `init_db()` creates the table if it doesn't exist; there
are no migrations, since a schema change just means deleting
`data/bureau.db` and letting sources repopulate it.

### `backend/app/auth.py`
Single-user session auth. `set_credentials()`/`verify_credentials()`
read and write `data/auth.json` (bcrypt hash only, via `scripts/
set_password.py` — never plaintext, never hardcoded). `make_session_
cookie()`/`read_session_cookie()` use `itsdangerous` to sign a cookie
containing just the username; `require_session()` is the FastAPI
dependency every protected router pulls in, and raises a 401 if the
cookie is missing, unsigned, or expired (30-day max age).

### `backend/app/schemas.py`
Pydantic response/request models: `LeadOut` (what a lead looks like over
the API — note `tags` is reconstituted from the DB's `tags_json` column
at serialization time, not stored as a real column), `LeadsPage` (a
paginated list), and `LoginRequest`.

### `backend/app/regions.py`
The static continent → country tree that powers the top-level region
selector (`CONTINENTS`) and its inverse lookup (`COUNTRY_TO_CONTINENT`,
built once at import time). Deliberately does **not** list cities —
those come from whatever's actually in the database, see `/api/regions/
cities` in `routers/leads.py`.

### `backend/app/ingest.py`
The one function every source funnels through: `upsert_leads(db, leads)`.
Takes an iterable of plain dicts, validates the required fields are
present, serializes `tags`/`raw` to JSON columns, and either updates an
existing row (matched on `source` + `external_id`, never touching its
`starred` flag) or inserts a new one. Returns `(created, updated)` counts,
which is what the ingestion endpoints and the background loop report
back.

### `backend/app/enrichment.py`
Two pieces of enrichment that don't need an external API call:
`guess_seniority()` — a regex over the job title for words like
"senior"/"staff"/"junior" — and `apply_growth_signals()`, which counts how
many other job leads the same company has posted within a rolling
30-day window and writes a "Hiring N roles in the last 30 days" signal
onto each one if that count is ≥2. This is what fills in the growth
signal for the three keyless job sources, which don't carry funding/
hiring-surge data themselves the way a Firecrawl-sourced business lead
does.

### `backend/app/scheduler.py`
The background refresh loop for the **keyless job sources only** —
Firecrawl-based sources are deliberately excluded here because they cost
credits per call; those only run when a person clicks something (see
`routers/ingest.py`). `run_job_sources_once()` calls every fetcher in
`sources.registry.JOB_FETCHERS`, upserts the results, and reapplies
growth signals; `background_loop()` wraps that in an infinite
sleep-then-run cycle at `config.INGEST_INTERVAL_SECONDS`, started once
from `main.py`'s lifespan hook. `LAST_RUN` is an in-memory dict the
`/api/ingest/status` endpoint reads — it resets on restart, which is fine
since it's just a "when did this last run" display value.

### `backend/app/mock_data.py`
Hand-written sample leads (10 jobs, 8 businesses) used only to make the
UI look populated before real sources have run — never imported by the
actual API or ingestion code. Only reachable via `scripts/
seed_mock_data.py`.

### `backend/app/routers/auth.py`
`/api/auth/*`: `GET /status` (has a password ever been set — lets the
frontend distinguish "not configured" from "wrong password"), `POST
/login` (verifies against the bcrypt hash and sets the session cookie),
`POST /logout` (clears it), `GET /me` (the session check the frontend
runs on every load to decide whether to show the login screen).

### `backend/app/routers/leads.py`
`/api/leads*` and `/api/regions*` — everything the results feed and
region selector call, and the only router with real query logic.
`_apply_filters()` builds up the SQLAlchemy query from whichever of
`lead_type`/`continent`/`country`/`city`/`search`/`remote_type`/
`starred_only` are set (search does a case-insensitive `ILIKE` across
title/company/signal); `_sorted()` applies the newest/oldest/company-A-Z
ordering. `list_leads()` and `export_leads()` share those two helpers so
"what you're looking at" and "what you export" can never drift apart —
export just runs the same query unpaginated and streams it back as CSV or
JSON. `toggle_star()` flips one boolean. `get_cities()` is the dynamic
city autocomplete: a `DISTINCT` query over whatever cities exist in the
DB for the current lead type/continent/country/search-prefix, capped at
50 results — this is why the city list only ever shows places leads
actually exist, instead of a static gazetteer.

### `backend/app/routers/ingest.py`
The manual-trigger endpoints, all requiring a session: `POST /jobs`
(re-runs the keyless sources on demand, same function the background
loop uses), `POST /careers` (Firecrawl career-page discovery for a
specific list of `{name, domain}` companies), `POST /business`
(Firecrawl business-lead discovery for one industry/region). The latter
two both 400 immediately if `FIRECRAWL_API_KEY` isn't set, via
`sources.firecrawl_client.is_configured()`, rather than attempting a call
that would fail anyway. `GET /status` reports whether Firecrawl is
configured and the background loop's last-run timestamps.

## `backend/app/sources/` — one module per lead source

### `backend/app/sources/location.py`
Turns whatever free-text location string a source API provides
("Berlin", "USA", "Paris, France", "Berlin HQ") into `(continent,
country, city)`. Tries, in order: matching the last comma-separated
token against the known country list (with common aliases like "UK" →
"United Kingdom" in `ALIASES` and two-letter codes in
`city_lookup.COUNTRY_CODE_ALIASES`); treating the whole string as a
country name; and finally falling back to `city_lookup`'s bare-city
table for the very common case of a city with no country attached at
all. Strings like "Worldwide"/"Remote"/"" deliberately resolve to
`(None, None, None)` rather than guessing — those leads simply show up
under the unfiltered "Global" view instead of under a wrong country.

### `backend/app/sources/city_lookup.py`
A hand-curated table of ~150 major-city → country mappings (`CITY_TO_
COUNTRY`) and two-letter country-code aliases (`COUNTRY_CODE_ALIASES`).
Exists purely because European job boards overwhelmingly give a bare
city name with no country (confirmed empirically against live Arbeitnow
data while building this — about 40% of listings are just "Berlin",
"London", "Paris" with nothing else). Anything not in this table still
safely falls through to "unknown" in `location.py` rather than a wrong
guess.

### `backend/app/sources/firecrawl_client.py`
A single `get_client()` (lru-cached) that constructs a `firecrawl.
Firecrawl` SDK client from `config.FIRECRAWL_API_KEY`, or returns `None`
if it isn't set — every Firecrawl-based source module calls this and
bails out (returning an empty list) rather than raising, which is why the
app still runs fine with zero leads from these two sources when no key
is configured. `is_configured()` is the cheap check the ingest router
uses to 400 early.

### `backend/app/sources/registry.py`
`JOB_FETCHERS`: the dict of `{name: fetch_function}` for the three
keyless job sources, consumed by `scheduler.py`'s background loop and by
the manual `/api/ingest/jobs` trigger. Firecrawl-based sources are
intentionally not registered here (see `scheduler.py`).

### `backend/app/sources/jobs/remotive.py`, `arbeitnow.py`, `remoteok.py`
One file per keyless job-board API. Each `fetch()` hits that API's public
JSON endpoint with `httpx`, and maps its native field names onto the
common lead dict — RemoteOK additionally needs a descriptive `User-Agent`
header or it 403s. All three run `parse_location()` on whatever location
string the API gives, run `guess_seniority()` on the title, and are all
hardcoded `remote_type="remote"` (Remotive/RemoteOK, which are remote-only
boards) or derived from a `remote` boolean field (Arbeitnow, which lists
onsite roles too). Each is wrapped in a `try/except httpx.HTTPError` that
logs and returns `[]` rather than taking the whole ingest run down if one
API is temporarily unreachable.

### `backend/app/sources/jobs/firecrawl_careers.py`
Given a list of `{name, domain}` companies, `firecrawl.map()`s each
domain looking for a URL containing "career"/"job", then
`firecrawl.scrape()`s that page with a JSON-mode extraction schema
(`JOB_LISTING_SCHEMA`) asking for every open listing's title, location,
department, and URL. Only triggered from `/api/ingest/careers` — never
on the background schedule, since every call spends Firecrawl credits.

### `backend/app/sources/business/firecrawl_business.py`
The business-opportunity pipeline. `_search_urls()` runs `firecrawl.
search()` against four query templates per industry/region (funding,
active hiring, expansion, new leadership — the four signal types the
build brief called out), pooling and deduping the result URLs. `fetch()`
then `firecrawl.scrape()`s each URL with `COMPANY_SCHEMA` — a JSON-mode
extraction asking for the company's name, domain, HQ location, size,
funding stage, the specific signal, and a **company-level** contact path,
explicitly prompted to never return a named individual's personal contact
info. This is also where Crunchbase/LinkedIn company pages would be
picked up if a search result lands on one — no domain filtering excludes
them, per the explicit call made when this was built, only their public
unauthenticated pages are ever touched. Verified against live data while
building this: it correctly extracts a single specific company (not the
whole roundup) out of a multi-company funding-news article. Also
manual-only, for the same credit-cost reason as `firecrawl_careers.py`.

## `backend/scripts/` — one-off CLI scripts

### `backend/scripts/set_password.py`
Sets or changes the login credentials — prompts for username/password
(or takes them as `--username`/`--password` flags for non-interactive
use) and writes the bcrypt hash via `auth.set_credentials()`. This is the
only supported way to manage the password; it is never hardcoded
anywhere in the codebase.

### `backend/scripts/seed_mock_data.py`
Inserts the sample leads from `app/mock_data.py` through the normal
`upsert_leads()` path, so they behave exactly like real leads (dedupe,
starring, export) while you're looking at the UI before real sources
have populated anything.

### `backend/scripts/clear_mock_data.py`
Deletes every lead with `source = "mock"`. The natural next step after
`seed_mock_data.py` once real sources (or a real Firecrawl-sourced
business lead) have replaced the need for sample data.

---

## `frontend/` — the React SPA

Built with Vite, no server-side rendering. `npm run dev` runs it
standalone on port 5173 with `/api` proxied to the backend on 8910 (see
`vite.config.ts`) for hot-reload iteration; `npm run build` produces
`frontend/dist/`, which `backend/app/main.py` serves directly in
production — there is no separate frontend deployment.

### `frontend/src/main.tsx`
Standard Vite/React bootstrap: mounts `<App />` into `#root` inside
`StrictMode`.

### `frontend/src/App.tsx`
The top-level component and the only place that talks to `api.ts`
directly for page-level state. Holds: auth state (checks `/api/auth/me`
on load to decide whether to render `LoginPage`), the current lead type
and region filter, the debounced search/sort/remote-mode/starred filters,
the current page of loaded leads, and a `refreshTick` counter that's
bumped to force a re-fetch after a manual ingest without otherwise
disturbing the query-parameter dependency array. `queryParams()` is the
single source of truth for what the current filter state maps to as API
query params — both the leads fetch and the CSV/JSON export URL are built
from it, so they can't drift apart. Renders the masthead header (lead-
type tabs + region selector), the Business-Opportunities-only
`BusinessDiscovery` bar, `FiltersBar`, and `ResultsFeed`.

### `frontend/src/api.ts`
The one file that calls `fetch()`. A small `request()` wrapper adds
`credentials: 'include'` (so the session cookie is sent) and throws a
typed `ApiError` with the backend's error detail on a non-2xx response.
`api.exportUrl()` doesn't fetch anything — it just builds the URL for
`window.open()`, since a file download needs to be a real navigation, not
a fetch.

### `frontend/src/types.ts`
Shared TypeScript types mirroring the backend's Pydantic schemas
(`Lead`, `LeadsPage`, `Regions`) plus frontend-only types like
`SortOrder`.

### `frontend/src/index.css`
The design system: CSS custom properties for the warm paper/ink/oxblood
palette (redefined under `prefers-color-scheme: dark`), the serif/sans/
mono font stacks, and two small utility classes (`font-serif-mast`,
`font-mono-kicker`) used everywhere the masthead treatment shows up.
Everything else is Tailwind utility classes referencing these variables
via `bg-[var(--paper)]`-style arbitrary values, rather than Tailwind's
own default color palette.

### `frontend/src/components/LoginPage.tsx`
The masthead login screen: the large italic serif "Bureau" wordmark, a
short accent-colored hairline rule, and a letterspaced uppercase tagline
above a plain username/password form. Posts to `api.login()` and calls
`onLoggedIn` on success.

### `frontend/src/components/LeadTypeToggle.tsx`
The Jobs / Business Opportunities switch, styled as underlined tabs
rather than a pill toggle, to match the broadsheet-section-header look.

### `frontend/src/components/RegionSelector.tsx`
Continent and country `<select>`s plus the city autocomplete. The city
input debounces (200ms) and calls `api.cities()` scoped to whatever
continent/country/lead-type is currently selected, rendering the matches
as a dropdown; picking one, typing a fresh query, or clicking "Reset to
Global" all flow back through the single `onChange(RegionValue)` prop
that `App.tsx` owns. `GLOBAL` (all-empty) is exported as the shared
"no filter" constant.

### `frontend/src/components/FiltersBar.tsx`
Search input, work-mode filter (jobs only), sort order, "starred only"
checkbox, and the two export buttons — a controlled component over the
`Filters` type it also exports, with no state of its own.

### `frontend/src/components/LeadCard.tsx`
Renders one lead. Builds a small tag list (work mode/seniority for jobs,
industry for businesses, plus company size and funding stage when
present) shown as a letterspaced mono line, and — if the lead has a
`signal` — renders it as an italic serif pull-quote with a left accent
border, which is the card's visual focal point. The star button toggles
directly via the `onToggleStar` callback passed down from `App.tsx`.

### `frontend/src/components/ResultsFeed.tsx`
The grid of `LeadCard`s plus the three non-happy-path states: an error
message, an empty-state message (styled as an italic serif line, matching
the masthead voice), and a "Load more" button shown while `leads.length <
total`. Purely a presentational component — pagination state lives in
`App.tsx`.

### `frontend/src/components/BusinessDiscovery.tsx`
The industry/region search bar shown above the feed on the Business
Opportunities tab. If `firecrawlConfigured` is false (checked once by
`App.tsx` via `/api/ingest/status`), renders a note about setting
`FIRECRAWL_API_KEY` instead of the input. Otherwise, submitting calls
`api.ingestBusiness()` and reports how many leads were created/updated,
then calls `onDiscovered()` so `App.tsx` re-fetches the feed.

### `frontend/vite.config.ts`
Registers the React and Tailwind v4 Vite plugins, and proxies `/api` to
`http://127.0.0.1:8910` in dev mode so the frontend dev server and the
backend can run on different ports without a CORS setup.

---

## `deploy/` and `.claude/` — running it

### `deploy/com.bureau.backend.plist`
The `launchd` user-agent unit that keeps the backend running: runs
`.venv/bin/uvicorn app.main:app` from `backend/`, restarts on crash
(`KeepAlive`) and on login (`RunAtLoad`), and logs to `~/Library/Logs/
Bureau/`. Installed with `launchctl bootstrap gui/$(id -u) <path to this
file>` — see `README.md`'s "Running as a persistent background service"
section for the full command set. Note: a Python venv embeds absolute
paths in its script shebangs, so if this repo is ever moved to a
different path, `backend/.venv` has to be deleted and recreated there —
`mv`-ing it along with the rest of the repo will silently break it.

### `.claude/launch.json`
Not part of the running app — this only tells Claude Code's browser
preview tool how to start `scripts/dev-frontend.sh` and `scripts/
dev-backend.sh` as named dev servers for interactive verification while
working on the code.

### `scripts/dev-frontend.sh`, `scripts/dev-backend.sh`
Thin wrappers that `cd` into `frontend/` or `backend/` (resolved relative
to the script's own location, so they work regardless of the caller's
current directory) and run the dev server. Exist so `.claude/launch.json`
can reference a fixed path without needing to know the repo's absolute
location.

---

## Everything else

### `backend/app/__init__.py`, `backend/app/routers/__init__.py`, `backend/app/sources/__init__.py`, `backend/app/sources/jobs/__init__.py`, `backend/app/sources/business/__init__.py`
Empty — they exist only to make each directory an importable Python
package.

### `backend/requirements.txt`
Pinned backend dependencies: FastAPI, Uvicorn, SQLAlchemy, httpx (job-API
calls), bcrypt, itsdangerous (session signing), python-dotenv, and
firecrawl-py.

### `backend/.env.example`
The template for `backend/.env` (which is gitignored and never
committed): `FIRECRAWL_API_KEY`, `BUREAU_SECRET_KEY`, and
`BUREAU_INGEST_INTERVAL_SECONDS`, each commented with what it does and
what happens if you leave it blank.

### `README.md`
The pitch, setup steps, credential management, launchd service commands,
the Tailscale Serve-vs-Funnel explanation and exact commands, and the
data-source/ToS notes (including the explicit call made on scraping
Crunchbase/LinkedIn's public pages for business leads). Read that one
first; read this file when you need to know how the code itself works.

### `frontend/index.html`
The single HTML shell Vite injects the built JS/CSS into — just the
`<title>` and a `#root` div.

### `frontend/public/favicon.svg`, `frontend/public/icons.svg`
Static assets Vite copies as-is into `dist/`; the favicon and an icon
sprite left over from the Vite React template (unused by any Bureau-
specific UI, harmless to leave in place).

### `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`
Standard Vite/React TypeScript project setup — `tsconfig.json` just
references the other two, which split "code that runs in the browser"
from "code that runs in Node" (i.e. `vite.config.ts`) so each gets the
right `lib`/`types` settings.

### `frontend/.oxlintrc.json`, `frontend/.gitignore`
Linter config (`oxlint`, run via `npm run lint`) and the frontend-local
gitignore (`node_modules/`, `dist/` — redundant with the root
`.gitignore` but kept since the Vite template ships it by default).

### `.gitignore` (repo root)
Excludes `backend/.venv/`, `backend/data/` (the SQLite DB and auth file —
runtime state, never committed), `backend/.env`, `frontend/node_modules/`,
`frontend/dist/`, and `.DS_Store`.
