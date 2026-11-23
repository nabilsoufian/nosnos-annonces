"use strict";

// ---------- constants & helpers ----------
const FLOORS = { GROUND: "RDC", FIRST: "1er", SECOND: "2e", THIRD: "3e", FOURTH: "4e", FIFTH: "5e",
  SIXTH: "6e", SEVENTH: "7e", EIGHTH: "8e", NINTH: "9e", TENTH: "10e", ABOVE_TENTH: ">10e",
  CELLAR: "sous-sol", GARRET: "combles" };
const DEFAULT_DISTRICTS = ["Śródmieście", "Wola", "Ochota", "Żoliborz", "Mokotów", "Praga-Południe"];
const DEFAULT_FILTERS = {
  areaMin: 140, areaMax: 180, budget: 25000, includeUnknownPrice: true,
  groundOnly: true, newOnly: false, districts: DEFAULT_DISTRICTS, sort: "recent",
};
const STORE_KEY = "nosnos-annonces:filters:v1";
const DAY = 86400000;

const fmt = (n, d = 0) => n == null ? null : n.toLocaleString("fr-FR", { maximumFractionDigits: d });
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const $ = sel => document.querySelector(sel);
const keyOf = l => `${l.source}:${l.source_id}`;
const isDesktop = () => matchMedia("(min-width: 900px)").matches;
const ago = iso => {
  const d = Math.floor((Date.now() - new Date(iso)) / DAY);
  if (Number.isNaN(d)) return "date inconnue";
  return d <= 0 ? "aujourd'hui" : d === 1 ? "hier" : `il y a ${d} j`;
};
const dateFr = iso => {
  const d = new Date(iso);
  return Number.isNaN(+d) ? "inconnue" : d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
};

let ALL = [];        // active listings
let META = {};
let filters = loadFilters();

// ---------- favourites (this device only) ----------
// key -> { added_at, snapshot }. The snapshot keeps a favourite visible after the listing
// disappears from the source.
const FAV_KEY = "nosnos-annonces:favorites:v1";
let favorites = loadFavorites();
let favOnly = false;

function loadFavorites() {
  try {
    const saved = JSON.parse(localStorage.getItem(FAV_KEY) || "{}");
    return saved && typeof saved === "object" ? saved : {};
  } catch { return {}; }
}
function saveFavorites() {
  try { localStorage.setItem(FAV_KEY, JSON.stringify(favorites)); } catch { /* ignore */ }
}
const isFav = key => Object.prototype.hasOwnProperty.call(favorites, key);
function toggleFavorite(key) {
  if (isFav(key)) {
    delete favorites[key];
  } else {
    const l = findListing(key);
    if (!l) return;
    const { price_history, ...snapshot } = l;
    favorites[key] = { added_at: new Date().toISOString(), snapshot };
  }
  saveFavorites();
  // Update in place (keeps the scroll position); in favourites mode the list itself changes.
  document.querySelectorAll(`[data-fav="${CSS.escape(key)}"]`).forEach(b => setFavButton(b, isFav(key)));
  renderFavCount();
  if (favOnly) { render(); return; }
  const l = findListing(key);
  const m = markers.get(key);
  if (m && l) m.setStyle(markerStyle(l)).setPopupContent(popupHtml(l));
}
function setFavButton(btn, on) {
  btn.setAttribute("aria-pressed", String(on));
  btn.textContent = btn.classList.contains("fav") ? (on ? "★" : "☆") : (on ? "★ Retirer des favoris" : "☆ Ajouter aux favoris");
  if (btn.classList.contains("fav")) btn.setAttribute("aria-label", on ? "Retirer des favoris" : "Ajouter aux favoris");
}
function renderFavCount() {
  const n = Object.keys(favorites).length;
  $("#fav-count").hidden = !n;
  $("#fav-count").textContent = n;
  $("#fav-toggle").setAttribute("aria-pressed", String(favOnly));
}
/** Active listing, or the saved snapshot of a favourite that is no longer online. */
function findListing(key) {
  return ALL.find(x => keyOf(x) === key)
    || (isFav(key) ? { ...favorites[key].snapshot, gone_since: favorites[key].snapshot.gone_since || "retirée" } : null);
}

function loadFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
    if (saved && typeof saved === "object") return { ...DEFAULT_FILTERS, ...saved };
  } catch { /* storage unavailable: use defaults */ }
  return { ...DEFAULT_FILTERS };
}
function saveFilters() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(filters)); } catch { /* ignore */ }
}

// ---------- money ----------
function eurRate() { return META.eur_pln?.rate ?? null; }
/** Monthly rent converted to PLN, or null when unknown (no price, or EUR without a rate). */
function monthlyPln(l) {
  if (l.rent == null) return null;
  if (l.rent_currency === "EUR") return eurRate() ? l.rent * eurRate() : null;
  return l.rent;
}
function pricePerM2Pln(l) {
  const m = monthlyPln(l);
  return m != null && l.area_m2 ? m / l.area_m2 : null;
}
function priceLine(l) {
  if (l.rent == null) return "Prix non indiqué";
  if (l.rent_currency === "EUR") {
    const pln = monthlyPln(l);
    return `${fmt(l.rent)} €/mois${pln != null ? ` (≈ ${fmt(pln)} PLN)` : ""}`;
  }
  return `${fmt(l.rent)} PLN/mois`;
}
function ppmLine(l) {
  const p = pricePerM2Pln(l);
  return p == null ? "" : `${fmt(p, 1)} PLN/m²`;
}
const isNew = l => Date.now() - new Date(l.created_at || l.first_seen) < 7 * DAY;
function placeLine(l) {
  return [l.district, l.neighbourhood].filter(Boolean).join(" · ");
}
function subLine(l) {
  return [l.area_m2 && `${fmt(l.area_m2, 1)} m²`, FLOORS[l.floor] || (l.floor ? l.floor.toLowerCase() : null), placeLine(l)]
    .filter(Boolean).join(" · ");
}

// ---------- filtering & sorting ----------
function passes(l, f) {
  if (f.areaMin && (l.area_m2 == null || l.area_m2 < f.areaMin)) return false;
  if (f.areaMax && (l.area_m2 == null || l.area_m2 > f.areaMax)) return false;
  if (f.groundOnly && l.floor !== "GROUND") return false;
  if (f.newOnly && !isNew(l)) return false;
  const cost = monthlyPln(l);
  if (cost == null) { if (!f.includeUnknownPrice) return false; }
  else if (f.budget && cost > f.budget) return false;
  if (f.districts && !f.districts.includes(l.district || "Inconnu")) return false;
  return true;
}
const SORTERS = {
  recent: (a, b) => new Date(b.created_at || b.first_seen) - new Date(a.created_at || a.first_seen),
  price: (a, b) => (monthlyPln(a) ?? Infinity) - (monthlyPln(b) ?? Infinity),
  ppm: (a, b) => (pricePerM2Pln(a) ?? Infinity) - (pricePerM2Pln(b) ?? Infinity),
  "area-asc": (a, b) => (a.area_m2 ?? Infinity) - (b.area_m2 ?? Infinity),
  "area-desc": (a, b) => (b.area_m2 ?? -Infinity) - (a.area_m2 ?? -Infinity),
};
function visible() {
  const sorter = SORTERS[filters.sort] || SORTERS.recent;
  if (favOnly) return Object.keys(favorites).map(findListing).filter(Boolean).sort(sorter);
  return ALL.filter(l => passes(l, filters)).sort(sorter);
}
function activeFilterCount() {
  let n = 0;
  if (filters.areaMin || filters.areaMax) n++;
  if (filters.budget) n++;
  if (filters.groundOnly) n++;
  if (filters.newOnly) n++;
  if (filters.districts) n++;
  return n;
}

