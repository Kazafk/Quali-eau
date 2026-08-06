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
