# Recherche & Géolocalisation — Design (Phase 2, sous-projet 3/5)

## Contexte

Sous-projets 1 (carte nationale) et 2 (fiche communale au clic) mergés sur `master`. `public/map.js` a un handler de clic sur la carte qui résout l'arrondissement, vérifie l'existence de la commune dans `carteScores`, puis appelle `panel.js`'s `afficherCommune`/`afficherCommuneSansDonnees`. Ce sous-projet ajoute deux nouveaux moyens d'atteindre une commune sans cliquer directement sur la carte : recherche par nom et géolocalisation.

## API vérifiées (geo.api.gouv.fr, appelées directement par le navigateur — CORS natif, décision déjà actée §5.1)

- Recherche par nom : `GET https://geo.api.gouv.fr/communes?nom={q}&fields=nom,code,departement,centre&boost=population&limit=5` → tableau d'objets `{nom, code, departement: {code, nom}, centre: {coordinates: [lon, lat]}}`. Testé en direct : "Saint-Denis" renvoie bien plusieurs résultats distincts avec leur département (974, 93, 11, ...), ce qui permet d'afficher "Saint-Denis (Seine-Saint-Denis)" pour désambiguïser sans logique supplémentaire.
- Géocodage inverse : `GET https://geo.api.gouv.fr/communes?lat={lat}&lon={lon}&fields=nom,code,departement,centre` → tableau (généralement 1 élément) avec le même schéma, la commune la plus proche du point donné.

## Objectif

Une barre de recherche dans le header (à côté des boutons Boisson/Cosmétique) avec suggestions en direct (debounce 300ms, dès 2 caractères), et un bouton de géolocalisation. Sélectionner un résultat (recherche ou géoloc) centre/zoome la carte sur la commune et ouvre sa fiche, en réutilisant exactement le chemin déjà utilisé par le clic sur la carte.

## Architecture

```
public/search.js (nouveau) :
  - Input de recherche : à chaque frappe, débounce 300ms, si ≥2 caractères
    fetch l'API recherche par nom. Compteur de requête incrémenté à chaque
    frappe (même pattern que panel.js "dernier clic gagnant") pour ignorer
    une réponse de recherche obsolète si l'utilisateur a continué à taper.
    Affiche jusqu'à 5 suggestions "Nom (Département)", cliquables.
  - Bouton géolocalisation : navigator.geolocation.getCurrentPosition,
    puis fetch l'API géocodage inverse avec les coordonnées obtenues.
  - Sélection (clic sur une suggestion, ou résultat de géoloc) : appelle
    map.js::centrerEtSelectionner(codeInsee, nom, lon, lat).

public/map.js (modifié) :
  - Le corps actuel de onClicCommune (résolution arrondissement — non
    nécessaire ici puisque l'API renvoie déjà le code commune final, pas un
    arrondissement — puis vérification carteScores[code], puis
    afficherCommune/afficherCommuneSansDonnees) est extrait dans une
    fonction exportée selectionnerCommune(code, nom), appelée par
    onClicCommune ET par centrerEtSelectionner.
  - Nouvelle fonction exportée centrerEtSelectionner(code, nom, lon, lat) :
    map.flyTo({center: [lon, lat], zoom: 11}) puis selectionnerCommune(code, nom).
  - initCarte() appelle initRecherche() (nouveau, depuis search.js) aux
    côtés de renderLegend()/initBascule()/initPanel() déjà présents.

public/index.html + public/style.css (modifiés) :
  - Champ de recherche + liste de suggestions + bouton géolocalisation
    dans #app-header, aux côtés de #toggle-indicateur (le flex-wrap déjà
    en place gère le passage à la ligne sur mobile).
```

## Cas limites & gestion d'erreurs

- Recherche : échec réseau/API → message d'erreur inline discret sous le champ, la saisie reste utilisable (nouvel essai possible).
- Recherche donnant 0 résultat → message "Aucune commune trouvée", pas de liste vide silencieuse.
- Géolocalisation refusée par l'utilisateur, indisponible, ou timeout → message inline près du bouton ("Position non disponible" ou "Autorisation refusée"), jamais d'échec silencieux.
- Résultat (recherche ou géoloc) correspondant à une des ~522 communes du geojson tiers sans fiche (absentes de la source DIS, cf. sous-projet 2) : `selectionnerCommune` réutilise le garde-fou déjà existant (`!carteScores[code]` → `afficherCommuneSansDonnees`, jamais de fetch voué à échouer).
- Frappe rapide dans la recherche (plusieurs requêtes lancées avant que la première ne réponde) : seule la réponse à la dernière frappe met à jour la liste de suggestions.

## Tests

Pas de framework JS (décision actée aux sous-projets précédents). Vérification manuelle en navigateur : recherche d'un nom avec homonymes ("Saint-Denis" — vérifier que les départements différencient bien les résultats), clic sur une suggestion (carte se centre + fiche s'ouvre), recherche sans résultat, géolocalisation acceptée (nécessite d'autoriser la permission navigateur) et refusée, résultat tombant sur une commune sans fiche, frappe rapide successive, layout mobile.

## Hors scope

- Déploiement CI (sous-projet 4), page méthodologie (sous-projet 5).
- Historique de recherches récentes, favoris — non demandés.
