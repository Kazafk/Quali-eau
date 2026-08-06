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
