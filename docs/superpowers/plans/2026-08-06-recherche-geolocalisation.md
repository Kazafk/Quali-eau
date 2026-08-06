# Recherche & Géolocalisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a debounced commune-name search (with department disambiguation) and a geolocation button to the header, both reusing the existing click-to-fiche path.

**Architecture:** A new module `public/panel.js`-style split: `public/search.js` has a pure HTML-builder (`suggestionHtml`, reusing `echapperHtml` from `panel.js` — no new escaping logic) plus a thin DOM/fetch/debounce layer that calls back into `map.js` via an injected callback (no circular import). `public/map.js`'s existing `onClicCommune` body is extracted into an exported `selectionnerCommune(code, nom)`, reused by a new exported `centrerEtSelectionner(code, nom, lon, lat)` (flies the map, then selects) that `search.js` calls after a search/geoloc result.

**Tech Stack:** Same as prior sub-projects — vanilla JS ES modules, no bundler, no framework; `geo.api.gouv.fr` (public, CORS-enabled, no key required); `node` for the pure function, manual browser verification for DOM/fetch/geolocation.

## Global Constraints

- Search endpoint: `https://geo.api.gouv.fr/communes?fields=nom,code,departement,centre&boost=population&limit=5&nom={terme}` — verified live to return an array of `{nom, code, departement: {code, nom} | null, centre: {coordinates: [lon, lat]}}`.
- Reverse-geocoding endpoint: `https://geo.api.gouv.fr/communes?fields=nom,code,departement,centre&lat={lat}&lon={lon}` — same response shape, verified live.
- Debounce: 300ms, only fires once the trimmed input is ≥2 characters; shorter input immediately clears suggestions/errors and invalidates any in-flight search.
- "Latest keystroke wins": an incrementing request counter (same pattern as `panel.js`'s "latest click wins") — a stale search response must never overwrite what the user has typed since.
- Any text from the `geo.api.gouv.fr` response (`nom`, `departement.nom`) reaching `innerHTML` must be escaped via `echapperHtml` (imported from `public/panel.js`, not reimplemented — single source of truth for this escaping logic across the whole front-end).
- Selecting a search result or a geolocation result must go through the exact same `carteScores[code]` presence check already used by map clicks (`selectionnerCommune`) — a result landing on one of the ~522 communes absent from `carte_scores.json` must show the "no data" panel state, never attempt a fetch that would 404.
- No JS test framework. The one pure function (`suggestionHtml`) is sanity-checked via `node --input-type=module -e`; everything else (debounce, fetch, geolocation, DOM) is verified manually via local HTTP server + browser.
- Repeat of the known `[hidden]` CSS-specificity bug (fixed for `#map-error` and correctly avoided for `#panel` in prior sub-projects): this plan's new hideable elements (`#recherche-suggestions`, `#recherche-erreur`) must NOT get an unconditional `display` rule in their base CSS — rely on the browser's default `[hidden]{display:none}` / default block rendering instead, exactly as this plan's CSS is written.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `public/search.js` | Create | `suggestionHtml` (pure, Task 1) + debounced search, geolocation, DOM wiring (Task 2) |
| `public/index.html` | Modify | Search input + suggestions list + geoloc button in `#app-header` |
| `public/style.css` | Modify | Styling for the above, desktop + mobile wrap |
| `public/map.js` | Modify | Extract `selectionnerCommune`, add `centrerEtSelectionner`, wire `initRecherche` |

---

### Task 1: `public/search.js` — pure suggestion-rendering function

**Files:**
- Create: `public/search.js`

**Interfaces:**
- Consumes: `echapperHtml` from `public/panel.js` (already exported, established sub-project 2).
- Produces: `suggestionHtml(communes: Array<{nom, code, departement: {nom} | null, centre: {coordinates: [number, number]}}>) -> string`. Used internally by Task 2's DOM layer in this same file.

- [x] **Step 1: Write `public/search.js` with the pure function**

```js
import { echapperHtml } from './panel.js';

export function suggestionHtml(communes) {
  if (communes.length === 0) {
    return '<li class="recherche-vide">Aucune commune trouvée</li>';
  }
  return communes.map((c) => {
    const dept = c.departement ? ` (${echapperHtml(c.departement.nom)})` : '';
    return `<li data-code="${echapperHtml(c.code)}" data-nom="${echapperHtml(c.nom)}" data-lon="${c.centre.coordinates[0]}" data-lat="${c.centre.coordinates[1]}">${echapperHtml(c.nom)}${dept}</li>`;
  }).join('');
}
```

- [x] **Step 2: Sanity-check with `node`**

Run (from the repo root):
```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
node --input-type=module -e "
import { suggestionHtml } from './public/search.js';

console.log(suggestionHtml([]).includes('Aucune commune trouvée'));
console.log(suggestionHtml([{ code: '93066', nom: 'Saint-Denis', departement: { code: '93', nom: 'Seine-Saint-Denis' }, centre: { coordinates: [2.3657, 48.9378] } }]).includes('Saint-Denis (Seine-Saint-Denis)'));
console.log(suggestionHtml([{ code: '1', nom: '<script>', departement: null, centre: { coordinates: [0, 0] } }]).includes('&lt;script&gt;'));
"
```
Expected:
```
true
true
true
```

- [x] **Step 3: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/search.js
git commit -m "feat: add pure suggestion-rendering function for commune search"
```

---

### Task 2: `public/search.js` — debounced search, geolocation, DOM wiring

**Files:**
- Modify: `public/search.js` (append to the file from Task 1 — do not remove or change `suggestionHtml`)

**Interfaces:**
- Consumes: `suggestionHtml` (Task 1, same file); DOM ids `recherche-input`, `recherche-suggestions`, `recherche-erreur`, `btn-geoloc` (Task 3, not yet created — this task's verification is syntax-only, real behavior verified in Task 5 once Tasks 3-4 exist).
- Produces: `initRecherche(callbackSelection: (code: string, nom: string, lon: number, lat: number) => void) -> void`. Used by `public/map.js` (Task 4), which passes its own `centrerEtSelectionner` as the callback — this indirection avoids a circular import between `map.js` and `search.js`.

- [x] **Step 1: Append the DOM/fetch layer to `public/search.js`**

```js
const RECHERCHE_URL = 'https://geo.api.gouv.fr/communes?fields=nom,code,departement,centre&boost=population&limit=5&nom=';
const GEOLOC_URL = 'https://geo.api.gouv.fr/communes?fields=nom,code,departement,centre';
const DEBOUNCE_MS = 300;

let requeteRechercheActuelle = 0;
let minuteurDebounce = null;
let selectionnerCallback = null;

function afficherErreurRecherche(message) {
  const el = document.getElementById('recherche-erreur');
  el.textContent = message;
  el.hidden = false;
}

function masquerErreurRecherche() {
  document.getElementById('recherche-erreur').hidden = true;
}

function masquerSuggestions() {
  const ul = document.getElementById('recherche-suggestions');
  ul.hidden = true;
  ul.innerHTML = '';
}

async function rechercher(terme) {
  requeteRechercheActuelle += 1;
  const monNumero = requeteRechercheActuelle;
  masquerErreurRecherche();
  try {
    const reponse = await fetch(RECHERCHE_URL + encodeURIComponent(terme));
    if (!reponse.ok) {
      throw new Error(`HTTP ${reponse.status}`);
    }
    const communes = await reponse.json();
    if (monNumero !== requeteRechercheActuelle) return;
    const ul = document.getElementById('recherche-suggestions');
    ul.innerHTML = suggestionHtml(communes);
    ul.hidden = false;
  } catch (erreur) {
    if (monNumero !== requeteRechercheActuelle) return;
    console.error(erreur);
    masquerSuggestions();
    afficherErreurRecherche('Recherche indisponible. Réessayez.');
  }
}

function onSaisie(event) {
  const terme = event.target.value.trim();
  if (minuteurDebounce) clearTimeout(minuteurDebounce);
  if (terme.length < 2) {
    masquerSuggestions();
    masquerErreurRecherche();
    requeteRechercheActuelle += 1;
    return;
  }
  minuteurDebounce = setTimeout(() => rechercher(terme), DEBOUNCE_MS);
}

function onClicSuggestion(event) {
  const li = event.target.closest('li[data-code]');
  if (!li) return;
  masquerSuggestions();
  document.getElementById('recherche-input').value = '';
  selectionnerCallback(li.dataset.code, li.dataset.nom, Number(li.dataset.lon), Number(li.dataset.lat));
}

async function onClicGeoloc() {
  masquerErreurRecherche();
  if (!navigator.geolocation) {
    afficherErreurRecherche('Géolocalisation non disponible sur ce navigateur.');
    return;
  }
  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const { latitude, longitude } = position.coords;
      try {
        const reponse = await fetch(`${GEOLOC_URL}&lat=${latitude}&lon=${longitude}`);
        if (!reponse.ok) {
          throw new Error(`HTTP ${reponse.status}`);
        }
        const communes = await reponse.json();
        if (communes.length === 0) {
          afficherErreurRecherche('Aucune commune trouvée à votre position.');
          return;
        }
        const c = communes[0];
        selectionnerCallback(c.code, c.nom, c.centre.coordinates[0], c.centre.coordinates[1]);
      } catch (erreur) {
        console.error(erreur);
        afficherErreurRecherche('Impossible de déterminer votre commune. Réessayez.');
      }
    },
    (erreur) => {
      console.error(erreur);
      afficherErreurRecherche(erreur.code === erreur.PERMISSION_DENIED ? 'Autorisation de géolocalisation refusée.' : 'Position non disponible.');
    }
  );
}

