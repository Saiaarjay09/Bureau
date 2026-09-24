"""CV matching, in two deliberately separate tiers.

Sabha (github.com/…/hiring-council, running locally on port 8700) puts a
seven-member council of independently-trained local models through a job
and a CV. Its own recorded timings put a full run at 5–7.5 minutes — so
running it across a feed of 1,500+ leads is tens of GPU-hours and simply
isn't a thing you can do in the background.

So there are two numbers here and they are never conflated:

- **screen** (`quick_screen`): one call to a small local model, ~1-3s, giving
  a rough 0-100 so the *feed can be ranked*. It is a triage signal. It reads
  the job and the CV together, which is exactly the keyword-ish shortcut
  Sabha's design argues against — that's an accepted tradeoff for something
  that has to run 1,500 times, not a claim that it's equivalent.
- **council** (`run_council`): the real Sabha pipeline, on demand, for one
  job you've decided is worth five minutes. This is the number to trust.

The CV is read from data/cv.txt (gitignored, never leaves the machine).
Sabha itself holds a CV only in memory and drops it when a run ends;
Bureau persisting one is a deliberate departure, needed so new leads can
be screened while nobody's at the keyboard.
"""

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from .config import CV_PATH, OLLAMA_URL, SABHA_URL, SCREEN_MODEL

logger = logging.getLogger("bureau.sabha")

MAX_CV_CHARS = 6000
MAX_JD_CHARS = 3000

SCREEN_PROMPT = """You are triaging job leads for one specific candidate.

Rate how well this candidate's CV fits this job, 0-100:
- 80-100: strong fit, clearly has what the role asks for
- 60-79: plausible fit, most of it with some gaps
- 40-59: partial, transferable but a stretch
- 0-39: weak fit or a different field entirely

Judge the substance of the work, not shared vocabulary. Someone who has
done the thing under a different job title still fits.

=== CANDIDATE CV ===
{cv}

=== JOB ===
Title: {title}
Company: {company}
{description}

Reply with ONLY a JSON object, no other text:
{{"score": <0-100 integer>, "reason": "<one short sentence, max 15 words>"}}"""


def cv_text() -> str | None:
    """The stored CV, or None if one hasn't been set yet."""
    if not CV_PATH.exists():
        return None
    text = CV_PATH.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def set_cv(text: str) -> None:
    CV_PATH.parent.mkdir(parents=True, exist_ok=True)
    CV_PATH.write_text(text.strip(), encoding="utf-8")


def clear_cv() -> None:
    CV_PATH.unlink(missing_ok=True)


def cv_status() -> dict:
    text = cv_text()
    if not text:
        return {"present": False, "chars": 0, "updated_at": None}
    return {
        "present": True,
        "chars": len(text),
        "updated_at": datetime.fromtimestamp(CV_PATH.stat().st_mtime, tz=timezone.utc).isoformat(),
    }


def sabha_health() -> dict:
    """Whether the local Sabha service is up. Its models live in Ollama and
    a cold machine can take a while, so this is surfaced rather than
    discovered by a five-minute request that fails at the end."""
    try:
        resp = httpx.get(f"{SABHA_URL}/api/health", timeout=5)
        resp.raise_for_status()
        return {"available": True, **resp.json()}
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "error": str(exc)}


def _extract_json(raw: str) -> dict | None:
    """Small models wrap JSON in prose or fences often enough that parsing
    the whole reply is unreliable; take the first balanced object instead."""
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def quick_screen(title: str, company: str, description: str | None, cv: str) -> tuple[int, str] | None:
    """One small-model pass. Returns (score, reason), or None if the model
    was unreachable or gave something unusable — callers leave the lead
    unscored rather than recording a fabricated number."""
    prompt = SCREEN_PROMPT.format(
        cv=cv[:MAX_CV_CHARS],
        title=title,
        company=company or "unknown",
        description=(description or "(no description captured — judge on the title alone)")[:MAX_JD_CHARS],
    )
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": SCREEN_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 120},
            },
            timeout=90,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
    except (httpx.HTTPError, ValueError):
        logger.exception("screen: model call failed for %r", title)
        return None

    parsed = _extract_json(raw)
    if not parsed or "score" not in parsed:
        logger.warning("screen: unusable reply for %r: %r", title, raw[:200])
        return None

    try:
        score = int(float(parsed["score"]))
    except (TypeError, ValueError):
        return None
    score = max(0, min(100, score))
    reason = str(parsed.get("reason") or "").strip()[:200]
    return score, reason


def run_council(title: str, description: str | None, cv: str, timeout_s: int = 1500) -> dict:
    """The full Sabha run for one job. Blocking, and genuinely minutes long.

    Sabha's contract is two-step and order-dependent: POST /api/analyze
    registers the run and returns an id, but the work only starts when you
    open the SSE stream, and the run is discarded once that stream closes —
    so the stream has to be consumed in one go, right here.
    """
    jd = (description or "").strip()
    if len(jd) < 40:
        # Sabha decomposes the posting into requirements before it reads the
        # CV. With nothing but a title there's nothing to decompose, and the
        # verdict would be noise dressed as a score.
        raise ValueError("This lead has no description captured, so there's nothing for the council to assess.")

    with httpx.Client(timeout=httpx.Timeout(30.0, read=timeout_s)) as client:
        resp = client.post(
            f"{SABHA_URL}/api/analyze",
            data={"job_title": title, "job_description": jd, "ats_cv_text": cv},
        )
        resp.raise_for_status()
        run_id = resp.json()["run_id"]

        result: dict | None = None
        error: str | None = None
        with client.stream("GET", f"{SABHA_URL}/api/stream/{run_id}") as stream:
            stream.raise_for_status()
            for line in stream.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                kind = event.get("type")
                if kind == "progress":
                    logger.info("council[%s]: %s", run_id[:8], event.get("message"))
                elif kind == "result":
                    result = event.get("result")
                elif kind == "error":
                    error = event.get("message")
                elif kind == "done":
                    break

    if error:
        raise RuntimeError(f"Sabha run failed: {error}")
    if not result:
        raise RuntimeError("Sabha stream ended without returning a verdict.")
    return result


def summarise_council(result: dict) -> dict:
    """The few fields worth storing on the lead. The full verdict is kept
    verbatim alongside this, so nothing here is lossy in a way that matters."""
    return {
        "score": int(round(float(result.get("score") or 0))),
        "match_pct": int(round(float(result.get("match_pct") or 0))),
        "verdict": result.get("verdict"),
        "confidence": result.get("confidence"),
        "summary": result.get("summary"),
        "blocking_gaps": result.get("blocking_gaps") or [],
    }
