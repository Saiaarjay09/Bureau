# Bureau

A single-user, single-page lead-generation tool. It surfaces two kinds of
leads — **job openings** and **business opportunities** — filterable by
region (continent → country → city), with save/star and CSV/JSON export.
It's meant to run on your own Mac and be reachable only from your own
Tailscale network, not the public internet.

## Architecture

- **Backend**: Python/FastAPI (`backend/`), SQLite for storage/dedup.
- **Frontend**: React + Tailwind, built with Vite (`frontend/`), served as
  static files by the backend in production (one process, one port).
- **Auth**: single username/password, bcrypt-hashed, session cookie —
  see "Credentials" below.
- **Job sources**: three keyless public APIs (Remotive, Arbeitnow,
  RemoteOK) refreshed automatically every 6 hours, plus Firecrawl-based
  career-page discovery triggered manually.
- **Business-lead sources**: Firecrawl web/news search + page scraping,
  triggered manually per industry/region from the UI's "Discover
  businesses" bar (Business Opportunities tab).

## Data sources and their limits — read before relying on this

**Job leads (automatic, no signup needed):**
[Remotive](https://remotive.com), [Arbeitnow](https://www.arbeitnow.com),
and [RemoteOK](https://remoteok.com)'s public JSON APIs. All three are
free and keyless. Coverage skews toward remote/tech roles; onsite and
non-tech roles are underrepresented. Broadening this (e.g.
[Adzuna](https://developer.adzuna.com) for much wider geographic/industry
coverage, or [USAJobs](https://developer.usajobs.gov) for US federal
listings) is a deliberate next step, not done here — both need you to
sign up for a free API key yourself first.

**Job leads (manual, costs Firecrawl credits):** career-page discovery
for specific companies via `/api/ingest/careers` — maps a company's
domain, finds its careers page, and extracts current listings.

**Business-opportunity leads (manual, costs Firecrawl credits):**
Firecrawl web/news search per industry+region, then scrapes the matched
pages for company details and a "why now" signal (funding, hiring surge,
expansion, new exec). **This includes Crunchbase and LinkedIn company
pages** — both explicitly prohibit scraping in their Terms of Service.
That's a real risk (IP blocks at minimum, possible ToS/legal exposure)
that you've explicitly accepted for this build; only their public,
unauthenticated pages are ever touched, never anything behind a login
wall, and never a named individual's personal contact info — only
company-level contact paths (an inquiry email pattern or contact page
URL).

**Firecrawl requires its own API key** (get one at
[firecrawl.dev](https://www.firecrawl.dev)) — set `FIRECRAWL_API_KEY` in
`backend/.env`. Without it, `/api/ingest/careers` and `/api/ingest/business`
return 400 and the "Discover businesses" bar shows a note instead of the
search box; everything else (job sources, mock business data, filtering,
export) still works.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # edit in FIRECRAWL_API_KEY etc. if you have them
python3 scripts/set_password.py   # sets your login — prompts for username/password

cd ../frontend
npm install
npm run build                # produces frontend/dist, which the backend serves
```

### Try it locally first

```bash
cd backend && source .venv/bin/activate
python3 scripts/seed_mock_data.py   # optional: sample leads to look at immediately
uvicorn app.main:app --host 127.0.0.1 --port 8910
```

Open `http://127.0.0.1:8910` and sign in. The three keyless job sources
ingest automatically on startup and every 6 hours after.

To iterate on the frontend with hot reload instead of rebuilding each
time: `cd frontend && npm run dev` (proxies `/api` to port 8910 — see
`frontend/vite.config.ts`).

## Credentials

Set or change your login any time:

```bash
cd backend && source .venv/bin/activate
python3 scripts/set_password.py --username you --password 'new-password'
```

This writes a bcrypt hash to `backend/data/auth.json` — never plaintext.
Changing it invalidates nothing else; existing sessions just check
against the new hash on their next request.

## Running as a persistent background service

A `launchd` user-agent keeps the backend running across reboots and
restarts it if it crashes, the same way Haven's own services do on this
machine.

```bash
mkdir -p ~/Library/Logs/Bureau
launchctl bootstrap gui/$(id -u) ~/Developer/bureau/deploy/com.bureau.backend.plist
```

Useful commands:

```bash
# Check it's running
launchctl list | grep com.bureau

# Restart after a code change (rebuild the frontend first if you touched it)
launchctl kickstart -k gui/$(id -u)/com.bureau.backend

# Stop it entirely
launchctl bootout gui/$(id -u) ~/Developer/bureau/deploy/com.bureau.backend.plist

# Logs
tail -f ~/Library/Logs/Bureau/backend.log
```

The plist assumes this repo lives at `~/Developer/bureau` — edit the paths
inside it first if you move it.

## Serving over Tailscale

You asked whether this needs Serve or Funnel: **Serve**. Funnel exposes a
port to the whole public internet (that's what Haven uses, since
friends outside your tailnet need to reach it); Serve only makes it
reachable from devices logged into your own tailnet, which is all Bureau
needs since it's just for you.

This is already set up and running on this machine:

```bash
tailscale serve --bg --https=8930 http://127.0.0.1:8910
```

That maps `https://haven.taila6d3cb.ts.net:8930` to the backend on
127.0.0.1:8910 — HTTPS handled entirely by Tailscale, tailnet-only (no
public exposure). Verify any time with:

```bash
tailscale serve status
```

Look for `(tailnet only)` next to the 8930 entry, not `(Funnel on)`. To
tear it down: `tailscale serve --https=8930 off`.

Because Funnel and Serve share config per-port on this device, and ports
443/8443/10000 are already funneled (public) for Haven's other apps,
Bureau deliberately uses its own port (8930) that's never been funneled —
don't run `tailscale funnel --https=8930 ...` unless you specifically
want to make Bureau public too.

**Visit `https://haven.taila6d3cb.ts.net:8930` from any device signed
into your tailnet.** It won't resolve from anywhere else.

## Populating business leads

The "Discover businesses" bar (Business Opportunities tab) takes an
industry and searches within whatever region you've currently filtered
to (or globally, if set to "Global"). Each click spends Firecrawl
credits, so it's manual rather than on a schedule — check
[firecrawl.dev](https://www.firecrawl.dev)'s pricing before running it
across a lot of industries/regions.

Career-page discovery for specific companies is API-only for now (no UI
yet):

```bash
curl -s -b cookies.txt -X POST http://127.0.0.1:8910/api/ingest/careers \
  -H "Content-Type: application/json" \
  -d '{"companies": [{"name": "Acme Inc", "domain": "acme.com"}]}'
```

## Mock data

`scripts/seed_mock_data.py` inserts sample leads (tagged `source: mock`)
so the UI has something to show before real sources are wired up. Once
you're happy with real data, clear them out:

```bash
python3 backend/scripts/clear_mock_data.py
```

## What's explicitly out of scope

Per the boundaries this was built to: no login-walled scraping, no
CAPTCHA/paywall bypassing, no scraping individuals' private profile
data, and business leads only ever surface company-level contact paths
— never a named individual's personal email or phone number.
