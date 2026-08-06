# Fiche Communale au Clic — Design (Phase 2, sous-projet 2/5)

## Contexte

Le sous-projet 1 (socle carte nationale, PR #1, mergée) a livré `public/index.html`, `public/style.css`, `public/scoring.js`, `public/geo_join.js`, `public/map.js`. Le clic sur une commune y est un stub (`console.log`). Ce document couvre son remplacement par l'affichage réel de la fiche communale.

## Découverte utile

Le geojson tiers déjà chargé par `map.js` (`communes-version-simplifiee.geojson`) contient une propriété `nom` en plus de `code` — vérifié directement sur les données réelles. On peut donc afficher un nom de commune lisible sans toucher au pipeline ni au schéma des fiches JSON (qui, lui, reste volontairement pauvre — décision actée au sous-projet 1).

## Objectif

Au clic sur une commune, afficher sa fiche complète (scores Boisson & Cosmétique, sous-scores, recommandations) dans un panneau : colonne latérale fixe sur desktop, tiroir remontant depuis le bas sur mobile (`@media max-width:600px`).

## Architecture & flux de données

```
Clic sur une commune (map.js, remplace le stub onClicCommune) :
  1. code = resolveCodeInsee(feature.properties.code)   (réutilise geo_join.js)
  2. nom  = feature.properties.nom                        (déjà en mémoire, aucun fetch)
  3. panel.js : ouvrir #panel (état "chargement…"), afficher le tiroir sur mobile
  4. fetch public/data/communes/{code}.json — lazy, à la demande uniquement
     → mis en cache mémoire (Map JS, clé=code) : un second clic sur la même
       commune dans la session ne refetch pas
     → si un clic sur une AUTRE commune arrive avant la résolution de ce fetch,
       la réponse tardive est ignorée (dernier clic gagnant, pas d'affichage
       obsolète) — un simple compteur de requête incrémenté à chaque clic suffit
  5. Rendu de la fiche dans #panel
```

## Contrat de données consommé (rappel, inchangé — `public/data/communes/{code}.json`)

```json
{
  "commune": { "code_insee": "34116" },
  "statut_donnees": "complet",
  "scores": {
    "donnees_partielles": false,
    "boisson": { "score": 90, "veto_sanitaire": false, "sous_scores": { "securite_sanitaire": 95, "mineraux_equilibre": 85, "gout_organoleptique": 80 } },
    "cosmetique": { "score": 76, "sous_scores": { "durete_calcaire": 59, "chlore_agressivite": 80, "respect_ph": 100, "metaux_depots": 95 } }
  },
  "recommandations": [ { "usage": "cosmetique", "type": "adoucisseur", "titre": "...", "description": "...", "estimation_cout": { "materiel": "...", "achat_eur": "...", "entretien_annuel_eur": "...", "niveau_severite": "..." } } ]
}
```
- `statut_donnees` peut être `"indisponible"` → `scores: null`, aucune recommandation.
- Un score de domaine (`boisson.score` ou `cosmetique.score`) peut être `null` même si `statut_donnees == "complet"` (cas réel observé, cf. sous-projet 1) — traiter par domaine, pas globalement.
- Pas de `nom`/`departement`/`population`, pas de `classe`, pas d'`historique`, pas d'`indicateurs_cles` — absence assumée, ne pas les inventer côté front.

## Composants livrés

| Fichier | Rôle |
|---|---|
| `public/panel.js` | Nouveau. Cache mémoire des fiches déjà fetchées, logique de "dernier clic gagnant", rendu HTML du panneau (nom, jauges Boisson/Cosmétique via `classeFromScore` de `scoring.js`, sous-scores, alerte veto sanitaire, recommandations, cas indisponible, cas erreur) |
| `public/map.js` | Modifié : `onClicCommune` appelle `panel.js` au lieu du `console.log` stub |
| `public/style.css` | Modifié : styles du panneau (colonne desktop existante via flex, tiroir bas mobile), jauges, badges de recommandation |
| `public/index.html` | Modifié si besoin : `#panel` a déjà son conteneur ; ajout d'un bouton de fermeture si absent |

## Cas limites & gestion d'erreurs

- Échec de fetch (404/réseau) : message d'erreur inline dans le panneau (pas de panneau vide/cassé), avec le nom de la commune déjà affiché (connu sans fetch).
- Clics rapides successifs : la dernière requête l'emporte, jamais d'affichage d'une fiche qui ne correspond plus à la commune actuellement sélectionnée.
- `statut_donnees: "indisponible"` : message dédié ("Aucune donnée disponible pour cette commune"), pas de jauges à 0/vides.
- Sous-score de domaine `null` sur fiche `"complet"` : jauge "Données insuffisantes" pour ce domaine précis uniquement, l'autre domaine s'affiche normalement.
- Fermeture du panneau : bouton explicite ; réouverture sur une autre commune remplace proprement le contenu (pas d'empilement).

## Tests

Pas de framework JS (décision déjà actée au sous-projet 1). Vérification manuelle en navigateur : clic sur commune normale, sur commune "indisponible", sur Paris/Lyon/Marseille (vérifie que le code résolu correspond bien à la fiche 75056/69123/13055), clics rapides successifs, simulation d'échec réseau, fermeture/réouverture, layout mobile (tiroir bas).

## Hors scope

- Recherche/géolocalisation (sous-projet 3), déploiement CI (sous-projet 4), page méthodologie (sous-projet 5).
- Historique temporel, indicateurs bruts (TH/nitrates en valeur), profil café/thé SCA — absents du schéma actuel, non ajoutés ici.