export function initRecherche(callbackSelection) {
  selectionnerCallback = callbackSelection;
  document.getElementById('recherche-input').addEventListener('input', onSaisie);
  document.getElementById('recherche-suggestions').addEventListener('click', onClicSuggestion);
  document.getElementById('btn-geoloc').addEventListener('click', onClicGeoloc);
}
```

- [x] **Step 2: Syntax-check with `node`**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
grep -v "^import " public/search.js > /tmp/search_no_imports.js
node --check /tmp/search_no_imports.js
```
Expected: no output (syntax OK). DOM/fetch/geolocation behavior cannot run under plain `node` — verified manually in Task 5, once Tasks 3-4 give it a real page and real callback to run against.

- [x] **Step 3: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/search.js
git commit -m "feat: add debounced search, geolocation, and DOM wiring to search.js"
```

---

### Task 3: `public/index.html` + `public/style.css` — search bar and geoloc button

**Files:**
- Modify: `public/index.html`
- Modify: `public/style.css`

**Interfaces:**
- Consumes: nothing new.
- Produces: DOM ids `recherche-input`, `recherche-suggestions`, `recherche-erreur`, `btn-geoloc` — consumed by `public/search.js` (Task 2, already written but not yet exercisable) and this task's own manual verification (layout only, no behavior yet).

- [x] **Step 1: Update `public/index.html`**

Replace:
```html
    <header id="app-header">
      <h1>💧 Quali'eau</h1>
      <div id="toggle-indicateur">
        <button id="btn-boisson" class="toggle-btn active" type="button">🥤 Boisson &amp; Santé</button>
        <button id="btn-cosmetique" class="toggle-btn" type="button">🧴 Cosmétique &amp; Lavage</button>
      </div>
    </header>
