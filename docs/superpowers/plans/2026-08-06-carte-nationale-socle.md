# Carte Nationale — Socle Site Statique Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first slice of Quali'eau's static front-end (Phase 2, sub-project 1/5): a national map of metropolitan France, communes colored by a 5-class A-E score, with a toggle between the "Boisson & Santé" and "Cosmétique & Lavage" scores.

**Architecture:** One additive pipeline output (`public/data/carte_scores.json`, a compact per-commune score map derived from the already-computed `fiches` dict, no change to the existing rich commune fiche schema) feeds a vanilla-JS front-end that, at runtime, fetches that file plus a third-party pre-simplified commune-boundary GeoJSON, joins them client-side (with a static arrondissement→commune mapping for Paris/Lyon/Marseille), and renders via MapLibre GL JS. No server-side geometry processing, no build step.

**Tech Stack:** Python 3.12 stdlib (pipeline, unchanged toolchain) + pytest; vanilla JS ES modules (no bundler, no framework) + MapLibre GL JS v4 via CDN; `node` (already listed as an optional project prerequisite) used only to sanity-check the two pure JS logic modules — not a test framework, no `package.json` introduced.

## Global Constraints

- Map background style: `https://tiles.openfreemap.org/styles/positron` — the only style, no dark/light toggle (explicitly out of scope).
- Commune geometry source: `https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/communes-version-simplifiee.geojson` — metropolitan France only, fetched client-side at every page load, never downloaded by the Python pipeline.
- MapLibre GL JS via `https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js` and matching `.css` (same major-version pin already proven in production by the sibling project `sca-water-map`).
- Arrondissement → parent-commune mapping (geometry source splits these 3 cities, DIS data does not): Paris `751xx` (01-20) → `75056`; Lyon `6938x` (1-9) → `69123`; Marseille `132xx` (01-16) → `13055`.
- Default indicator on load: Boisson & Santé (`score_boisson`); toggle switches to `score_cosmetique`.
- A-E thresholds (README "Système de Scoring Dual", single source of truth, lives only in `public/scoring.js`): 80-100=A, 60-79=B, 40-59=C, 20-39=D, 0-19=E. No `classe` field is added to the Python pipeline's output — classification is computed client-side.
- Do not modify the existing commune fiche schema (`public/data/communes/{code}.json`) or `public/data/index.json` — this plan only *adds* `public/data/carte_scores.json`.
- No JS test framework (jest/mocha/etc.) is introduced. Pure-logic JS modules (`scoring.js`, `geo_join.js`) are sanity-checked via plain `node --input-type=module -e`; DOM/map-rendering code is verified manually in a browser against a local HTTP server.
- Commune-click behavior (opening a detail panel) is a stub in this plan — the actual fiche display is a future sub-project.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `pipeline/compute_scores.py` | Modify | Add `construire_carte_scores(fiches)`, call it from `main()` |
| `tests/test_compute_scores.py` | Modify | Unit tests for `construire_carte_scores` |
| `tests/test_pipeline_integration.py` | Modify | End-to-end test that `main()` writes `carte_scores.json` |
| `public/data/carte_scores.json` | Create (generated) | Real data for the 34 845 already-computed communes, regenerated from existing fiches — not hand-written |
| `public/scoring.js` | Create | Single source of truth for A-E thresholds/colors and `classeFromScore()` |
| `public/geo_join.js` | Create | Arrondissement mapping + client-side geometry/score join, pure logic, no DOM |
| `public/index.html` | Create | Page shell: header, toggle buttons, map container, legend container, panel placeholder |
| `public/style.css` | Create | Mobile-first layout and styling for the shell |
| `public/map.js` | Create | MapLibre init, data fetch, rendering, legend, toggle wiring, error handling, click stub |

---

### Task 1: Pipeline — `construire_carte_scores()` and real data regeneration

**Files:**
- Modify: `pipeline/compute_scores.py`
- Modify: `tests/test_compute_scores.py`
- Modify: `tests/test_pipeline_integration.py`
- Create (generated, not hand-written): `public/data/carte_scores.json`

