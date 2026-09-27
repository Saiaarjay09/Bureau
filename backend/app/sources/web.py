"""Search, fetch and structured extraction — the free, local replacement
for Firecrawl.

Firecrawl did three separable things, and each has a free equivalent that
runs on this machine:

  search    → DuckDuckGo via ddgs. No key, no account, ~2s.
  scrape    → httpx + trafilatura, falling back to a real headless browser.
  extract   → the Ollama already running here for CV screening.

That last one is the interesting part: paying an API to run an LLM over a
page is the expensive half of a scrape, and this machine already has four
local models resident for Sabha. Extraction was never the thing that
needed to be bought.

Fetching is two-tier on purpose, because measurement says it has to be:
plain HTTP gets arbeitnow and michaelpage in ~0.5s, but returns 403 on
Indeed, Bayt and GulfTalent, and 0 characters on mycareersfuture (a JS
app that renders client-side). A headless Chromium gets all four, at
3-4s. So the cheap path runs first and the browser is only started when
it actually fails — most pages never pay the 3s.

None of this is as robust as a commercial scraping API: no proxy pool, no
CAPTCHA solving, and sites behind the hardest bot protection will still
refuse. Callers treat a failed fetch as "no data for this lead" rather
than an error, which is the same posture they had toward Firecrawl
failures anyway.
"""

import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from ..config import EXTRACT_MODEL, OLLAMA_URL

logger = logging.getLogger("bureau.sources.web")

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HTTP_HEADERS = {"User-Agent": BROWSER_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

# Below this, a "successful" fetch is really a cookie wall, a bot check or
# an unrendered JS shell, and is worth retrying with the browser.
MIN_USEFUL_TEXT = 400
MAX_PAGE_CHARS = 12_000
BROWSER_SETTLE_MS = 2500
SEARCH_ATTEMPTS = 3
SEARCH_RETRY_WAIT_S = 3


@dataclass
class SearchResult:
    url: str
    title: str = ""
    snippet: str = ""


def search(query: str, limit: int = 5, include_domains: list[str] | None = None) -> list[SearchResult]:
    """Free web search. `include_domains` is translated into DuckDuckGo's
    site: operator, which is how the discovered-sites sweep scopes itself
    to one domain."""
    if include_domains:
        sites = " OR ".join(f"site:{d}" for d in include_domains)
        query = f"{query} ({sites})" if len(include_domains) > 1 else f"{query} site:{include_domains[0]}"

    # DuckDuckGo intermittently answers a perfectly good query with "No
    # results found" when it's rate-limiting. Observed losing a whole query
    # (a third of a search's coverage) to this, so it's worth one backoff
    # rather than treating a throttle as an empty internet.
    rows = []
    for attempt in range(SEARCH_ATTEMPTS):
        try:
            from ddgs import DDGS

            rows = list(DDGS().text(query, max_results=limit))
            if rows:
                break
        except Exception as exc:
            if attempt == SEARCH_ATTEMPTS - 1:
                logger.warning("web search failed for %r: %s", query, exc)
                return []
        time.sleep(SEARCH_RETRY_WAIT_S * (attempt + 1))

    out = []
    for row in rows:
        url = row.get("href") or row.get("url") or ""
        if url:
            out.append(SearchResult(url=url, title=row.get("title") or "", snippet=row.get("body") or ""))
    return out


def _extract_main_text(html: str) -> str:
    try:
        import trafilatura

        return (trafilatura.extract(html) or "").strip()
    except Exception:
        logger.exception("trafilatura failed")
        return ""


def _fetch_with_http(url: str, timeout: int = 25) -> str:
    try:
        resp = httpx.get(url, headers=HTTP_HEADERS, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        return ""
    if resp.status_code >= 400:
        return ""
    return _extract_main_text(resp.text)


def _fetch_with_browser(url: str, timeout_ms: int = 30_000) -> str:
    """Real Chromium. Started per call rather than kept warm: this runs a
    handful of times a day, and a persistent browser is a process to
    supervise and leak memory for the other 23 hours."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not installed — skipping browser fetch for %s", url)
        return ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(user_agent=BROWSER_USER_AGENT, locale="en-US")
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(BROWSER_SETTLE_MS)
                html = page.content()
            finally:
                browser.close()
    except Exception:
        logger.info("browser fetch failed for %s", url)
        return ""
    return _extract_main_text(html)


def fetch_text(url: str, allow_browser: bool = True) -> str | None:
    """Page text, or None. Tries cheap HTTP first and only starts a browser
    if that came back blocked, empty or suspiciously thin."""
    if not url:
        return None

    text = _fetch_with_http(url)
    if len(text) >= MIN_USEFUL_TEXT:
        return text[:MAX_PAGE_CHARS]

    if allow_browser:
        logger.info("http fetch thin (%d chars) for %s — retrying with browser", len(text), url)
        browser_text = _fetch_with_browser(url)
        if len(browser_text) > len(text):
            text = browser_text

    return text[:MAX_PAGE_CHARS] if len(text) >= MIN_USEFUL_TEXT else None


def _first_json_object(raw: str) -> dict | None:
    """Local models wrap JSON in prose or fences often enough that parsing
    the whole reply is unreliable."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract(text: str, prompt: str, schema: dict | None = None, timeout: int = 180) -> dict | None:
    """Pull structured data out of page text with the local model.

    Replaces Firecrawl's JSON-mode scrape. num_ctx is set explicitly
    because Ollama's default context window is small enough to silently
    truncate a job posting, which looks like a model that ignored half the
    page rather than a configuration problem.
    """
    if not text:
        return None

    instruction = prompt
    if schema:
        instruction += (
            "\n\nReturn ONLY a JSON object matching this shape, no other text:\n"
            + json.dumps(schema, indent=2)
        )

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": EXTRACT_MODEL,
                "prompt": f"{instruction}\n\n=== PAGE CONTENT ===\n{text[:MAX_PAGE_CHARS]}",
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 1500},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
    except (httpx.HTTPError, ValueError):
        logger.exception("local extraction call failed")
        return None

    parsed = _first_json_object(raw)
    if parsed is None:
        logger.warning("local extraction returned unusable output: %r", raw[:200])
    return parsed


def is_available() -> bool:
    """The free stack needs no API key. It does need Ollama for extraction,
    which is the only part that can actually be 'not configured'."""
    try:
        httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3).raise_for_status()
        return True
    except (httpx.HTTPError, ValueError):
        return False
