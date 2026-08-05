from pipeline.scoring import (
    score_durete,
    score_chlore_cosmetique,
    score_ph,
    score_cuivre,
    score_fer,
    score_manganese,
    score_metaux_depots,
    score_cosmetique,
)


def test_durete_reperes_spec():
    # Repères documentés en §3.2.1
    assert abs(score_durete(4.0) - 90.0) < 1e-9
    assert abs(score_durete(10.0) - 100.0) < 1e-9
    assert abs(score_durete(20.0) - 87.5) < 1e-9
    assert abs(score_durete(30.0) - 60.0) < 1e-9
    assert abs(score_durete(40.0) - 30.0) < 1e-9
    assert score_durete(50.0) == 0.0
    assert score_durete(60.0) == 0.0  # plancher, ne devient pas négatif


def test_durete_exemple_paris():
    # TH=30.19 -> 75 - 3.0*(30.19-25) = 59.43 (arrondi -> 59, cf. fiche §5.3)
    resultat = score_durete(30.19)
    assert abs(resultat - 59.43) < 1e-2


def test_durete_paliers_bas():
    assert score_durete(1.0) == 85.0
    assert score_durete(5.0) == 90.0
    assert score_durete(12.0) == 100.0


def test_chlore_cosmetique_bandes():
    assert score_chlore_cosmetique(0.03) == 100.0
    assert score_chlore_cosmetique(0.10) == 80.0
    assert score_chlore_cosmetique(0.20) == 50.0
    assert score_chlore_cosmetique(0.40) == 20.0


def test_ph_bandes():
    assert score_ph(7.0) == 100.0
    assert score_ph(6.6) == 85.0
    assert score_ph(7.6) == 80.0
    assert score_ph(8.0) == 55.0
    assert score_ph(9.0) == 25.0
    assert score_ph(6.0) == 25.0


def test_cuivre_bandes():
    assert score_cuivre(0.05) == 100.0
    assert abs(score_cuivre(0.3) - 75.0) < 1e-9  # milieu 0.1-0.5 -> 100-0.5*50=75
    assert score_cuivre(1.0) == 30.0


def test_fer_bandes():
    assert score_fer(30.0) == 100.0
    assert abs(score_fer(125.0) - 70.0) < 1e-9  # milieu 50-200 -> 100-0.5*60=70
    assert score_fer(300.0) == 20.0


def test_manganese_bandes():
    assert score_manganese(5.0) == 100.0
    assert abs(score_manganese(30.0) - 70.0) < 1e-9  # milieu 10-50 -> 70
    assert score_manganese(60.0) == 20.0


def test_metaux_depots_est_le_minimum():
    assert abs(score_metaux_depots(cu=0.08, fe=62.5, mn=5.0) - 95.0) < 1e-6


def test_score_cosmetique_exemple_spec_paris():
    # Reprend l'exemple de la fiche communale (§5.3) :
    # durete=59 (arrondi de 59.43), chlore=80, pH=100, metaux_depots=95 -> 76
    score, sous_scores = score_cosmetique(th=30.19, chlore_total=0.12, ph=7.0, cu=0.08, fe=62.5, mn=5.0)
    assert score == 76
    assert sous_scores == {
        "durete_calcaire": 59,
        "chlore_agressivite": 80,
        "respect_ph": 100,
        "metaux_depots": 95,
    }


def test_chlore_cosmetique_borne_0_05_alignee_sur_boisson():
    from pipeline.scoring import score_chlore_gout
    # A 0.05 mg/L pile, les deux fonctions doivent maintenant s'accorder (80, pas 100)
    assert score_chlore_cosmetique(0.05) == score_chlore_gout(0.05) == 80.0