**Interfaces:**
- Consumes: nothing new — operates on the `fiches: dict` shape already produced by `pipeline.compute_scores.construire_fiches` (each value has `statut_donnees: str` and either `scores: None` or `scores: {"boisson": {"score": int, ...}, "cosmetique": {"score": int, ...}, ...}`).
- Produces: `pipeline.compute_scores.construire_carte_scores(fiches: dict) -> dict`, mapping `code_insee -> {"score_boisson": int | None, "score_cosmetique": int | None, "statut_donnees": str}`. Called by `main()`, which writes it to `{output_dir}/carte_scores.json`.

- [ ] **Step 1: Write the failing unit tests**

Append to `tests/test_compute_scores.py`:

```python
from pipeline.compute_scores import construire_carte_scores


def test_construire_carte_scores_extrait_scores_commune_complete():
    fiches = {
        "75056": {
            "commune": {"code_insee": "75056"},
            "statut_donnees": "complet",
            "scores": {
                "donnees_partielles": False,
                "boisson": {"score": 90, "veto_sanitaire": False, "sous_scores": {}},
                "cosmetique": {"score": 76, "sous_scores": {}},
            },
            "recommandations": [],
        },
    }
    carte = construire_carte_scores(fiches)
    assert carte == {
        "75056": {"score_boisson": 90, "score_cosmetique": 76, "statut_donnees": "complet"},
    }


def test_construire_carte_scores_commune_indisponible_a_scores_null():
    fiches = {
        "99999": {"commune": {"code_insee": "99999"}, "statut_donnees": "indisponible", "scores": None},
    }
    carte = construire_carte_scores(fiches)
    assert carte == {
        "99999": {"score_boisson": None, "score_cosmetique": None, "statut_donnees": "indisponible"},
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compute_scores.py -v -k construire_carte_scores`
Expected: FAIL with `ImportError: cannot import name 'construire_carte_scores'`

- [ ] **Step 3: Implement `construire_carte_scores`**

In `pipeline/compute_scores.py`, add this function directly after `construire_fiches`:

```python
def construire_carte_scores(fiches: dict) -> dict:
    """Extrait de `fiches` (sortie de construire_fiches) le sous-ensemble
    minimal nécessaire à la coloration de la carte nationale côté client :
    score_boisson, score_cosmetique, statut_donnees par commune. N'ajoute
    aucun champ au schéma existant des fiches (classe A-E, historique,
    etc. restent hors du pipeline, calculés côté front-end)."""
    carte = {}
    for code_insee, fiche in fiches.items():
        scores = fiche.get("scores")
        carte[code_insee] = {
            "score_boisson": scores["boisson"]["score"] if scores else None,
            "score_cosmetique": scores["cosmetique"]["score"] if scores else None,
            "statut_donnees": fiche["statut_donnees"],
        }
    return carte
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compute_scores.py -v -k construire_carte_scores`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire `construire_carte_scores` into `main()`**

In `pipeline/compute_scores.py`, in `main()`, replace:

```python
    index = {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "nb_communes_scorees": sum(1 for f in fiches.values() if f["statut_donnees"] == "complet"),
        "nb_communes_sans_donnees": sum(1 for f in fiches.values() if f["statut_donnees"] == "indisponible"),
    }
    with open(os.path.join(output_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
```

with:

```python
    index = {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "nb_communes_scorees": sum(1 for f in fiches.values() if f["statut_donnees"] == "complet"),
        "nb_communes_sans_donnees": sum(1 for f in fiches.values() if f["statut_donnees"] == "indisponible"),
    }
    with open(os.path.join(output_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    carte_scores = construire_carte_scores(fiches)
    with open(os.path.join(output_dir, "carte_scores.json"), "w", encoding="utf-8") as f:
        json.dump(carte_scores, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 6: Write the failing integration test**

Append to `tests/test_pipeline_integration.py`:

```python
def test_pipeline_ecrit_carte_scores_json(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    import shutil
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"), raw_dir / "DIS_PLV.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), raw_dir / "DIS_RESULT.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"), raw_dir / "DIS_COM_UDI.txt")

    output_dir = tmp_path / "output"
    from datetime import date
    main(raw_dir=str(raw_dir), output_dir=str(output_dir), date_reference=date(2026, 8, 5))

    carte_path = output_dir / "carte_scores.json"
    assert carte_path.exists()
    carte = json.loads(carte_path.read_text(encoding="utf-8"))
    assert "34116" in carte
    assert carte["34116"]["statut_donnees"] == "complet"
    assert isinstance(carte["34116"]["score_boisson"], int)
    assert isinstance(carte["34116"]["score_cosmetique"], int)
