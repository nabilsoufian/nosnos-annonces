# NOS/NOS Annonces — Spécifications

Agrégateur d'annonces de locaux commerciaux à louer à Varsovie, pour la recherche du premier café NOS/NOS. Vue liste + carte, style Otodom, publié sur GitHub Pages.

**Contraintes de Nabil** : rien ne tourne sur son PC (la collecte se fait entièrement dans le cloud) ; l'outil se consulte d'abord **sur téléphone**.

Statut au 21/11/2026 : lots 1 et 2 en ligne (Otodom, 629 annonces, collecte depuis GitHub validée), plus les favoris (avancés depuis le lot 4, à la demande de Nabil). Prochain : lot 3.

---

## 1. Objectif

Voir en un seul endroit toutes les annonces de locaux qui correspondent au brief, sans refaire la recherche sur six sites. Repérer vite les nouvelles annonces et les baisses de prix, comparer le coût mensuel réel, et suivre chaque local (à visiter, visité, écarté).

## 2. Sources

| Source | Méthode | Faisabilité vérifiée le 21/11 |
|---|---|---|
| Otodom | Page de résultats (JSON `__NEXT_DATA__`) + fiche détail pour les coordonnées GPS | ✅ 629 annonces de 120–220 m² ; coordonnées présentes sur la fiche |
| OLX | Pages HTML de résultats (l'API JSON répond 403) | ⚠️ page accessible, format à analyser |
| Gratka | Pages HTML | ⚠️ page accessible, format à analyser |
| Morizon | Pages HTML | ⚠️ URL de recherche à corriger (404) |
| Nieruchomosci-online | Pages HTML | ⚠️ page accessible, format à analyser |
| Domiporta | Pages HTML | ⚠️ page accessible, format à analyser |

Chaque source a son propre module. Une source qui casse (changement de site, blocage) n'empêche pas les autres de tourner, et l'outil affiche la date de dernière collecte réussie pour chacune.

## 3. Critères

**Collecte (large, pour ne rien rater)** : Varsovie, location, locaux commerciaux, 120 à 220 m².

**Filtres par défaut dans l'interface (modifiables)** :
- surface 140–180 m² ;
- rez-de-chaussée ;
- coût mensuel ≤ 25 000 PLN (quand il est connu) ;
- quartiers : Śródmieście, Powiśle, Wola, Ochota, Żoliborz, Mokotów, Saska Kępa (Praga-Południe).

Mokotów est inclus parce que la passation ChatGPT le cite, alors que celle de claude.ai dit qu'il a été exclu. Il suffira de le décocher.

## 4. Fonctions

### 4.1 Liste + carte
- Pensé pour le téléphone d'abord : onglets Liste / Carte, filtres dans un panneau qui glisse, gros boutons. Sur grand écran, liste et carte côte à côte.
- Installable sur l'écran d'accueil du téléphone comme une app (PWA).
- Carte OpenStreetMap (Leaflet) avec un marqueur par annonce.
- Cliquer sur un marqueur sélectionne l'annonce dans la liste, et inversement. La carte n'affiche que les annonces filtrées.
- Carte d'annonce : photo, titre, surface, étage, loyer, prix/m², coût mensuel estimé, quartier, source(s), agence, ancienneté, badges.
- Tri : plus récentes, prix, prix/m², surface, coût mensuel.
- Lien vers l'annonce d'origine (on ne recopie pas la description complète).

### 4.2 Nouveautés et baisses de prix
- Chaque annonce garde sa date de première apparition et son historique de prix.
- Badges : « Nouveau » (depuis la dernière visite de l'outil, ou moins de 3 jours), « Baisse de prix −x % », « Disparue » (n'est plus en ligne, gardée 30 jours).
- Filtre « seulement les nouveautés ».

### 4.3 Dédoublonnage
- Une même annonce publiée sur plusieurs sites ou par plusieurs agences est regroupée en une seule carte qui liste toutes ses sources.
- Règle : à moins de 75 m l'une de l'autre, et surface à ±3 %. Le prix peut différer d'une agence à l'autre, alors on affiche le plus bas et l'écart.
- Bouton « ce n'est pas un doublon » pour séparer un regroupement erroné.

### 4.4 Coût mensuel complet
- Coût mensuel = loyer + charges (quand l'annonce les indique), en PLN.
- Loyers en euros convertis au taux du jour de la Banque nationale polonaise (NBP), avec le taux et sa date affichés.
- Affiché pour chaque annonce : loyer/m², charges/m², coût mensuel total, et l'écart avec le budget (25 000 PLN, modifiable).
- Si le loyer ou les charges manquent, on l'indique (« charges non indiquées ») au lieu de les supposer.

### 4.5 Suivi par annonce
- Statut : Nouveau / À visiter / Visité / Écarté (avec la raison), favori ⭐, note libre.
- Ajout manuel d'un local hors portails (Square, Rydygiera 12, Wilcza 9A…), avec position sur la carte, surface, loyer et charges.
- **Ce suivi reste dans le navigateur de ton téléphone** (voir §6). Bouton Export / Import (fichier JSON) pour le sauvegarder ou le passer sur un autre appareil.

## 5. Architecture

```
GitHub Actions (cron toutes les 3 h)          GitHub Pages (statique)
  scraper Python  ──► data/*.json ──►  index.html + JS + Leaflet
  (1 module/source)    (commit auto)    filtres, liste, carte
                                         suivi = localStorage du navigateur
```

- **Collecte** : Python 3.13, des requêtes lentes (une page toutes les 2–3 s), un User-Agent de navigateur générique. On ne récupère les fiches détail (pour les coordonnées) que pour les annonces nouvelles ou modifiées.
- **Données** : `data/listings.json` (annonces actives et disparues récemment) et `data/history.json` (historique des prix). Ce sont des fichiers JSON et non une base SQLite, parce que GitHub Pages ne sert que des fichiers statiques et que le JSON se versionne proprement dans git.
- **Interface** : une page HTML et du JavaScript sans framework, Leaflet et les tuiles OpenStreetMap. Rien à compiler.
- **Plan B si un portail bloque les serveurs de GitHub** (fréquent avec les adresses de datacenter) : on fait passer les requêtes de cette source par un service de proxy « résidentiel » ou de scraping hébergé (ScraperAPI, Apify…), qui est payant et dont le coût sera chiffré avant de décider. On teste ce risque dès le lot 1, avant de construire le reste.

## 6. Points d'attention

- **Le site sera public.** Avec un compte GitHub gratuit, Pages publie depuis un dépôt public, et même un dépôt privé (GitHub Pro) donne un site accessible à quiconque a l'URL. On ne publie donc que les annonces, qui sont déjà publiques. Tes statuts, notes, favoris et locaux ajoutés à la main (Square, budget…) restent dans ton navigateur et ne sont jamais envoyés. Le site sera exclu des moteurs de recherche (`noindex`, `robots.txt`).
- **Conditions des portails.** Otodom, OLX et les autres interdisent en général la collecte automatisée dans leurs CGU. On reste sur un usage personnel à faible fréquence, sans republier les descriptions ni les photos en dur (les miniatures restent chargées depuis le site d'origine). Un portail peut néanmoins bloquer la collecte à tout moment.
- **Coordonnées approximatives** : certaines annonces ne donnent que la rue ou le quartier. Leur marqueur est alors affiché en pointillé (« position approximative »).
- **Une position « exacte » peut être fausse** (contrôle du 21/11). On a comparé 8 annonces « exactes » donnant un numéro de rue avec le géocodage de leur adresse (OpenStreetMap) : 6 sont à moins de 65 m (médiane 40 m), 2 sont à 1,7–1,9 km (repère mal placé par l'annonceur). À ajouter : quand l'adresse comporte un numéro et que l'écart dépasse 300 m, marquer l'annonce « position à vérifier ».

## 7. Découpage en lots

| Lot | Contenu | Vérification |
|---|---|---|
| 1 | Dépôt GitHub + collecte Otodom dans GitHub Actions (cron) + publication Pages d'une première page | La collecte réussit **depuis GitHub** (sinon plan B) ; le site s'ouvre sur ton téléphone |
| 2 | Interface téléphone : liste, carte, filtres, tri, fiche annonce | Comparer avec Otodom : nombre d'annonces et 5 annonces vérifiées à la main |
| 3 | Nouveautés, historique et baisses de prix, coût mensuel complet (NBP) | Badges et coûts corrects sur des cas vérifiés |
| 4 | Suivi : statuts, notes, favoris, ajout manuel, export/import, installation sur l'écran d'accueil | Les données survivent à la fermeture de l'app sur le téléphone |
| 5 | Sources OLX + Gratka | Annonces présentes, sans casser Otodom |
| 6 | Sources Morizon, Nieruchomosci-online, Domiporta + dédoublonnage | Doublons connus bien regroupés |

## 8. Prérequis de ton côté

- Installer Git et GitHub CLI sur le PC, uniquement pour que Claude Code puisse envoyer le code sur GitHub pendant le développement. Ensuite, rien ne tourne sur le PC.
- Te connecter une fois à GitHub (`gh auth login`, dans ton navigateur : c'est toi qui le fais).
- Choisir le nom du dépôt (proposition : `nosnos-annonces`) ; l'URL sera `https://<ton-compte>.github.io/nosnos-annonces/`.

## 9. Hors périmètre (pour l'instant)

Alertes e-mail ou push, contact automatique des agences, analyse des photos ou des plans, annonces hors Varsovie.
