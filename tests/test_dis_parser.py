import os
from datetime import date

from pipeline.dis_parser import normaliser_code_insee, parse_valeur_rqana, load_prelevements, load_udi_reseaux, iter_mesures


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


def test_iter_mesures_valeur_quantifiee():
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    nitrates = [(insee, m) for insee, code, m in resultats if code == "1340"]
    assert len(nitrates) == 4  # REF-001, REF-002, REF-003, REF-004 (REF-999 exclu, pas de jointure PLV)
    insee, mesure = nitrates[0]
    assert insee == "34116"
    assert mesure.valeur == 14.0
    assert mesure.sous_lq is False
    assert mesure.date_prelevement == date(2026, 2, 10)


def test_iter_mesures_sous_lq_lit_rqana_pas_valtraduite():
    # BUG POTENTIEL évité : valtraduite="0.000000" pour ce glyphosate sous LQ.
    # Si le parseur lisait valtraduite au lieu de rqana, on obtiendrait
    # (valeur=0.0, sous_lq=False) au lieu de (0.020, True) — silencieusement faux.
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    glyphosate = [(insee, m) for insee, code, m in resultats if code == "1506"]
    assert len(glyphosate) == 1
    _, mesure = glyphosate[0]
    assert mesure.sous_lq is True
    assert abs(mesure.valeur - 0.020) < 1e-9


def test_iter_mesures_ignore_referenceprel_inconnu():
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    # 7 lignes dans la fixture (REF-001 x2, REF-002, REF-999, ligne sans cdparametre,
    # REF-003, REF-004) ; REF-999 (pas de jointure PLV) et la ligne sans cdparametre
    # doivent être exclues.
    assert len(resultats) == 5  # 4 nitrates (REF-001..REF-004) + 1 glyphosate (REF-001)


def test_iter_mesures_ignore_ligne_sans_code_parametre():
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    codes = {code for _, code, _ in resultats}
    assert "" not in codes


def test_load_prelevements_ignore_date_malformee(tmp_path):
    contenu = (
        "cddept,cdreseau,inseecommuneprinc,nomcommuneprinc,cdreseauamont,nomreseauamont,"
        "pourcentdebit,referenceprel,dateprel,heureprel,conclusionprel,ugelib,distrlib,"
        "moalib,plvconformitebacterio,plvconformitechimique,plvconformitereferencebact,"
        "plvconformitereferencechim\n"
        '"034","034000123","34116","GRABELS","","","","REF-BAD","00/00/0000","09h00",'
        '"x","","","","C","C","C","C"\n'
        '"034","034000123","34116","GRABELS","","","","REF-OK","2026-02-10","09h00",'
        '"x","","","","C","C","C","C"\n'
    )
    chemin = tmp_path / "DIS_PLV_bad.txt"
    chemin.write_text(contenu, encoding="utf-8")
    idx = load_prelevements(str(chemin))
    assert "REF-BAD" not in idx
    assert "REF-OK" in idx


def test_charger_prelevements_multi_fusionne_plusieurs_annees():
    from pipeline.dis_parser import charger_prelevements_multi
    idx = charger_prelevements_multi([
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee1.txt"),
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee2.txt"),
    ])
    assert set(idx) == {"REF-A1", "REF-A2"}
    assert idx["REF-A1"].code_insee == "12345"
    assert idx["REF-A2"].code_insee == "12345"


def test_iter_mesures_multi_chaine_plusieurs_annees():
    from pipeline.dis_parser import charger_prelevements_multi, iter_mesures_multi
    prelevements = charger_prelevements_multi([
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee1.txt"),
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee2.txt"),
    ])
    resultats = list(iter_mesures_multi([
        os.path.join(FIXTURES_DIR, "DIS_RESULT_annee1.txt"),
        os.path.join(FIXTURES_DIR, "DIS_RESULT_annee2.txt"),
    ], prelevements))
    valeurs = sorted(m.valeur for _, code, m in resultats if code == "1340")
    assert valeurs == [10.0, 12.0]