```
with:
```html
    <header id="app-header">
      <h1>💧 Quali'eau</h1>
      <div id="recherche">
        <input id="recherche-input" type="text" placeholder="Rechercher une commune…" autocomplete="off">
        <button id="btn-geoloc" type="button" aria-label="Me géolocaliser">📍</button>
        <ul id="recherche-suggestions" hidden></ul>
        <p id="recherche-erreur" hidden></p>
      </div>
      <div id="toggle-indicateur">
        <button id="btn-boisson" class="toggle-btn active" type="button">🥤 Boisson &amp; Santé</button>
        <button id="btn-cosmetique" class="toggle-btn" type="button">🧴 Cosmétique &amp; Lavage</button>
      </div>
    </header>
```

- [x] **Step 2: Update `public/style.css`**

Replace:
```css
#toggle-indicateur { display: flex; gap: 4px; flex-wrap: wrap; }
```
with:
```css
#recherche { position: relative; display: flex; gap: 4px; align-items: center; flex: 1 1 200px; max-width: 280px; }
#recherche-input {
  flex: 1; min-width: 0; padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.15); color: #fff; font-size: 0.85rem;
}
#recherche-input::placeholder { color: rgba(255, 255, 255, 0.7); }
#btn-geoloc {
  border: 1px solid rgba(255, 255, 255, 0.4); background: transparent; color: #fff;
  padding: 6px 8px; border-radius: 6px; cursor: pointer; font-size: 0.9rem;
}
#recherche-suggestions {
  position: absolute; top: 100%; left: 0; right: 0; margin: 4px 0 0; padding: 0; list-style: none;
  background: #fff; border-radius: 6px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25); z-index: 10; overflow: hidden;
}
#recherche-suggestions li { padding: 8px 10px; font-size: 0.85rem; color: #222; cursor: pointer; }
#recherche-suggestions li:hover { background: #f0f0f0; }
#recherche-erreur {
  position: absolute; top: 100%; left: 0; margin: 4px 0 0; font-size: 0.75rem; color: #fff;
  background: #c0392b; padding: 4px 8px; border-radius: 6px; z-index: 10;
}

