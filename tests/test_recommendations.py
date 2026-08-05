from pipeline.recommendations import generate_recommendations


def test_recommandations_exemple_paris():
    # Reprend l'exemple de la fiche communale (§5.3) : TH=30.19 (>25, palier "eleve"),
    # chlore libre=0.12 (>0.05 -> carafe), chlore total=0.12 (<=0.15 -> pas de pommeau),
    # nitrates=18.4 (<=25 -> pas de reco nitrates), pas de pollution chimique significative.
    mesures = {
        "1345": 30.19,
        "1398": 0.12,
        "1399": 0.12,
        "1340": 18.4,
        "6276": 0.01,
        "8847": 0.005,
        "_pesticide_molecule_max": 0.0,
    }
    recos = generate_recommendations(mesures, bact_actif=False)
    types = {r["type"] for r in recos}
    assert types == {"carafe", "adoucisseur"}

    adoucisseur = next(r for r in recos if r["type"] == "adoucisseur")
    assert adoucisseur["estimation_cout"]["niveau_severite"] == "eleve"
    assert adoucisseur["estimation_cout"]["achat_eur"] == "1200-1600"


def test_recommandations_bacterio_active_prioritaire():
    mesures = {"1345": 5.0}
    recos = generate_recommendations(mesures, bact_actif=True)
    assert recos[0]["type"] == "alerte_bacteriologique"


def test_recommandations_pollution_chimique_declenche_filtration():
    mesures = {
        "1345": 5.0,
        "6276": 0.4,
        "8847": 0.01,
        "_pesticide_molecule_max": 0.02,
    }
    recos = generate_recommendations(mesures, bact_actif=False)
    filtration = next(r for r in recos if r["type"] == "filtration_chimique")
    # total pesticides = 0.4 -> ratio 0.8 vs seuil 0.5 -> "eleve"
    assert filtration["estimation_cout"]["niveau_severite"] == "eleve"


def test_recommandations_eau_parfaite_liste_vide():
    mesures = {
        "1345": 10.0, "1398": 0.02, "1399": 0.02, "1340": 5.0,
        "6276": 0.0, "8847": 0.0, "_pesticide_molecule_max": 0.0,
    }
    assert generate_recommendations(mesures, bact_actif=False) == []


def test_recommandations_molecule_pesticide_domine_la_severite():
    # BUG CRITIQUE (revue finale) : avant le correctif, seuls pesticide_total et
    # pfas étaient comparés pour choisir la sévérité — une molécule individuelle
    # 5x au-dessus de sa limite (0.1 µg/L) avec un total/PFAS bas ne produisait
    # qu'une recommandation "modere" (filtre à charbon, 80-120€) alors que
    # veto_sanitaire() classe ce cas en "extreme".
    mesures = {
        "1345": 5.0,
        "6276": 0.02,
        "8847": 0.005,
        "_pesticide_molecule_max": 0.5,
    }
    recos = generate_recommendations(mesures, bact_actif=False)
    filtration = next(r for r in recos if r["type"] == "filtration_chimique")
    assert filtration["estimation_cout"]["niveau_severite"] == "extreme"


def test_recommandations_nitrites_declenche_alerte():
    mesures = {"1345": 5.0, "1339": 0.3}
    recos = generate_recommendations(mesures, bact_actif=False)
    nitrites_reco = next(r for r in recos if r["type"] == "nitrites_alerte")
    assert nitrites_reco["estimation_cout"]["niveau_severite"] == "extreme"


def test_recommandations_nitrates_biberons():
    mesures = {"1345": 5.0, "1340": 30.0}
    recos = generate_recommendations(mesures, bact_actif=False)
    reco = next(r for r in recos if r["type"] == "nitrates_biberons")
    assert reco["usage"] == "boisson"


def test_recommandations_pommeau_filtrant():
    mesures = {"1345": 5.0, "1399": 0.25}
    recos = generate_recommendations(mesures, bact_actif=False)
    reco = next(r for r in recos if r["type"] == "pommeau_filtrant")
    assert reco["usage"] == "cosmetique"


def test_recommandations_metaux_traces():
    mesures = {"1345": 5.0, "1393": 300.0}
    recos = generate_recommendations(mesures, bact_actif=False)
    reco = next(r for r in recos if r["type"] == "metaux_traces")
    assert reco["usage"] == "cosmetique"
