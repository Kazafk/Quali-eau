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
