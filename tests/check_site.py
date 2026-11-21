"""Browser checks of the static site (desktop + phone), with screenshots.

Usage: python tests/check_site.py [out_dir] [--url https://...]
Serves ./site on a local port (or tests the given live URL), drives Chromium with
Playwright, prints PASS/FAIL lines and exits non-zero on any failure.
"""
from __future__ import annotations

import functools
import http.server
import json
import re
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent / "site"
STORE_KEY = "nosnos-annonces:filters:v1"
WIDE = {"areaMin": None, "areaMax": None, "budget": None, "includeUnknownPrice": True,
        "groundOnly": False, "newOnly": False, "districts": None, "sort": "recent"}

args = sys.argv[1:]
live_url = None
if "--url" in args:
    i = args.index("--url")
    live_url = args[i + 1]
    del args[i:i + 2]
OUT = Path(args[0]) if args else Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

server = None
if live_url:
    URL = live_url
else:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    URL = f"http://127.0.0.1:{server.server_port}/"

failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")


def shown_count(page) -> tuple[int, int]:
    m = re.match(r"(\d+) annonces? sur (\d+)", page.locator("#count").inner_text())
    return (int(m.group(1)), int(m.group(2))) if m else (-1, -1)


def finger_tap(page, locator) -> None:
    """Tap the element's centre like a finger would (Playwright's tap() can stall on long lists)."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def open_wide(page) -> None:
    """Load the page with every filter off, so the checks below have data to work on."""
    page.goto(URL)
    page.evaluate(f"localStorage.setItem({json.dumps(STORE_KEY)}, {json.dumps(json.dumps(WIDE))})")
    page.reload()
    page.wait_for_selector(".card")


with sync_playwright() as p:
    browser = p.chromium.launch()
    errors: list[str] = []

    # ---- defaults & filters (desktop) ----
    page = browser.new_page(viewport={"width": 1366, "height": 860})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL)
    page.wait_for_selector("#count:not(:empty)")
    shown, total = shown_count(page)
    check("defaults: brief filters reduce the list", 0 <= shown < total, f"{shown} of {total}")
    check("defaults: filter badge shows active filters", page.locator("#filter-count").is_visible())
    floors = page.locator(".card .s").all_inner_texts()
    check("defaults: only ground floor shown", all("RDC" in t for t in floors[::2]) if floors else True)
    page.wait_for_load_state("networkidle")
    tiles = page.locator(".leaflet-tile-loaded").count()
    check("map: background tiles load", tiles > 0, f"{tiles} tiles")
    imgs_ok = page.evaluate("[...document.querySelectorAll('.card img')].slice(0, 3)"
                            ".every(i => i.complete && i.naturalWidth > 0)")
    check("list: first thumbnails load", imgs_ok)
    page.screenshot(path=str(OUT / "desktop-defaults.png"))

    page.click("#open-filters")
    check("filters: sheet opens", page.locator("#filters.open").count() == 1)
    page.uncheck("#f-ground")
    page.fill("#f-area-min", "")
    page.fill("#f-area-max", "")
    page.wait_for_timeout(200)
    wider, _ = shown_count(page)
    check("filters: removing area + ground-floor shows more", wider > shown, f"{shown} -> {wider}")
    page.screenshot(path=str(OUT / "desktop-filters.png"))
    label = page.locator("#apply-filters").inner_text()
    check("filters: button shows the result count", label == f"Voir {wider} annonces", label)
    page.click("#apply-filters")
    check("filters: sheet closes", page.locator("#filters.open").count() == 0)
    page.reload()
    page.wait_for_selector("#count:not(:empty)")
    check("filters: remembered after reload", shown_count(page)[0] == wider)

    # ---- sorting ----
    open_wide(page)
    page.select_option("#sort", "area-asc")
    areas = [float(m.replace(",", ".").replace(" ", "").replace(" ", ""))
             for m in re.findall(r"([\d\s ,]+) m²", " ".join(page.locator(".card .s").all_inner_texts()))
             if "PLN" not in m]
    check("sort: surface ascending", areas == sorted(areas) and len(areas) > 3, f"{len(areas)} areas read")

    # ---- hover -> map (desktop) ----
    open_wide(page)
    card = page.locator(".card:has(.pin:not([disabled]))").first
    card.hover()
    page.wait_for_timeout(600)
    popup = page.locator(".leaflet-popup")
    title = card.locator(".t").inner_text().replace("Nouveau", "").strip()[:25]
    check("hover: card highlighted + popup on that listing",
          "active" in (card.get_attribute("class") or "") and popup.count() == 1 and title in popup.inner_text())
    page.screenshot(path=str(OUT / "desktop-hover.png"))
    page.mouse.move(1300, 400)
    page.wait_for_timeout(300)
    check("hover: leaving the list keeps the popup open (so it can be clicked)",
          page.locator(".leaflet-popup").count() == 1)
    second = page.locator(".card:has(.pin:not([disabled]))").nth(1)
    second.hover()
    page.wait_for_timeout(400)
    check("hover: hovering another card moves the highlight",
          page.locator(".card.active").count() == 1 and "active" in (second.get_attribute("class") or ""))

    # ---- detail sheet ----
    card.click()
    page.wait_for_timeout(300)
    check("detail: opens on card click", page.locator("#detail.open").count() == 1)
    check("detail: shows facts and source link",
          page.locator("#detail .facts dt").count() >= 8 and page.locator('#detail a[href^="http"]').count() == 1)
    page.screenshot(path=str(OUT / "desktop-detail.png"))
    page.keyboard.press("Escape")
    check("detail: closes with Escape", page.locator("#detail.open").count() == 0)

    # ---- hover a card, then move to the map and click the popup title -> detail ----
    page.locator(".card:has(.pin:not([disabled]))").first.hover()
    page.wait_for_timeout(500)
    page.locator(".leaflet-popup [data-open]").click()
    page.wait_for_timeout(300)
    check("popup: title link opens the detail", page.locator("#detail.open").count() == 1)

    # ---- phone ----
    phone = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    phone.on("pageerror", lambda e: errors.append(str(e)))
    phone.goto(URL)
    phone.wait_for_selector("#count:not(:empty)")
    phone.screenshot(path=str(OUT / "phone-list.png"))
    open_wide(phone)
    finger_tap(phone, phone.locator(".card .pin:not([disabled])").first)
    phone.wait_for_timeout(800)
    check("phone: pin switches to the map, popup open",
          phone.locator("#map").is_visible() and phone.locator(".leaflet-popup").count() == 1)
    phone.screenshot(path=str(OUT / "phone-map.png"))
    finger_tap(phone, phone.locator('.tabs button[data-view="list"]'))
    phone.wait_for_timeout(300)
    finger_tap(phone, phone.locator(".card .t").first)
    phone.wait_for_timeout(300)
    check("phone: card tap opens the detail", phone.locator("#detail.open").count() == 1)
    phone.screenshot(path=str(OUT / "phone-detail.png"))
    phone.keyboard.press("Escape")
    check("phone: no '0' badge when no filter is active",
          not phone.locator("#filter-count").is_visible())
    phone.click("#open-filters")
    phone.wait_for_timeout(200)
    phone.screenshot(path=str(OUT / "phone-filters.png"))

    check("no JavaScript errors", not errors, "; ".join(errors))
    browser.close()

if server:
    server.shutdown()
print(f"tested {URL}; screenshots in {OUT}")
sys.exit(1 if failures else 0)
