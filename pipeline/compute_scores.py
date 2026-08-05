"""Orchestrateur : fenêtre temporelle, résolution réseau/PLM, puis calcul
complet de la fiche communale (§5.3) via le moteur de scoring déjà testé
(pipeline.scoring / pipeline.aggregation / pipeline.recommendations)."""
import glob
import json
import os
from datetime import date, datetime, timezone

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

    Correctif (revue finale) : la première version de cette fonction
    retournait (conforme_dernier=True, resolu=True) pour le cas "résolu",
    mais score_bacteriologie vérifie conforme_dernier EN PREMIER et
    court-circuite à 100 dès qu'il est vrai — donc resolu=True n'était
    jamais consulté et le cas 50 n'était jamais atteignable. Redéfinition
    compatible avec le contrat réel (déjà verrouillé par les tests de
    score_bacteriologie) : conforme_dernier=True signifie "aucun incident
    dans toute la fenêtre" (dossier vierge) ; conforme_dernier=False avec
    resolu=True signifie "un incident a existé dans la fenêtre mais le
    dernier enregistrement est conforme" (résolu) ; conforme_dernier=False
    avec resolu=False signifie "le dernier enregistrement est non conforme"
    (actif). Entièrement dérivable de l'ordre chronologique, sans nécessiter
    de distinction prélèvement de routine / prélèvement de contrôle (absente
    de DIS_PLV) — l'ambiguïté flaguée dans le plan est résolue par cette
    redéfinition, pas contournée."""
    if not historique:
        return True, False
    historique_trie = sorted(historique, key=lambda c: c.date_prelevement)
    if all(c.conforme for c in historique_trie):
        return True, False
    dernier = historique_trie[-1]
    if dernier.conforme:
        return False, True
    return False, False


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
    score_nitrates_securite, score_nitrates_mineraux, score_chlorures, score_sulfates,
    score_chlore_gout, score_turbidite, score_durete, score_chlore_cosmetique, score_ph,
    score_cuivre, score_fer, score_manganese, veto_sanitaire, arrondi,
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


def _valeur_disponible(mesures_par_parametre: dict, code: str, fenetre, date_reference: date):
    """Retourne (valeur, disponible). disponible=False si aucune mesure
    dans la fenêtre pour ce code SANDRE — l'appelant doit alors EXCLURE ce
    paramètre du calcul plutôt que de lui substituer 0.0 (§3 : un paramètre
    absent ne doit jamais compter comme un score parfait)."""
    m = fenetre(mesures_par_parametre.get(code, []))
    if not m:
        return None, False
    return moyenne_ponderee(m, date_reference), True


def _score_pondere_avec_veto(composantes: list, veto_actif: bool, veto_composante):
    """composantes : list[(note: float | None, poids_nominal: float)].
    Combine par moyenne pondérée en renormalisant sur les composantes
    disponibles (§3) ; chaque composante disponible est arrondie avant
    combinaison (convention déjà utilisée par les formules de la spec).
    Si veto_actif et qu'une composante de veto est disponible, plafonne le
    résultat à cette composante (arrondie). Retourne None si aucune
    composante n'est disponible."""
    disponibles = [(arrondi(note), poids) for note, poids in composantes if note is not None]
    if not disponibles:
        return None
    poids_total = sum(poids for _, poids in disponibles)
    brut = sum(note * poids for note, poids in disponibles) / poids_total
    if veto_actif and veto_composante is not None:
        brut = min(brut, arrondi(veto_composante))
    return arrondi(max(0.0, min(100.0, brut)))


