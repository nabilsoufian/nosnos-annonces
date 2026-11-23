# NOS/NOS Annonces

Agrégateur d'annonces de locaux commerciaux à louer à Varsovie (recherche du café NOS/NOS). La référence fonctionnelle est [SPECS.md](SPECS.md).

## Règles
- Échanger en français avec Nabil. Code, noms de fichiers et commentaires en anglais.
- Avancer lot par lot (SPECS.md §7). Vérifier chaque lot sur des données réelles avant de passer au suivant.
- Collecte polie : 2–3 s entre deux requêtes, User-Agent de navigateur générique, aucune donnée personnelle dans les requêtes.
- Une source = un module dans `scraper/sources/`, qui renvoie des annonces au format normalisé. Une source en échec n'arrête pas les autres.
- Ne publier que des données d'annonces publiques. Le suivi personnel (statuts, notes, locaux manuels) reste en localStorage, jamais dans `data/`.
- Ne jamais inventer une valeur manquante (loyer, charges, étage, coordonnées) : la laisser vide et l'afficher comme « non indiqué ».
- Montants : toujours préciser la devise et la périodicité (PLN/mois, €/m²/mois).

## Structure
- `scraper/` : collecte (Python 3.13, bibliothèque standard uniquement). `scraper/run.py` fusionne les sources dans `site/data/`.
- `site/` : le site statique publié sur GitHub Pages (`index.html`, `data/listings.json`, `data/meta.json`).
- `.github/workflows/collect-and-deploy.yml` : la collecte tourne toutes les 3 h (à h+17, cron GitHub peu fiable à l'heure pile) ou à la demande (lien « Actualiser maintenant » du site → « Run workflow » sur GitHub), commit les données, puis déploie Pages. Un push sur main redéploie seulement le site, sans collecter.

## Vérification avant chaque push
- `node --check` sur le JavaScript de la page (extraire le `<script>` de `site/index.html`).
- `python tests/check_site.py <dossier_captures>` : sert `site/` en local, teste dans Chromium (Playwright) le survol sur ordinateur et le bouton 📍 sur téléphone, et fait des captures. Regarder les captures avant d'annoncer quoi que ce soit.

- Après chaque déploiement, relancer le même test sur le site en ligne (`--url https://nabilsoufian.github.io/nosnos-annonces/?v=<aléatoire>`) avant de dire à Nabil que c'est en ligne. Un « c'est fait » n'est valable qu'une fois le test en ligne passé.

- GitHub Pages met chaque fichier en cache 10 min, indépendamment des autres. `index.html` charge `app.js?v=__BUILD__` et `style.css?v=__BUILD__`, et le workflow remplace `__BUILD__` par le commit. Tout nouveau fichier JS ou CSS doit suivre le même principe.
- WebKit est installé (moteur de l'iPhone) : tester aussi un iPhone simulé pour tout ce qui touche au tactile.

## Commandes
- Lancer une collecte sur GitHub : `gh workflow run collect-and-deploy.yml`, puis suivre avec `gh run watch`.
- Dépôt : github.com/nabilsoufian/nosnos-annonces. Site : https://nabilsoufian.github.io/nosnos-annonces/
- La collecte ne tourne jamais en production sur le PC de Nabil (c'est sa contrainte). Les tests locaux ponctuels, pendant le développement, sont permis.
