# Bureau

A single-user, single-page lead-generation tool. It surfaces two kinds of
leads — **job openings** and **business opportunities** — filterable by
region (continent → country → city), with save/star and CSV/JSON export.

**Links:** [github.com/Saiaarjay09/Bureau](https://github.com/Saiaarjay09/Bureau)
(source) · [ARCHITECTURE.md](ARCHITECTURE.md) (a full code tour, file by
file) · **[haven.taila6d3cb.ts.net:8930](https://haven.taila6d3cb.ts.net:8930)**
— a running instance, open to anyone with the URL. It's still gated by a
username/password login (see "Credentials" below) — this link gets you
to the sign-in screen, not straight into anyone's data. If you're
running your own copy rather than using that one, see "Setup" below.

## Architecture

- **Backend**: Python/FastAPI (`backend/`), SQLite for storage/dedup.
- **Frontend**: React + Tailwind, built with Vite (`frontend/`), served as
  static files by the backend in production (one process, one port).
- **Auth**: single username/password, bcrypt-hashed, session cookie —
  see "Credentials" below.
- **Job sources**: three keyless public APIs (Remotive, Arbeitnow,
  RemoteOK) refreshed automatically every 6 hours, plus web search and
  career-page discovery triggered manually.
- **Business-lead sources**: web search + page reading per industry/region,
  triggered manually from the UI's "Discover businesses" bar.
- **Scraping stack**: free and local — DuckDuckGo search, httpx with a
  headless-Chromium fallback, and Ollama for extraction. No paid API.

## Data sources and their limits — read before relying on this

**Job leads (automatic, no signup needed):**
[Remotive](https://remotive.com), [Arbeitnow](https://www.arbeitnow.com),
and [RemoteOK](https://remoteok.com)'s public JSON APIs. All three are
free and keyless, but have two structural blind spots: they skew toward
individual-contributor tech roles (leadership titles like "IT Director"
essentially never appear — Remotive/RemoteOK/Arbeitnow just aren't where
those get posted), and their regional coverage is Western/remote-only
(Remotive/RemoteOK are remote-only, Arbeitnow is Europe-centric — neither
has any Gulf/Middle East presence). [Adzuna](https://developer.adzuna.com)
would broaden general coverage (needs a free signup) but doesn't fix the
Middle East gap either — its country list is AU/AT/BE/BR/CA/FR/DE/IN/IT/
MX/NL/NZ/PL/SG/ZA/ES/CH/GB/US, no Middle East at all (checked directly
against Adzuna's own docs).
[USAJobs](https://developer.usajobs.gov) (US federal listings, also
needs a signup) is narrower still. Neither is wired up here — see
"Finding what the automatic sources miss" below for what actually
closes those two gaps today.

**Job leads (manual, free but slow):** career-page discovery for
specific companies via `/api/ingest/careers`, and a general role/region
job search via `/api/ingest/job_search` — the "Discover" bar on the Jobs
tab — which is what actually reaches leadership titles and regions like
the UAE that the three automatic sources can't. Both search, fetch and
extract locally, so they cost nothing but take a couple of minutes.

**Business-opportunity leads (manual, free but slow):**
web search per industry+region, then reads the matched
pages for company details and a "why now" signal (funding, hiring surge,
expansion, new exec). **This includes Crunchbase and LinkedIn company
pages** — both explicitly prohibit scraping in their Terms of Service.
That's a real risk (IP blocks at minimum, possible ToS/legal exposure)
that you've explicitly accepted for this build; only their public,
unauthenticated pages are ever touched, never anything behind a login
wall, and never a named individual's personal contact info — only
company-level contact paths (an inquiry email pattern or contact page
URL).

**Nothing here needs a paid API.** Web search is DuckDuckGo (no key),
pages are fetched with plain HTTP and — only when a site refuses that or
renders client-side — a local headless Chromium, and the structured
extraction that turns a page into leads runs on the same local Ollama
that does CV screening. The only external dependency is Ollama being up;
if it isn't, the discovery bars say so.

This replaced Firecrawl, which was doing the same three jobs for money.
The honest tradeoff: there's no proxy pool or CAPTCHA solving, so sites
behind the very hardest bot protection can still refuse, and a page takes
seconds rather than being someone else's problem. In testing the browser
tier recovered every site that blocked plain HTTP — Indeed, Bayt,
GulfTalent — and a UAE "IT Director" search returned 24 real leads.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional; nothing in it is required any more

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

Open `http://127.0.0.1:8910`. The first time, you'll see a **Create
account** screen instead of a login form — pick a username and password
(8+ characters), and you'll immediately be shown a **12-word recovery
phrase**, once, in a boxed layout with a "save this now" warning. Write
it down; it's the only way back in if you forget your password, and
Bureau never shows it again. Checking "I've saved this phrase" and
clicking Continue logs you straight in. The three keyless job sources
ingest automatically on startup and every 6 hours after.

To iterate on the frontend with hot reload instead of rebuilding each
time: `cd frontend && npm run dev` (proxies `/api` to port 8910 — see
`frontend/vite.config.ts`).

## Credentials

Bureau is single-user — one account, no separate profiles. Sharing
access with someone else (a family member, e.g.) means sharing that one
username/password with them directly, out of band — text, call, in
person — never by putting it in this README or anywhere else in the
repo, especially now that the repo and the running instance are both
public. Whoever's logged in sees the same leads, stars, and everything
else; there's no per-person data separation.

**Forgot your password?** Click "Forgot password?" on the sign-in
screen, paste in your 12-word recovery phrase, and set a new one — no
CLI needed. The recovery phrase itself doesn't change when you do this.

**Lost the recovery phrase too?** There's no way to recover the account
through the UI at that point (by design — the recovery phrase is the
only backup, same as Haven's). Fall back to the CLI escape hatch, which
force-sets the password directly on the server (only reaches whoever has
shell access to this Mac):

```bash
cd backend && source .venv/bin/activate
python3 scripts/set_password.py --username you --password 'new-password'
```

This writes a bcrypt hash to `backend/data/auth.json` — never plaintext.
Since it's single-user, signup (and the recovery phrase that comes with
it) only ever happens once; running this script on an existing account
just changes the password and leaves the existing recovery phrase valid.
Changing it invalidates nothing else; existing sessions just check
against the new hash on their next request.

## Running as a persistent background service

A `launchd` user-agent keeps the backend running across reboots and
restarts it if it crashes, the same way Haven's own services do on this
machine. `deploy/com.bureau.backend.plist` in the repo is a **template**
with `/Users/YOURNAME/...` placeholders — copy it into
`~/Library/LaunchAgents/`, fill in your actual username/paths, and run
launchd from that copy, not the repo file directly, so your real paths
never need to be committed:

```bash
mkdir -p ~/Library/Logs/Bureau
cp deploy/com.bureau.backend.plist ~/Library/LaunchAgents/
# then edit ~/Library/LaunchAgents/com.bureau.backend.plist,
# replacing every /Users/YOURNAME/... with your actual home directory
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.bureau.backend.plist
```

Useful commands:

```bash
# Check it's running
launchctl list | grep com.bureau

# Restart after a code change (rebuild the frontend first if you touched it)
launchctl kickstart -k gui/$(id -u)/com.bureau.backend

# Stop it entirely
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.bureau.backend.plist

# Logs
tail -f ~/Library/Logs/Bureau/backend.log
```

## Serving over Tailscale

Two options here, and which one you want depends on who needs to reach
it:

- **Serve** — reachable only from devices logged into your own tailnet.
  No public exposure at all; the right default if it's just for you.
- **Funnel** — reachable from the open internet at a stable
  `*.ts.net` URL, the same way Haven exposes itself to friends. Needed
  if someone without Tailscale installed (a family member, e.g.) should
  be able to just open a link.

This machine runs **Funnel**, because that's what's needed for someone
outside the tailnet to use it:

```bash
tailscale funnel --bg --https=8930 http://127.0.0.1:8910
```

That maps `https://<your-device>.<your-tailnet>.ts.net:8930` to the
backend on 127.0.0.1:8910 — HTTPS handled entirely by Tailscale. Run
`tailscale status` to see your own device/tailnet name. Verify any time
with `tailscale funnel status` — look for `(Funnel on)` next to the 8930
entry.

If you'd rather keep it private, swap `funnel` for `serve` in that
command instead (or run `tailscale funnel --https=8930 off` to drop back
to tailnet-only, assuming a `serve` mapping for the same port already
exists). Because Funnel/Serve config is shared per-port on this device,
and ports 443/8443/10000 are already funneled for Haven's other apps,
Bureau uses its own port (8930) rather than reusing one of those.

**Because this is now open to the whole internet, not just your
tailnet:** the login and password-recovery endpoints are rate-limited
(5 failed attempts per 5 minutes per IP, in-memory — see
`backend/app/rate_limit.py`) specifically to blunt automated password
guessing now that the URL is public. That's a basic deterrent, not a
hardened defense — use a real password, and treat the recovery phrase
with the same care as the password itself, since either one alone gets
in.

**Visit `https://<your-device>.<your-tailnet>.ts.net:8930` from
anywhere** — no Tailscale required on the visitor's end when Funnel is
on.

## Matching leads against your CV (Sabha)

Bureau hands jobs to [Sabha](https://github.com/Saiaarjay09/hiring-council),
the local hiring-council service, which runs a seven-member panel of
open-weight models over a job and a CV. Both tiers run entirely on this
Mac — nothing is sent to any external service.

Add your CV under **CV** in the header — either **Browse files…** for a
PDF or Word (.docx) file, or paste the text. Uploaded files are parsed in
memory and the bytes discarded; only the extracted text is stored, at
`backend/data/cv.txt` (gitignored). That's a deliberate departure from
Sabha, which keeps a CV in memory and never writes it down: Bureau needs
it on disk so new leads can be screened while nobody's at the keyboard.
Delete it any time from the same panel.

A scanned or image-only PDF has no extractable text, and Bureau says so
rather than silently storing an empty CV — which would otherwise screen
every lead as a poor match for a reason that looked like the jobs' fault.

There are **two numbers, and they mean different things**:

| | What it is | Cost | Where |
|---|---|---|---|
| **screen** | One pass of a single local model over the job + CV, giving a rough 0-100 so the feed can be sorted | ~5s/lead, automatic | On every card, and the "Best fit first" sort |
| **council** | Sabha's real pipeline — job decomposed into requirements *before* the CV is read, then seven biased assessors argue | ~5 min/job, on demand | "Convene the council" inside a lead |

The screen exists only to rank 1,500+ leads so the council's five minutes
get spent on the right ones. It reads the job and CV together, which is
exactly the shortcut Sabha's design argues against — treat it as triage,
not as a verdict. Measured on this machine: a full council run took 293s
and returned a considered 30/100 with seven specific blocking gaps, where
the screen had put the same job at 45.

Screening runs continuously in the background and **stands down whenever a
council run is in flight**, so the thing you're waiting on gets the GPU.
Changing or removing your CV clears every existing score — screen *and*
council — because a score against an old CV is worse than no score.
Fetched job descriptions are kept, since those don't depend on your CV.

**Leads without a description still work.** About two thirds arrive with
only a title (job boards that aged out, or listing pages that showed no
body text). Convening the council on one of those fetches the real
posting first — a few seconds of local fetching, well spent given the run
costs five minutes of GPU either way — and stores it, so the
screen and any later run get it too. If the fetch fails or there's no
URL, Sabha assesses the title against a generic rubric for that role and
says so in its own summary.

Sabha must be running locally (port 8700) for the council button to work —
the CV panel shows whether it's reachable.

## Daily automation: discovering new sources

Two halves, split by what each needs:

**On GitHub** (`.github/workflows/discover-sources.yml`, daily at 03:17
UTC): sweeps regions for job boards and opportunity portals worldwide and
commits anything new to [`sources/discovered_sites.json`](sources/discovered_sites.json).
It found `mycareersfuture.gov.sg` (Singapore's official government job
portal), `dubaicareers.ae`, and `gebiz.gov.sg` (government procurement) on
its first run — exactly the regional coverage the three keyless APIs lack.

It needs **no repository secret at all** — DuckDuckGo search takes no API
key. (It used to need `FIRECRAWL_API_KEY`, which in a public repo meant
being careful no fork-PR trigger could ever expose it; that whole class
of problem went away with the paid API.)

**On this Mac**: the background loop sweeps a rotating slice of those
sites once a day (8 per pass, so the list gets covered over several days
rather than spending an hour of local compute every morning) and ingests
what it finds. Run it by hand any time with:

```bash
cd backend && source .venv/bin/activate
python3 scripts/discover_sources.py --regions "India,Kenya" --dry-run
```

## Finding what the automatic sources miss

The "Search the web for [a role]" bar on the Jobs tab exists specifically
for the two gaps above: leadership titles and non-Western regions.
Type a role (e.g. "IT Director", "Head of IT") and, if you've set a
region filter, it searches within that region — e.g. filter to United
Arab Emirates first, then search "IT Director" — or leave the filter on
Global to search everywhere. Each search costs no money but a couple of minutes of local fetching and
model time (pages are fetched concurrently — see
`backend/app/sources/concurrency.py`), so like the business-leads bar,
it's manual rather than automatic. A spinner shows
in the button while it's running. Verified live while building this:
found 47 director/IT-director-titled roles and 19 real UAE listings,
both zero from the three automatic sources alone.

## Populating business leads

Live-tested end to end: search → fetch → extraction → dedupe → visible in
the feed, all on free local infrastructure. A UAE "IT Director" search
returned 24 real leads (including roles at IOTA Group in Abu Dhabi and
Focus Direct in Dubai) in about two and a half minutes, and a Singapore
fintech sweep returned companies with genuine funding signals.

The "Discover businesses" bar (Business Opportunities tab) takes an
industry and searches within whatever region you've currently filtered
to (or globally, if set to "Global"). Each click costs a couple of minutes of local fetching and model time
rather than money, so it's manual rather than on a schedule.

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
