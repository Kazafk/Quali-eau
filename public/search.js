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
