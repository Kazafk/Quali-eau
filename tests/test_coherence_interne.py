from pipeline.scoring import veto_sanitaire
from pipeline.cost_estimate import estimate_cost, VETO_THRESHOLDS


def test_veto_implique_toujours_palier_extreme():
    # Pour chacune des conditions de veto_sanitaire couvertes par VETO_THRESHOLDS,
    # un dépassement doit produire à la fois veto_sanitaire()=True (le score
    # est plafonné) ET estimate_cost(...)["niveau_severite"]=="extreme" (la
    # recommandation chiffrée reflète la même sévérité). Les valeurs testées
    # sont dérivées de VETO_THRESHOLDS (pas de littéraux dupliqués), pour que
    # ce test échoue si l'un des deux modules dérive sans l'autre.
    cas = [
        ("1340", "nitrates"),
        ("1339", "nitrites"),
        ("6276", "pesticide_total"),
        ("8847", "pfas"),
        ("_pesticide_molecule_max", "pesticide_molecule_max"),
    ]
    for code, kwarg in cas:
        valeur = VETO_THRESHOLDS[code] * 1.01
        kwargs = dict(
            bact_actif=False, nitrates=0.0, nitrites=0.0,
            pb=0.0, as_=0.0, cd=0.0,
            pesticide_molecule_max=0.0, pesticide_total=0.0, pfas=0.0,
        )
        kwargs[kwarg] = valeur
        assert veto_sanitaire(**kwargs) is True, code
        assert estimate_cost(code, valeur)["niveau_severite"] == "extreme", code
