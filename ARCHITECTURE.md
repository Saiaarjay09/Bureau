# How Bureau's code works

This is a technical tour of the repository: the overall architecture, then
what every individual file does. `README.md` is the pitch, setup steps,
and Tailscale/launchd operations guide; this document is the one to read
to understand the *code* — how a lead actually gets from a public API or
a web fetch onto your screen, and which file is responsible for
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
  asyncio loop, plus web search and company-careers-page discovery
  triggered manually (each costs minutes of local fetching and model
  time, so it's never automatic).
- **Business-opportunity leads**: web search per
  industry+region, then local extraction over each matched page to
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
`data/`). Also names the local models used for CV screening and page
extraction, and the background-ingest interval. It still reads
`FIRECRAWL_API_KEY` so an existing `.env` doesn't error, but nothing
uses it any more.

### `backend/app/db.py`
The SQLAlchemy setup: one `Lead` table with every field either family of
source might populate (job-only fields like `remote_type`/`seniority`,
business-only fields like `industry`/`contact_path`, and shared fields
like `signal`/`company_size`/`funding_stage`). A unique constraint on
`(source, external_id)` is what makes re-running a source idempotent —
see `ingest.py`. Also carries `description` (the posting's own text, as
plain text — see `sources/html_text.py`), the cheap `fit_score`/
`fit_reason` screen, and the `council_*` columns holding a full Sabha
verdict.

`init_db()` creates the table, then `_add_missing_columns()` ALTERs in any
column the model has but the table doesn't. That second step exists
because `create_all()` only ever creates missing *tables* — a new column
on an existing database would otherwise be silently absent until
something SELECTed it. There are still no real migrations (this is a
single-user SQLite tool), so it handles exactly one kind of change:
adding a nullable column. Anything structural means rebuilding
`data/bureau.db`.

### `backend/app/auth.py`
Single-user session auth, now with a Haven-style recovery phrase.
`create_account()` is the normal path (called from the web signup
screen): refuses if an account already exists, generates a 12-word
recovery phrase via `recovery.py`, and stores bcrypt hashes of both the
password and the (normalized) phrase in `data/auth.json` — the phrase
itself is returned once, in-memory, for the caller to display, and never
written anywhere in plaintext. `verify_credentials()` and
`verify_recovery_phrase()` check a candidate against those two hashes
independently; `reset_password_with_recovery()` is what "forgot
password" actually calls — it re-hashes and overwrites only the password,
leaving the recovery phrase (and its hash) untouched, so the same phrase
keeps working across future resets. `set_credentials()` is the separate
CLI-only path `scripts/set_password.py` uses: it force-sets the password
hash without touching (or requiring) a recovery phrase at all, which is
the deliberate escape hatch for "I lost both the password and the
phrase." `make_session_cookie()`/`read_session_cookie()` use
`itsdangerous` to sign a cookie containing just the username;
`require_session()` is the FastAPI dependency every protected router
pulls in — it checks the cookie's signature/expiry *and* cross-checks the
username against the current account record, so a cookie issued before
an account was recreated (e.g. after wiping `data/auth.json`) can't
silently keep authenticating as a no-longer-current account.

### `backend/app/recovery.py`
Generates and normalizes 12-word recovery phrases from the standard
2048-word BIP39 English wordlist (`app/data/wordlist.txt`, copied
directly from Haven's — chosen there for the phrase's human-transcription
safety, not for BIP39's mnemonic math, which isn't used here either).
`generate_recovery_phrase()` draws each word from `os.urandom` (not the
non-cryptographic `random` module — 12 words is 132 bits of entropy).
`normalize_phrase()` collapses whitespace/case so a phrase typed back in
during recovery still matches regardless of formatting.

