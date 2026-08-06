# Carte Nationale — Socle Site Statique (Phase 2, sous-projet 1/5)

## Contexte

La Phase 1 (pipeline batch + moteur de scoring) est fonctionnellement terminée : `pipeline/compute_scores.py` a tourné sur les données réelles DIS 2023-2026 et produit 34 845 fiches communales dans `public/data/communes/{code_insee}.json`, plus `public/data/index.json` (métadonnées agrégées uniquement).

La Phase 2 (site statique, roadmap `SPECIFICATION.md` §8) regroupe plusieurs sous-systèmes largement indépendants. Ce document couvre uniquement le premier : **afficher une carte nationale des communes colorées par score**, socle sur lequel s'appuieront les sous-projets suivants (fiche communale au clic, recherche/géolocalisation, déploiement CI, page méthodologie).

### Écart assumé avec `SPECIFICATION.md`

Deux décisions de ce document dévient de ce qu'annonce `SPECIFICATION.md` §5.1/§5.3, à corriger dans une future revue de la spec technique :

1. **Schéma des fiches communales** : le schéma réellement généré par `compute_scores.py` est plus pauvre que celui documenté en §5.3 (pas de `nom`/`departement`/`population` de commune, pas de `classe` A-E, pas d'`historique`, pas d'`indicateurs_cles`, pas de `sca_coffee_index`, pas de `reseaux[]`). Décision produit : **ne pas enrichir le pipeline pour l'instant**, concevoir le site pour consommer le schéma existant tel quel.
2. **Génération de `national.geojson`** : §5.1 prévoit un fichier auto-suffisant fusionné par le pipeline batch. Ce document choisit une **jointure côté client** à la place (voir Architecture ci-dessous), pour éviter d'ajouter une étape de téléchargement/traitement de géométries dans le pipeline Python. `national.geojson` en tant que fichier fusionné n'existera donc pas ; il est remplacé par `public/data/carte_scores.json` (nouveau, léger) joint en JS avec une géométrie tierce.

## Objectif

Une page qui affiche une carte de France métropolitaine, une commune = un polygone coloré selon une échelle Nutri-Score A-E (5 classes discrètes), pour le score "Boisson & Santé" par défaut, avec une bascule vers "Cosmétique & Lavage". Le clic sur une commune est un point d'extension (stub) pour le sous-projet suivant (fiche communale) — non implémenté ici.

## Architecture & flux de données

```
Build-time (pipeline Python — un seul ajout, additif) :
  pipeline/compute_scores.py::main() écrit, en plus des fiches existantes,
  public/data/carte_scores.json — dérivé du dict `fiches` déjà en mémoire,
  aucun nouveau calcul, aucune modification du schéma des fiches existantes.

Runtime (navigateur, à chaque visite, aucune étape serveur) :
  1. fetch public/data/carte_scores.json            (notre CDN GitHub Pages)
  2. fetch communes-version-simplifiee.geojson       (raw.githubusercontent.com/
                                                       gregoiredavid/france-geojson,
                                                       métropole uniquement)
  3. Jointure JS : pour chaque feature du geojson, résoudre son code_insee
     (via mappage arrondissement → commune parente pour Paris/Lyon/Marseille),
     chercher le score correspondant dans carte_scores.json, calculer une
     couleur, écrire feature.properties.color, un seul geojson.setData()
     ensuite (pas de rendu par feature).
  4. MapLibre affiche la source avec fill-color = ['coalesce', ['get','color'], noDataColor]
```

Pas de fusion serveur, pas de nouvelle dépendance Python, un seul fichier auto-généré léger côté pipeline.

## Contrat de données — `public/data/carte_scores.json` (nouveau)

```json
{
  "75056": { "score_boisson": 90, "score_cosmetique": 76, "statut_donnees": "complet" },
  "99999": { "score_boisson": null, "score_cosmetique": null, "statut_donnees": "indisponible" }
}
```

