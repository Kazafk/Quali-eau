import json
import os

from pipeline.compute_scores import main

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_pipeline_bout_en_bout_ecrit_fiches_json(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # main() attend DIS_PLV.txt / DIS_RESULT.txt / DIS_COM_UDI.txt (noms
    # génériques, sans suffixe d'année) dans raw_dir — on y copie les
    # fixtures qui reproduisent le format réel vérifié §2.1.
    import shutil
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"), raw_dir / "DIS_PLV.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), raw_dir / "DIS_RESULT.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"), raw_dir / "DIS_COM_UDI.txt")

    output_dir = tmp_path / "output"
    from datetime import date
    main(raw_dir=str(raw_dir), output_dir=str(output_dir), date_reference=date(2026, 8, 5))

    fiche_path = output_dir / "communes" / "34116.json"
    assert fiche_path.exists()
    fiche = json.loads(fiche_path.read_text(encoding="utf-8"))
    assert fiche["commune"]["code_insee"] == "34116"
    assert fiche["statut_donnees"] == "complet"
    assert "boisson" in fiche["scores"]
    assert "cosmetique" in fiche["scores"]

    index_path = output_dir / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["nb_communes_scorees"] >= 1


def test_pipeline_multi_annees_fusionne_via_main(tmp_path):
    import shutil
    from datetime import date

    raw_dir = tmp_path / "raw"
    (raw_dir / "2025").mkdir(parents=True)
    (raw_dir / "2026").mkdir(parents=True)
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_annee1.txt"), raw_dir / "2025" / "DIS_PLV_2025.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_annee1.txt"), raw_dir / "2025" / "DIS_RESULT_2025.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_annee2.txt"), raw_dir / "2026" / "DIS_PLV_2026.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_annee2.txt"), raw_dir / "2026" / "DIS_RESULT_2026.txt")

    udi_contenu = (
        "inseecommune,nomcommune,quartier,cdreseau,nomreseau,debutalim\n"
        '"12345","TESTVILLE","-","012000001","RESEAU TEST","2010-01-01"\n'
    )
    (raw_dir / "2026" / "DIS_COM_UDI_2026.txt").write_text(udi_contenu, encoding="utf-8")

    output_dir = tmp_path / "output"
    main(raw_dir=str(raw_dir), output_dir=str(output_dir), date_reference=date(2026, 8, 5))

    fiche = json.loads((output_dir / "communes" / "12345.json").read_text(encoding="utf-8"))
    assert fiche["statut_donnees"] == "complet"
    # nitrates 10 (2025) et 12 (2026), tous deux bien en dessous de 50 -> pas de veto,
    # peu importe le poids relatif exact des deux années dans la moyenne pondérée.
    assert fiche["scores"]["boisson"]["veto_sanitaire"] is False


def test_pipeline_ecrit_carte_scores_json(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    import shutil
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"), raw_dir / "DIS_PLV.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), raw_dir / "DIS_RESULT.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"), raw_dir / "DIS_COM_UDI.txt")

    output_dir = tmp_path / "output"
    from datetime import date
    main(raw_dir=str(raw_dir), output_dir=str(output_dir), date_reference=date(2026, 8, 5))

    carte_path = output_dir / "carte_scores.json"
    assert carte_path.exists()
    carte = json.loads(carte_path.read_text(encoding="utf-8"))
    assert "34116" in carte
    assert carte["34116"]["statut_donnees"] == "complet"
    assert isinstance(carte["34116"]["score_boisson"], int)
    # La fixture DIS_RESULT_sample.txt ne contient aucun code SANDRE pour
    # TH/chlore total/pH/métaux (1345/1399/1302/1392-1394), dont dépend
    # cosmetique.score : il est donc toujours None avec ces données, même si
    # la commune est "complet" (score_boisson, lui, ne dépend que de 1340/1506 ici).
    assert carte["34116"]["score_cosmetique"] is None
