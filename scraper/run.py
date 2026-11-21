"""Collect listings from every source and update data/*.json.

Usage: python -m scraper.run
Each source runs independently: a failing source keeps its previous listings
and its error is recorded in data/meta.json.
"""
from __future__ import annotations

import json
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .sources import SOURCES

AREA_MIN, AREA_MAX = 120, 220      # collect wide; the UI filters narrower
GONE_RETENTION_DAYS = 30           # keep vanished listings visible this long

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
LISTINGS = DATA / "listings.json"
META = DATA / "meta.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _key(rec: dict) -> str:
    return f"{rec['source']}:{rec['source_id']}"


def merge(previous: dict[str, dict], fresh: list[dict], source: str, now: str) -> None:
    """Update `previous` in place with this run's results for one source."""
    seen = set()
    for rec in fresh:
        key = _key(rec)
        seen.add(key)
        old = previous.get(key)
        if old is None:
            rec["first_seen"] = now
            rec["price_history"] = [[now, rec["rent"]]] if rec["rent"] is not None else []
        else:
            rec["first_seen"] = old["first_seen"]
            history = old.get("price_history", [])
            if rec["rent"] is not None and (not history or history[-1][1] != rec["rent"]):
                history = history + [[now, rec["rent"]]]
            rec["price_history"] = history
        rec["last_seen"] = now
        rec["gone_since"] = None
        previous[key] = rec

    for key, rec in list(previous.items()):
        if rec["source"] != source or key in seen:
            continue
        if rec.get("gone_since") is None:
            rec["gone_since"] = now
        gone = datetime.fromisoformat(rec["gone_since"])
        if (datetime.fromisoformat(now) - gone).days > GONE_RETENTION_DAYS:
            del previous[key]


def eur_pln_rate() -> dict | None:
    """Today's NBP mid rate for EUR (table A). The API has no CORS, so the site can't call it."""
    url = "https://api.nbp.pl/api/exchangerates/rates/a/eur/?format=json"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            rate = json.load(resp)["rates"][0]
        return {"rate": rate["mid"], "date": rate["effectiveDate"], "source": "NBP, tabela A"}
    except Exception as exc:
        print(f"NBP rate unavailable: {exc}")
        return None


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    previous = {_key(r): r for r in _load(LISTINGS, [])}
    meta = _load(META, {"sources": {}})
    now = _now()
    failures = 0

    for module in SOURCES:
        name = module.NAME
        status = meta["sources"].setdefault(name, {})
        status["last_attempt"] = now
        known = {r["source_id"]: r for r in previous.values() if r["source"] == name}
        print(f"[{name}] collecting...")
        try:
            fresh = [l.to_dict() for l in module.scrape(AREA_MIN, AREA_MAX, known)]
            if not fresh:
                raise RuntimeError("0 listings returned (blocked or layout changed?)")
            merge(previous, fresh, name, now)
            status.update(last_success=now, count=len(fresh), error=None)
            status.pop("note", None)
            print(f"[{name}] {len(fresh)} listings")
        except Exception as exc:
            failures += 1
            status["error"] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()

    meta["updated_at"] = now
    meta["area_range"] = [AREA_MIN, AREA_MAX]
    meta["eur_pln"] = eur_pln_rate() or meta.get("eur_pln")  # keep the last known rate on failure
    listings = sorted(previous.values(), key=lambda r: r["first_seen"], reverse=True)
    LISTINGS.write_text(json.dumps(listings, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"total listings: {len(listings)}; failed sources: {failures}")
    return 1 if failures == len(SOURCES) else 0


if __name__ == "__main__":
    raise SystemExit(main())
