import { NO_DATA, SCORE_THRESHOLDS } from './scoring.js';
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

function initCarte() {
  renderLegend();
  initBascule();
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