def calculer_fiche_commune(code_insee: str, mesures_par_parametre: dict,
                            historique_bacterio: list, date_reference: date) -> dict:
    """Assemble la fiche communale complète (§5.3) pour une commune, à partir
    des Mesure déjà jointes (dict[code_parametre, list[Mesure]]) et de
    l'historique de conformité bactériologique. Tout paramètre absent de la
    fenêtre pour un sous-score est exclu (min) ou son poids est renormalisé
    (moyenne pondérée) sur les composantes disponibles (§3) ; si TOUTES les
    composantes d'un sous-score sont absentes, ce sous-score vaut None et le
    parent se recalcule sans lui. `donnees_partielles` reflète si un tel
    renormalisation a eu lieu quelque part dans la fiche."""

    toutes_dates = [m.date_prelevement for mesures in mesures_par_parametre.values() for m in mesures]
    if not toutes_dates:
        return {"commune": {"code_insee": code_insee}, "statut_donnees": "indisponible", "scores": None}

    fenetre_jours = selectionner_fenetre_jours(toutes_dates, date_reference)

    def fenetre(mesures):
        return [m for m in mesures if 0 <= (date_reference - m.date_prelevement).days <= fenetre_jours]

    # --- Bactériologie (§3.1.1), filtrée sur la fenêtre (correctif C2 : la
    # docstring d'evaluer_bacteriologie exige déjà un historique "de la
    # fenêtre", ce filtrage manquait). ---
    historique_fenetre = [
        h for h in historique_bacterio
        if 0 <= (date_reference - h.date_prelevement).days <= fenetre_jours
    ]
    if historique_fenetre:
        conforme_dernier, resolu = evaluer_bacteriologie(historique_fenetre)
        p_bact = score_bacteriologie(conforme_dernier, resolu)
    else:
        conforme_dernier, resolu = True, False  # pas de non-conformité connue -> pas de veto par défaut
        p_bact = None

    # --- Pesticides & PFAS (§3.1.1) ---
    pesticide_total, pesticide_total_dispo = _valeur_disponible(mesures_par_parametre, "6276", fenetre, date_reference)
    pesticide_molecule_max = None
    molecule_dispo = False
    for code in PESTICIDE_CODES:
        v, dispo = _valeur_disponible(mesures_par_parametre, code, fenetre, date_reference)
        if dispo:
            molecule_dispo = True
            pesticide_molecule_max = v if pesticide_molecule_max is None else max(pesticide_molecule_max, v)
    if pesticide_total_dispo or molecule_dispo:
        p_pest = score_pesticides(pesticide_total or 0.0, pesticide_molecule_max or 0.0)
    else:
        p_pest = None

    pfas_total, pfas_dispo = _valeur_disponible(mesures_par_parametre, "8847", fenetre, date_reference)
    p_pfas = score_pfas(pfas_total) if pfas_dispo else None

    # --- Métaux toxiques (§3.1.1 v1.5, LQ seule) ---
    valeurs_metaux = {}
    notes_metaux = []
    for code, lq in METAUX_LQ.items():
        v, dispo = _valeur_disponible(mesures_par_parametre, code, fenetre, date_reference)
        if dispo:
            valeurs_metaux[code] = v
            notes_metaux.append(score_metal_toxique(v, lq))
    p_metaux = min(notes_metaux) if notes_metaux else None

    # --- Nitrates/nitrites sécurité (§3.1.1 P_nitrates) ---
    nitrates, nitrates_dispo = _valeur_disponible(mesures_par_parametre, "1340", fenetre, date_reference)
    nitrites, nitrites_dispo = _valeur_disponible(mesures_par_parametre, "1339", fenetre, date_reference)
    if nitrates_dispo or nitrites_dispo:
        p_nitrates = score_nitrates_securite(nitrates or 0.0, nitrites or 0.0)
    else:
        p_nitrates = None

    composantes_securite = [p for p in (p_bact, p_pest, p_pfas, p_metaux, p_nitrates) if p is not None]
    s_securite = min(composantes_securite) if composantes_securite else None
    securite_partielle = not (p_bact is not None and p_pest is not None and p_pfas is not None
                               and p_metaux is not None and p_nitrates is not None)

    # --- Minéraux & goût (§3.1.2, §3.1.3) ---
    nitrates_mineraux_note = score_nitrates_mineraux(nitrates) if nitrates_dispo else None
    chlorures, chlorures_dispo = _valeur_disponible(mesures_par_parametre, "1337", fenetre, date_reference)
    chlorures_note = score_chlorures(chlorures) if chlorures_dispo else None
    sulfates, sulfates_dispo = _valeur_disponible(mesures_par_parametre, "1338", fenetre, date_reference)
    sulfates_note = score_sulfates(sulfates) if sulfates_dispo else None
    s_mineraux = _score_pondere_avec_veto(
        [(nitrates_mineraux_note, 0.70), (chlorures_note, 0.15), (sulfates_note, 0.15)],
        veto_actif=False, veto_composante=None,
    )
    mineraux_partielle = not (nitrates_dispo and chlorures_dispo and sulfates_dispo)

    chlore_libre, chlore_libre_dispo = _valeur_disponible(mesures_par_parametre, "1398", fenetre, date_reference)
    chlore_gout_note = score_chlore_gout(chlore_libre) if chlore_libre_dispo else None
    turbidite, turbidite_dispo = _valeur_disponible(mesures_par_parametre, "1295", fenetre, date_reference)
    turbidite_note = score_turbidite(turbidite) if turbidite_dispo else None
    s_gout = _score_pondere_avec_veto(
        [(chlore_gout_note, 0.60), (turbidite_note, 0.40)],
        veto_actif=False, veto_composante=None,
    )
    gout_partielle = not (chlore_libre_dispo and turbidite_dispo)

    bact_actif = (not conforme_dernier) and (not resolu)
    veto = veto_sanitaire(
        bact_actif=bact_actif, nitrates=nitrates or 0.0, nitrites=nitrites or 0.0,
        pb=valeurs_metaux.get("1382", 0.0), as_=valeurs_metaux.get("1369", 0.0),
        cd=valeurs_metaux.get("1388", 0.0),
        pesticide_molecule_max=pesticide_molecule_max or 0.0, pesticide_total=pesticide_total or 0.0,
        pfas=pfas_total or 0.0,
    )
    score_boisson_val = _score_pondere_avec_veto(
        [(s_securite, 0.55), (s_mineraux, 0.25), (s_gout, 0.20)],
        veto_actif=veto, veto_composante=s_securite,
    )

    # --- Cosmétique (§3.2) ---
    th, th_dispo = _valeur_disponible(mesures_par_parametre, "1345", fenetre, date_reference)
    chlore_total, chlore_total_dispo = _valeur_disponible(mesures_par_parametre, "1399", fenetre, date_reference)
    ph, ph_dispo = _valeur_disponible(mesures_par_parametre, "1302", fenetre, date_reference)
    cuivre, cuivre_dispo = _valeur_disponible(mesures_par_parametre, "1392", fenetre, date_reference)
    fer, fer_dispo = _valeur_disponible(mesures_par_parametre, "1393", fenetre, date_reference)
    manganese, manganese_dispo = _valeur_disponible(mesures_par_parametre, "1394", fenetre, date_reference)

    durete_note = score_durete(th) if th_dispo else None
    chlore_cosmetique_note = score_chlore_cosmetique(chlore_total) if chlore_total_dispo else None
    ph_note = score_ph(ph) if ph_dispo else None
    notes_metaux_depots = []
    if cuivre_dispo:
        notes_metaux_depots.append(score_cuivre(cuivre))
    if fer_dispo:
        notes_metaux_depots.append(score_fer(fer))
    if manganese_dispo:
        notes_metaux_depots.append(score_manganese(manganese))
    metaux_depots_dispo = bool(notes_metaux_depots)
    metaux_depots_note = min(notes_metaux_depots) if notes_metaux_depots else None

    score_cosmetique_val = _score_pondere_avec_veto(
        [(durete_note, 0.45), (chlore_cosmetique_note, 0.25), (ph_note, 0.15), (metaux_depots_note, 0.15)],
        veto_actif=False, veto_composante=None,
    )
    cosmetique_partielle = not (th_dispo and chlore_total_dispo and ph_dispo and metaux_depots_dispo)

    donnees_partielles = securite_partielle or mineraux_partielle or gout_partielle or cosmetique_partielle

    # --- Recommandations (§4) — n'inclure une clé que si le paramètre est
    # réellement disponible, pour respecter le contrat déjà existant de
    # generate_recommendations (.get(code) -> None si absent pour th/nitrates/
    # chlore/fer/cuivre ; .get(code, 0.0) -> 0.0 si absent pour les totaux). ---
    mesures_recommandations = {}
    if th_dispo:
        mesures_recommandations["1345"] = th
    if chlore_libre_dispo:
        mesures_recommandations["1398"] = chlore_libre
    if chlore_total_dispo:
        mesures_recommandations["1399"] = chlore_total
    if nitrates_dispo:
        mesures_recommandations["1340"] = nitrates
    if nitrites_dispo:
        mesures_recommandations["1339"] = nitrites
    if pesticide_total_dispo:
        mesures_recommandations["6276"] = pesticide_total
    if pfas_dispo:
        mesures_recommandations["8847"] = pfas_total
    if fer_dispo:
        mesures_recommandations["1393"] = fer
    if cuivre_dispo:
        mesures_recommandations["1392"] = cuivre
    if molecule_dispo:
        mesures_recommandations["_pesticide_molecule_max"] = pesticide_molecule_max
    recommandations = generate_recommendations(mesures_recommandations, bact_actif=bact_actif)

    return {
        "commune": {"code_insee": code_insee},
        "statut_donnees": "complet",
        "scores": {
            "donnees_partielles": donnees_partielles,
            "boisson": {
                "score": score_boisson_val,
                "veto_sanitaire": veto,
                "sous_scores": {
                    "securite_sanitaire": arrondi(s_securite) if s_securite is not None else None,
                    "mineraux_equilibre": arrondi(s_mineraux) if s_mineraux is not None else None,
                    "gout_organoleptique": arrondi(s_gout) if s_gout is not None else None,
                },
            },
            "cosmetique": {
                "score": score_cosmetique_val,
                "sous_scores": {
                    "durete_calcaire": arrondi(durete_note) if durete_note is not None else None,
                    "chlore_agressivite": arrondi(chlore_cosmetique_note) if chlore_cosmetique_note is not None else None,
                    "respect_ph": arrondi(ph_note) if ph_note is not None else None,
                    "metaux_depots": arrondi(metaux_depots_note) if metaux_depots_note is not None else None,
                },
            },
        },
        "recommandations": recommandations,
    }