#toggle-indicateur { display: flex; gap: 4px; flex-wrap: wrap; }
```
(Note: neither `#recherche-suggestions` nor `#recherche-erreur` sets an unconditional `display` — they rely on the browser's default `[hidden]{display:none}` and default block rendering, avoiding the known CSS-specificity bug class entirely, per this plan's Global Constraints.)

Replace the `@media (max-width: 600px)` block:
```css
@media (max-width: 600px) {
  #app-header { padding: 8px 12px; }
  #app-header h1 { font-size: 1rem; width: 100%; }
  #legend { left: 8px; bottom: 8px; font-size: 0.72rem; padding: 8px 10px; }

  main { flex-direction: column; }
  #panel {
    position: fixed; left: 0; right: 0; bottom: 0; width: auto;
    max-height: 70vh; max-height: 70dvh; border-left: none; border-top: 1px solid #ddd;
    border-radius: 12px 12px 0 0; box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.15); z-index: 6;
  }
}
```
with:
```css
@media (max-width: 600px) {
  #app-header { padding: 8px 12px; }
  #app-header h1 { font-size: 1rem; width: 100%; }
  #legend { left: 8px; bottom: 8px; font-size: 0.72rem; padding: 8px 10px; }

  #recherche { flex: 1 1 100%; max-width: none; order: 3; }

  main { flex-direction: column; }
  #panel {
    position: fixed; left: 0; right: 0; bottom: 0; width: auto;
    max-height: 70vh; max-height: 70dvh; border-left: none; border-top: 1px solid #ddd;
    border-radius: 12px 12px 0 0; box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.15); z-index: 6;
  }
}
```

- [x] **Step 3: Manual verification (layout only, no behavior)**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000`. Expected: a search input with a 📍 button appears in the header between the title and the Boisson/Cosmétique toggle, styled consistently with the dark header (semi-transparent input, white text/placeholder). Typing does nothing yet (no JS wired). Narrow the window below 600px — expected: the search bar drops to its own full-width row (via `order: 3` + `flex-wrap` already on `#app-header`), below the title and toggle buttons. Stop the server when done.

