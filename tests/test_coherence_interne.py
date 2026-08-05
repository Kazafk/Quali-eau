from pipeline.scoring import veto_sanitaire
from pipeline.cost_estimate import estimate_cost, VETO_THRESHOLDS


def test_veto_implique_toujours_palier_extreme():
    # Pour chacune des conditions de veto_sanitaire couvertes par VETO_THRESHOLDS,
    # un dépassement doit produire la même sévérité dans le score (veto=True)
    # et dans la recommandation chiffrée (niveau_severite="extreme").
    cas = [
        ("1340", 50.01),   # nitrates
        ("1339", 0.11),    # nitrites
        ("6276", 0.51),    # pesticides total
        ("8847", 0.11),    # PFAS
        ("_pesticide_molecule_max", 0.11),  # pesticide molécule individuelle
    ]
    for code, valeur in cas:
        assert estimate_cost(code, valeur)["niveau_severite"] == "extreme", code