from pipeline.dis_parser import load_prelevements, load_udi_reseaux, iter_mesures


def construire_fiches(plv_path: str, result_path: str, udi_path: str, date_reference: date) -> dict:
    """Charge PLV+RESULT+UDI et construit la fiche de chaque commune connue.
    Le réseau principal (§2.5.4) n'est pas encore filtré ici : toutes les
    mesures de toutes les communes du fichier sont agrégées ensemble (une
    commune multi-réseaux verra ses réseaux fusionnés — affinage laissé à
    un futur plan si un cas réel l'exige)."""
    prelevements = load_prelevements(plv_path)
    _reseaux_par_commune = load_udi_reseaux(udi_path)  # réservé pour affinage futur

    mesures_par_commune: dict = {}
    for code_insee, code_parametre, mesure in iter_mesures(result_path, prelevements):
        mesures_par_commune.setdefault(code_insee, {}).setdefault(code_parametre, []).append(mesure)

    historique_bacterio_par_commune: dict = {}
    for info in prelevements.values():
        if info.conforme_bacterio is None:
            continue
        historique_bacterio_par_commune.setdefault(info.code_insee, []).append(
            ConclusionBacterio(date_prelevement=info.date_prelevement, conforme=info.conforme_bacterio)
        )

    fiches = {}
    for code_insee, mesures_par_parametre in mesures_par_commune.items():
        historique = historique_bacterio_par_commune.get(code_insee, [])
        fiches[code_insee] = calculer_fiche_commune(code_insee, mesures_par_parametre, historique, date_reference)
    return fiches


