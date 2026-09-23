"""A minimal in-memory login throttle, keyed by client IP.

Exists specifically because the app is reachable from the open internet
via Tailscale Funnel and its URL is published in a public README — the
threat model changed from "nobody can even reach this" to "anything
that finds the URL can hammer the login form." This blunts automated
password guessing; it does not defend against a patient, distributed
attacker, and it resets on a backend restart. That tradeoff is fine for
a single-user personal tool — the goal is raising the cost of casual
credential stuffing, not building a WAF.
"""

import time
from collections import defaultdict

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 5 * 60

_failures: dict[str, list[float]] = defaultdict(list)


def _prune(key: str, now: float) -> None:
    _failures[key] = [t for t in _failures[key] if now - t < WINDOW_SECONDS]
    if not _failures[key]:
        _failures.pop(key, None)


def seconds_until_retry(key: str) -> int:
    """0 if not locked out, otherwise how many seconds until the oldest
    attempt in the window ages out and a retry is allowed again."""
    now = time.time()
    _prune(key, now)
    attempts = _failures.get(key, [])
    if len(attempts) < MAX_ATTEMPTS:
        return 0
    return max(0, int(WINDOW_SECONDS - (now - attempts[0])))


def record_failure(key: str) -> None:
    _failures[key].append(time.time())


def record_success(key: str) -> None:
    _failures.pop(key, None)
