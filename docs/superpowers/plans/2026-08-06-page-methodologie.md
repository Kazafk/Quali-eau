# Page Méthodologie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone `public/methodologie.html` page explaining the full scoring methodology (formulas, sanitary veto, SCA coffee/tea index, recommendation cost tiers, legal notices), reachable from a header link on the main site.

**Architecture:** A fully static page, no JavaScript, styled via the existing shared `public/style.css`. The content is a direct, faithful transcription of `README.md`'s scoring/recommendations/legal sections into semantic HTML, with LaTeX formulas converted to plain text with `<sub>` subscripts (no math-rendering library — consistent with the project's zero-extra-dependency front-end).

**Tech Stack:** Same as the rest of `public/` — plain HTML + the existing `public/style.css`. No new JS files, no build step.

## Global Constraints

- No math-rendering library (MathJax/KaTeX) — formulas are plain text with `<sub>` for subscripts, e.g. `S<sub>boisson</sub> = 0,55 × S<sub>sécurité</sub> + ...`.
- Content is a faithful transcription of `README.md`'s §Vision & Objectifs (intro only), §Système de Scoring Dual (both usages, full formulas, veto sanitaire, SCA index), §Recommandations & Estimation Budgétaire, §Mentions Légales & Licence — verbatim values (percentages, thresholds, prices) copied exactly, not paraphrased or recalculated.
- Developer-facing README sections (Architecture Technique, Structure du Dépôt, Guide de Démarrage, Tests) are explicitly OUT of scope — do not include them.
- The page reuses `public/style.css` (same `<link>`, same `#app`/`#app-header` shell) for visual consistency with the rest of the site — no separate stylesheet.
- No fetch, no state, no interactivity — a pure static document.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `public/index.html` | Modify | Header link to the new page |
| `public/style.css` | Modify | Nav-link styling (Task 1) + article/table/content styling for the methodology page (Task 2) |
| `public/methodologie.html` | Create | The methodology page itself |

---

### Task 1: Header link to the methodology page

**Files:**
- Modify: `public/index.html`
- Modify: `public/style.css`

**Interfaces:**
- Consumes: nothing new.
- Produces: a reachable link to `methodologie.html` from the main site's header. `public/methodologie.html` (Task 2) must exist at that exact relative path for this link to resolve — Task 3 verifies the full round trip.

- [x] **Step 1: Add the link to `public/index.html`**

Replace:
```html
    <header id="app-header">
      <h1>💧 Quali'eau</h1>
      <div id="recherche">
```
with:
```html
    <header id="app-header">
      <h1>💧 Quali'eau</h1>
      <a id="lien-methodologie" href="methodologie.html">ℹ️ Méthodologie</a>
      <div id="recherche">
```

- [x] **Step 2: Style the link in `public/style.css`**

Replace:
```css
#toggle-indicateur { display: flex; gap: 4px; flex-wrap: wrap; }
```
with:
```css
#lien-methodologie {
  color: #fff; font-size: 0.85rem; text-decoration: none; white-space: nowrap;
  border: 1px solid rgba(255, 255, 255, 0.4); border-radius: 6px; padding: 6px 10px;
}
#lien-methodologie:hover { background: rgba(255, 255, 255, 0.15); }

#toggle-indicateur { display: flex; gap: 4px; flex-wrap: wrap; }
```

