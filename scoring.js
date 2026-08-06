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
