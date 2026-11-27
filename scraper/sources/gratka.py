"""Gratka: commercial premises for rent in Warsaw.

Pages are Nuxt 3 apps: the data sits in <script id="__NUXT_DATA__"> (see common.nuxt_data).
Only shops/services and restaurant premises are collected; offices, office
buildings and warehouses are left out, like Otodom's "lokal" category.
Search results have no coordinates, so each new listing's detail page is
fetched once; known coordinates are reused afterwards.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote

from ..common import Listing, fetch, nuxt_data

NAME = "gratka"
BASE = "https://gratka.pl"
SUBCATEGORIES = ("handel-uslugi", "lokale-gastronomiczne")
SEARCH = (
    BASE + "/nieruchomosci/lokale-uzytkowe/{sub}/warszawa/wynajem"
    "?powierzchnia-w-m2:min={area_min}&powierzchnia-w-m2:max={area_max}"
)  # "&page=N" from page 2 on: "&page=1" answers 404
PAGE_SIZE = 35
THUMB = "https://img1.staticmorizon.com.pl/thumb/{id}/3x2_m:fill_and_crop/{name}.jpg"
FLOOR_NAMES = ["GROUND", "FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH",
               "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH"]


def _payload(html: str, prefix: str) -> dict:
    data = (nuxt_data(html) or {}).get("data") or {}
    for key, value in data.items():
        if key.startswith(prefix) or key.endswith(prefix):
            return (value or {}).get("data") or {}
    raise RuntimeError(f"gratka: '{prefix}' block not found (page layout changed?)")


def _search_page(sub: str, page: int, area_min: int, area_max: int) -> tuple[list[dict], int]:
    url = SEARCH.format(sub=sub, area_min=area_min, area_max=area_max)
    html = fetch(url + (f"&page={page}" if page > 1 else ""))
    props = _payload(html, "-offers")["searchResult"]["properties"]
    total = props.get("totalCount") or 0
    return props.get("nodes") or [], max(1, -(-total // PAGE_SIZE))


def _floor(text: str | None) -> str | None:
    """'parter/3' -> GROUND, 'piętro 2/5' -> SECOND, 'piętro -1/4' -> CELLAR."""
    if not text:
        return None
    t = text.lower()
    if t.startswith("parter"):
        return "GROUND"
    if "suteren" in t or "piwnic" in t:
        return "CELLAR"
    if "poddasze" in t:
        return "GARRET"
    m = re.search(r"-?\d+", t)
    if not m:
        return None
    n = int(m.group())
    if n < 0:
        return "CELLAR"
    return FLOOR_NAMES[n] if n < len(FLOOR_NAMES) else "ABOVE_TENTH"


def _number(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _thumbnail(photos: list[dict]) -> str | None:
    if not photos or not photos[0].get("id"):
        return None
    return THUMB.format(id=photos[0]["id"], name=quote(photos[0].get("name") or "zdjecie"))


def _date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace(" ", "T")).isoformat()
    except ValueError:
        return None


def _to_listing(node: dict) -> Listing:
    loc = node.get("location") or {}
    names = loc.get("location") or []          # ["mazowieckie", "Warszawa", district, neighbourhood]
    price = node.get("price") or {}
    contact = node.get("contact") or {}
    company = contact.get("company") or {}
    person = contact.get("person") or {}
    title = (node.get("advertisementText") or node.get("title") or "").strip()
    return Listing(
        source=NAME,
        source_id=str(node["idOnFrontend"]),
        url=BASE + node["url"],
        title=title[:1].upper() + title[1:],
        area_m2=_number(node.get("area")),
        rent=_number(price.get("amount")),
        rent_currency=price.get("currency") if _number(price.get("amount")) else None,
        floor=_floor(node.get("floorFormatted")),
        district=names[2] if len(names) > 2 else None,
        neighbourhood=names[3] if len(names) > 3 else None,
        street=loc.get("street"),
        agency=company.get("name") if company.get("type") == "AGENCY" else None,
        private_owner=True if person.get("type") == "OWNER" and not company else (False if company else None),
        thumbnail=_thumbnail(node.get("photos") or []),
        created_at=_date(node.get("addedAt")),
    )


def _add_coordinates(listing: Listing) -> None:
    """Gratka returns the city centre when no street is given: only keep street-level positions."""
    data = _payload(fetch(listing.url), "property-details")
    loc = (data.get("propertyData") or {}).get("location") or {}
    center = (loc.get("map") or {}).get("center") or {}
    if not loc.get("street") or center.get("latitude") is None:
        return
    listing.lat, listing.lng = center["latitude"], center["longitude"]
    listing.location_precise = bool(loc.get("number"))
    if loc.get("number"):
        listing.street = f"{loc['street']} {loc['number']}"


def scrape(area_min: int, area_max: int, known: dict[str, dict]) -> list[Listing]:
    """Return all current listings. `known` maps source_id -> previous record (for coordinate reuse)."""
    unique: dict[str, Listing] = {}
    for sub in SUBCATEGORIES:
        page, total_pages = 1, 1
        while page <= total_pages:
            nodes, total_pages = _search_page(sub, page, area_min, area_max)
            for node in nodes:
                if node.get("idOnFrontend") and node.get("url"):
                    unique.setdefault(str(node["idOnFrontend"]), _to_listing(node))
            print(f"  gratka/{sub}: page {page}/{total_pages}, {len(nodes)} items")
            page += 1

    to_locate = []
    for listing in unique.values():
        prev = known.get(listing.source_id)
        if prev and (prev.get("extra") or {}).get("coords_checked"):
            listing.lat, listing.lng = prev.get("lat"), prev.get("lng")
            listing.location_precise = prev.get("location_precise", False)
            listing.street = prev.get("street") or listing.street
            listing.extra["coords_checked"] = True
        else:
            to_locate.append(listing)

    print(f"  gratka: {len(unique)} unique listings, {len(to_locate)} need coordinates")
    for n, listing in enumerate(to_locate, 1):
        try:
            _add_coordinates(listing)
            listing.extra["coords_checked"] = True
        except Exception as exc:  # one broken detail page must not stop the run
            print(f"  gratka: no coordinates for {listing.source_id}: {exc}")
        if n % 50 == 0:
            print(f"  gratka: coordinates {n}/{len(to_locate)}")
    return list(unique.values())
