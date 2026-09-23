from .jobs import arbeitnow, remotive, remoteok

# Keyless job-board sources — safe to run automatically on the background
# schedule (see app/scheduler.py). Firecrawl-based sources (career pages,
# business leads) are NOT here: they cost credits per call, so they're only
# triggered manually via routers/ingest.py.
JOB_FETCHERS = {
    "remotive": remotive.fetch,
    "arbeitnow": arbeitnow.fetch,
    "remoteok": remoteok.fetch,
}