- [x] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/index.html public/style.css
git commit -m "feat: add search bar and geolocation button to the header"
```

---

### Task 4: `public/map.js` — extract `selectionnerCommune`, add `centrerEtSelectionner`, wire search

**Files:**
- Modify: `public/map.js`

**Interfaces:**
- Consumes: `initRecherche` from `public/search.js` (Task 2).
- Produces: `selectionnerCommune(code: string, nom: string) -> void` (exported, refactor of the existing `onClicCommune` body — same behavior, now reusable), `centrerEtSelectionner(code: string, nom: string, lon: number, lat: number) -> void` (exported, new — flies the map then calls `selectionnerCommune`). These are the final wiring points for this plan.

- [x] **Step 1: Update imports**

Replace:
```js
import { afficherCommune, afficherCommuneSansDonnees, initPanel } from './panel.js';
```
with:
```js
import { afficherCommune, afficherCommuneSansDonnees, initPanel } from './panel.js';
import { initRecherche } from './search.js';
```

- [x] **Step 2: Extract `selectionnerCommune` and add `centrerEtSelectionner`**

Replace:
```js
function onClicCommune(event) {
  const feature = event.features[0];
  const code = resolveCodeInsee(feature.properties.code);
  if (!carteScores[code]) {
    afficherCommuneSansDonnees(code, feature.properties.nom);
    return;
  }
  afficherCommune(code, feature.properties.nom);
}
```
with:
```js
export function selectionnerCommune(code, nom) {
  if (!carteScores[code]) {
    afficherCommuneSansDonnees(code, nom);
    return;
  }
  afficherCommune(code, nom);
}

function onClicCommune(event) {
  const feature = event.features[0];
  const code = resolveCodeInsee(feature.properties.code);
  selectionnerCommune(code, feature.properties.nom);
}

export function centrerEtSelectionner(code, nom, lon, lat) {
  map.flyTo({ center: [lon, lat], zoom: 11 });
  selectionnerCommune(code, nom);
}
```

- [x] **Step 3: Call `initRecherche` from `initCarte()`**

Replace:
```js
function initCarte() {
  renderLegend();
  initBascule();
  initPanel();
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);
```
with:
```js
function initCarte() {
  renderLegend();
  initBascule();
  initPanel();
  initRecherche(centrerEtSelectionner);
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);
```

- [x] **Step 4: Syntax-check with `node`**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
grep -v "^import " public/map.js > /tmp/map_no_imports.js
node --check /tmp/map_no_imports.js
```
Expected: no output (syntax OK).

- [x] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/map.js
git commit -m "feat: wire search and geolocation to the map and panel"
```

(Full manual verification of the search-to-fiche and geoloc-to-fiche flows happens in Task 5.)

---

### Task 5: Final end-to-end verification

**This task is not a code task** — it walks through the full manual checklist from the design spec (`docs/superpowers/specs/2026-08-06-recherche-geolocalisation-design.md`) against the finished feature.

- [x] **Step 1: Full manual walkthrough**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000` and confirm every item:
- Type "Saint-Denis" into the search box — after ~300ms (once ≥2 characters), a dropdown of up to 5 suggestions appears, each showing "Saint-Denis (Département)" with DIFFERENT department names (e.g. Seine-Saint-Denis, La Réunion, Aude...), confirming the homonym disambiguation works with the real API.
- Click a suggestion — the map flies to that commune and zooms in, the input clears, the suggestion list closes, and the commune's fiche panel opens with real data (or the "no data" state if that specific commune happens to lack a fiche).
- Type a nonsense string (e.g. "zzzzxxxx") — "Aucune commune trouvée" appears in the dropdown, not an empty or broken list.
- Type fast, backspace, retype — no flicker of stale suggestions from an earlier keystroke; only the latest typed term's results ever appear.
- Type a single character — no request fires, no dropdown appears (below the 2-character threshold).
- Click the 📍 geolocation button and ALLOW the browser's permission prompt — the map flies to your approximate location and opens that commune's fiche.
- Click 📍 again and DENY the permission prompt (or test via browser devtools' geolocation override set to "block") — an inline error message appears ("Autorisation de géolocalisation refusée."), no silent failure, no broken UI state.
- Narrow the viewport below 600px — the search bar appears on its own row below the header title/toggle, remains usable (type, see suggestions, tap one).
- Browser console free of errors throughout (aside from any browser-level permission-prompt logging, which is not an application error).

Stop the server (Ctrl+C) when done. If any check fails, fix it as part of this task before proceeding.

- [x] **Step 2: Report**

Confirm to the user that the recherche + géolocalisation sub-project (Phase 2, 3/5) is complete and working end-to-end, with a summary of what was verified in Step 1, before moving on to the next sub-project (déploiement CI GitHub Pages).
