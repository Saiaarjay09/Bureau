import logging
from functools import lru_cache
from typing import Optional

from ..config import FIRECRAWL_API_KEY

logger = logging.getLogger("bureau.firecrawl")


@lru_cache(maxsize=1)
def get_client():
    """Returns a configured Firecrawl client, or None if FIRECRAWL_API_KEY
    isn't set — callers should skip gracefully rather than error."""
    if not FIRECRAWL_API_KEY:
        logger.warning("FIRECRAWL_API_KEY not set — Firecrawl-based sources are disabled")
        return None
    from firecrawl import Firecrawl

    return Firecrawl(api_key=FIRECRAWL_API_KEY)


def is_configured() -> bool:
    return bool(FIRECRAWL_API_KEY)
