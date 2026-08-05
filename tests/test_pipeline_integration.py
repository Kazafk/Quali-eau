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
