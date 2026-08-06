# Diagnostic Transparent — Design (Phase 3, item 1/3)

## Contexte

Source : `diagnostic_composition_eau.md` (note de conception fournie par l'utilisateur). Constat : les fiches communales actuelles n'exposent que des scores synthétiques (`11/100 — E`) sans expliquer *pourquoi*. Ce sous-projet enrichit le pipeline et la fiche panneau pour rendre chaque score décomposable et justifié.

Décision utilisateur : la fiche liste **systématiquement tous les paramètres suivis** (pas seulement ceux en anomalie).

**Précision de portée (pour lever l'ambiguïté du "tous")** : "tous les paramètres suivis" désigne tous les paramètres qui alimentent réellement un sous-score existant (19 entrées, cf. §Contrat de données) — pas les 17 molécules de pesticides individuelles une par une (qui donneraient ~30 lignes dont ~29 "non détecté" pour la quasi-totalité des communes). Les pesticides sont représentés par 2 lignes : le total réglementaire et la molécule individuelle la plus défavorable (déjà calculée aujourd'hui en interne sous le nom `pesticide_molecule_max`, simplement jamais exposée).

## Insight de conception clé

`calculer_fiche_commune` (`pipeline/compute_scores.py`) calcule déjà, en interne, une note 0-100 par paramètre individuel (`p_bact`, `p_pest`, `p_pfas`, chaque métal toxique avant le `min()`, `nitrates_mineraux_note`, `chlorures_note`, `sulfates_note`, `chlore_gout_note`, `turbidite_note`, `durete_note`, `chlore_cosmetique_note`, `ph_note`, et chaque métal de dépôt avant le `min()`) — ces notes sont utilisées puis **jetées** une fois combinées dans les sous-scores. Ce sous-projet ne recalcule rien : il conserve et expose ces notes déjà produites, plus la valeur brute mesurée à côté.

Un même barème statut↔note est appliqué uniformément à toutes ces notes déjà 0-100 (au lieu d'inventer un système de seuils propre à chaque paramètre) :
- note ≥ 90 → `"ideal"`
- 70 ≤ note < 90 → `"bon"`
- 40 ≤ note < 70 → `"vigilance"`
- note < 40 → `"degradation"`

## Contrat de données — enrichissement de `public/data/communes/{code}.json`

Ajout de deux blocs à la fiche existante (schéma actuel inchangé par ailleurs — `scores.boisson.score`, `sous_scores`, etc. restent identiques) :

```json
{
  "diagnostic_sanitaire": {
    "veto_actif": true,
    "motifs": [
      {
        "parametre": "Somme des 20 PFAS",
        "code_sandre": "8847",
        "valeur": 0.18,
        "unite": "µg/L",
        "seuil_limite": 0.10,
        "message": "Dépassement de la norme sur les PFAS (0,18 µg/L mesurés vs 0,10 µg/L autorisés)."
      }
    ]
  },
  "indicateurs_complets": [
    {
      "code_parametre": "8847",
      "nom": "PFAS (somme de 20 substances)",
      "valeur": 0.18,
      "unite": "µg/L",
      "statut": "degradation",
      "seuil_ref": "limite réglementaire 0,10 µg/L",
      "impact": "boisson"
    }
  ]
}
```

- `diagnostic_sanitaire` : présent uniquement si `scores.boisson.veto_sanitaire == true` (sinon `{"veto_actif": false, "motifs": []}`). `motifs[]` décompose mécaniquement les 8 conditions déjà testées par `veto_sanitaire()` (`pipeline/scoring.py:136-147`) : bactériologie active, nitrates > 50, nitrites > 0,1, plomb > 10, arsenic > 10, cadmium > 5, pesticide molécule > 0,1, pesticide total > 0,5, PFAS > 0,1 — un motif par condition individuellement dépassée (une commune peut avoir plusieurs motifs simultanés).
- `indicateurs_complets` : 19 entrées fixes (liste ci-dessous), chacune avec `statut: null`/`valeur: null` si le paramètre est absent des mesures de la commune (jamais omise silencieusement — cohérent avec le principe déjà appliqué aux sous-scores).

**Les 19 paramètres exposés** (code SANDRE, nom, impact) : `1449`/`6455` bactériologie (statut conforme/résolu/actif, pas de valeur numérique), `6276` pesticides total, molécule pesticide max (nom + valeur, code variable), `8847` PFAS total, `1382` plomb, `1369` arsenic, `1388` cadmium, `1340` nitrates, `1339` nitrites, `1337` chlorures, `1338` sulfates, `1398` chlore libre, `1295` turbidité, `1345` TH/dureté, `1399` chlore total, `1302` pH, `1392` cuivre, `1393` fer, `1394` manganèse.

## Composants livrés

| Fichier | Rôle |
|---|---|
| `pipeline/compute_scores.py` | `calculer_fiche_commune` conserve les notes intermédiaires au lieu de les jeter ; nouvelle fonction `construire_diagnostic_sanitaire(...)` (décompose `veto_sanitaire` en motifs) et `construire_indicateurs_complets(...)` (statut générique par bandes de note) ; les deux blocs ajoutés au retour de `calculer_fiche_commune` |
| `public/panel.js` | Nouvelle section "Pourquoi ce résultat ?" (accordéon ou liste par statut), bandeau d'alerte sanitaire en tête de panneau si `diagnostic_sanitaire.veto_actif` |
| `public/style.css` | Styles du bandeau d'alerte + badges de statut (idéal/bon/vigilance/dégradation) |

## Cas limites

- Commune `statut_donnees: "indisponible"` : ni `diagnostic_sanitaire` ni `indicateurs_complets` (cohérent avec `scores: null` déjà en place).
- Paramètre non mesuré pour une commune par ailleurs `"complet"` : entrée présente dans `indicateurs_complets` avec `valeur: null, statut: null` — jamais absente de la liste (les 19 entrées sont toujours présentes).
- Régénération : les 34 845 fiches doivent être régénérées (`data/raw/` déjà présent en local sous ce worktree — pas de retéléchargement nécessaire).

## Tests

Pipeline : tests pytest sur `construire_diagnostic_sanitaire` (chaque condition de veto individuellement, plusieurs motifs simultanés, aucun motif si pas de veto) et sur le mapping note→statut (bornes 90/70/40 exactes). Front-end : vérification manuelle (commune avec veto multi-motifs, commune parfaite sans aucune ligne "vigilance/dégradation", commune avec paramètre non mesuré).

## Hors scope

- Recalcul des formules de score existantes (§3 de `SPECIFICATION.md`, inchangées).
- Historique temporel des indicateurs (item séparé, déjà au backlog Phase 3).