- Une entrée par commune connue du pipeline (mêmes clés que `fiches`, soit les 34 845 codes INSEE actuels).
- `score_boisson`/`score_cosmetique` : entiers 0-100, ou `null` si `statut_donnees != "complet"` — ou, même quand `statut_donnees == "complet"`, si toutes les mesures sous-jacentes à ce sous-score précis sont indisponibles pour la commune (cas réel observé en production, cf. `_score_pondere_avec_veto`).
- Pas de champ `classe` : les seuils A-E (80/60/40/20, cf. README) sont une constante JS unique, pas dupliqués côté pipeline.

## Composants livrés

| Fichier | Rôle |
|---|---|
| `public/index.html` | Squelette : `<div id="map">`, légende, bouton bascule Boisson/Cosmétique, conteneur panneau vide (rempli par le sous-projet suivant) |
| `public/style.css` | Mobile-first, un seul thème (pas de bascule sombre/clair — simplification volontaire, hors scope) |
| `public/scoring.js` | Module pur, source unique de vérité : table de seuils A-E + couleurs (README), fonction `classeFromScore(score)`. Réutilisé tel quel par le futur panneau de fiche communale (sous-projet 2). |
| `public/map.js` | Init MapLibre avec le style `https://tiles.openfreemap.org/styles/positron` (fond clair, seul style retenu — même URL que le `LIGHT_MAP_STYLE` déjà validé en production par `sca-water-map`), fetch des deux sources, jointure + mappage arrondissements (repris de `sca-water-map`), légende générée depuis `scoring.js`, bouton bascule, handler de clic (stub) |
| `pipeline/compute_scores.py` | Ajout additif : `main()` écrit aussi `carte_scores.json` |

## Cas limites & gestion d'erreurs

- **Échec de fetch** (l'un ou l'autre fichier, réseau ou tiers indisponible) : message d'erreur inline visible à la place de la carte. Jamais de carte silencieusement vide.
- **`statut_donnees == "indisponible"`** : couleur grise neutre, distincte de l'échelle A-E, avec sa propre entrée dans la légende ("Données indisponibles").
- **Arrondissements Paris/Lyon/Marseille** (75101-75120, 69381-69389, 13201-13216 dans le geojson tiers) : résolus vers la commune parente (75056/69123/13055) via un mappage statique JS repris du patron déjà validé par `sca-water-map` (`ARR_PARENT`).
- **Feature géométrique sans entrée dans `carte_scores.json`** (cas résiduel, ne devrait pas arriver en métropole après le mappage arrondissements) : traité comme "indisponible" (gris), pas d'erreur JS.

## Tests

- **Pipeline** : test pytest pour la nouvelle fonction d'écriture de `carte_scores.json`, suivant la convention existante du projet (fixtures, `tests/test_compute_scores.py`).
- **Front-end** : pas de framework de test JS dans le projet actuellement. Vérification manuelle via serveur HTTP local (`python -m http.server`) + navigateur : chargement de la carte, cohérence des couleurs avec la légende, bascule Boisson/Cosmétique, rendu correct de Paris/Lyon/Marseille (pas de trous gris), comportement sur échec de fetch (ex. couper le réseau). Décision assumée de ne pas introduire d'outillage de test JS pour ce sous-projet minimal.

## Hors scope (sous-projets suivants ou futurs)

- Fiche communale au clic (panel.js) — sous-projet 2.
- Recherche + géolocalisation (geo.api.gouv.fr) — sous-projet 3.
- Workflow GitHub Actions + déploiement `gh-pages` — sous-projet 4.
- Page méthodologie — sous-projet 5.
- Thème sombre/clair, mode comparaison, historique de consultation, DOM-TOM sur la carte.
- Enrichissement du schéma des fiches communales (`classe`, `historique`, `indicateurs_cles`, `nom`/`departement`/`population`, `sca_coffee_index`) — décision produit explicite de ne pas y toucher pour l'instant (voir Contexte).
