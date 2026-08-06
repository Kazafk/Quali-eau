# Deep Linking & Tooltip Carte — Design (Phase 3, item 3/3)

## Contexte

Source : `analyse_sca_water_map.md`, deux fonctionnalités indépendantes de `sca-water-map` jugées à faible effort et forte valeur : partage d'un lien direct vers une commune, et infobulle au survol de la carte (aujourd'hui, il faut cliquer pour voir le nom d'une commune). Sous-projet purement front-end, aucun changement de schéma de données ni de pipeline.

Dépendance : réutilise `selectionnerCommune`/`centrerEtSelectionner` (exportés par `public/map.js` depuis le sous-projet 3, Phase 2) et `carteScores` (déjà chargé au démarrage). Si le module SCA (item 2/3 de ce backlog) est implémenté avant celui-ci, le paramètre d'indicateur inclut `score_cafe` comme 3ème valeur possible ; sinon, seuls `score_boisson`/`score_cosmetique` sont valides — ce document reste correct dans les deux cas.

## Deep linking

**Format d'URL** : `?commune={code_insee}&indicateur={score_boisson|score_cosmetique}` (paramètre `indicateur` optionnel, défaut `score_boisson`). Choix d'une query string plutôt qu'un hash (`#insee=...`) : plus simple à lire avec `URLSearchParams`, pas de conflit avec un futur usage du hash pour autre chose (ancre de page, etc.).

**Au chargement** : après que `chargerDonnees()` a résolu et que `carteScores` est disponible (dans `demarrer()`, avant ou juste après `initCarte()`), lire `new URLSearchParams(window.location.search)`. Si un `commune` est présent :
- Résoudre l'indicateur (`indicateur` si valide, sinon défaut).
- Attendre que la carte ait fini de charger (`map.on('load', ...)`, déjà l'événement existant) avant d'appeler `centrerEtSelectionner`, pour que `map.flyTo` ait un style chargé sur lequel s'appliquer.
- Si le code commune n'existe pas dans `carteScores`, ignorer silencieusement le paramètre d'URL (pas d'erreur bloquante au chargement — juste la carte par défaut) plutôt que de déclencher le panneau "sans données" pour un lien potentiellement mal formé/obsolète.

**Mise à jour de l'URL** : à chaque sélection de commune (clic carte, recherche, géolocalisation, lien direct), `history.replaceState(null, '', url)` avec l'URL reconstruite (pas `pushState` — la navigation dans la carte ne doit pas empiler l'historique du navigateur à chaque commune visitée). Basculer l'indicateur (boutons Boisson/Cosmétique) met aussi à jour l'URL si une commune est sélectionnée.

**Bouton "Copier le lien"** : dans le panneau (`public/panel.js`), à côté du bouton de fermeture. `navigator.clipboard.writeText(window.location.href)`, confirmation visuelle brève (ex. texte du bouton passe à "Copié !" pendant 1,5s puis revient).

## Tooltip au survol

MapLibre expose déjà `mouseenter`/`mouseleave` sur la couche `communes-fill` (utilisés aujourd'hui pour changer le curseur, `public/map.js`). Ajout d'un troisième événement `mousemove` sur la même couche :
- Un `<div id="carte-tooltip">` positionné en `position: fixed`, caché par défaut (même patron `:not([hidden])` que le reste du projet — aucun `display` inconditionnel sur cet élément).
- Au `mousemove`, lire `event.features[0].properties.nom` et `.code` (résolu via `resolveCodeInsee`, déjà utilisé pour le clic), lire le score correspondant à `indicateurActif` dans `carteScores`, afficher `Nom — Score (Classe)` ou `Nom — Données indisponibles`.
- Position du tooltip : suit le curseur (`event.point.x/y` fournis par l'événement MapLibre, positionnement CSS `left`/`top` mis à jour à chaque `mousemove`), avec un léger décalage pour ne pas être sous le curseur.
- `mouseleave` (déjà présent) cache le tooltip en plus de réinitialiser le curseur.

Pas de debounce nécessaire : `mousemove` sur une couche vectorielle MapLibre est déjà cadencé par le rendu (`requestAnimationFrame` interne), pas d'explosion d'appels DOM à contrôler côté application.

## Composants livrés

| Fichier | Rôle |
|---|---|
| `public/map.js` | Lecture des query params au démarrage, `history.replaceState` à chaque sélection/bascule, handler `mousemove` pour le tooltip |
| `public/panel.js` | Bouton "Copier le lien" |
| `public/index.html` | `<div id="carte-tooltip" hidden>` |
| `public/style.css` | Styles du tooltip (position fixed, petit encart avec fond semi-opaque) et du bouton copier-le-lien |

## Cas limites

- `commune` absent de l'URL : comportement actuel inchangé (carte vue par défaut, pas de panneau ouvert).
- `commune` présent mais code invalide/inexistant : ignoré silencieusement (voir ci-dessus).
- `indicateur` avec une valeur non reconnue : traité comme absent (défaut `score_boisson`).
- `navigator.clipboard` indisponible (contexte non sécurisé, ancien navigateur) : le bouton affiche un message d'erreur bref plutôt que d'échouer silencieusement.
- Survol pendant que le panneau est ouvert : le tooltip reste fonctionnel (pas de conflit de z-index attendu, le tooltip suit le curseur sur la carte, le panneau est sur le côté/en bas).

## Tests

Pas de framework JS (décision actée depuis le sous-projet 1). Vérification manuelle : ouvrir l'app avec `?commune=75056`, confirmer que la carte se centre et que la fiche Paris s'ouvre automatiquement ; sélectionner une commune puis vérifier que l'URL de la barre d'adresse change ; copier le lien et le recharger dans un nouvel onglet ; survoler plusieurs communes et vérifier que le tooltip suit le curseur et affiche le bon score selon l'indicateur actif ; tester avec un code commune invalide dans l'URL.

## Hors scope

- Partage direct vers réseaux sociaux (Open Graph, etc.) — non demandé.
- Historique de navigation "précédent/suivant" entre communes visitées (au-delà du bouton retour navigateur natif, qui fonctionne déjà grâce à `replaceState`... en fait `replaceState` ne crée PAS d'entrée d'historique, donc pas de bouton retour navigateur entre communes — c'est un choix assumé, cf. ci-dessus, pas un oubli).