// ---------- map ----------
let map, layer;
const markers = new Map();
const BASE_STYLE = { radius: 7, weight: 2 };
const HOT_STYLE = { radius: 12, weight: 3 };
/** Colours per listing: favourites get a gold ring, new listings a gold fill. */
function markerStyle(l) {
  const fav = l && isFav(keyOf(l));
  return { color: fav ? "#C4963C" : "#1A1815", weight: fav ? 4 : BASE_STYLE.weight };
}

function initMap() {
  map = L.map("map").setView([52.2297, 21.0122], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "© OpenStreetMap",
  }).addTo(map);
  layer = L.layerGroup().addTo(map);
}
function popupHtml(l) {
  return `${isFav(keyOf(l)) ? "★ " : ""}<a href="#" data-open="${esc(keyOf(l))}"><b>${esc(l.title)}</b></a><br>
    ${esc(priceLine(l))}${ppmLine(l) ? " · " + esc(ppmLine(l)) : ""}<br>${esc(subLine(l))}
    ${l.location_precise ? "" : "<br><i>Position approximative</i>"}`;
}
function highlight(key, { pan = false, popup = false } = {}) {
  document.querySelectorAll(".card.active").forEach(c => c.classList.remove("active"));
  for (const [k, m] of markers) m.setStyle(markerStyle(findListing(k))).setRadius(BASE_STYLE.radius);
  if (!key) { map.closePopup(); return; }
  document.querySelector(`.card[data-key="${CSS.escape(key)}"]`)?.classList.add("active");
  const m = markers.get(key);
  if (!m) { map.closePopup(); return; }
  m.setStyle({ ...markerStyle(findListing(key)), weight: HOT_STYLE.weight }).setRadius(HOT_STYLE.radius).bringToFront();
  if (pan && !map.getBounds().pad(-0.1).contains(m.getLatLng())) map.panTo(m.getLatLng());
  if (popup) m.openPopup();
}
function showOnMap(key) {
  closeSheets();
  if (!isDesktop()) document.querySelector('.tabs button[data-view="map"]').click();
  const m = markers.get(key);
  if (!m) return;
  map.setView(m.getLatLng(), Math.max(map.getZoom(), 15));
  highlight(key, { popup: true });
}

