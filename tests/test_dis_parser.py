from pipeline.dis_parser import normaliser_code_insee, parse_valeur_rqana


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
