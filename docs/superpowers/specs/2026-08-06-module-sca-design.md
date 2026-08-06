# Module Expert Café / Thé SCA — Design (Phase 3, item 2/3)

## Contexte

Source : `analyse_sca_water_map.md` + `SPECIFICATION.md` §3.1.4/§8 (déjà roadmapé, jamais implémenté — la page méthodologie le décrit explicitement comme "prévu, fonctionnalité à venir" depuis le sous-projet 5). Décision utilisateur : ce module devient un **3ème mode de coloration de la carte nationale** (comme Boisson/Cosmétique aujourd'hui), pas seulement un onglet dans la fiche.

## Vérification technique préalable

Les codes SANDRE nécessaires sont bien présents dans les exports DIS réels (vérifié directement sur `data/raw/2026/DIS_RESULT_2026.txt`) : `1303` Conductivité, `1374` Calcium, `1347` Titre alcalimétrique complet (TAC), en plus de `1399` Chlore total déjà suivi. Aucun blocage de données.

`SPECIFICATION.md` §2.5.7/§2.5.8/§3.1.4 fixe déjà les cibles et deux formules de conversion — reprises telles quelles, rien n'est réinventé :
- TDS estimé = `0,65 × Conductivité (µS/cm)`, cible 150 mg/L, plage acceptable 75–250 mg/L.
- GH (dureté calcique) = `Calcium (mg/L) × 2,5` (facteur standard Ca→CaCO₃), ou si calcium absent : `TH (°fH) × 10 × 0,65`. Cible 68 mg/L CaCO₃.
- TAC = `Titre alcalimétrique complet (°fH) × 10` (conversion °fH→mg/L CaCO₃, cohérente avec celle déjà utilisée pour TH). Cible 40 mg/L CaCO₃.
- Chlore total (`1399`) : cible 0 mg/L.

**Ce qui n'existe encore nulle part et que ce document doit fixer** : la formule de combinaison de ces 4 grandeurs en un score 0-100 comparable aux scores Boisson/Cosmétique. Proposition ci-dessous, dans le même style que les fonctions déjà en place (`score_durete`, `score_ph` — paliers par bandes) : à valider, ce sont des seuils que je propose, pas une valeur officielle SCA supplémentaire à celles déjà actées.

## Formule proposée

$$S_{\text{café}} = 0{,}30 \cdot S_{\text{TDS}} + 0{,}30 \cdot S_{\text{GH}} + 0{,}25 \cdot S_{\text{TAC}} + 0{,}15 \cdot S_{\text{chlore}}$$

Pas de veto (ce n'est pas un score sanitaire — une eau hors plage SCA n'est pas dangereuse, juste sous-optimale pour l'extraction).

- **S_TDS** (mg/L) : 100–200 → 100 ; [75,100[ ou ]200,250] → 80 ; [50,75[ ou ]250,300] → 55 ; sinon → 30.
- **S_GH** (mg/L CaCO₃) : [50,90] → 100 ; [30,50[ ou ]90,130] → 75 ; [15,30[ ou ]130,180] → 50 ; sinon → 25.
- **S_TAC** (mg/L CaCO₃) : [25,60] → 100 ; [15,25[ ou ]60,90] → 75 ; sinon → 45.
- **S_chlore** (mg/L, `1399`) : 0 → 100 ; ]0,0,05] → 90 ; ]0,05,0,15] → 60 ; > 0,15 → 20 (barème plus strict que `score_chlore_cosmetique` existant — le café est nettement plus sensible au chlore que la peau).

Classement A-E identique au reste du site (mêmes seuils 80/60/40/20 de `public/scoring.js`, aucune nouvelle échelle).

## Contrat de données

`pipeline/compute_scores.py` : ajout de `scores.cafe` à la fiche communale (même forme que `boisson`/`cosmetique`, sans `veto_sanitaire`) :
```json
"cafe": {
  "score": 62,
  "sous_scores": { "tds": 80, "durete_calcique": 55, "alcalinite": 100, "chlore": 20 },
  "valeurs": { "tds_mg_l": 208, "gh_mg_l_caco3": 45, "tac_mg_l_caco3": 42, "chlore_total_mg_l": 0.18 }
}
```
Absent (`null`) si aucune des 3 mesures primaires (conductivité, calcium/TH, TAC) n'est disponible sur la fenêtre — même logique de disponibilité que les autres sous-scores.

`public/data/carte_scores.json` : `construire_carte_scores` ajoute `score_cafe` (3ème clé, à côté de `score_boisson`/`score_cosmetique`).

## Composants livrés

| Fichier | Rôle |
|---|---|
| `pipeline/scoring.py` | 4 nouvelles fonctions `score_tds`, `score_gh`, `score_tac`, `score_chlore_cafe` (banded, style existant) + `score_cafe(...)` combinant |
| `pipeline/compute_scores.py` | Extraction TDS/GH/TAC dans `calculer_fiche_commune`, ajout de `scores.cafe` ; `construire_carte_scores` ajoute `score_cafe` |
| `public/map.js` | 3ème bouton de bascule (`btn-cafe`), `activerIndicateur`/`initBascule` étendus à 3 valeurs |
| `public/index.html` | 3ème bouton `☕ Café & Thé` dans `#toggle-indicateur` |
| `public/panel.js` | 3ème bloc jauge (réutilise `jaugeHtml` existant) + graphique SVG 2D (Calcium vs Alcalinité, zone idéale, point de la commune) + recommandations barista |
| `pipeline/recommendations.py` | Nouvelles recommandations `usage: "cafe"` (TAC élevé → torréfaction plus foncée / filtration décarbonatante ; TDS élevé → température d'extraction abaissée) |

## Graphique SVG 2D (panel.js)

Plan cartésien statique en SVG inline (pas de librairie, cohérent avec le reste du front) : axe X = alcalinité (TAC, 0-150 mg/L CaCO₃), axe Y = dureté calcique (GH, 0-150 mg/L CaCO₃). Zone rectangulaire verte = plage idéale (25-60 × 50-90), point cible marqué (40, 68), point de la commune affiché avec une ligne pointillée vers le point cible. Fonction pure `graphiqueScaHtml(tac, gh)` retournant une chaîne SVG — testable via `node` comme les autres fonctions pures du projet.

## Cas limites

- Une seule mesure primaire manquante (ex. TAC absent, conductivité et calcium présents) : `S_café` recalculé par renormalisation sur les composantes disponibles (même principe que `_score_pondere_avec_veto`), pas de note par défaut à 0.
- Ni conductivité, ni calcium/TH, ni TAC disponibles : `scores.cafe: null`, 3ème jauge affiche "Données insuffisantes" (comportement déjà géré par `jaugeHtml`).
- Carte : commune sans `score_cafe` → grise, comme pour les deux autres indicateurs.

## Tests

Pipeline : tests unitaires sur chaque fonction de score par bandes (bornes exactes), sur la formule de conversion GH (calcium présent vs fallback TH), sur la renormalisation en cas de composante manquante. Front-end : vérification manuelle (bascule 3 indicateurs sur la carte, jauge café dans la fiche, rendu du graphique SVG, recommandations barista affichées).

## Hors scope

- Base de données des eaux en bouteille (item séparé du backlog, non retenu pour l'instant).
- Ajustement des poids de la formule proposée au-delà de cette première version — à revoir après usage réel si besoin.
