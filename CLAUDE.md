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
- `.github/workflows/collect-and-deploy.yml` : la collecte tourne à 05:00 et 15:00 UTC ou à la demande, commit les données, puis déploie Pages. Un push sur main redéploie seulement le site, sans collecter.

## Commandes
- Lancer une collecte sur GitHub : `gh workflow run collect-and-deploy.yml`, puis suivre avec `gh run watch`.
- Dépôt : github.com/nabilsoufian/nosnos-annonces. Site : https://nabilsoufian.github.io/nosnos-annonces/
- La collecte ne tourne jamais en production sur le PC de Nabil (c'est sa contrainte). Les tests locaux ponctuels, pendant le développement, sont permis.