### `backend/app/schemas.py`
Pydantic response/request models: `LeadOut` (what a lead looks like over
the API — note `tags` is reconstituted from the DB's `tags_json` column
at serialization time, not stored as a real column), `LeadsPage` (a
paginated list), `LoginRequest`, `SignupRequest`, and `RecoverRequest`.

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
back. Dedupes against a `pending` dict of this batch's own new rows, not
just the database — a single search can legitimately
return the same job twice (matched by two different query templates,
scraped off two different search-result pages), and without the in-batch
check the second occurrence looks "new" to a plain SELECT (SQLAlchemy
hasn't flushed the first one yet) and crashes the whole batch on
SQLite's UNIQUE constraint at commit time instead of just updating in
place (found while live-testing the web job search).

### `backend/app/enrichment.py`
Two pieces of enrichment that don't need an external API call:
`guess_seniority()` — a regex over the job title for words like
"senior"/"staff"/"junior" — and `apply_growth_signals()`, which counts how
many other job leads the same company has posted within a rolling
30-day window and writes a "Hiring N roles in the last 30 days" signal
onto each one if that count is ≥2. This is what fills in the growth
signal for the three keyless job sources, which don't carry funding/
hiring-surge data themselves the way a web-sourced business lead does.

### `backend/app/scheduler.py`
The background refresh loop. The three keyless job APIs are free and fast,
so they refresh every few hours; the discovered-sites sweep fetches and
extracts pages locally — free, but seconds of GPU each — so it runs once a
day over a rotating slice. The on-demand endpoints stay manual, since
each is minutes of local compute (see `routers/ingest.py`). `run_job_sources_once()` calls every fetcher in
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
frontend decide whether to render the signup screen or the login
screen), `POST /signup` (409s if an account already exists; otherwise
creates one and returns the recovery phrase plus a session cookie — you
land in the app already signed in), `POST /login` (verifies against the
bcrypt hash and sets the session cookie), `POST /recover` (verifies the
recovery phrase and, if it matches, sets a new password — 400 on a
non-matching phrase), `POST /logout` (clears the cookie), `GET /me` (the
session check the frontend runs on every load to decide whether to show
the login screen at all). `login` and `recover` both call
`_enforce_throttle()` first (keyed on `request.client.host`) and
`record_failure()`/`record_success()` after, via `rate_limit.py` — added
once the app moved from tailnet-only to Tailscale Funnel, since a
publicly reachable login form is a meaningfully different threat model
than one only your own tailnet can even reach.

