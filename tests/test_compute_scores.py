from datetime import date

import pytest

from pipeline.models import ConclusionBacterio
from pipeline.compute_scores import selectionner_fenetre_jours, evaluer_bacteriologie
from pipeline.scoring import score_bacteriologie


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
    # conforme_dernier=False ici (et non True) car score_bacteriologie vérifie
    # conforme_dernier EN PREMIER et court-circuiterait à 100 sinon, rendant
    # le cas "résolu" (50) inatteignable — cf. docstring d'evaluer_bacteriologie.
    historique = [
        ConclusionBacterio(date_prelevement=date(2026, 1, 1), conforme=False),
        ConclusionBacterio(date_prelevement=date(2026, 3, 1), conforme=True),
    ]
    conforme_dernier, resolu = evaluer_bacteriologie(historique)
    assert conforme_dernier is False
    assert resolu is True
    assert score_bacteriologie(conforme_dernier, resolu) == 50.0


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


import os

from pipeline.dis_parser import load_prelevements, load_udi_reseaux
from pipeline.compute_scores import construire_fiches, _trouver_fichiers

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_construire_fiches_depuis_fixtures_reelles():
    # Bout-en-bout : PLV + RESULT + UDI (fixtures Tasks 3-5) -> fiches multi-communes
    date_ref = date(2026, 8, 5)
    fiches = construire_fiches(
        plv_paths=[os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt")],
        result_paths=[os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt")],
        udi_path=os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"),
        date_reference=date_ref,
    )
    assert "34116" in fiches
    fiche = fiches["34116"]
    assert fiche["statut_donnees"] == "complet"
    # nitrates moyens ~ (14+17)/2-ish pondéré, bien en dessous de 50 -> pas de veto
    assert fiche["scores"]["boisson"]["veto_sanitaire"] is False


def test_construire_fiches_bacterio_resolue_via_paris_plm():
    # Exercise le chemin auparavant non couvert (Finding I5) : REF-003 (mars,
    # non-conforme) puis REF-004 (juin, conforme) sur l'arrondissement 75101,
    # normalisé vers 75056 (§2.5.5) -> bactériologie "résolue" (P_bact=50),
    # pas "conforme" (100).
    date_ref = date(2026, 8, 5)
    fiches = construire_fiches(
        plv_paths=[os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt")],
        result_paths=[os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt")],
        udi_path=os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"),
        date_reference=date_ref,
    )
    assert "75056" in fiches
    fiche = fiches["75056"]
    assert fiche["statut_donnees"] == "complet"
    assert fiche["scores"]["boisson"]["sous_scores"]["securite_sanitaire"] == 50


def test_calculer_fiche_commune_parametre_manquant_renormalise_pas_de_faux_100():
    # BUG CRITIQUE (revue finale, Finding C1) : avant le correctif, un
    # paramètre jamais mesuré (chlorures/sulfates ici) était remplacé par
    # 0.0, qui scorait 100 pour ces fonctions précises -> un sous-score
    # "mineraux_equilibre" artificiellement bon alors qu'aucune donnée
    # n'existe pour 2 de ses 3 composantes. Ici nitrates=60 (mauvais) est
    # la SEULE mesure disponible pour ce sous-score : il doit le dominer
    # entièrement (renormalisé sur son seul poids), pas être dilué à 30
    # par deux "100" fantômes.
    date_ref = date(2026, 6, 15)
    mesures = {"1340": [_mesure(60.0, 30, date_ref)]}
    historique = [ConclusionBacterio(date_prelevement=date_ref, conforme=True)]
    fiche = calculer_fiche_commune("00000", mesures, historique, date_ref)
    assert fiche["scores"]["boisson"]["sous_scores"]["mineraux_equilibre"] == 0
    assert fiche["scores"]["donnees_partielles"] is True


def test_calculer_fiche_commune_cosmetique_sans_aucune_donnee_est_null():
    date_ref = date(2026, 6, 15)
    mesures = {"1340": [_mesure(5.0, 30, date_ref)]}  # seule la boisson a des données
    fiche = calculer_fiche_commune("00000", mesures, [], date_ref)
    assert fiche["scores"]["cosmetique"]["score"] is None
    assert fiche["scores"]["cosmetique"]["sous_scores"]["durete_calcaire"] is None
    assert fiche["scores"]["donnees_partielles"] is True


def test_construire_fiches_commune_sans_mesure_recoit_fiche_indisponible():
    # §2.5.6 : une commune connue via le référentiel réseau (DIS_COM_UDI)
    # mais sans aucune mesure doit recevoir une fiche "indisponible",
    # pas être silencieusement absente du résultat.
    date_ref = date(2026, 8, 5)
    fiches = construire_fiches(
        plv_paths=[os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt")],
        result_paths=[os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt")],
        udi_path=os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"),
        date_reference=date_ref,
    )
    assert "99999" in fiches
    assert fiches["99999"]["statut_donnees"] == "indisponible"
    assert fiches["99999"]["scores"] is None


def test_construire_fiches_commune_avec_mesures_trop_anciennes_est_indisponible(tmp_path):
    # BUG CRITIQUE (revue finale, Finding C1) : avant le correctif, une
    # commune dont TOUTES les mesures sont hors fenêtre (>730 jours) recevait
    # statut_donnees="complet" avec des sous-scores None — la fusion
    # multi-années de ce plan rend ce cas atteignable (~2023-2024 sont hors
    # fenêtre par rapport à une date_reference de 2026), en violation de
    # §2.5.6 (une commune sans mesure exploitable doit être "indisponible").
    date_ref = date(2026, 8, 5)
    plv_contenu = (
        "cddept,cdreseau,inseecommuneprinc,nomcommuneprinc,cdreseauamont,nomreseauamont,"
        "pourcentdebit,referenceprel,dateprel,heureprel,conclusionprel,ugelib,distrlib,"
        "moalib,plvconformitebacterio,plvconformitechimique,plvconformitereferencebact,"
        "plvconformitereferencechim\n"
        '"012","012000009","54321","VIEILLEVILLE","","","","REF-OLD","2023-01-01","09h00",'
        '"x","","","","C","C","C","C"\n'
    )
    result_contenu = (
        "cddept,referenceprel,cdparametresiseeaux,cdparametre,libmajparametre,libminparametre,"
        "libwebparametre,qualitparam,insituana,rqana,cdunitereferencesiseeaux,cdunitereference,"
        "limitequal,refqual,valtraduite,casparam,referenceanl\n"
        '"012","REF-OLD","NO3","1340","NITRATES (EN NO3)","Nitrates (en NO3)",,"N","L","15",'
        '"mg/L","162","<=50 mg/L","","15.000000","14797-55-8","ANL-OLD"\n'
    )
    udi_contenu = (
        "inseecommune,nomcommune,quartier,cdreseau,nomreseau,debutalim\n"
        '"54321","VIEILLEVILLE","-","012000009","RESEAU VIEILLEVILLE","2010-01-01"\n'
    )
    plv_path = tmp_path / "DIS_PLV_old.txt"
    result_path = tmp_path / "DIS_RESULT_old.txt"
    udi_path = tmp_path / "DIS_COM_UDI_old.txt"
    plv_path.write_text(plv_contenu, encoding="utf-8")
    result_path.write_text(result_contenu, encoding="utf-8")
    udi_path.write_text(udi_contenu, encoding="utf-8")

    fiches = construire_fiches(
        plv_paths=[str(plv_path)], result_paths=[str(result_path)], udi_path=str(udi_path),
        date_reference=date_ref,
    )
    assert "54321" in fiches
    assert fiches["54321"]["statut_donnees"] == "indisponible"
    assert fiches["54321"]["scores"] is None


def test_trouver_fichiers_recherche_sous_repertoires_annuels(tmp_path):
    (tmp_path / "2025").mkdir()
    (tmp_path / "2026").mkdir()
    (tmp_path / "2025" / "DIS_PLV_2025.txt").write_text("x", encoding="utf-8")
    (tmp_path / "2026" / "DIS_PLV_2026.txt").write_text("x", encoding="utf-8")
    resultats = _trouver_fichiers(str(tmp_path), "DIS_PLV*.txt")
    assert len(resultats) == 2
    assert resultats[0].endswith("DIS_PLV_2025.txt")
    assert resultats[1].endswith("DIS_PLV_2026.txt")


def test_trouver_fichiers_recherche_aussi_a_plat(tmp_path):
    (tmp_path / "DIS_PLV.txt").write_text("x", encoding="utf-8")
    resultats = _trouver_fichiers(str(tmp_path), "DIS_PLV*.txt")
    assert len(resultats) == 1


def test_trouver_fichiers_leve_si_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        _trouver_fichiers(str(tmp_path), "DIS_PLV*.txt")


from pipeline.compute_scores import construire_carte_scores


def test_construire_carte_scores_extrait_scores_commune_complete():
    fiches = {
        "75056": {
            "commune": {"code_insee": "75056"},
            "statut_donnees": "complet",
            "scores": {
                "donnees_partielles": False,
                "boisson": {"score": 90, "veto_sanitaire": False, "sous_scores": {}},
                "cosmetique": {"score": 76, "sous_scores": {}},
            },
            "recommandations": [],
        },
    }
    carte = construire_carte_scores(fiches)
    assert carte == {
        "75056": {"score_boisson": 90, "score_cosmetique": 76, "statut_donnees": "complet"},
    }


def test_construire_carte_scores_commune_indisponible_a_scores_null():
    fiches = {
        "99999": {"commune": {"code_insee": "99999"}, "statut_donnees": "indisponible", "scores": None},
    }
    carte = construire_carte_scores(fiches)
    assert carte == {
        "99999": {"score_boisson": None, "score_cosmetique": None, "statut_donnees": "indisponible"},
    }
