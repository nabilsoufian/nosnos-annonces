"""Shared helpers: polite HTTP fetching and the normalized listing format."""
from __future__ import annotations

import random
import time
import urllib.request
from dataclasses import dataclass, field, asdict

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

_last_request = 0.0


def fetch(url: str, min_delay: float = 2.0, max_delay: float = 3.0, timeout: int = 30) -> str:
    """GET a page as text, waiting 2-3 s since the previous request."""
    global _last_request
    wait = random.uniform(min_delay, max_delay) - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pl,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    finally:
        _last_request = time.monotonic()


@dataclass
class Listing:
    """One listing, normalized across sources. Unknown values stay None."""

    source: str
    source_id: str
    url: str
    title: str
    area_m2: float | None = None
    rent: float | None = None            # monthly rent as published
    rent_currency: str | None = None     # "PLN" or "EUR"
    charges: float | None = None         # monthly charges (czynsz administracyjny), PLN
    floor: str | None = None             # "GROUND", "FIRST", ... as published
    district: str | None = None
    neighbourhood: str | None = None
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    location_precise: bool = False       # False when only street/district is known
    agency: str | None = None
    private_owner: bool | None = None
    thumbnail: str | None = None         # hot-linked from the source, never copied
    created_at: str | None = None        # first publication date on the source
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
