# Page Méthodologie — Design (Phase 2, sous-projet 5/5)

## Contexte

Sous-projets 1-4 mergés sur `master` : le site fonctionne et est déployé (carte nationale, fiche communale, recherche + géolocalisation, CI GitHub Pages). C'est le dernier item de la roadmap `SPECIFICATION.md` §8 Phase 2 — après ce sous-projet, la Phase 2 est complète.

Le `README.md` documente déjà en détail le système de scoring (formules complètes, veto sanitaire, indice SCA café/thé, recommandations budgétaires) mais ce contenu n'est visible qu'aux développeurs consultant le dépôt GitHub, pas aux visiteurs du site public.

## Objectif

Une page statique `public/methodologie.html`, accessible depuis un lien dans le header du site, expliquant de façon complète (formules incluses) comment les scores affichés sur la carte et dans les fiches communales sont calculés.

## Structure

- `public/methodologie.html` : page autonome, réutilise `public/style.css` (même header/identité visuelle que le reste du site). Pas de JavaScript propre à cette page — contenu purement statique.
- `public/index.html` : ajout d'un lien "ℹ️ Méthodologie" dans le header, à côté des boutons de bascule.
- `public/methodologie.html` inclut un lien retour vers la carte (`index.html`).

## Contenu

Repris du README (formules complètes, seuils inclus), reformaté en HTML sémantique — **sans dépendance de rendu mathématique** (pas de MathJax/KaTeX, cohérent avec l'absence de dépendances JS supplémentaires du reste du projet) : les formules LaTeX du README (`$$S_{\text{boisson}} = 0{,}55 \cdot S_{\text{securite}} + ...$$`) sont converties en notation texte simple avec indices via `<sub>` (ex. « S<sub>boisson</sub> = 0,55 × S<sub>sécurité</sub> + 0,25 × S<sub>minéraux</sub> + 0,20 × S<sub>goût</sub> »).

Sections incluses, dans cet ordre :
1. **Vision & objectifs** — bandeau d'intro (adapté du README §Vision).
2. **Système de scoring dual A-E** — barème des 5 classes (tableau des seuils, déjà dans `public/scoring.js` côté JS, dupliqué ici en texte statique) ; formule complète Boisson & Santé avec ses 3 sous-scores détaillés ; le veto sanitaire et ses 5 conditions déclencheuses ; formule complète Cosmétique & Lavage avec ses 4 sous-scores détaillés ; l'indice café/thé SCA (4 critères).
3. **Recommandations & estimation budgétaire** — les paliers déjà documentés (dureté/calcaire, polluants chimiques).
4. **Mentions légales & licence** — sources (data.gouv.fr, Hub'eau), licence Etalab, avertissement réglementaire (repris tel quel du README, c'est un texte juridique, pas à reformuler).

**Exclu délibérément** (contenu développeur, hors sujet pour un visiteur du site) : architecture technique, structure du dépôt, guide de démarrage/installation, section tests.

## Cas limites

Aucun — page statique sans état, sans fetch, sans dépendance aux données JSON. Le seul risque est une désynchronisation future entre cette page et `public/scoring.js`/`pipeline/scoring.py` si les seuils ou formules changent sans que la page méthodologie soit mise à jour ; hors scope de ce sous-projet (pas de mécanisme de synchronisation automatique demandé).

## Tests

Vérification manuelle : la page se charge en local, le lien header y mène et inversement, contenu lisible et correctement formaté (formules, tableau des seuils, listes), layout mobile cohérent avec le reste du site.

## Hors scope

- Rendu mathématique via une librairie tierce.
- Synchronisation automatique entre cette page et les seuils réels du code.
- Mise à jour des sections développeur du README (hors périmètre de ce sous-projet).
