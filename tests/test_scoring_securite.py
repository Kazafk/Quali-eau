from pipeline.scoring import (
    arrondi,
    score_bacteriologie,
    score_pesticides,
    score_pfas,
    score_metal,
    score_nitrates_securite,
    score_securite,
)


def test_arrondi_moitie_monte():
    assert arrondi(89.5) == 90
    assert arrondi(75.8) == 76
    assert arrondi(59.43) == 59


def test_bacteriologie_conforme():
    assert score_bacteriologie(conforme_dernier=True, resolu=False) == 100.0


def test_bacteriologie_resolue():
    assert score_bacteriologie(conforme_dernier=False, resolu=True) == 50.0


def test_bacteriologie_active():
    assert score_bacteriologie(conforme_dernier=False, resolu=False) == 0.0


def test_pesticides_parfait():
    assert score_pesticides(total=0.03, molecule_max=0.01) == 100.0


def test_pesticides_bande_lineaire():
    # total=0.05 -> 100, total=0.5 -> 70 (bornes de la bande linéaire)
    assert abs(score_pesticides(total=0.05, molecule_max=0.02) - 100.0) < 1e-9
    assert abs(score_pesticides(total=0.5, molecule_max=0.05) - 70.0) < 1e-9
    # milieu de bande : total=0.275 -> 85
    assert abs(score_pesticides(total=0.275, molecule_max=0.05) - 85.0) < 1e-6


def test_pesticides_depassement_total():
    # total=1.0 > 0.5 -> 50 * (0.5/1.0) = 25
    assert abs(score_pesticides(total=1.0, molecule_max=0.05) - 25.0) < 1e-9


def test_pesticides_depassement_molecule():
    # molecule=0.2 > 0.1 -> 50 * (0.1/0.2) = 25, même si le total est bas
    assert abs(score_pesticides(total=0.1, molecule_max=0.2) - 25.0) < 1e-9


def test_pfas_parfait():
    assert score_pfas(0.01) == 100.0


def test_pfas_bande_lineaire():
    assert abs(score_pfas(0.02) - 90.0) < 1e-9
    assert abs(score_pfas(0.10) - 60.0) < 1e-9


def test_pfas_depassement_plafonne():
    # 0.10 -> 60 (borne exacte de la bande linéaire, cf. test précédent)
    # 0.20 -> 60*0.10/0.20 = 30 (plafond atteint)
    assert abs(score_pfas(0.20) - 30.0) < 1e-9
    # 0.15 -> 60*0.10/0.15 = 40, sous le plafond de 30 -> doit être plafonné à 30
    assert abs(score_pfas(0.15) - 30.0) < 1e-9


def test_metal_conforme():
    assert score_metal(valeur=0.5, rq=1.0, lq=2.0) == 100.0


def test_metal_interpolation():
    # RQ=1, LQ=2 : à mi-chemin (1.5) -> 100 - 0.5/1.0*30 = 85
    assert abs(score_metal(valeur=1.5, rq=1.0, lq=2.0) - 85.0) < 1e-9


def test_metal_depassement():
    # LQ=2, valeur=4 -> 70 * 2/4 = 35
    assert abs(score_metal(valeur=4.0, rq=1.0, lq=2.0) - 35.0) < 1e-9


def test_nitrates_securite_conforme():
    assert score_nitrates_securite(nitrates=40.0, nitrites=0.05) == 100.0


def test_nitrates_securite_depassement_nitrates():
    # BUG CRITIQUE v1.1/v1.2 : ce test aurait été impossible à écrire correctement
    # avant le correctif v1.3, car P_nitrates n'existait pas.
    # 60 mg/L > 50 -> 50 * (50/60) = 41.666...
    resultat = score_nitrates_securite(nitrates=60.0, nitrites=0.05)
    assert abs(resultat - 41.6666667) < 1e-4


def test_nitrates_securite_depassement_nitrites():
    # 0.2 mg/L > 0.1 -> 50 * (0.1/0.2) = 25
    resultat = score_nitrates_securite(nitrates=20.0, nitrites=0.2)
    assert abs(resultat - 25.0) < 1e-9


def test_nitrates_securite_double_depassement_prend_le_pire():
    # nitrates -> 50*50/60=41.67 ; nitrites -> 50*0.1/0.2=25 -> min = 25
    resultat = score_nitrates_securite(nitrates=60.0, nitrites=0.2)
    assert abs(resultat - 25.0) < 1e-9


def test_securite_est_le_minimum():
    assert score_securite(p_bact=100, p_pest=100, p_pfas=100, p_metaux=100, p_nitrates=41.67) == 41.67
    assert score_securite(p_bact=0, p_pest=100, p_pfas=100, p_metaux=100, p_nitrates=100) == 0