// ---------- rendering ----------
function render({ fit = false } = {}) {
  const items = visible();
  $("#count").textContent = `${items.length} annonce${items.length > 1 ? "s" : ""} sur ${ALL.length}`
    + (items.length ? ` · ${items.filter(l => l.lat != null).length} sur la carte` : "");
  const n = activeFilterCount();
  $("#filter-count").hidden = !n;
  $("#filter-count").textContent = n;
  $("#apply-filters").textContent = items.length
    ? `Voir ${items.length} annonce${items.length > 1 ? "s" : ""}` : "Aucune annonce";
  $("#sort").value = filters.sort;

  if (favOnly) {
    $("#count").textContent = `${items.length} favori${items.length > 1 ? "s" : ""} · filtres ignorés`;
  }
  renderFavCount();

  $("#list").innerHTML = items.length ? items.map(l => {
    const key = keyOf(l);
    const fav = isFav(key);
    return `
    <div class="card${l.gone_since ? " gone" : ""}" data-key="${esc(key)}" role="button" tabindex="0">
      ${l.thumbnail ? `<img loading="lazy" referrerpolicy="no-referrer" src="${esc(l.thumbnail)}" alt="">` : `<div class="noimg"></div>`}
      <div>
        <div class="t">${l.gone_since ? '<span class="badge gone">Retirée</span>' : isNew(l) ? '<span class="badge">Nouveau</span>' : ""}${esc(l.title)}</div>
        <div class="p">${esc(priceLine(l))}</div>
        <div class="s">${esc([ppmLine(l), subLine(l)].filter(Boolean).join(" · "))}</div>
        <div class="s">${esc(l.source)} · ${esc(ago(l.created_at || l.first_seen))}</div>
      </div>
      <button class="pin" type="button" ${l.lat == null ? "disabled" : ""}
        title="${l.lat == null ? "Position inconnue" : "Voir sur la carte"}"
        aria-label="${l.lat == null ? "Position inconnue" : "Voir sur la carte"}">📍</button>
      <button class="fav" type="button" data-fav="${esc(key)}" aria-pressed="${fav}"
        aria-label="${fav ? "Retirer des favoris" : "Ajouter aux favoris"}">${fav ? "★" : "☆"}</button>
    </div>`;
  }).join("")
    : favOnly
      ? `<div class="empty">Aucun favori pour l'instant.<br>Touche ☆ sur une annonce pour l'ajouter.</div>`
      : `<div class="empty">Aucune annonce ne correspond aux filtres.<br><br>
         <button class="btn" type="button" id="empty-reset">Réinitialiser les filtres</button></div>`;

  layer.clearLayers();
  markers.clear();
  for (const l of items) {
    if (l.lat == null) continue;
    const key = keyOf(l);
    const m = L.circleMarker([l.lat, l.lng], {
      ...BASE_STYLE, ...markerStyle(l), fillColor: isNew(l) ? "#C4963C" : "#7A8C7E",
      fillOpacity: l.gone_since ? .4 : .9, dashArray: l.location_precise ? null : "3 3",
    }).bindPopup(popupHtml(l)).addTo(layer);
    m.on("click", () => {
      highlight(key);
      if (isDesktop()) document.querySelector(`.card[data-key="${CSS.escape(key)}"]`)
        ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    markers.set(key, m);
  }
  if (fit && markers.size) {
    map.fitBounds(L.featureGroup([...markers.values()]).getBounds().pad(0.15), { maxZoom: 14 });
  }
}

// GitHub page of the collection workflow: "Run workflow" there starts a collection.
const REFRESH_URL = "https://github.com/nabilsoufian/nosnos-annonces/actions/workflows/collect-and-deploy.yml";

function renderSummary() {
  const when = META.updated_at
    ? new Date(META.updated_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })
    : null;
  const failing = Object.entries(META.sources || {}).filter(([, s]) => s.error).map(([n]) => n);
  $("#summary").innerHTML = when
    ? `Mis à jour ${esc(when)} · ${Object.keys(META.sources || {}).map(esc).join(", ")}`
      + (failing.length ? ` · <span class="err">⚠ échec : ${failing.map(esc).join(", ")}</span>` : "")
      + ` · <a id="refresh-link" href="${REFRESH_URL}" target="_blank" rel="noopener">Actualiser maintenant</a>`
    : "Pas encore de collecte.";
}

// ---------- listing detail ----------
function openDetail(key) {
  const l = findListing(key);
  if (!l) return;
  const hero = l.thumbnail ? l.thumbnail.replace(/;s=\d+x\d+$/, ";s=1024x768") : null;
  const history = (l.price_history || []);
  const facts = [
    ["Loyer", priceLine(l)],
    ["Prix/m²", ppmLine(l) || "—"],
    ["Charges", l.charges != null ? `${fmt(l.charges)} PLN/mois` : "non indiquées"],
    ["Surface", l.area_m2 ? `${fmt(l.area_m2, 2)} m²` : "non indiquée"],
    ["Étage", FLOORS[l.floor] || l.floor || "non indiqué"],
    ["Quartier", placeLine(l) || "non indiqué"],
    ["Adresse", l.street || "non indiquée"],
    ["Position", l.lat == null ? "inconnue" : l.location_precise ? "exacte (déclarée par l'annonceur)" : "approximative"],
    ["Annonceur", l.private_owner ? "particulier" : (l.agency || "agence (nom non indiqué)")],
    ["Publiée", dateFr(l.created_at)],
    ["Vue ici depuis", dateFr(l.first_seen)],
  ];
  $("#detail-body").innerHTML = `
    ${hero ? `<img class="hero" referrerpolicy="no-referrer" src="${esc(hero)}" alt="">` : ""}
    <h2>${l.gone_since ? '<span class="badge gone">Retirée</span>' : isNew(l) ? '<span class="badge">Nouveau</span>' : ""}${esc(l.title)}</h2>
    <div class="price">${esc(priceLine(l))}</div>
    ${l.gone_since ? `<p class="hint">Cette annonce n'est plus en ligne. Elle reste dans tes favoris avec ses dernières informations connues.</p>` : ""}
    <button class="btn" type="button" data-fav="${esc(key)}" aria-pressed="${isFav(key)}" style="width:100%;margin-top:10px">${isFav(key) ? "★ Retirer des favoris" : "☆ Ajouter aux favoris"}</button>
    <dl class="facts">${facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    ${history.length > 1 ? `<div class="label"><b>Historique du prix</b></div>
      <ul class="history">${history.map(([d, p]) => `<li>${esc(dateFr(d))} : ${esc(fmt(p))} ${esc(l.rent_currency || "")}</li>`).join("")}</ul>` : ""}
    ${l.rent_currency === "EUR" && META.eur_pln ? `<p class="hint">Conversion au taux NBP du ${esc(META.eur_pln.date)} : 1 € = ${esc(fmt(META.eur_pln.rate, 4))} PLN.</p>` : ""}
    <div class="actions">
      <button class="btn" type="button" data-map="${esc(key)}" ${l.lat == null ? "disabled" : ""}>📍 Voir sur la carte</button>
      <a class="btn primary" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer" style="text-align:center;text-decoration:none">Ouvrir sur ${esc(l.source)}</a>
    </div>`;
  openSheet("#detail");
  highlight(key);
}

// ---------- sheets ----------
function openSheet(sel) {
  const s = $(sel);
  s.classList.add("open");
  s.setAttribute("aria-hidden", "false");
}
function closeSheets() {
  document.querySelectorAll(".sheet.open").forEach(s => {
    s.classList.remove("open");
    s.setAttribute("aria-hidden", "true");
  });
}

// ---------- filters form ----------
function fillFilterForm() {
  $("#f-area-min").value = filters.areaMin ?? "";
  $("#f-area-max").value = filters.areaMax ?? "";
  $("#f-budget").value = filters.budget ?? "";
  $("#f-unknown-price").checked = !!filters.includeUnknownPrice;
  $("#f-ground").checked = !!filters.groundOnly;
  $("#f-new").checked = !!filters.newOnly;
  const counts = {};
  for (const l of ALL) counts[l.district || "Inconnu"] = (counts[l.district || "Inconnu"] || 0) + 1;
  const names = Object.keys(counts).sort((a, b) => a.localeCompare(b, "pl"));
  const selected = new Set(filters.districts || names);
  $("#f-districts").innerHTML = names.map(n => `
    <label class="chip"><input type="checkbox" value="${esc(n)}" ${selected.has(n) ? "checked" : ""}>${esc(n)} <small>${counts[n]}</small></label>`).join("");
  const range = META.area_range;
  $("#area-hint").textContent = range ? `La collecte couvre ${range[0]} à ${range[1]} m².` : "";
  $("#rate-hint").textContent = META.eur_pln
    ? `Loyers en euros convertis au taux NBP du ${META.eur_pln.date} (1 € = ${fmt(META.eur_pln.rate, 4)} PLN).`
    : "Taux EUR/PLN indisponible : les loyers en euros sont traités comme « sans prix ».";
}
function readFilterForm() {
  const num = id => { const v = parseFloat($(id).value); return Number.isFinite(v) && v > 0 ? v : null; };
  const checked = [...document.querySelectorAll("#f-districts input:checked")].map(i => i.value);
  const all = document.querySelectorAll("#f-districts input").length;
  filters = {
    ...filters,
    areaMin: num("#f-area-min"), areaMax: num("#f-area-max"), budget: num("#f-budget"),
    includeUnknownPrice: $("#f-unknown-price").checked,
    groundOnly: $("#f-ground").checked, newOnly: $("#f-new").checked,
    districts: checked.length === all ? null : checked,   // null = every district
  };
  saveFilters();
  render({ fit: true });
}

// ---------- events ----------
function wireEvents() {
  document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach(x => x.setAttribute("aria-selected", x === b));
    document.body.classList.toggle("show-map", b.dataset.view === "map");
    if (b.dataset.view === "map") map.invalidateSize();
  }));

  const list = $("#list");
  list.addEventListener("mouseover", e => {
    const card = e.target.closest(".card");
    if (card && !card.classList.contains("active") && isDesktop() && !$("#detail").classList.contains("open")) {
      highlight(card.dataset.key, { pan: true, popup: true });
    }
  });
  // Leaving the list keeps the last hovered listing highlighted, so its map popup
  // stays open and can be clicked.
  list.addEventListener("click", e => {
    if (e.target.closest("#empty-reset")) return resetFilters();
    const favBtn = e.target.closest("[data-fav]");
    if (favBtn) return toggleFavorite(favBtn.dataset.fav);
    const card = e.target.closest(".card");
    if (!card) return;
    const pin = e.target.closest(".pin");
    if (pin) {
      if (!pin.disabled) isDesktop() ? highlight(card.dataset.key, { pan: true, popup: true }) : showOnMap(card.dataset.key);
      return;
    }
    openDetail(card.dataset.key);
  });
  list.addEventListener("keydown", e => {
    if (e.target.closest("button")) return;   // buttons inside a card handle their own keys
    const card = e.target.closest(".card");
    if (card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openDetail(card.dataset.key); }
  });

  // Links inside map popups open the in-app detail (Leaflet stops click propagation
  // out of popups, so bind on the popup element itself).
  map.on("popupopen", e => {
    e.popup.getElement()?.querySelector("[data-open]")?.addEventListener("click", ev => {
      ev.preventDefault();
      openDetail(ev.currentTarget.dataset.open);
    });
  });
  $("#detail").addEventListener("click", e => {
    const favBtn = e.target.closest("[data-fav]");
    if (favBtn) return toggleFavorite(favBtn.dataset.fav);
    const b = e.target.closest("[data-map]");
    if (b && !b.disabled) showOnMap(b.dataset.map);
  });

  $("#fav-toggle").addEventListener("click", () => {
    favOnly = !favOnly;
    render({ fit: true });
  });

  document.querySelectorAll(".sheet").forEach(s => s.addEventListener("click", e => {
    if (e.target.closest("[data-close]")) closeSheets();
  }));
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeSheets(); });

  $("#open-filters").addEventListener("click", () => { fillFilterForm(); openSheet("#filters"); });
  $("#filters").addEventListener("change", e => { if (e.target.closest(".panel")) readFilterForm(); });
  $("#filters").addEventListener("input", e => { if (e.target.type === "number") readFilterForm(); });
  $("#reset-filters").addEventListener("click", resetFilters);
  $("#sort").addEventListener("change", e => { filters.sort = e.target.value; saveFilters(); render(); });
}
function resetFilters() {
  filters = { ...DEFAULT_FILTERS };
  saveFilters();
  fillFilterForm();
  render({ fit: true });
}

// ---------- boot ----------
initMap();
wireEvents();
Promise.all([
  fetch("data/listings.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : []),
  fetch("data/meta.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}),
]).then(([listings, meta]) => {
  META = meta || {};
  ALL = (listings || []).filter(l => !l.gone_since);
  renderSummary();
  render({ fit: true });
}).catch(err => {
  console.error(err);
  $("#summary").textContent = "Impossible de charger les données.";
});