### `backend/app/rate_limit.py`
A deliberately simple in-memory throttle: `seconds_until_retry(key)`
prunes that key's failure timestamps older than a 5-minute window and
returns how long until the oldest one ages out, or 0 if under the
5-attempt limit; `record_failure()`/`record_success()` add or clear
entries. No persistence (resets on restart) and no distributed
coordination — intentional, since the goal is raising the cost of casual
automated password guessing against a single-user tool, not building a
production-grade WAF.

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
loop uses), `POST /careers` (career-page discovery for a
specific list of `{name, domain}` companies), `POST /business`
(business-lead discovery for one industry/region), `POST
/job_search` (job search for any role/region combo —
this is what reaches leadership titles and regions like the Gulf/Middle
East that the three keyless boards structurally can't). All three
web-scraping endpoints 503 immediately if Ollama — which does the
extraction — isn't reachable, via `sources.web.is_available()`, rather
than attempting a run that would fail minutes later. `GET /status`
reports that availability and the background loop's last-run
timestamps.

### `backend/app/sabha.py`
The bridge to Sabha, the local hiring-council service on port 8700, and
the place the two-tier design is written down. `quick_screen()` is one
call to a single local model (~5s) giving a rough 0-100 so 1,500+ leads
can be *ranked*; `run_council()` is Sabha's real seven-assessor pipeline
(~5 min measured) for one job someone has decided is worth it. They are
never conflated in the UI or the schema.

`run_council()` has to follow Sabha's two-step, order-dependent contract:
`POST /api/analyze` only *registers* a run and hands back an id — the work
doesn't start until the SSE stream is opened, and the run is discarded the
moment that stream closes. So the stream has to be opened and consumed in
one pass, which is why this blocks for minutes and gets called from a
background task rather than a request handler.

`quick_screen()` returns `None` rather than a number when the model is
unreachable or replies with something unparseable — an unscored lead is
recoverable, a fabricated score silently poisons the ranking.

### `backend/app/cv_extract.py`
Turns an uploaded PDF/`.docx`/text file into CV text, using the same two
libraries Sabha's `council/extract.py` uses (pypdf, python-docx) but
deliberately *not* importing it: the two repos are separately cloneable,
and coupling them through a filesystem path would break both. Bureau also
doesn't need Sabha's structural ATS signals (tables, text boxes, embedded
images) — those exist to audit how a parser will mangle a CV, which isn't
Bureau's job.

The guard worth keeping is the scan check: a PDF yielding under ~120
characters is almost certainly an image-only export, and saying so beats
storing an empty CV that then screens every lead as a poor match. Format
detection sniffs magic bytes as well as the extension, since a CV emailed
around for years often arrives misnamed. Errors are phrased to be shown
to a person and are passed through the API verbatim.

### `backend/app/screener.py`
The background loop that works through unscored leads. Two deliberate
properties: it polls Sabha's health and **stands down entirely while a
council run is active** (bulk work should never slow down the thing a
person is sitting waiting for), and it uses the `fit_score IS NULL`
column itself as the queue, so it resumes across restarts with no
separate progress file to fall out of sync.

`rescore_all()` clears every score when the CV changes — council verdicts
as well as screen scores. The council number is the more authoritative
one and the one someone acts on, so leaving a stale verdict on a card
whose screen score had just been cleared would be exactly backwards.
Fetched descriptions survive, since a posting's text doesn't depend on
whose CV it's being read against.

### `backend/app/routers/match.py`
`/api/match/*`: `GET /status` (is a CV stored, is Sabha up, how much
screening is left), `PUT|DELETE /cv`, and `POST /council/{lead_id}` which
marks the lead `running`, hands the work to a background task, and
returns immediately — the frontend polls the lead for the verdict, since
no sensible HTTP timeout survives a five-minute council.

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

### `backend/app/sources/web.py`
The free, local replacement for Firecrawl, and the only module that knows
how the open web is reached. Firecrawl did three separable things and each
has a free equivalent here: `search()` is DuckDuckGo via ddgs (no key),
`fetch_text()` is httpx + trafilatura, and `extract()` runs the local
Ollama over a page to pull out structured records.

That last one is the point worth noting — paying an API to run an LLM over
a page is the expensive half of a scrape, and this machine already has
models resident for Sabha. Extraction was never the part that needed
buying.

`fetch_text()` is two-tier on measurement, not principle: plain HTTP gets
arbeitnow and michaelpage in ~0.5s but returns 403 on Indeed, Bayt and
GulfTalent and 0 characters on mycareersfuture (a client-rendered app).
A headless Chromium gets all four at 3-4s. So HTTP runs first and the
browser only starts when that came back blocked, empty or suspiciously
thin — most pages never pay the 3s. `search()` retries on DuckDuckGo's
habit of answering a throttled query with "No results found", which was
observed silently costing a third of a search's coverage.

What this gives up versus a commercial scraping API: no proxy pool, no
CAPTCHA solving, so the hardest bot protection still wins. Callers treat
a failed fetch as "no data for this lead", which is the same posture they
had toward Firecrawl failures.


### `backend/app/sources/registry.py`
`JOB_FETCHERS`: the dict of `{name: fetch_function}` for the three
keyless job sources, consumed by `scheduler.py`'s background loop and by
the manual `/api/ingest/jobs` trigger. The web-scraping sources are
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

### `backend/app/sources/html_text.py`
Turns a posting's HTML into plain text at ingest time. This is a security
boundary, not a formatting nicety: storing third-party HTML and rendering
it in the logged-in page would let a malicious posting read the session
cookie, and the app is now reachable from the open internet. Sanitising
HTML properly needs an allowlist parser kept patched; job descriptions
lose almost nothing as text, so this converts instead and leaves nothing
to sanitise. Block tags become newlines, `<li>` becomes a bullet,
`<script>`/`<style>` content is dropped entirely. Verified against a real
36KB Remotive posting (→ 2.8KB readable) and an XSS payload (→ just the
harmless text).

### `backend/app/sources/job_description.py`
Fetches one posting's text on demand, immediately before a council run on
a lead that has no description — about two thirds of job leads, all of
which do have a URL. Backfilling all ~1,250 would spend a credit each on
pages almost none of which get opened; doing it at this moment spends a
few seconds to give five minutes of GPU something real to assess, and the
result is written back so the screen and later runs benefit.

Uses schema extraction rather than plain markdown, which was tried first
and rejected on evidence: `only_main_content` left a job-board page as
20KB of "Dismiss / Close menu / Popular / Locations" navigation with the
posting buried in it. Handing that to Sabha would be worse than a
title-only run, since its first step decomposes the posting into
requirements and would have been decomposing a nav bar. Naming the role
in the prompt also disambiguates aggregator pages listing many jobs.

Fetching and extraction both go through `sources/web.py`, so this
inherits its HTTP-then-browser fallback and its search retry.

### `backend/app/sources/discovered.py`

The local half of the daily automation: reads the
`sources/discovered_sites.json` that the GitHub Action commits, and turns
those domains into leads via domain-scoped searches. Sweeps a bounded
rotating slice (`todays_slice()`, 8 sites a day) rather than the whole
list, because the list only grows and a full daily sweep would scale
local fetch-and-extract time with it. The rotation is keyed on the date
rather than a stored cursor, so it's stable within a day and needs
nothing persisted.

### `backend/app/sources/concurrency.py`

`parallel_map(fn, items)` — what keeps a discovery run to minutes rather
than tens of minutes. Every source runs a handful of searches and then a
handful of page fetches, each a network round trip (and, on the browser
tier, several seconds). None depend on each other, so a
`ThreadPoolExecutor` (6 workers) runs them concurrently, preserving input
order and logging-and-skipping a failed item rather than aborting the
batch.

### `backend/app/sources/jobs/career_pages.py`

Given a list of `{name, domain}` companies, finds each one's careers page
and extracts its open listings. Firecrawl's `map` used to enumerate a
domain's URLs to locate that page; without it this probes the handful of
paths companies actually use (`/careers`, `/jobs`, …) and falls back to a
site-scoped search. Less thorough than a real crawl, but free, and those
conventional paths cover most company sites. The probe deliberately
passes `allow_browser=False` — starting Chromium six times just to
discover a URL would cost more than the page is worth. Manual-only, via
`/api/ingest/careers`.

### `backend/app/sources/jobs/job_search.py`

The general-purpose job source, added because the three keyless boards
have two structural blind spots: they skew toward individual-contributor
tech roles (leadership titles essentially never appear) and their
regional coverage is Western/remote-only (no Gulf presence at all, and
Adzuna — the other free-tier option — doesn't cover the Middle East
either). `_search_urls()` runs three query templates through
`web.search()` concurrently; `fetch()` then fetches and extracts each
matched page, also concurrently.

The extraction prompt deliberately does **not** ask the model to filter
by role or region, which was measured actively losing leads: a page found
by searching "IT Director in UAE" listed a Riyadh role, and the model
dutifully returned nothing because it wasn't in the UAE. The search
already did the targeting, each job's own location is parsed below, and
the app has its own region filter — a second, stricter filter here only
discards good leads. After that fix the same search returned 24 real UAE
leads.

`fetch_scoped()` is the variant the discovered-sites sweep uses: one raw
query confined to specific domains, with no template fan-out, since the
domain is already the narrowing.

### `backend/app/sources/business/company_signals.py`

The business-opportunity pipeline. Four query templates per
industry/region (funding, active hiring, expansion, new leadership — the
four signal types the brief called out) go through `web.search()`, and
each matched page is fetched and read by the local model for the
company's name, domain, HQ, size, funding stage, the specific signal, and
a **company-level** contact path — explicitly prompted never to return a
named individual's personal contact details.

This is also where Crunchbase/LinkedIn company pages get picked up if a
search lands on one: in scope per explicit sign-off despite both
prohibiting scraping in their ToS, public unauthenticated pages only.
Worth knowing that both now refuse a plain HTTP fetch and are only
reachable through the browser tier, and LinkedIn often refuses outright —
those come back empty rather than failing the run.

## `backend/scripts/` — one-off CLI scripts

### `backend/scripts/set_password.py`
The emergency CLI path — force-sets the password via
`auth.set_credentials()`, bypassing the recovery phrase entirely. Prompts
for username/password (or takes `--username`/`--password` flags for
non-interactive use). The normal way to create an account and to reset a
forgotten password is the web UI (signup screen, and "Forgot password?"
respectively); this script exists only for "I lost both the password and
the recovery phrase, but I have shell access to this Mac."

### `backend/scripts/seed_mock_data.py`
Inserts the sample leads from `app/mock_data.py` through the normal
`upsert_leads()` path, so they behave exactly like real leads (dedupe,
starring, export) while you're looking at the UI before real sources
have populated anything.

### `backend/scripts/clear_mock_data.py`
Deletes every lead with `source = "mock"`. The natural next step after
`seed_mock_data.py` once real sources have replaced the need for sample
data.

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
The masthead auth screen — the large italic serif "Bureau" wordmark, a
short accent-colored hairline rule, and a letterspaced uppercase tagline
sit above one of four forms depending on internal `mode` state. On
mount it calls `/api/auth/status` to decide the starting mode: `signup`
if no account exists yet, `login` otherwise. `signup` posts to
`api.signup()` and, on success, switches to `recovery-display` — a
distinct full screen (not a modal) showing the 12 returned words in a
numbered 3-column grid with a "shown once" warning; a required
"I've saved this" checkbox gates the Continue button, which calls
`onLoggedIn` directly since signup already set the session cookie.
`login` is the plain username/password form, with a "Forgot password?"
button that switches to `recover` instead of navigating anywhere.
`recover` posts a phrase + new password to `api.recover()` and, on
success, drops back to `login` with a confirmation message rather than
logging the user in automatically — deliberately a separate step from
authenticating, so a successful recovery doesn't silently skip straight
past re-entering credentials.

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
border, which is the card's visual focal point.

The whole card is the click target (opening `LeadDetailPanel`), which
means the two interactive things *inside* it have to opt out: the star
button calls `stopPropagation()` so starring doesn't also open the panel,
and the title is no longer a link — "open the original posting" moved
into the panel, since a link inside a clickable card gives two different
outcomes for what looks like one target. Keyboard access is explicit
(`role="button"`, Enter/Space) because a `<div>` doesn't get it for free.

### `frontend/src/components/LeadDetailPanel.tsx`
The drawer a card opens into: the full description (rendered as plain
text with `whitespace-pre-wrap`, since it *is* plain text by the time it
reaches here), the screen score and its note, and the council section —
which is a small state machine over `council_status`: a run button, a
"the council is sitting" state that polls every 10s, or the finished
verdict with score, requirement-match percentage and blocking gaps.
Polling rather than holding a connection is what makes closing the panel
mid-run safe.

### `frontend/src/components/CvPanel.tsx`
Where the CV goes in, and the honest status panel for the whole matching
stack: whether a CV is stored and how big, whether Sabha is reachable
(so a five-minute run doesn't fail at the end for a reason that was
knowable up front), and how many leads are still queued for screening.

### `frontend/src/components/Spinner.tsx`
A small `<span>` styled as a spinning ring purely with Tailwind
(`animate-spin` + a transparent top border-side), no image/SVG asset.
Takes an optional `className` so callers can resize/recolor it (it
inherits `currentColor` for the ring, so it matches whatever text color
context it's dropped into). Used anywhere a request can visibly take a
while: both Discover buttons, "Refresh job sources," and the initial
results load.

### `frontend/src/components/ResultsFeed.tsx`
The grid of `LeadCard`s plus four states: an error message, a centered
`Spinner` for the initial load (`loading && leads.length === 0`), an
empty-state message (styled as an italic serif line, matching the
masthead voice) once loading has finished with nothing to show, and a
smaller inline spinner+"Loading…" under the grid while paginating
further pages of an already-populated list. Purely a presentational
component — pagination state lives in `App.tsx`.

### `frontend/src/components/BusinessDiscovery.tsx`

The industry/region search bar above the feed on the Business
Opportunities tab. If the backend reports the local extraction model is
unreachable (checked once by `App.tsx` via `/api/ingest/status`), it says
so instead of offering a search that would fail. Otherwise, submitting
calls `api.ingestBusiness()`, shows a `Spinner` while the request is in
flight — this one is genuinely minutes long — and reports how many leads
were created/updated before calling `onDiscovered()` so `App.tsx`
re-fetches.

### `frontend/src/components/JobDiscovery.tsx`

The equivalent search bar for the Jobs tab — a free-text role rather than
an industry, calling `api.ingestJobSearch()`. This is what a person
actually uses to pull in a leadership title or a region the automatic
sources don't cover. Renders nothing at all when the extraction model is
unreachable, unlike `BusinessDiscovery`: the job feed already has three
working automatic sources and doesn't need to nag about a fourth,
optional one.

### `frontend/vite.config.ts`
Registers the React and Tailwind v4 Vite plugins, and proxies `/api` to
`http://127.0.0.1:8910` in dev mode so the frontend dev server and the
backend can run on different ports without a CORS setup.

---

## `deploy/` and `.claude/` — running it

### `deploy/com.bureau.backend.plist`
The `launchd` user-agent **template** that keeps the backend running:
runs `.venv/bin/uvicorn app.main:app` from `backend/`, restarts on crash
(`KeepAlive`) and on login (`RunAtLoad`), and logs to `~/Library/Logs/
Bureau/`. Committed with `/Users/YOURNAME/...` placeholders rather than
a real path, since this repo is public — the actual, filled-in copy
lives outside the repo entirely, at `~/Library/LaunchAgents/com.bureau.
backend.plist`, which is what `launchctl` actually loads (see `README.
md`'s "Running as a persistent background service" section for the copy
+ fill-in + bootstrap steps). Note: a Python venv embeds absolute paths
in its script shebangs, so if this repo is ever moved to a different
path, `backend/.venv` has to be deleted and recreated there — `mv`-ing
it along with the rest of the repo will silently break it.

### `site/index.html`, `backend/scripts/build_site.py` and `.github/workflows/pages.yml`
The always-on published copy, at
[saiaarjay09.github.io/Bureau](https://saiaarjay09.github.io/Bureau/).
Bureau runs on a laptop, and a laptop sleeps; GitHub Pages is free, never
sleeps and needs no card, but cannot run Python, SQLite or a local model.
So the build ships the data and the filtering, and is explicit about the
two things it can't do — CV matching (local models, private CV) and
on-demand Discover searches (need server-side fetching).

Where the data comes from is the whole design. The Action can't reach this
Mac's database, so `build_site.py` **refetches the three keyless job APIs
live in CI** — they're plain HTTP and import nothing heavier than httpx,
which is what keeps the site current with the Mac switched off. The
locally-scraped regional leads (UAE, Gulf, APAC) *can't* be regenerated
there, since extraction needs Ollama, so they come from a committed
snapshot that `export_leads.py` writes. The CI job therefore installs only
`httpx sqlalchemy python-dotenv`, verified in a clean venv.

`export_leads.py` deliberately withholds everything personal: the
`fit_score`/`fit_reason` screen, the `council_*` verdicts and the starred
flags are all judgements about one private CV or one private shortlist.
Only the postings — public to begin with — are published. It also limits
**per lead type** rather than globally, because one global limit let the
far more numerous job leads fill the whole quota and exported zero
business leads, silently emptying that tab on the published site.

`site/index.html` is a single checked-in file with inlined CSS and vanilla
JS — no build step, no framework — carrying the same broadsheet tokens and
masthead treatment as the app. Two bugs worth recording from building it:
the lead grid used `1fr` columns, and since a bare `1fr` means
`minmax(auto, 1fr)` whose `auto` is the *min-content* width of a
`white-space:nowrap` title, the grid blew out to 1893px inside a 1024px
viewport and the ellipsis never engaged (`minmax(0, 1fr)` fixes it); and
switching tabs carried filters across, so a leftover "director" search
showed 0 business leads with no hint that a stale filter rather than an
empty feed was the cause. Stars are `localStorage`, keyed on
source+title+company rather than an index, because a daily rebuild
renumbers every lead and an index key would silently re-point stars at
different jobs.

Enabling it is a one-time repo setting (**Settings → Pages → Source:
GitHub Actions**); until that's switched the workflow builds fine but the
deploy step has nowhere to publish.

### `.github/workflows/discover-sources.yml` and `backend/scripts/discover_sources.py`

The cloud half of the daily automation. The script sweeps regions through
DuckDuckGo for job boards and opportunity portals, normalises what it
finds to bare domains (dropping aggregators, social sites, search engines
and our own existing sources), and merges new entries into
`sources/discovered_sites.json` — append-only, each carrying the query
that found it, because Bureau spends a fetch and a model call on every
domain in that file and a bad entry keeps costing until someone removes
it. It retries a throttled search, since DuckDuckGo answers those with
"No results found" and would otherwise silently drop a region's coverage.

The workflow needs **no secrets at all** — DuckDuckGo takes no API key.
It previously needed `FIRECRAWL_API_KEY`, which in a public repo meant
carefully ensuring no `pull_request` trigger could ever expose it to a
fork PR; dropping the paid API removed that whole class of problem.

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

### `backend/app/data/wordlist.txt`
The 2048-word BIP39 English wordlist, copied verbatim from Haven
(`haven/data/wordlist.txt`). Loaded once at import time by
`recovery.py`, which asserts it has exactly 2048 lines.

### `backend/requirements.txt`
Pinned backend dependencies: FastAPI, Uvicorn, SQLAlchemy, httpx, bcrypt,
itsdangerous (session signing), python-dotenv; ddgs/trafilatura/playwright
for the free scraping stack; and pypdf/python-docx/python-multipart for CV
uploads. Playwright also needs a one-off `python -m playwright install
chromium`.

### `backend/.env.example`
The template for `backend/.env` (which is gitignored and never
committed). Nothing in it is required any more now that scraping runs
free and locally; it documents the optional `BUREAU_SECRET_KEY` and
`BUREAU_INGEST_INTERVAL_SECONDS`.

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
