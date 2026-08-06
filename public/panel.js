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
