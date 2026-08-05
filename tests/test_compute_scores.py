from datetime import date

from pipeline.models import ConclusionBacterio
from pipeline.compute_scores import selectionner_fenetre_jours, evaluer_bacteriologie


def test_fenetre_12_mois_si_4_prelevements_ou_plus():
    date_ref = date(2026, 6, 15)
    dates = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    assert selectionner_fenetre_jours(dates, date_ref) == 365


def test_fenetre_etendue_24_mois_si_moins_de_4():
    date_ref = date(2026, 6, 15)
    dates = [date(2026, 1, 1), date(2026, 2, 1)]  # seulement 2
    assert selectionner_fenetre_jours(dates, date_ref) == 730


def test_fenetre_ignore_dates_hors_12_mois_pour_le_comptage():
    date_ref = date(2026, 6, 15)
    dates = [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1)]  # trop vieilles
    assert selectionner_fenetre_jours(dates, date_ref) == 730


def test_evaluer_bacteriologie_conforme_sans_historique_non_conforme():
    historique = [
        ConclusionBacterio(date_prelevement=date(2026, 1, 1), conforme=True),
        ConclusionBacterio(date_prelevement=date(2026, 3, 1), conforme=True),
    ]
    conforme_dernier, resolu = evaluer_bacteriologie(historique)
    assert conforme_dernier is True
    assert resolu is False


def test_evaluer_bacteriologie_resolue():
    # Non-conformité en janvier, mais le dernier prélèvement (mars) est conforme.
    historique = [
        ConclusionBacterio(date_prelevement=date(2026, 1, 1), conforme=False),
        ConclusionBacterio(date_prelevement=date(2026, 3, 1), conforme=True),
    ]
    conforme_dernier, resolu = evaluer_bacteriologie(historique)
    assert conforme_dernier is True
    assert resolu is True


def test_evaluer_bacteriologie_active():
    historique = [
        ConclusionBacterio(date_prelevement=date(2026, 1, 1), conforme=True),
        ConclusionBacterio(date_prelevement=date(2026, 3, 1), conforme=False),
    ]
    conforme_dernier, resolu = evaluer_bacteriologie(historique)
    assert conforme_dernier is False
    assert resolu is False


def test_evaluer_bacteriologie_aucun_historique():
    conforme_dernier, resolu = evaluer_bacteriologie([])
    assert conforme_dernier is True
    assert resolu is False


from pipeline.dis_parser import ReseauRef
from pipeline.compute_scores import choisir_reseau_principal


def test_choisir_reseau_principal_le_plus_de_prelevements():
    reseaux = [ReseauRef("R1", "Réseau 1"), ReseauRef("R2", "Réseau 2")]
    nb = {"R1": 5, "R2": 20}
    assert choisir_reseau_principal(reseaux, nb) == "R2"


def test_choisir_reseau_principal_un_seul_reseau():
    reseaux = [ReseauRef("R1", "Réseau unique")]
    assert choisir_reseau_principal(reseaux, {"R1": 3}) == "R1"


def test_choisir_reseau_principal_aucun_reseau():
    assert choisir_reseau_principal([], {}) is None


def test_choisir_reseau_principal_reseau_sans_prelevement_compte_zero():
    reseaux = [ReseauRef("R1", "Réseau 1"), ReseauRef("R2", "Réseau 2")]
    nb = {"R1": 5}  # R2 absent du dict -> 0 prélèvements
    assert choisir_reseau_principal(reseaux, nb) == "R1"


from pipeline.models import Mesure
from pipeline.compute_scores import calculer_fiche_commune


def _mesure(valeur, jours_avant_ref, date_reference, sous_lq=False):
    from datetime import timedelta
    return Mesure(valeur=valeur, sous_lq=sous_lq, date_prelevement=date_reference - timedelta(days=jours_avant_ref))


def test_calculer_fiche_commune_eau_bonne_qualite():
    date_ref = date(2026, 6, 15)
    mesures = {
        "1345": [_mesure(10.0, 30, date_ref), _mesure(10.0, 60, date_ref), _mesure(10.0, 90, date_ref), _mesure(10.0, 120, date_ref)],
        "1398": [_mesure(0.03, 30, date_ref)],
        "1399": [_mesure(0.03, 30, date_ref)],
        "1302": [_mesure(7.0, 30, date_ref)],
        "1295": [_mesure(0.1, 30, date_ref)],
        "1340": [_mesure(5.0, 30, date_ref)],
    }
    historique = [ConclusionBacterio(date_prelevement=date_ref, conforme=True)]

    fiche = calculer_fiche_commune("34116", mesures, historique, date_ref)

    assert fiche["statut_donnees"] == "complet"
    assert fiche["scores"]["boisson"]["score"] >= 90
    assert fiche["scores"]["boisson"]["veto_sanitaire"] is False
    assert fiche["scores"]["cosmetique"]["score"] >= 90
    assert fiche["scores"]["cosmetique"]["sous_scores"]["durete_calcaire"] == 100


def test_calculer_fiche_commune_veto_nitrates_plafonne_le_score():
    # Régression directe du bug corrigé en v1.3 (§3.1) : un dépassement
    # nitrates doit réellement plafonner le score boisson, pas juste
    # cosmétiquement apparaître dans un sous-score.
    date_ref = date(2026, 6, 15)
    mesures = {
        "1345": [_mesure(10.0, 30, date_ref)],
        "1398": [_mesure(0.03, 30, date_ref)],
        "1399": [_mesure(0.03, 30, date_ref)],
        "1302": [_mesure(7.0, 30, date_ref)],
        "1295": [_mesure(0.1, 30, date_ref)],
        "1340": [_mesure(60.0, 30, date_ref)],  # > 50 mg/L : veto
    }
    historique = [ConclusionBacterio(date_prelevement=date_ref, conforme=True)]

    fiche = calculer_fiche_commune("34116", mesures, historique, date_ref)

    assert fiche["scores"]["boisson"]["veto_sanitaire"] is True
    assert fiche["scores"]["boisson"]["score"] < 50


def test_calculer_fiche_commune_aucune_mesure_statut_indisponible():
    fiche = calculer_fiche_commune("99999", {}, [], date(2026, 6, 15))
    assert fiche["statut_donnees"] == "indisponible"
    assert fiche["scores"] is None
