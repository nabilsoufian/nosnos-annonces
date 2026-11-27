"""Shared helpers: polite HTTP fetching and the normalized listing format."""
from __future__ import annotations

import json
import random
import re
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


_NUXT_DATA = re.compile(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)
_NUXT_WRAPPERS = {"ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"}


def nuxt_data(html: str) -> dict:
    """Decode the payload Nuxt 3 sites embed in <script id="__NUXT_DATA__">.

    The payload is a flat array (devalue format): every int inside a container
    is an index into that array. Index -1 means undefined.
    """
    m = _NUXT_DATA.search(html)
    if not m:
        raise RuntimeError("__NUXT_DATA__ not found (page layout changed or request blocked)")
    flat = json.loads(m.group(1))
    cache: dict[int, object] = {}

    def hydrate(i: int):
        if i < 0:
            return None
        if i in cache:
            return cache[i]
        v = flat[i]
        if isinstance(v, list):
            tag = v[0] if v and isinstance(v[0], str) else None
            if tag in _NUXT_WRAPPERS:
                cache[i] = hydrate(v[1]) if len(v) > 1 else None
            elif tag == "Date":
                cache[i] = v[1]
            elif tag == "Set":
                cache[i] = [hydrate(x) for x in v[1:]]
            elif tag == "Map":
                cache[i] = {str(hydrate(v[k])): hydrate(v[k + 1]) for k in range(1, len(v), 2)}
            elif tag == "null":
                cache[i] = None
            else:
                out: list = []
                cache[i] = out
                out.extend(hydrate(x) for x in v)
            return cache[i]
        if isinstance(v, dict):
            obj: dict = {}
            cache[i] = obj
            for k, x in v.items():
                obj[k] = hydrate(x)
            return obj
        cache[i] = v
        return v

    return hydrate(0)


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