def _trouver_fichier(raw_dir: str, motif: str) -> str:
    """Résout un fichier DIS par motif glob plutôt qu'un nom exact : les
    ZIPs extraits par pipeline/download_data.py gardent leur suffixe
    d'année (DIS_PLV_2026.txt), pas un nom générique."""
    correspondances = sorted(glob.glob(os.path.join(raw_dir, motif)))
    if not correspondances:
        raise FileNotFoundError(f"Aucun fichier correspondant à {motif!r} dans {raw_dir}")
    return correspondances[0]


def main(raw_dir: str, output_dir: str, date_reference: date | None = None) -> None:
    """Point d'entrée batch : lit les 3 fichiers DIS de `raw_dir` (année la
    plus récente uniquement — l'agrégation multi-années glissantes est un
    raffinement futur), écrit une fiche JSON par commune sous
    `output_dir/communes/{code_insee}.json` + un `index.json` global."""
    date_reference = date_reference or datetime.now(timezone.utc).date()
    plv_path = _trouver_fichier(raw_dir, "DIS_PLV*.txt")
    result_path = _trouver_fichier(raw_dir, "DIS_RESULT*.txt")
    udi_path = _trouver_fichier(raw_dir, "DIS_COM_UDI*.txt")

    fiches = construire_fiches(plv_path, result_path, udi_path, date_reference)

    communes_dir = os.path.join(output_dir, "communes")
    os.makedirs(communes_dir, exist_ok=True)
    for code_insee, fiche in fiches.items():
        with open(os.path.join(communes_dir, f"{code_insee}.json"), "w", encoding="utf-8") as f:
            json.dump(fiche, f, ensure_ascii=False, indent=2)

    index = {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "nb_communes_scorees": sum(1 for f in fiches.values() if f["statut_donnees"] == "complet"),
        "nb_communes_sans_donnees": sum(1 for f in fiches.values() if f["statut_donnees"] == "indisponible"),
    }
    with open(os.path.join(output_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main(
        raw_dir=os.path.join(PROJECT_ROOT, "data", "raw", "2026"),
        output_dir=os.path.join(PROJECT_ROOT, "public", "data"),
    )
