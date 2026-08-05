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


from pipeline.aggregation import moyenne_ponderee
from pipeline.scoring import (
    score_bacteriologie, score_pesticides, score_pfas, score_metal_toxique,
    score_nitrates_securite, score_securite, score_mineraux, score_gout,
    score_boisson, score_cosmetique, veto_sanitaire, arrondi,
)
from pipeline.recommendations import generate_recommendations

# §2.4 — 17 codes pesticides validés
PESTICIDE_CODES = [
    "1107", "1108", "1113", "1129", "1177", "1208", "1209", "1473",
    "1506", "1667", "1877", "1907", "2974", "6894", "6895", "7717", "8865",
]

# §2.3 / §3.1.1 v1.5 — LQ seule, pas de RQ documentée pour ces métaux toxiques
METAUX_LQ = {
    "1382": 10.0,  # Plomb, µg/L
    "1369": 10.0,  # Arsenic, µg/L
    "1388": 5.0,   # Cadmium, µg/L
    "1386": 20.0,  # Nickel, µg/L
}


def _moyenne_ou_zero(mesures: list, date_reference: date) -> float:
    if not mesures:
        return 0.0
    valeur = moyenne_ponderee(mesures, date_reference)
    return valeur if valeur is not None else 0.0


def calculer_fiche_commune(code_insee: str, mesures_par_parametre: dict,
                            historique_bacterio: list, date_reference: date) -> dict:
    """Assemble la fiche communale complète (§5.3) pour une commune, à partir
    des Mesure déjà jointes (dict[code_parametre, list[Mesure]]) et de
    l'historique de conformité bactériologique de la fenêtre."""

    toutes_dates = [m.date_prelevement for mesures in mesures_par_parametre.values() for m in mesures]
    if not toutes_dates:
        return {"commune": {"code_insee": code_insee}, "statut_donnees": "indisponible", "scores": None}

    fenetre_jours = selectionner_fenetre_jours(toutes_dates, date_reference)

    def fenetre(mesures):
        return [m for m in mesures if (date_reference - m.date_prelevement).days <= fenetre_jours]

    # --- Sécurité sanitaire (§3.1.1) ---
    conforme_dernier, resolu = evaluer_bacteriologie(historique_bacterio)
    p_bact = score_bacteriologie(conforme_dernier, resolu)

    # 6276 est lui-même un paramètre mesuré et rapporté par le labo (confirmé
    # sur données réelles §2.1) : on le lit comme un paramètre individuel
    # (moyenne pondérée directe), sans recalcul par sommation des 17
    # molécules — cf. note de simplification dans "Out of Scope" (le
    # recalcul LQ/2 de valeur_somme_reglementaire, quand le champ total
    # lui-même est sous LQ, est un raffinement futur, pas encore câblé ici).
    pesticide_total = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("6276", [])), date_reference)
    pesticide_molecule_max = 0.0
    for code in PESTICIDE_CODES:
        m = fenetre(mesures_par_parametre.get(code, []))
        if m:
            pesticide_molecule_max = max(pesticide_molecule_max, moyenne_ponderee(m, date_reference))
    p_pest = score_pesticides(pesticide_total, pesticide_molecule_max)

    pfas_total = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("8847", [])), date_reference)
    p_pfas = score_pfas(pfas_total)

    valeurs_metaux = {}
    notes_metaux = []
    for code, lq in METAUX_LQ.items():
        m = fenetre(mesures_par_parametre.get(code, []))
        if m:
            v = moyenne_ponderee(m, date_reference)
            valeurs_metaux[code] = v
            notes_metaux.append(score_metal_toxique(v, lq))
    p_metaux = min(notes_metaux) if notes_metaux else 100.0

    nitrates = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1340", [])), date_reference)
    nitrites = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1339", [])), date_reference)
    p_nitrates = score_nitrates_securite(nitrates, nitrites)

    s_securite = score_securite(p_bact, p_pest, p_pfas, p_metaux, p_nitrates)

    # --- Minéraux & goût (§3.1.2, §3.1.3) ---
    chlorures = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1337", [])), date_reference)
    sulfates = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1338", [])), date_reference)
    s_mineraux = score_mineraux(nitrates, chlorures, sulfates)

    chlore_libre = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1398", [])), date_reference)
    turbidite = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1295", [])), date_reference)
    s_gout = score_gout(chlore_libre, turbidite)

    bact_actif = (not conforme_dernier) and (not resolu)
    veto = veto_sanitaire(
        bact_actif=bact_actif, nitrates=nitrates, nitrites=nitrites,
        pb=valeurs_metaux.get("1382", 0.0), as_=valeurs_metaux.get("1369", 0.0),
        cd=valeurs_metaux.get("1388", 0.0),
        pesticide_molecule_max=pesticide_molecule_max, pesticide_total=pesticide_total,
        pfas=pfas_total,
    )
    score_boisson_val = score_boisson(s_securite, s_mineraux, s_gout, veto)

    # --- Cosmétique (§3.2) ---
    th = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1345", [])), date_reference)
    chlore_total = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1399", [])), date_reference)
    ph_mesures = fenetre(mesures_par_parametre.get("1302", []))
    ph = moyenne_ponderee(ph_mesures, date_reference) if ph_mesures else 7.0
    cuivre = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1392", [])), date_reference)
    fer = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1393", [])), date_reference)
    manganese = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1394", [])), date_reference)
    score_cosmetique_val, sous_scores_cosmetique = score_cosmetique(th, chlore_total, ph, cuivre, fer, manganese)

    # --- Recommandations (§4) ---
    mesures_recommandations = {
        "1345": th, "1398": chlore_libre, "1399": chlore_total, "1340": nitrates,
        "1339": nitrites, "6276": pesticide_total, "8847": pfas_total,
        "1393": fer, "1392": cuivre, "_pesticide_molecule_max": pesticide_molecule_max,
    }
    recommandations = generate_recommendations(mesures_recommandations, bact_actif=bact_actif)

    return {
        "commune": {"code_insee": code_insee},
        "statut_donnees": "complet",
        "scores": {
            "boisson": {
                "score": score_boisson_val,
                "veto_sanitaire": veto,
                "sous_scores": {
                    "securite_sanitaire": arrondi(s_securite),
                    "mineraux_equilibre": arrondi(s_mineraux),
                    "gout_organoleptique": arrondi(s_gout),
                },
            },
            "cosmetique": {
                "score": score_cosmetique_val,
                "sous_scores": sous_scores_cosmetique,
            },
        },
        "recommandations": recommandations,
    }
