"""Shared helper for running independent Firecrawl calls in parallel.

Every Firecrawl-based source was doing its searches, then its scrapes,
one at a time — each is a network round trip (a scrape can take several
seconds on a JS-heavy page), so a discovery run with 4 search queries and
10 scrapes was 14 sequential network calls, ~45s in practice. None of
these calls depend on each other, so they're safe to run concurrently:
Firecrawl's Python SDK makes a plain HTTP request per call and releases
the GIL while waiting on the network, which is exactly what a thread
pool is for."""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

logger = logging.getLogger("bureau.sources.concurrency")

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_MAX_WORKERS = 6


def parallel_map(fn: Callable[[T], R], items: list[T], max_workers: int = DEFAULT_MAX_WORKERS) -> list[R | None]:
    """Runs fn(item) for each item concurrently, preserving input order.
    A failing item logs and yields None in its slot rather than aborting
    the rest of the batch — callers already filter out empty/None results."""
    if not items:
        return []

    def run(item: T) -> R | None:
        try:
            return fn(item)
        except Exception:
            logger.exception("parallel_map: item failed: %r", item)
            return None

    with ThreadPoolExecutor(max_workers=min(max_workers, len(items))) as pool:
        return list(pool.map(run, items))
