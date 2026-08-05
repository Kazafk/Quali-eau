from pipeline.cost_estimate import estimate_cost


def test_durete_palier_modere():
    resultat = estimate_cost("1345", 20.0)
    assert resultat is not None
    assert resultat["niveau_severite"] == "modere"
    assert resultat["achat_eur"] == "700-900"


def test_durete_palier_eleve():
    # TH=30.19, cas de l'exemple Paris (§5.3) -> "eleve", 1200-1600
    resultat = estimate_cost("1345", 30.19)
    assert resultat is not None
    assert resultat["niveau_severite"] == "eleve"
    assert resultat["achat_eur"] == "1200-1600"


def test_durete_palier_extreme():
    resultat = estimate_cost("1345", 45.0)
    assert resultat is not None
    assert resultat["niveau_severite"] == "extreme"
    assert resultat["achat_eur"] == "1600-2000"


def test_durete_sous_seuil_pas_de_recommandation():
    assert estimate_cost("1345", 10.0) is None


def test_nitrates_palier_modere():
    # ratio = 20/50 = 0.4 < 0.5 -> modere
    resultat = estimate_cost("1340", 20.0)
    assert resultat["niveau_severite"] == "modere"
    assert resultat["materiel"] == "Filtre sous-évier à charbon actif"


def test_nitrates_palier_eleve():
    # ratio = 40/50 = 0.8 -> eleve
    resultat = estimate_cost("1340", 40.0)
    assert resultat["niveau_severite"] == "eleve"


def test_nitrates_palier_extreme_veto_atteint():
    # ratio = 60/50 = 1.2 >= 1.0 -> extreme
    resultat = estimate_cost("1340", 60.0)
    assert resultat["niveau_severite"] == "extreme"
    assert resultat["materiel"] == "Osmoseur à pompe de perméat + reminéralisation"


def test_pfas_palier_eleve_borne():
    # ratio = 0.05/0.1 = 0.5 -> eleve (borne inclusive)
    resultat = estimate_cost("8847", 0.05)
    assert resultat["niveau_severite"] == "eleve"


def test_code_inconnu_retourne_none():
    assert estimate_cost("9999", 42.0) is None
