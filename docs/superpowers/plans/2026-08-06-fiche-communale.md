# Fiche Communale au Clic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `onClicCommune` console.log stub in `public/map.js` with a real commune-fiche panel: sidebar on desktop, bottom sheet on mobile, showing both Boisson and Cosmétique scores, sub-scores, sanitary veto alert, and recommendations, fetched lazily and cached.

**Architecture:** A new pure-logic-first module `public/panel.js` — HTML-string-building functions (no DOM) for the actual content, and a thin DOM/fetch orchestration layer around them (cache by code_insee, "latest click wins" via a request counter). `public/index.html` gains a `#map-container` wrapper so `#panel` can become a real flex sidebar; `public/style.css` gets the sidebar/bottom-sheet styling. `public/map.js` wires the existing click handler to the new module.

**Tech Stack:** Same as sub-project 1 — vanilla JS ES modules, no bundler, no framework; MapLibre GL JS (unchanged); `node` for sanity-checking pure functions, manual browser verification for DOM/fetch behavior.

## Global Constraints

- Commune name comes from `feature.properties.nom` on the already-loaded geojson (verified present on the real, pinned geometry file) — never fetched, never invented.
- Fiche fetch URL: `./data/communes/{code_insee}.json` (relative, same-origin), fetched lazily on click only, never preloaded.
- Cache fetched fiches in memory (module-scope `Map`, keyed by `code_insee`) — a second click on the same commune in the same session does not refetch.
- "Latest click wins": if a click on commune B arrives before commune A's fetch resolves, A's late response must not overwrite B's panel content. Implemented via an incrementing request counter, not `AbortController` (simpler, sufficient here).
- Any text sourced from the third-party geojson (`feature.properties.nom`) must be HTML-escaped before reaching `innerHTML` — text originating in our own pipeline (recommendation copy, commune codes) does not need this (same trust boundary already established in sub-project 1's final review).
- No `classe`/`historique`/`indicateurs_cles`/`nom`/`departement`/`population` fields exist in `public/data/communes/{code}.json` — do not assume them. A domain score (`boisson.score` or `cosmetique.score`) can be `null` even when `statut_donnees == "complet"`.
- No JS test framework introduced. Pure functions (no `document` access) are sanity-checked via `node --input-type=module -e`, exactly as `public/scoring.js`/`public/geo_join.js` were in sub-project 1. DOM/fetch code is verified manually via local HTTP server + browser.
- Repeat of a real bug from sub-project 1: any CSS rule that sets `display` unconditionally on an element also toggled via the `hidden` attribute will silently defeat that attribute (specificity beats the UA `[hidden]{display:none}` rule). Every such rule in this plan uses the `:not([hidden])` pattern instead.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `public/panel.js` | Create | Pure HTML-building functions (Task 1) + DOM/fetch orchestration, cache, latest-click-wins (Task 2) |
| `public/index.html` | Modify | Wrap map elements in `#map-container`; give `#panel` real content structure + close button |
| `public/style.css` | Modify | `#map-container`/`#panel` flex sidebar (desktop) and fixed bottom sheet (mobile), jauge/reco styling |
| `public/map.js` | Modify | `onClicCommune` calls `panel.js` instead of `console.log`; `initCarte()` calls `initPanel()` |

---

### Task 1: `public/panel.js` — pure rendering functions

**Files:**
- Create: `public/panel.js`

**Interfaces:**
- Consumes: `classeFromScore` from `public/scoring.js` (`{classe, couleur, libelle}` for a score, or `NO_DATA`-shaped object for `null`).
- Produces: `echapperHtml(texte: string) -> string`, `jaugeHtml(titre: string, score: number | null, sousScores: object, vetoSanitaire: boolean) -> string`, `recommandationsHtml(recommandations: Array<{usage, type, titre, description, estimation_cout?}>) -> string`. Used internally by Task 2's DOM layer in this same file — not exported beyond this module, but written first and tested standalone since they touch no `document` API.

- [ ] **Step 1: Write `public/panel.js` with the three pure functions**

```js
import { classeFromScore } from './scoring.js';

export function echapperHtml(texte) {
  return String(texte)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function jaugeHtml(titre, score, sousScores, vetoSanitaire) {
  if (score == null) {
    return `<div class="jauge"><h3>${titre}</h3><p class="jauge-indispo">Données insuffisantes</p></div>`;
  }
  const c = classeFromScore(score);
  const alerte = vetoSanitaire ? '<p class="jauge-veto">⚠ Alerte sanitaire</p>' : '';
  const lignes = Object.entries(sousScores || {})
    .map(([cle, valeur]) => `<div class="sous-score-row"><span>${cle}</span><span>${valeur == null ? '—' : valeur}</span></div>`)
    .join('');
  return `
    <div class="jauge">
      <h3>${titre}</h3>
      <div class="jauge-score" style="color:${c.couleur}">${score} — ${c.classe} (${c.libelle})</div>
      ${alerte}
      <div class="sous-scores">${lignes}</div>
    </div>`;
}

function sectionRecommandations(titre, items) {
  if (!items || items.length === 0) return '';
  const html = items.map((r) => {
    const cout = r.estimation_cout
      ? `<p class="reco-cout">${r.estimation_cout.materiel} — ${r.estimation_cout.achat_eur} € (entretien : ${r.estimation_cout.entretien_annuel_eur})</p>`
      : '';
    return `<div class="reco"><strong>${r.titre}</strong><p>${r.description}</p>${cout}</div>`;
  }).join('');
  return `<h4>${titre}</h4>${html}`;
}

export function recommandationsHtml(recommandations) {
  if (!recommandations || recommandations.length === 0) return '';
  const parUsage = { boisson: [], cosmetique: [] };
  for (const r of recommandations) {
    (parUsage[r.usage] || (parUsage[r.usage] = [])).push(r);
  }
  return `<h3>Recommandations</h3>${sectionRecommandations('🥤 Boisson & Santé', parUsage.boisson)}${sectionRecommandations('🧴 Cosmétique & Lavage', parUsage.cosmetique)}`;
}
```

- [ ] **Step 2: Sanity-check with `node`**

Run (from the repo root):
```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
node --input-type=module -e "
import { echapperHtml, jaugeHtml, recommandationsHtml } from './public/panel.js';

console.log(echapperHtml('<script>alert(1)</script>'));
console.log(jaugeHtml('Boisson', 90, { securite_sanitaire: 95 }, false).includes('90 — A'));
console.log(jaugeHtml('Boisson', null, {}, false).includes('Données insuffisantes'));
console.log(jaugeHtml('Boisson', 11, {}, true).includes('Alerte sanitaire'));
console.log(recommandationsHtml([{ usage: 'boisson', type: 'carafe', titre: 'Titre test', description: 'Desc test' }]).includes('Titre test'));
console.log(recommandationsHtml([]));
"
```
Expected:
```
&lt;script&gt;alert(1)&lt;/script&gt;
true
true
true
true

```
(the last line is an empty string — `recommandationsHtml([])` returns `''`)

- [ ] **Step 3: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/panel.js
git commit -m "feat: add pure HTML-rendering functions for the commune panel"
```

---

### Task 2: `public/panel.js` — cache, latest-click-wins fetch, DOM orchestration

**Files:**
- Modify: `public/panel.js` (append to the file from Task 1 — do not remove or change the Task 1 functions)

**Interfaces:**
- Consumes: `jaugeHtml`, `recommandationsHtml`, `echapperHtml` (Task 1, same file); DOM ids `panel`, `panel-content`, `panel-close` (Task 3, not yet created at this point in the plan — this task's manual verification therefore requires Task 3's HTML to exist; see note in Step 4).
- Produces: `afficherCommune(codeInsee: string, nom: string) -> Promise<void>`, `initPanel() -> void`. Used by `public/map.js` (Task 4).

- [ ] **Step 1: Append the DOM/fetch layer to `public/panel.js`**

```js
const cacheFiches = new Map();
let requeteActuelle = 0;

function fermerPanneau() {
  document.getElementById('panel').hidden = true;
}

function ouvrirPanneau() {
  document.getElementById('panel').hidden = false;
}

function rendreFiche(nom, codeInsee, fiche) {
  const contenu = document.getElementById('panel-content');
  if (fiche.statut_donnees === 'indisponible') {
    contenu.innerHTML = `<h2>${echapperHtml(nom)}</h2><p class="panel-code">${codeInsee}</p><p class="panel-indispo">Aucune donnée disponible pour cette commune.</p>`;
    return;
  }
  contenu.innerHTML = `
    <h2>${echapperHtml(nom)}</h2>
    <p class="panel-code">${codeInsee}</p>
    ${jaugeHtml('🥤 Boisson & Santé', fiche.scores.boisson.score, fiche.scores.boisson.sous_scores, fiche.scores.boisson.veto_sanitaire)}
    ${jaugeHtml('🧴 Cosmétique & Lavage', fiche.scores.cosmetique.score, fiche.scores.cosmetique.sous_scores, false)}
    ${recommandationsHtml(fiche.recommandations)}
  `;
}

function afficherErreurPanneau(nom) {
  document.getElementById('panel-content').innerHTML =
    `<h2>${echapperHtml(nom)}</h2><p class="panel-erreur">Impossible de charger les données de cette commune. Réessayez plus tard.</p>`;
}

export async function afficherCommune(codeInsee, nom) {
  ouvrirPanneau();
  requeteActuelle += 1;
  const monNumero = requeteActuelle;
  document.getElementById('panel-content').innerHTML = `<h2>${echapperHtml(nom)}</h2><p class="panel-chargement">Chargement…</p>`;

  if (cacheFiches.has(codeInsee)) {
    rendreFiche(nom, codeInsee, cacheFiches.get(codeInsee));
    return;
  }

  try {
    const reponse = await fetch(`./data/communes/${codeInsee}.json`);
    if (!reponse.ok) {
      throw new Error(`HTTP ${reponse.status}`);
    }
    const fiche = await reponse.json();
    if (monNumero !== requeteActuelle) return;
    cacheFiches.set(codeInsee, fiche);
    rendreFiche(nom, codeInsee, fiche);
  } catch (erreur) {
    if (monNumero !== requeteActuelle) return;
    console.error(erreur);
    afficherErreurPanneau(nom);
  }
}

export function initPanel() {
  document.getElementById('panel-close').addEventListener('click', fermerPanneau);
}
```

- [ ] **Step 2: Syntax-check with `node`**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
grep -v "^import " public/panel.js > /tmp/panel_no_imports.js
node --check /tmp/panel_no_imports.js
```
Expected: no output (syntax OK). This only checks syntax — the DOM-touching functions cannot run under plain `node` (no `document` global) and are verified manually in Task 5, once Tasks 3-4 give them a real page to run on.

- [ ] **Step 3: Find one real "indisponible" commune code for later manual testing**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
python -c "
import json, os
for nom in os.listdir('public/data/communes'):
    with open(os.path.join('public/data/communes', nom), encoding='utf-8') as f:
        if json.load(f)['statut_donnees'] == 'indisponible':
            print(nom.removesuffix('.json'))
            break
"
```
Expected: prints one 5-digit INSEE code. **Write this code down** — it is needed in Task 5's manual verification checklist (this plan cannot hardcode it since it depends on the current data snapshot).

- [ ] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/panel.js
git commit -m "feat: add cache, latest-click-wins fetch, and DOM rendering to panel.js"
```

(No manual browser verification yet — `#panel-content`/`#panel-close` don't exist in `index.html` until Task 3, and nothing calls `afficherCommune` until Task 4. This task's deliverable is code-complete and syntax-checked; end-to-end behavior is verified in Task 5.)

---

### Task 3: `public/index.html` + `public/style.css` — sidebar / bottom-sheet layout

**Files:**
- Modify: `public/index.html`
- Modify: `public/style.css`

**Interfaces:**
- Consumes: nothing new.
- Produces: DOM ids `map-container` (wraps `map`/`map-error`/`legend`, unchanged behavior), `panel-content`, `panel-close` — consumed by `public/panel.js` (Task 2, already written but not yet exercisable) and this task's own manual verification (layout only, no data yet).

- [ ] **Step 1: Restructure `public/index.html`'s `<main>`**

In `public/index.html`, replace:
```html
    <main>
      <div id="map"></div>
      <div id="map-error" hidden>Impossible de charger la carte. Réessayez plus tard.</div>
      <div id="legend"></div>
      <aside id="panel"></aside>
    </main>
```
with:
```html
    <main>
      <div id="map-container">
        <div id="map"></div>
        <div id="map-error" hidden>Impossible de charger la carte. Réessayez plus tard.</div>
        <div id="legend"></div>
      </div>
      <aside id="panel" hidden>
        <button id="panel-close" type="button" aria-label="Fermer la fiche">✕</button>
        <div id="panel-content"></div>
      </aside>
    </main>
```

- [ ] **Step 2: Update `public/style.css`**

Replace:
```css
main { position: relative; flex: 1; }
#map { position: absolute; inset: 0; background: #e8eef2; }
```
with:
```css
main { position: relative; flex: 1; display: flex; }
#map-container { position: relative; flex: 1; min-width: 0; }
#map { position: absolute; inset: 0; background: #e8eef2; }
```

Replace:
```css
#panel { display: none; }
```
with:
```css
#panel {
  position: relative; width: 380px; flex-shrink: 0; background: #fff; overflow-y: auto;
  border-left: 1px solid #ddd; padding: 16px 16px 32px;
}
/* Même piège de spécificité que #map-error (sous-projet 1, commit 825af745) :
   ne jamais mettre display:block/flex sans le conditionner à :not([hidden]),
   sous peine de rendre l'attribut hidden inopérant. */
#panel:not([hidden]) { display: block; }

#panel-close {
  position: absolute; top: 8px; right: 8px; border: none; background: transparent;
  font-size: 1.1rem; cursor: pointer; line-height: 1;
}

.jauge { margin-bottom: 16px; }
.jauge h3 { margin: 0 0 4px; font-size: 0.95rem; }
.jauge-score { font-size: 1.3rem; font-weight: 700; }
.jauge-veto { color: #c0392b; font-weight: 600; margin: 4px 0; }
.jauge-indispo { color: #777; font-style: italic; }
.sous-score-row { display: flex; justify-content: space-between; font-size: 0.85rem; padding: 2px 0; }
.reco { margin-bottom: 10px; font-size: 0.85rem; }
.reco-cout { color: #555; font-size: 0.8rem; margin: 2px 0 0; }
.panel-code { color: #777; font-size: 0.8rem; margin: -8px 0 12px; }
.panel-indispo, .panel-erreur, .panel-chargement { color: #555; }
```

Replace the `@media (max-width: 600px)` block:
```css
@media (max-width: 600px) {
  #app-header { padding: 8px 12px; }
  #app-header h1 { font-size: 1rem; width: 100%; }
  #legend { left: 8px; bottom: 8px; font-size: 0.72rem; padding: 8px 10px; }
}
```
with:
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

- [ ] **Step 3: Manual verification (layout only, no data)**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000`. Expected: the map still fills the screen exactly as before (visually unchanged — `#map-container` is a transparent wrapper), no `#panel` visible (still `hidden`). Using the browser devtools, remove the `hidden` attribute from `#panel` (`document.getElementById('panel').hidden = false` in the console) — expected: a white sidebar ~380px wide appears on the right with a "✕" button top-right, the map area shrinks to fill the remaining space (MapLibre auto-resizes via its built-in `ResizeObserver`, no code needed). Resize the browser window below 600px wide — expected: the sidebar becomes a bottom sheet instead (fixed to the bottom, rounded top corners, doesn't extend past ~70% of the viewport height). Stop the server when done.

- [ ] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/index.html public/style.css
git commit -m "feat: add commune panel layout (desktop sidebar, mobile bottom sheet)"
```

---

### Task 4: `public/map.js` — wire the click handler to the panel

**Files:**
- Modify: `public/map.js`

**Interfaces:**
- Consumes: `resolveCodeInsee` from `public/geo_join.js` (already exported, not yet imported by `map.js`); `afficherCommune`, `initPanel` from `public/panel.js` (Task 2).
- Produces: nothing new for later tasks — this is the final wiring point.

- [ ] **Step 1: Update imports**

In `public/map.js`, replace:
```js
import { NO_DATA, SCORE_THRESHOLDS } from './scoring.js';
import { joindreScoresSurGeojson } from './geo_join.js';
```
with:
```js
import { NO_DATA, SCORE_THRESHOLDS } from './scoring.js';
import { joindreScoresSurGeojson, resolveCodeInsee } from './geo_join.js';
import { afficherCommune, initPanel } from './panel.js';
```

- [ ] **Step 2: Replace the `onClicCommune` stub**

Replace:
```js
function onClicCommune(event) {
  const feature = event.features[0];
  // Stub : la fiche communale au clic est un sous-projet futur, non
  // implémenté ici.
  console.log('Commune cliquée (fiche à venir) :', feature.properties.code);
}
```
with:
```js
function onClicCommune(event) {
  const feature = event.features[0];
  const code = resolveCodeInsee(feature.properties.code);
  afficherCommune(code, feature.properties.nom);
}
```

- [ ] **Step 3: Call `initPanel()` from `initCarte()`**

Replace:
```js
function initCarte() {
  renderLegend();
  initBascule();
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);
```
with:
```js
function initCarte() {
  renderLegend();
  initBascule();
  initPanel();
  joindreScoresSurGeojson(geojson, carteScores, indicateurActif);
```

- [ ] **Step 4: Syntax-check with `node`**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
grep -v "^import " public/map.js > /tmp/map_no_imports.js
node --check /tmp/map_no_imports.js
```
Expected: no output (syntax OK).

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/map.js
git commit -m "feat: wire commune click to the fiche panel"
```

(Full manual verification of the click-to-fiche flow happens in Task 5, together with the rest of the checklist.)

---

### Task 5: Final end-to-end verification

**This task is not a code task** — it walks through the full manual checklist from the design spec (`docs/superpowers/specs/2026-08-06-fiche-communale-design.md`) against the finished feature.

- [ ] **Step 1: Full manual walkthrough**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000` and confirm every item:
- Click any commune with real data (e.g. zoom into any green/red area and click) — the sidebar opens, shows "Chargement…" briefly, then the commune name (from the geojson, correctly capitalized/accented), both Boisson and Cosmétique jauges with their scores and sub-scores, and any recommendations grouped under the right usage heading.
- Click Paris, Lyon, or Marseille (any arrondissement) — the fiche shown is for the parent commune (75056/69123/13055's data), confirming `resolveCodeInsee` is applied before fetching (cross-check: the displayed score should match what was already visually confirmed for that city in sub-project 1's verification).
- Click a commune with `veto_sanitaire: true` on its Boisson score (Paris, from sub-project 1's testing, is such a commune) — the "⚠ Alerte sanitaire" line appears under the Boisson jauge.
- Click the "indisponible" commune found in Task 2 Step 3 — the panel shows "Aucune donnée disponible pour cette commune." and no jauges.
- Click two different communes in quick succession (before the first has finished loading) — the panel ends up showing the SECOND commune's data, never a mix or the first commune's stale data. (Simulate slow network via DevTools throttling if clicks resolve too fast to observe naturally.)
- Click the same commune twice — the second click renders instantly (no visible "Chargement…" flash), confirming the cache is used.
- Block the `data/communes/*.json` request (DevTools request-blocking) and click a commune — the panel shows "Impossible de charger les données de cette commune. Réessayez plus tard." with the commune name still shown (known from the geojson, not the failed fetch). Restore normal network after.
- Click the "✕" close button — the panel closes (sidebar disappears / bottom sheet slides away), map returns to full width.
- Reopen a different commune after closing — content replaces cleanly, no stacking or leftover previous content.
- Narrow the viewport below 600px and repeat the click flow — the panel appears as a bottom sheet, is scrollable if content overflows, and the close button works there too.
- Browser console free of errors throughout.

Stop the server (Ctrl+C) when done. If any check fails, fix it as part of this task before proceeding.

- [ ] **Step 2: Report**

Confirm to the user that the fiche communale sub-project (Phase 2, 2/5) is complete and working end-to-end, with a summary of what was verified in Step 1, before moving on to the next sub-project (recherche + géolocalisation).
