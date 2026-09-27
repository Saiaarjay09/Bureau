from .jobs import arbeitnow, remotive, remoteok

# Keyless job-board sources — safe to run automatically on the background
# schedule (see app/scheduler.py). The web-scraping sources (career pages,
# job search, business leads) are NOT here: each costs minutes of local
# fetching and model time, so they're triggered manually via
# routers/ingest.py.
JOB_FETCHERS = {
    "remotive": remotive.fetch,
    "arbeitnow": arbeitnow.fetch,
    "remoteok": remoteok.fetch,
}
