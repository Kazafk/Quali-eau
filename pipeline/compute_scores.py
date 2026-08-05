"""Orchestrateur : fenêtre temporelle, résolution réseau/PLM, puis calcul
complet de la fiche communale (§5.3) via le moteur de scoring déjà testé
(pipeline.scoring / pipeline.aggregation / pipeline.recommendations)."""
from datetime import date

from pipeline.models import ConclusionBacterio


def selectionner_fenetre_jours(dates_prelevements: list, date_reference: date) -> int:
    """§2.5.1 — 12 mois (365j), étendu à 24 (730j) si moins de 4 dates de
    prélèvement distinctes tombent dans les 12 derniers mois. Utilise le
    nombre de dates distinctes comme proxy du nombre d'analyses (une même
    date peut porter plusieurs paramètres)."""
    dates_12_mois = {d for d in dates_prelevements if (date_reference - d).days <= 365}
    return 365 if len(dates_12_mois) >= 4 else 730


def evaluer_bacteriologie(historique: list) -> tuple[bool, bool]:
    """§3.1.1 — évalue (conforme_dernier, resolu) à partir de l'historique
    ConclusionBacterio de la fenêtre, pour alimenter score_bacteriologie.

    ⚠️ INTERPRÉTATION RETENUE (à valider) : le fichier DIS_PLV ne distingue
    pas prélèvement de routine / prélèvement de contrôle. On lit donc :
    - dernier enregistrement de la fenêtre non conforme -> actif (0)
    - dernier enregistrement conforme, mais au moins une non-conformité
      plus tôt dans la même fenêtre -> résolu (50)
    - dernier enregistrement conforme et aucune non-conformité antérieure
      dans la fenêtre -> conforme (100)
    Sans cette lecture, le cas "résolu" de §3.1.1 serait inatteignable
    (si le dernier enregistrement est conforme, il n'y a par construction
    aucun contrôle postérieur à comparer)."""
    if not historique:
        return True, False
    historique_trie = sorted(historique, key=lambda c: c.date_prelevement)
    dernier = historique_trie[-1]
    if not dernier.conforme:
        return False, False
    y_a_eu_non_conformite = any(not c.conforme for c in historique_trie[:-1])
    return True, y_a_eu_non_conformite


def choisir_reseau_principal(reseaux: list, nb_prelevements_par_reseau: dict) -> str | None:
    """§2.5.4 — retourne le code du réseau ayant le plus de prélèvements
    récents parmi ceux desservant la commune. None si aucun réseau connu."""
    if not reseaux:
        return None
    return max(
        (r.code_reseau for r in reseaux),
        key=lambda code: nb_prelevements_par_reseau.get(code, 0),
    )
