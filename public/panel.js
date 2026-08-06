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