```

- [ ] **Step 7: Run test to verify it fails, then passes**

Run: `pytest tests/test_pipeline_integration.py -v -k carte_scores`
Expected: first FAIL (`carte_scores.json` doesn't exist — this only fails if Step 5 wasn't done; since it was, expect it to already PASS here) — run it and confirm PASS.

- [ ] **Step 8: Run the entire test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests, full project)

- [ ] **Step 9: Regenerate real `carte_scores.json` from the already-computed fiches**

`public/data/communes/*.json` (34 845 files) were already generated and committed against real DIS 2023-2026 data in a previous plan. Re-running the full pipeline would require re-downloading ~900 Mo. Instead, derive `carte_scores.json` directly from the fiches already on disk:

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
python -c "
import json, os
from pipeline.compute_scores import construire_carte_scores

communes_dir = os.path.join('public', 'data', 'communes')
fiches = {}
for nom_fichier in os.listdir(communes_dir):
    code_insee = nom_fichier.removesuffix('.json')
    with open(os.path.join(communes_dir, nom_fichier), encoding='utf-8') as f:
        fiches[code_insee] = json.load(f)

carte_scores = construire_carte_scores(fiches)
with open(os.path.join('public', 'data', 'carte_scores.json'), 'w', encoding='utf-8') as f:
    json.dump(carte_scores, f, ensure_ascii=False, indent=2)
print(f'{len(carte_scores)} communes ecrites dans carte_scores.json')
"
```
Expected: prints a count close to 34 845 (matches the number of files in `public/data/communes/`). This file is needed as real test data by Task 5 onward.

- [ ] **Step 10: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add pipeline/compute_scores.py tests/test_compute_scores.py tests/test_pipeline_integration.py public/data/carte_scores.json
git commit -m "feat: add carte_scores.json output for client-side map coloring"
```

---

### Task 2: `public/scoring.js` — A-E thresholds and colors (single source of truth)

**Files:**
- Create: `public/scoring.js`

**Interfaces:**
- Consumes: nothing.
- Produces: `SCORE_THRESHOLDS` (array of `{seuil: number, classe: 'A'|'B'|'C'|'D'|'E', couleur: string, libelle: string}`, ordered highest-to-lowest `seuil`), `NO_DATA` (`{classe: null, couleur: string, libelle: string}`), `classeFromScore(score: number | null) -> {classe, couleur, libelle}`. Used by `public/geo_join.js` (Task 3) and `public/map.js` (Tasks 5-6).

- [ ] **Step 1: Write `public/scoring.js`**

```js
// Seuils Nutri-Score A-E (README, "Système de Scoring Dual") — source unique
// de vérité, réutilisée par la carte (légende + couleurs) et par la future
// fiche communale.
export const SCORE_THRESHOLDS = [
  { seuil: 80, classe: 'A', couleur: '#1e8f4e', libelle: 'Parfait' },
  { seuil: 60, classe: 'B', couleur: '#6cbf3f', libelle: 'Bon' },
  { seuil: 40, classe: 'C', couleur: '#f4c430', libelle: 'Moyen' },
  { seuil: 20, classe: 'D', couleur: '#f2994a', libelle: 'Passable' },
  { seuil: 0, classe: 'E', couleur: '#e74c3c', libelle: 'Critique' },
];

export const NO_DATA = { classe: null, couleur: '#b0b0b0', libelle: 'Données indisponibles' };

export function classeFromScore(score) {
  if (score == null) return NO_DATA;
  for (const palier of SCORE_THRESHOLDS) {
    if (score >= palier.seuil) return palier;
  }
  return SCORE_THRESHOLDS[SCORE_THRESHOLDS.length - 1];
}
```

- [ ] **Step 2: Sanity-check with `node`**

Run (from the repo root):
```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
node --input-type=module -e "
import { classeFromScore } from './public/scoring.js';
const resultats = [90, 65, 45, 25, 5, null].map((s) => classeFromScore(s).classe);
console.log(JSON.stringify(resultats));
"
```
Expected: `["A","B","C","D","E",null]`

- [ ] **Step 3: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/scoring.js
git commit -m "feat: add scoring.js with A-E thresholds and classeFromScore"
```

---

### Task 3: `public/geo_join.js` — arrondissement mapping and client-side join

**Files:**
- Create: `public/geo_join.js`

**Interfaces:**
- Consumes: `classeFromScore` from `public/scoring.js` (Task 2).
- Produces: `ARR_PARENT` (object, arrondissement code → parent commune code), `resolveCodeInsee(codeInsee: string) -> string`, `joindreScoresSurGeojson(geojson: {features: Array<{properties: {code: string}}>}, carteScores: dict, indicateur: 'score_boisson' | 'score_cosmetique') -> geojson` (mutates `feature.properties.color` in place on every feature, returns the same object). Used by `public/map.js` (Tasks 5-6).

- [ ] **Step 1: Write `public/geo_join.js`**

```js
import { classeFromScore } from './scoring.js';

// Mappage arrondissements -> commune parente : le geojson tiers
// (france-geojson) découpe Paris/Lyon/Marseille en arrondissements, mais
// les données DIS sont agrégées au niveau commune. Sans ce mappage, ces
// polygones apparaîtraient à tort comme "sans données" sur la carte.
export const ARR_PARENT = {};
for (let i = 1; i <= 20; i++) {
  ARR_PARENT[`751${String(i).padStart(2, '0')}`] = '75056'; // Paris
}
for (let i = 1; i <= 9; i++) {
  ARR_PARENT[`6938${i}`] = '69123'; // Lyon
}
for (let i = 1; i <= 16; i++) {
  ARR_PARENT[`132${String(i).padStart(2, '0')}`] = '13055'; // Marseille
}

export function resolveCodeInsee(codeInsee) {
  return ARR_PARENT[codeInsee] ?? codeInsee;
}

export function joindreScoresSurGeojson(geojson, carteScores, indicateur) {
  for (const feature of geojson.features) {
    const code = resolveCodeInsee(feature.properties.code);
    const entree = carteScores[code];
    const score = entree ? entree[indicateur] : null;
    feature.properties.color = classeFromScore(score).couleur;
  }
  return geojson;
}
```

- [ ] **Step 2: Sanity-check with `node`**

Run (from the repo root):
```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
node --input-type=module -e "
import { resolveCodeInsee, joindreScoresSurGeojson } from './public/geo_join.js';

console.log(resolveCodeInsee('75108'));  // arrondissement Paris
console.log(resolveCodeInsee('69382'));  // arrondissement Lyon
console.log(resolveCodeInsee('13205'));  // arrondissement Marseille
console.log(resolveCodeInsee('34116'));  // commune ordinaire, inchangée

const geojson = { features: [
  { properties: { code: '75108' } },
  { properties: { code: '34116' } },
  { properties: { code: '99999' } },
] };
const carteScores = {
  '75056': { score_boisson: 90, score_cosmetique: 76, statut_donnees: 'complet' },
  '34116': { score_boisson: 45, score_cosmetique: 60, statut_donnees: 'complet' },
};
joindreScoresSurGeojson(geojson, carteScores, 'score_boisson');
console.log(geojson.features.map((f) => f.properties.color));
"
```
Expected:
```
75056
69123
13055
34116
["#1e8f4e","#f4c430","#b0b0b0"]
```
(75108 resolves to Paris, score 90 → classe A → `#1e8f4e`; 34116 score 45 → classe C → `#f4c430`; 99999 has no entry and isn't an arrondissement → no-data grey `#b0b0b0`.)

- [ ] **Step 3: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/geo_join.js
git commit -m "feat: add geo_join.js with arrondissement mapping and client-side score join"
```

---

### Task 4: Page shell — `public/index.html`, `public/style.css`, minimal `public/map.js`

**Files:**
- Create: `public/index.html`
- Create: `public/style.css`
- Create: `public/map.js` (minimal placeholder content in this task — Task 5 replaces it with the real implementation)

**Interfaces:**
- Consumes: nothing (static shell only).
- Produces: DOM element ids consumed by Tasks 5-6: `map` (map container), `map-error` (hidden error banner), `legend` (legend container), `btn-boisson` / `btn-cosmetique` (toggle buttons, `btn-boisson` starts with class `active`), `panel` (empty placeholder for a future sub-project).

- [ ] **Step 1: Write `public/index.html`**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Quali'eau — Qualité de l'eau du robinet en France</title>
  <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="app">
    <header id="app-header">
      <h1>💧 Quali'eau</h1>
      <div id="toggle-indicateur">
        <button id="btn-boisson" class="toggle-btn active" type="button">🥤 Boisson &amp; Santé</button>
        <button id="btn-cosmetique" class="toggle-btn" type="button">🧴 Cosmétique &amp; Lavage</button>
      </div>
    </header>
    <main>
      <div id="map"></div>
      <div id="map-error" hidden>Impossible de charger la carte. Réessayez plus tard.</div>
      <div id="legend"></div>
      <aside id="panel"></aside>
    </main>
  </div>
  <script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
  <script type="module" src="map.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `public/style.css`**

```css
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
#app { display: flex; flex-direction: column; height: 100vh; }

#app-header {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
  padding: 10px 16px; background: #0b3d5c; color: #fff;
}
#app-header h1 { font-size: 1.1rem; margin: 0; }

#toggle-indicateur { display: flex; gap: 4px; }
.toggle-btn {
  border: 1px solid rgba(255, 255, 255, 0.4); background: transparent; color: #fff;
  padding: 6px 10px; border-radius: 6px; font-size: 0.85rem; cursor: pointer;
}
.toggle-btn.active { background: #fff; color: #0b3d5c; font-weight: 600; }

main { position: relative; flex: 1; }
#map { position: absolute; inset: 0; background: #e8eef2; }

#map-error {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  padding: 24px; text-align: center; background: rgba(255, 255, 255, 0.95); z-index: 5;
}

#legend {
  position: absolute; bottom: 16px; left: 16px; z-index: 4;
  background: rgba(255, 255, 255, 0.92); border-radius: 8px; padding: 10px 12px;
  font-size: 0.8rem; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
}
.legend-row { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
.legend-swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }

#panel { display: none; }

@media (max-width: 600px) {
  #app-header { padding: 8px 12px; }
  #app-header h1 { font-size: 1rem; width: 100%; }
  #legend { left: 8px; bottom: 8px; font-size: 0.72rem; padding: 8px 10px; }
}
```

- [ ] **Step 3: Write a minimal `public/map.js` (replaced in Task 5)**

```js
console.log("Quali'eau — carte nationale : chargement de la page");
```

- [ ] **Step 4: Manual verification**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000` in a browser. Expected: dark blue header with "💧 Quali'eau" title and two toggle buttons (Boisson highlighted white/active), a light gray-blue rectangle filling the rest of the viewport (the future map area), no visible legend box content yet (empty `#legend` div), browser console shows exactly `Quali'eau — carte nationale : chargement de la page` with no errors. Resize the window to a narrow (mobile) width and confirm the header wraps without overlapping. Stop the server (Ctrl+C) when done.

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/index.html public/style.css public/map.js
git commit -m "feat: add static page shell for the national map"
```

---

### Task 5: `public/map.js` — data loading, client-side join, MapLibre rendering, error handling

**Files:**
- Modify: `public/map.js` (full replacement of Task 4's placeholder content)

**Interfaces:**
- Consumes: `NO_DATA` from `public/scoring.js` (Task 2); `joindreScoresSurGeojson` from `public/geo_join.js` (Task 3); DOM ids `map`, `map-error` from `public/index.html` (Task 4); global `maplibregl` (loaded via the CDN `<script>` tag in `index.html`).
- Produces: module-level state (`carteScores`, `geojson`, `map`, `indicateurActif`) and functions `chargerDonnees()`, `afficherErreur()`, `onClicCommune(event)`, `initCarte()`, `demarrer()` — `initCarte` and `indicateurActif` are extended by Task 6 (legend + toggle); `onClicCommune` is a stub for a future sub-project (fiche communale).

- [ ] **Step 1: Replace `public/map.js` with the full implementation**

```js
import { NO_DATA } from './scoring.js';
import { joindreScoresSurGeojson } from './geo_join.js';

const CARTE_SCORES_URL = './data/carte_scores.json';
const GEOJSON_URL = 'https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/communes-version-simplifiee.geojson';
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron';

let carteScores = null;
let geojson = null;
let map = null;
let indicateurActif = 'score_boisson';

async function chargerDonnees() {
  const [reponseScores, reponseGeojson] = await Promise.all([
    fetch(CARTE_SCORES_URL),
    fetch(GEOJSON_URL),
  ]);
  if (!reponseScores.ok || !reponseGeojson.ok) {
    throw new Error(`Échec du chargement (scores: ${reponseScores.status}, geojson: ${reponseGeojson.status})`);
  }
  carteScores = await reponseScores.json();
  geojson = await reponseGeojson.json();
}

function afficherErreur() {
  document.getElementById('map-error').hidden = false;
  document.getElementById('map').hidden = true;
}

function onClicCommune(event) {
  const feature = event.features[0];
  // Stub : la fiche communale au clic est un sous-projet futur, non
  // implémenté ici.
  console.log('Commune cliquée (fiche à venir) :', feature.properties.code);
}

function initCarte() {
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);

  map = new maplibregl.Map({
    container: 'map',
    style: MAP_STYLE,
    center: [2.5, 46.6],
    zoom: 4.5,
  });
  map.addControl(new maplibregl.NavigationControl(), 'top-right');

  map.on('load', () => {
    map.addSource('communes', { type: 'geojson', data: geojson });
    map.addLayer({
      id: 'communes-fill',
      type: 'fill',
      source: 'communes',
      paint: {
        'fill-color': ['coalesce', ['get', 'color'], NO_DATA.couleur],
        'fill-opacity': 0.75,
      },
    });
    map.addLayer({
      id: 'communes-line',
      type: 'line',
      source: 'communes',
      paint: { 'line-color': '#ffffff', 'line-width': 0.3 },
    });
    map.on('click', 'communes-fill', onClicCommune);
    map.on('mouseenter', 'communes-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'communes-fill', () => { map.getCanvas().style.cursor = ''; });
  });

  map.on('error', (e) => {
    console.error('Erreur MapLibre :', e.error);
    afficherErreur();
  });
}

async function demarrer() {
  try {
    await chargerDonnees();
    initCarte();
  } catch (erreur) {
    console.error(erreur);
    afficherErreur();
  }
}

demarrer();
```

- [ ] **Step 2: Manual verification — happy path**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000`. Expected: a map of metropolitan France appears within a few seconds, communes filled with colors from the A-E palette defined in `scoring.js` (greens/yellow/orange/red), Paris/Lyon/Marseille render as single-colored blobs (not a patchwork of 45+ grey slivers — confirms the arrondissement mapping works against the real geometry file), zoom/pan works via the top-right navigation control, no uncaught errors in the browser console. Zoom into Paris specifically and confirm all 20 arrondissements share the exact same fill color.

- [ ] **Step 3: Manual verification — error path**

With the local server still running, open the browser DevTools Network tab, set throttling to "Offline" (or block the request to `communes-version-simplifiee.geojson` via a request-blocking rule), then reload the page. Expected: the map area is replaced by the visible text "Impossible de charger la carte. Réessayez plus tard.", the `#map` div is hidden, the console shows the logged error, no infinite spinner or blank white screen. Restore normal network conditions afterward.

- [ ] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/map.js
git commit -m "feat: render national map with client-side geometry/score join"
```

---

### Task 6: Legend and Boisson/Cosmétique toggle

**Files:**
- Modify: `public/map.js`

**Interfaces:**
- Consumes: `SCORE_THRESHOLDS`, `NO_DATA` from `public/scoring.js` (Task 2, `NO_DATA` already imported by Task 5 — add `SCORE_THRESHOLDS` to that import); `joindreScoresSurGeojson` (already imported by Task 5); DOM ids `legend`, `btn-boisson`, `btn-cosmetique` from `public/index.html` (Task 4).
- Produces: `renderLegend()`, `activerIndicateur(indicateur)`, `initBascule()` — called once from `initCarte()`.

- [ ] **Step 1: Update the `scoring.js` import and add the new functions**

In `public/map.js`, change:
```js
import { NO_DATA } from './scoring.js';
```
to:
```js
import { NO_DATA, SCORE_THRESHOLDS } from './scoring.js';
```

Add these three functions directly above `function initCarte() {`:

```js
function renderLegend() {
  const lignes = SCORE_THRESHOLDS.map(
    (p) => `<div class="legend-row"><span class="legend-swatch" style="background:${p.couleur}"></span>${p.classe} — ${p.libelle}</div>`
  );
  lignes.push(
    `<div class="legend-row"><span class="legend-swatch" style="background:${NO_DATA.couleur}"></span>${NO_DATA.libelle}</div>`
  );
  document.getElementById('legend').innerHTML = lignes.join('');
}

function activerIndicateur(indicateur) {
  indicateurActif = indicateur;
  document.getElementById('btn-boisson').classList.toggle('active', indicateur === 'score_boisson');
  document.getElementById('btn-cosmetique').classList.toggle('active', indicateur === 'score_cosmetique');
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);
  map.getSource('communes').setData(geojson);
}

function initBascule() {
  document.getElementById('btn-boisson').addEventListener('click', () => activerIndicateur('score_boisson'));
  document.getElementById('btn-cosmetique').addEventListener('click', () => activerIndicateur('score_cosmetique'));
}
```

- [ ] **Step 2: Call the new functions from `initCarte()`**

In `public/map.js`, at the very start of `initCarte()`, change:
```js
function initCarte() {
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);
```
to:
```js
function initCarte() {
  renderLegend();
  initBascule();
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);
```

- [ ] **Step 3: Manual verification**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000`. Expected: the bottom-left legend box now shows 6 rows (A "Parfait" through E "Critique", plus "Données indisponibles"), each with a color swatch matching the map's palette. Click "🧴 Cosmétique & Lavage" — expected: that button becomes highlighted/active, "🥤 Boisson & Santé" loses its active style, and the map recolors (e.g., Paris — which scores low on `score_boisson` due to its sanitary veto but reasonably on `score_cosmetique` — visibly changes color). Click back to "🥤 Boisson & Santé" and confirm it reverts. No console errors during either toggle.

- [ ] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/map.js
git commit -m "feat: add score legend and Boisson/Cosmétique toggle to the map"
```

---

### Task 7: Final end-to-end verification

**This task is not a code task** — it re-runs the automated suite and walks through the full manual checklist from the design spec (`docs/superpowers/specs/2026-08-06-carte-nationale-design.md`) against the finished feature, across all previous tasks together.

- [ ] **Step 1: Run the full pytest suite**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
pytest tests/ -v
```
Expected: PASS (all tests, full project — pre-existing tests plus this plan's additions).

- [ ] **Step 2: Full manual walkthrough**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000` and confirm every item:
- Map loads within a few seconds, colored A-E per commune, legend matches the palette.
- Paris, Lyon, and Marseille each render as one uniformly-colored area (arrondissement mapping holds on the real 34 845-commune dataset generated in Task 1).
- Toggling Boisson/Cosmétique recolors the map and updates button active-states; toggling back and forth repeatedly causes no errors or visual glitches.
- Communes with `statut_donnees: "indisponible"` in `public/data/carte_scores.json` render in the neutral grey, not a stale or default color.
- Simulating an offline/blocked fetch (DevTools Network throttling) shows the inline error message, not a blank or frozen page.
- Browser console is free of errors and warnings throughout normal use.
- Narrow-viewport (mobile-width) layout: header wraps cleanly, legend remains readable and doesn't overflow the screen edge.
- Clicking any commune logs `Commune cliquée (fiche à venir) : <code_insee>` to the console (stub confirmed wired, actual panel deferred to the next sub-project).

Stop the server (Ctrl+C) when done. If any check fails, fix it as part of this task before proceeding (do not silently accept a broken behavior as "good enough").

- [ ] **Step 3: Report**

Confirm to the user that the socle carte nationale sub-project (Phase 2, 1/5) is complete and working end-to-end, with a summary of what was verified in Step 2, before moving on to the next sub-project (fiche communale au clic).
