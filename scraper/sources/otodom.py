"""Otodom: commercial premises for rent in Warsaw.

Search pages embed their data as JSON in <script id="__NEXT_DATA__">.
Search results have no coordinates, so each new or changed listing's detail
page is fetched once to get them; known coordinates are reused afterwards.
"""
from __future__ import annotations

import json
import re

from ..common import Listing, fetch

NAME = "otodom"
BASE = "https://www.otodom.pl"
SEARCH = (
    BASE + "/pl/wyniki/wynajem/lokal/mazowieckie/warszawa/warszawa/warszawa"
    "?areaMin={area_min}&areaMax={area_max}&limit=72&page={page}"
)
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _next_data(html: str) -> dict:
    m = _NEXT_DATA.search(html)
    if not m:
        raise RuntimeError("otodom: __NEXT_DATA__ not found (page layout changed or request blocked)")
    return json.loads(m.group(1))


def _location_names(item: dict) -> tuple[str | None, str | None]:
    district = neighbourhood = None
    locs = (item.get("location") or {}).get("reverseGeocoding", {}).get("locations") or []
    for loc in locs:
        if loc.get("locationLevel") == "district":
            district = loc.get("name")
        elif loc.get("locationLevel") in ("residential", "subdistrict"):
            neighbourhood = loc.get("name")
    return district, neighbourhood


def _search_page(page: int, area_min: int, area_max: int) -> tuple[list[dict], int]:
    data = _next_data(fetch(SEARCH.format(area_min=area_min, area_max=area_max, page=page)))
    ads = data["props"]["pageProps"]["data"]["searchAds"]
    return ads.get("items") or [], (ads.get("pagination") or {}).get("totalPages") or 1


def _thumbnail(images: list[dict]) -> str | None:
    url = images[0].get("url") if images else None
    # The OLX image CDN resizes on the fly with a ";s=WxH" suffix.
    return f"{url};s=480x360" if url and url.endswith("/image") else url


def _to_listing(item: dict) -> Listing:
    price = item.get("totalPrice") or {}
    charges = item.get("rentPrice") or {}
    street = ((item.get("location") or {}).get("address") or {}).get("street") or {}
    district, neighbourhood = _location_names(item)
    agency = item.get("agency") or {}
    images = item.get("images") or []
    slug = item.get("slug") or ""
    return Listing(
        source=NAME,
        source_id=str(item["id"]),
        url=f"{BASE}/pl/oferta/{slug}",
        title=(item.get("title") or "").strip(),
        area_m2=item.get("areaInSquareMeters"),
        rent=None if item.get("hidePrice") else price.get("value"),
        rent_currency=price.get("currency") if price.get("value") else None,
        charges=charges.get("value"),
        floor=item.get("floorNumber"),
        district=district,
        neighbourhood=neighbourhood,
        street=" ".join(x for x in (street.get("name"), street.get("number")) if x) or None,
        agency=agency.get("name"),
        private_owner=item.get("isPrivateOwner"),
        thumbnail=_thumbnail(images),
        created_at=item.get("createdAtFirst") or item.get("dateCreated"),
    )


def _add_coordinates(listing: Listing) -> None:
    ad = _next_data(fetch(listing.url))["props"]["pageProps"].get("ad") or {}
    loc = ad.get("location") or {}
    coords = loc.get("coordinates") or {}
    if coords.get("latitude") and coords.get("longitude"):
        listing.lat = coords["latitude"]
        listing.lng = coords["longitude"]
        # A non-zero radius means the advertiser only gave an approximate position.
        listing.location_precise = not (loc.get("mapDetails") or {}).get("radius")


def scrape(area_min: int, area_max: int, known: dict[str, dict]) -> list[Listing]:
    """Return all current listings. `known` maps source_id -> previous record (for coordinate reuse)."""
    listings: list[Listing] = []
    page, total_pages = 1, 1
    while page <= total_pages:
        items, total_pages = _search_page(page, area_min, area_max)
        listings += [_to_listing(i) for i in items if i.get("id")]
        page += 1

    # Otodom repeats promoted ads across pages: keep one per id.
    unique = {l.source_id: l for l in listings}

    for listing in unique.values():
        prev = known.get(listing.source_id)
        if prev and prev.get("lat") is not None:
            listing.lat, listing.lng = prev["lat"], prev["lng"]
            listing.location_precise = prev.get("location_precise", False)
            continue
        try:
            _add_coordinates(listing)
        except Exception as exc:  # one broken detail page must not stop the run
            print(f"  otodom: no coordinates for {listing.source_id}: {exc}")
    return list(unique.values())
