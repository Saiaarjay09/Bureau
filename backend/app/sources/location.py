"""Best-effort parsing of the free-text location strings job/company APIs
return (e.g. "Berlin, Germany", "USA", "Worldwide") into continent/country/city.

Unrecognized or non-specific strings (e.g. "Worldwide", "Remote") map to
(None, None, None) rather than a guess — those leads simply show up under
the default "Global" (unfiltered) view instead of a wrong country."""

import re

from ..regions import COUNTRY_TO_CONTINENT
from .city_lookup import COUNTRY_CODE_ALIASES, lookup_city_country

ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "uae": "United Arab Emirates",
    "south korea": "South Korea",
    "korea": "South Korea",
    "czech republic": "Czechia",
    "russia": "Russia",
    "netherlands": "Netherlands",
    "the netherlands": "Netherlands",
}

_COUNTRY_LOOKUP = {name.lower(): name for name in COUNTRY_TO_CONTINENT}
_COUNTRY_LOOKUP.update(ALIASES)
_COUNTRY_LOOKUP.update(COUNTRY_CODE_ALIASES)

NON_SPECIFIC = {"worldwide", "remote", "anywhere", "global", "international", ""}
NOISE_SUFFIXES = {"hq", "office", "headquarters", "homeoffice", "remote job", "job"}


def _match_country(token: str) -> str | None:
    token = token.strip().lower().strip(".")
    if not token or token in NON_SPECIFIC:
        return None
    return _COUNTRY_LOOKUP.get(token)


def parse_location(raw: str | None) -> tuple[str | None, str | None, str | None]:
    if not raw:
        return None, None, None
    raw = raw.strip()
    if raw.lower() in NON_SPECIFIC:
        return None, None, None

    parts = []
    for p in re.split(r"[,/]", raw):
        p = p.strip()
        if not p or p.lower() in NOISE_SUFFIXES:
            continue
        # Drop a trailing noise word within a part too, e.g. "Berlin HQ" -> "Berlin".
        stripped = re.sub(r"\s+(HQ|Office|Headquarters)$", "", p, flags=re.I).strip()
        parts.append(stripped or p)
    if not parts:
        return None, None, None

    # Try the last comma-separated token as the country first ("City, Country").
    country = _match_country(parts[-1])
    city = None
    if country and len(parts) > 1:
        city = parts[0]
    elif not country:
        # Maybe the whole string (or first token) IS the country, e.g. "USA".
        country = _match_country(raw) or _match_country(parts[0])

    if not country:
        # Bare city name with no country given (very common on EU boards,
        # e.g. "Berlin") — fall back to a known major-city lookup.
        city_guess = parts[0]
        country = lookup_city_country(city_guess)
        if country:
            city = city_guess

    if not country:
        return None, None, None

    if city and city.strip().lower() == country.strip().lower():
        # e.g. raw input was literally "Germany, Germany" — the source only
        # gave a country, not a city, so don't surface a fake duplicate one.
        city = None

    continent = COUNTRY_TO_CONTINENT.get(country)
    return continent, country, city