- [x] **Step 3: Structural verification**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
In another terminal: `curl -s http://localhost:8000/ | grep 'lien-methodologie'` — expect the `<a id="lien-methodologie" href="methodologie.html">` line to appear. Stop the server when done. (The link will 404 until Task 2 creates the target page — that's expected at this point in the plan.)

- [x] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/index.html public/style.css
git commit -m "feat: add header link to the methodology page"
```

---

### Task 2: `public/methodologie.html` — the page itself

**Files:**
- Create: `public/methodologie.html`
- Modify: `public/style.css`

**Interfaces:**
- Consumes: `public/style.css` (shared stylesheet, `#app`/`#app-header` shell already styled by Task 1 and earlier sub-projects).
- Produces: the reachable target of Task 1's header link. Contains its own link back to `index.html`.

- [x] **Step 1: Write `public/methodologie.html`**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Méthodologie — Quali'eau</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="app">
    <header id="app-header">
      <h1>💧 Quali'eau</h1>
      <a id="lien-retour" href="index.html">← Retour à la carte</a>
    </header>
    <main id="methodologie">
      <article>
        <h2>Vision &amp; objectifs</h2>
        <p>En France, l'eau du robinet est l'aliment le plus surveillé, mais les données brutes d'analyses sanitaires restent complexes et éparpillées. Quali'eau traduit automatiquement ces millions de mesures brutes en indicateurs simples et actionnables, sous la forme d'un double score (Nutri-Score A à E) adapté à deux usages de la vie quotidienne : Boisson &amp; Santé et Cosmétique &amp; Lavage.</p>

        <h2>Système de scoring dual (A à E)</h2>
        <p>Les deux scores sont exprimés sur une échelle de 0 à 100 avec attribution d'une lettre de A à E :</p>
        <table>
          <thead>
            <tr><th>Score global</th><th>Classe</th><th>Niveau d'appréciation</th></tr>
          </thead>
          <tbody>
            <tr><td>80 – 100</td><td>A</td><td>Parfait — Qualité optimale pour cet usage</td></tr>
            <tr><td>60 – 79</td><td>B</td><td>Bon — Très bonne qualité générale</td></tr>
            <tr><td>40 – 59</td><td>C</td><td>Moyen — Qualité passable, légers désagréments</td></tr>
            <tr><td>20 – 39</td><td>D</td><td>Passable — Inconfort marqué ou paramètres dégradés</td></tr>
            <tr><td>0 – 19</td><td>E</td><td>Critique — Risque sanitaire ou inconfort fort</td></tr>
          </tbody>
        </table>

        <h3>🥤 Usage 1 : Boisson &amp; Santé</h3>
        <p><strong>Formule globale :</strong><br>
        S<sub>boisson</sub> = 0,55 × S<sub>sécurité</sub> + 0,25 × S<sub>minéraux</sub> + 0,20 × S<sub>goût</sub></p>

        <h4>🛡️ Veto sanitaire (facteur limitant)</h4>
        <p>En cas de dépassement sanitaire grave, le score global est immédiatement plafonné :<br>
        S<sub>boisson</sub> = min(S<sub>boisson</sub>, S<sub>sécurité</sub>)</p>
        <p>Sont concernés par le veto :</p>
        <ul>
          <li>Non-conformité bactériologique active (ex. <em>E. coli</em>, Entérocoques)</li>
          <li>Nitrates &gt; 50 mg/L ou Nitrites &gt; 0,1 mg/L</li>
          <li>Métaux lourds hors normes (Plomb &gt; 10 µg/L, Arsenic &gt; 10 µg/L, Cadmium &gt; 5 µg/L)</li>
          <li>Dépassement de pesticides (molécule individuelle &gt; 0,1 µg/L ou total &gt; 0,5 µg/L)</li>
          <li>Dépassement de PFAS (somme des 20 PFAS &gt; 0,1 µg/L)</li>
        </ul>

        <h4>Composition des sous-scores Boisson</h4>
        <ol>
          <li><strong>Sécurité sanitaire</strong> (S<sub>sécurité</sub>) : S<sub>sécurité</sub> = min(P<sub>bact</sub>, P<sub>pest</sub>, P<sub>pfas</sub>, P<sub>métaux</sub>, P<sub>nitrates</sub>)</li>
          <li><strong>Minéraux &amp; équilibre</strong> (S<sub>minéraux</sub>) : S<sub>minéraux</sub> = 0,70 × N<sub>nitrates</sub> + 0,15 × N<sub>chlorures</sub> + 0,15 × N<sub>sulfates</sub></li>
          <li><strong>Profil gustatif</strong> (S<sub>goût</sub>) : S<sub>goût</sub> = 0,60 × N<sub>chlore</sub> + 0,40 × N<sub>turbidité</sub></li>
        </ol>

        <h3>🧴 Usage 2 : Cosmétique, peau &amp; lavage</h3>
        <p><strong>Formule globale :</strong><br>
        S<sub>cosmétique</sub> = 0,45 × S<sub>dureté</sub> + 0,25 × S<sub>chlore</sub> + 0,15 × S<sub>pH</sub> + 0,15 × S<sub>métaux_dépôts</sub></p>

        <h4>Composition des sous-scores Cosmétique</h4>
        <ol>
          <li>
            <strong>Dureté &amp; calcaire</strong> (S<sub>dureté</sub>) : basé sur le Titre Hydrotimétrique (TH en °fH).
            <ul>
              <li>3 à 8 °fH : idéal pour la peau (score 90–100)</li>
              <li>15 à 25 °fH : eau moyennement dure (score 75–100)</li>
              <li>&gt; 35 °fH : eau très dure (dessèchement cutané, tartre, surconsommation de savon)</li>
            </ul>
          </li>
          <li><strong>Chlore &amp; agressivité</strong> (S<sub>chlore</sub>) : évaluation de l'évaporation du chlore sous la douche et de l'oxydation de la kératine/film hydrolipidique.</li>
          <li><strong>Respect cutané</strong> (S<sub>pH</sub>) : adéquation avec le pH physiologique de la peau (~4,7–5,5). Plage idéale de l'eau : 6,8–7,4.</li>
          <li><strong>Métaux &amp; dépôts</strong> (S<sub>métaux_dépôts</sub>) : S<sub>métaux_dépôts</sub> = min(N<sub>Cu</sub>, N<sub>Fe</sub>, N<sub>Mn</sub>)</li>
        </ol>

        <h3>☕ Indice spécialisé café / thé (SCA Standard)</h3>
        <p>En complément, Quali'eau fournit un Coffee &amp; Tea Index calculé selon les standards de la Specialty Coffee Association :</p>
        <ul>
          <li><strong>TDS estimé</strong> : cible ~150 mg/L (0,65 × conductivité)</li>
          <li><strong>Dureté calcique (GH)</strong> : cible ~68 mg/L CaCO₃ (~6,8 °fH)</li>
          <li><strong>Alcalinité totale (TAC / KH)</strong> : cible ~40 mg/L CaCO₃ (~4,0 °fH)</li>
          <li><strong>Chlore total</strong> : cible 0 mg/L</li>
        </ul>

        <h2>💡 Recommandations &amp; estimation budgétaire</h2>
        <p>Pour chaque problème détecté (eau calcaire, chlore, polluants), des recommandations personnalisées et impartiales sont générées avec une estimation budgétaire par palier technologique (CAPEX/OPEX) :</p>

        <h3>Dureté &amp; calcaire (adoucisseurs / douche)</h3>
        <ul>
          <li><strong>15–25 °fH</strong> : adoucisseur standard 10–15 L (~700 € – 900 € | ~15 €/an)</li>
          <li><strong>25–40 °fH</strong> : adoucisseur renforcé 20–25 L (~1 200 € – 1 600 € | ~50 € – 70 €/an)</li>
          <li><strong>&gt; 40 °fH</strong> : adoucisseur haute capacité &gt; 25 L (~1 600 € – 2 000 € | ~70 € – 100 €/an)</li>
        </ul>

        <h3>Polluants chimiques (filtration eau de boisson)</h3>
        <ul>
          <li><strong>Dépassement modéré</strong> : filtre sous-évier à charbon actif (~80 € – 120 € | ~30 €/an)</li>
          <li><strong>Dépassement élevé</strong> : osmoseur inverse 3 étages (~200 € – 300 € | ~60 €/an)</li>
          <li><strong>Dépassement extrême (veto)</strong> : osmoseur à pompe de perméat + reminéralisation (~450 € – 700 € | ~90 €/an)</li>
        </ul>

        <h2>⚖️ Mentions légales &amp; licence</h2>
        <ul>
          <li><strong>Source des données</strong> : Ministère de la Santé / ARS via <a href="https://www.data.gouv.fr/fr/datasets/resultats-du-controle-sanitaire-de-leau-distribuee-commune-par-commune/" target="_blank" rel="noopener">data.gouv.fr</a> &amp; API <a href="https://hubeau.eaufrance.fr/" target="_blank" rel="noopener">Hub'eau</a>.</li>
          <li><strong>Licence des données</strong> : Licence Ouverte / Open Licence (Etalab).</li>
          <li><strong>Avertissement</strong> : Quali'eau est un outil d'information et d'évaluation indépendant. Seules les consignes et bulletins officiels émis par la Préfecture et l'ARS font foi sur le plan sanitaire réglementaire.</li>
        </ul>
      </article>
    </main>
  </div>
</body>
</html>
```

- [x] **Step 2: Add content styling to `public/style.css`**

Append at the end of the file (after the existing `@media (max-width: 600px) { ... }` block):

```css
#methodologie { overflow-y: auto; padding: 24px 16px 48px; }
#methodologie article { max-width: 720px; margin: 0 auto; line-height: 1.6; color: #222; }
#methodologie h2 { margin-top: 2rem; color: #0b3d5c; }
#methodologie h2:first-child { margin-top: 0; }
#methodologie h3 { margin-top: 1.5rem; }
#methodologie h4 { margin-top: 1rem; }
#methodologie table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
#methodologie th, #methodologie td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
#methodologie ul, #methodologie ol { padding-left: 1.4rem; }
#methodologie ul ul { margin-top: 0.3rem; }

#lien-retour {
  color: #fff; font-size: 0.85rem; text-decoration: none; white-space: nowrap;
  border: 1px solid rgba(255, 255, 255, 0.4); border-radius: 6px; padding: 6px 10px;
}
#lien-retour:hover { background: rgba(255, 255, 255, 0.15); }
```

- [x] **Step 3: Structural verification**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
In another terminal: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/methodologie.html` — expect `200`. `curl -s http://localhost:8000/methodologie.html | grep -c '<h2>'` — expect `4` (Vision, Système de scoring, Recommandations, Mentions légales). `curl -s http://localhost:8000/methodologie.html | grep 'lien-retour'` — expect the back-link to `index.html`. Stop the server when done. The controller performs the real visual verification after this task (Task 3).

