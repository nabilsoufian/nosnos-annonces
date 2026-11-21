"""Browser check of the static site: desktop hover + phone pin button, with screenshots.

Usage: python tests/check_site.py [out_dir] [--url https://...]
Serves ./site on a local port (or tests the given live URL), drives Chromium with
Playwright, prints PASS/FAIL lines.
"""
from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent / "site"
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


with sync_playwright() as p:
    browser = p.chromium.launch()
    errors: list[str] = []

    # Desktop: hovering a card highlights its marker and opens its popup.
    page = browser.new_page(viewport={"width": 1366, "height": 860})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL)
    page.wait_for_selector(".card")
    cards = page.locator(".card:has(.pin:not([disabled]))")
    check("desktop: cards with coordinates", cards.count() > 0, f"{cards.count()} cards")
    card = cards.nth(0)
    card.hover()
    page.wait_for_timeout(600)
    check("desktop: hovered card is highlighted", "active" in (card.get_attribute("class") or ""))
    popup = page.locator(".leaflet-popup")
    check("desktop: popup opens on hover", popup.count() == 1)
    title = card.locator(".t").inner_text().replace("Nouveau", "").strip()[:25]
    check("desktop: popup shows the hovered listing", popup.count() == 1 and title in popup.inner_text(),
          f"card title starts with {title!r}")
    page.screenshot(path=str(OUT / "desktop-hover.png"))
    page.mouse.move(1300, 400)  # leave the list
    page.wait_for_timeout(300)
    check("desktop: leaving the list clears the highlight", page.locator(".card.active").count() == 0)

    # Phone: the pin button switches to the map, centred on the listing.
    phone = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    phone.on("pageerror", lambda e: errors.append(str(e)))
    phone.goto(URL)
    phone.wait_for_selector(".card")
    phone.screenshot(path=str(OUT / "phone-list.png"))
    pin = phone.locator(".card .pin:not([disabled])").first
    pin.tap()
    phone.wait_for_timeout(800)
    check("phone: pin switches to the map tab", phone.locator("#map").is_visible())
    check("phone: popup opens on the listing", phone.locator(".leaflet-popup").count() == 1)
    phone.screenshot(path=str(OUT / "phone-map.png"))

    check("no JavaScript errors", not errors, "; ".join(errors))
    browser.close()

if server:
    server.shutdown()
print(f"tested {URL}; screenshots in {OUT}")
sys.exit(1 if failures else 0)
