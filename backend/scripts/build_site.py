#!/usr/bin/env python3
"""Build the static Bureau site for GitHub Pages.

WHY THIS EXISTS

Bureau runs on a personal Mac, which means it's unreachable whenever that
Mac sleeps — and a laptop sleeps. GitHub Pages is free, always on, needs no
card and never sleeps. It just cannot run Python, SQLite or a local model.

What survives that constraint is most of what the app is actually used for:

    the lead feed      a JSON file this script refreshes daily
    region filtering   continent/country/city, derived from the data itself
    search and sort    string matching and comparisons, fine in a browser
    CSV/JSON export    a Blob download, no server involved

What genuinely cannot:

    CV matching        the screen and the Sabha council both need the local
                       Ollama, and the CV is private — so the static site
                       doesn't pretend to have them
    Discover searches   need to fetch and extract pages server-side

Where the data comes from matters. The three keyless job APIs are plain
HTTP, so this refetches them live in CI every run — that's what makes the
site stay current without the Mac. The web-scraped regional leads (UAE,
Gulf, APAC) can't be regenerated here because extraction needs Ollama, so
they come from the committed snapshot that export_leads.py produces.

    python3 backend/scripts/build_site.py --out site
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

MAX_LEADS_PER_TYPE = 700
MAX_DESCRIPTION_CHARS = 1500


def fetch_live_sources() -> list[dict]:
    """The three keyless APIs, refetched here so the published site is current
    even if the Mac hasn't been on for a week. A failing source is logged and
    skipped rather than failing the build — a published site missing one
    source beats no deploy at all."""
    from app.sources.jobs import arbeitnow, remoteok, remotive

    leads: list[dict] = []
    for name, module in (("remotive", remotive), ("arbeitnow", arbeitnow), ("remoteok", remoteok)):
        try:
            fetched = module.fetch()
            print(f"  {name:12} {len(fetched)} leads")
            leads.extend(fetched)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {name}: {type(exc).__name__}: {str(exc)[:80]}", file=sys.stderr)
    return leads


def load_snapshot() -> list[dict]:
    """Locally-scraped leads committed by export_leads.py. Absent on a fresh
    clone, which is fine — the site just carries the live sources."""
    path = REPO_ROOT / "site" / "data" / "snapshot.json"
    if not path.exists():
        print("  (no snapshot.json — skipping locally-scraped leads)")
        return []
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        print("  ! snapshot.json is unparseable; ignoring it", file=sys.stderr)
        return []
    leads = payload.get("leads") or []
    print(f"  snapshot     {len(leads)} leads (exported {payload.get('exported_at', '?')[:10]})")
    return leads


def normalise(lead: dict) -> dict:
    """One shape for the browser, with descriptions capped — 700 leads at full
    length would be megabytes of text nobody has opened yet."""
    posted = lead.get("posted_date")
    if isinstance(posted, datetime):
        posted = posted.isoformat()
    description = (lead.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS].rstrip() + "…"
    return {
        "lead_type": lead.get("lead_type") or "job",
        "title": lead.get("title") or "",
        "company": lead.get("company") or "",
        "url": lead.get("url"),
        "source": lead.get("source") or "",
        "continent": lead.get("continent"),
        "country": lead.get("country"),
        "city": lead.get("city"),
        "remote_type": lead.get("remote_type"),
        "seniority": lead.get("seniority"),
        "industry": lead.get("industry"),
        "contact_path": lead.get("contact_path"),
        "company_size": lead.get("company_size"),
        "funding_stage": lead.get("funding_stage"),
        "signal": lead.get("signal"),
        "description": description or None,
        "posted_date": posted,
    }


def dedupe(leads: list[dict]) -> list[dict]:
    """Same key the database uses — (source, title, company) stands in for
    external_id, which the public shape doesn't carry."""
    seen: set[tuple] = set()
    out = []
    for lead in leads:
        key = (lead["source"], lead["title"].lower(), lead["company"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(lead)
    return out


def sort_key(lead: dict):
    """Newest first, undated last. Dates arrive both naive and tz-aware from
    different sources, so they're compared as strings — ISO-8601 sorts
    correctly either way and never raises on a mixed comparison."""
    return (0 if lead.get("posted_date") else 1, str(lead.get("posted_date") or ""))


def build(out_dir: Path) -> int:
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching live sources…")
    raw = fetch_live_sources()
    print("Loading committed snapshot…")
    raw += load_snapshot()

    leads = dedupe([normalise(lead) for lead in raw if lead.get("title") and lead.get("company")])

    buckets: dict[str, list[dict]] = {"job": [], "business": []}
    for lead in leads:
        buckets.setdefault(lead["lead_type"], []).append(lead)

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "counts": {},
        "sources": {},
    }

    for lead_type, rows in buckets.items():
        rows.sort(key=sort_key, reverse=True)
        rows = rows[:MAX_LEADS_PER_TYPE]
        path = data_dir / f"{lead_type}.json"
        path.write_text(json.dumps(rows, separators=(",", ":")))
        manifest["counts"][lead_type] = len(rows)
        print(f"  wrote {path.name}: {len(rows)} leads, {path.stat().st_size / 1024:.0f} KB")
        for row in rows:
            manifest["sources"][row["source"]] = manifest["sources"].get(row["source"], 0) + 1

    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # index.html is a real checked-in file rather than a string in this script,
    # so it stays editable and syntax-highlighted.
    template = REPO_ROOT / "site" / "index.html"
    if template.resolve() != (out_dir / "index.html").resolve():
        shutil.copyfile(template, out_dir / "index.html")
    (out_dir / ".nojekyll").touch()  # stop Pages running Jekyll over this

    print(f"\nBuilt {out_dir}: {sum(manifest['counts'].values())} leads total")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="site", help="Output directory")
    args = parser.parse_args()
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    return build(out_dir)


if __name__ == "__main__":
    sys.exit(main())