- [x] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale"
git add public/methodologie.html public/style.css
git commit -m "feat: add the methodology page content"
```

---

### Task 3: Final end-to-end verification

**This task is not a code task** — it walks through the full manual checklist from the design spec (`docs/superpowers/specs/2026-08-06-page-methodologie-design.md`) against the finished feature.

- [x] **Step 1: Full manual walkthrough**

```bash
cd "C:/Repos/Quali'eau/.claude/worktrees/phase2-carte-nationale/public"
python -m http.server 8000
```
Open `http://localhost:8000` and confirm every item:
- The "ℹ️ Méthodologie" link is visible in the header, styled consistently with the rest of the dark header (not a raw blue underlined link).
- Clicking it navigates to `methodologie.html` — page loads, header shows "💧 Quali'eau" and a "← Retour à la carte" link, content is readable (centered column, not full-bleed edge-to-edge text), the A-E threshold table renders as an actual table (borders, aligned columns), formulas display correctly with subscripts (e.g. "S" with a smaller "boisson" below the line, not literal underscores or braces).
- All four sections present in order: Vision, Système de scoring dual (both usages + veto + SCA index), Recommandations, Mentions légales.
- No developer-only content (no architecture diagrams, no repo structure, no install instructions).
- Clicking "← Retour à la carte" navigates back to `index.html` and the map/app still works normally (not just a dead link).
- Narrow the viewport below 600px — content remains readable, no horizontal overflow, header wraps sensibly (reuses the existing `flex-wrap` already on `#app-header`).
- Browser console free of errors on both pages.

Stop the server (Ctrl+C) when done. If any check fails, fix it as part of this task before proceeding.

- [x] **Step 2: Report**

Confirm to the user that the page méthodologie sub-project (Phase 2, 5/5, the last one) is complete and working end-to-end, with a summary of what was verified in Step 1. Phase 2 is now fully complete.
