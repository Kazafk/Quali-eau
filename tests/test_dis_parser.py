import os
from datetime import date

from pipeline.dis_parser import normaliser_code_insee, parse_valeur_rqana, load_prelevements, load_udi_reseaux


def test_normaliser_code_insee_paris_arrondissement():
    assert normaliser_code_insee("75101") == "75056"
    assert normaliser_code_insee("75120") == "75056"


def test_normaliser_code_insee_lyon_arrondissement():
    assert normaliser_code_insee("69381") == "69123"
    assert normaliser_code_insee("69389") == "69123"


def test_normaliser_code_insee_marseille_arrondissement():
    assert normaliser_code_insee("13201") == "13055"
    assert normaliser_code_insee("13216") == "13055"


def test_normaliser_code_insee_commune_normale_inchangee():
    assert normaliser_code_insee("34116") == "34116"
    assert normaliser_code_insee("01007") == "01007"


def test_parse_valeur_rqana_sous_lq():
    # Cas réel vérifié §2.1 : glyphosate "<0,020" -> valtraduite=0 à IGNORER,
    # la vraie LQ (0.020) et le sous-LQ ne sont lisibles que dans rqana.
    valeur, sous_lq = parse_valeur_rqana("<0,020")
    assert sous_lq is True
    assert abs(valeur - 0.020) < 1e-9


def test_parse_valeur_rqana_quantifie():
    # Cas réel vérifié §2.1 : nitrates "3,2" (pas de préfixe <)
    valeur, sous_lq = parse_valeur_rqana("3,2")
    assert sous_lq is False
    assert abs(valeur - 3.2) < 1e-9


def test_parse_valeur_rqana_entier_sans_virgule():
    # Cas réel vérifié §2.1 : nitrates "14"
    valeur, sous_lq = parse_valeur_rqana("14")
    assert sous_lq is False
    assert valeur == 14.0


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_load_prelevements_parse_champs_reels():
    idx = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    assert len(idx) == 4
    info = idx["REF-001"]
    assert info.code_insee == "34116"
    assert info.code_reseau == "034000123"
    assert info.date_prelevement == date(2026, 2, 10)
    assert info.conforme_bacterio is True
    assert info.conforme_chimique is True


def test_load_prelevements_normalise_plm():
    # REF-003/REF-004 sont sur Paris 1er (75101) -> doit remonter à 75056
    idx = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    assert idx["REF-003"].code_insee == "75056"
    assert idx["REF-004"].code_insee == "75056"


def test_load_prelevements_conformite_non_conforme():
    idx = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    assert idx["REF-003"].conforme_bacterio is False


def test_load_udi_reseaux_commune_simple():
    idx = load_udi_reseaux(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"))
    reseaux = idx["34116"]
    assert len(reseaux) == 1
    assert reseaux[0].code_reseau == "034000123"
    assert reseaux[0].nom_reseau == "RESEAU GRABELS PRINCIPAL"


def test_load_udi_reseaux_commune_multi_reseaux_normalise_plm():
    # Paris 1er (75101) -> normalisé vers 75056, les deux réseaux du même
    # arrondissement doivent se regrouper sous 75056 (§2.5.4)
    idx = load_udi_reseaux(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"))
    reseaux = idx["75056"]
    assert len(reseaux) == 2
    codes = {r.code_reseau for r in reseaux}
    assert codes == {"075000221", "075000999"}
