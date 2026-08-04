from pipeline.scoring import veto_sanitaire, score_boisson


def test_veto_declenche_par_nitrates():
    assert veto_sanitaire(
        bact_actif=False, nitrates=60.0, nitrites=0.05,
        pb=1.0, as_=1.0, cd=1.0,
        pesticide_molecule_max=0.01, pesticide_total=0.1, pfas=0.01,
    ) is True


def test_veto_non_declenche_cas_conforme():
    assert veto_sanitaire(
        bact_actif=False, nitrates=20.0, nitrites=0.05,
        pb=1.0, as_=1.0, cd=1.0,
        pesticide_molecule_max=0.01, pesticide_total=0.1, pfas=0.01,
    ) is False


def test_score_boisson_exemple_spec_paris():
    # Reprend l'exemple de la fiche communale (§5.3) : 95/85/80, sans veto -> 90
    assert score_boisson(s_securite=95, s_mineraux=85, s_gout=80, veto=False) == 90


def test_score_boisson_veto_nitrates_plafonne_reellement():
    # Régression du bug critique v1.1/v1.2 : nitrates=60mg/L (dépassement),
    # tout le reste parfait. P_nitrates = 50*(50/60) = 41.67 -> S_securite = 41.67.
    # S_mineraux : nitrates(0) 0.70 + chlorures(100) 0.15 + sulfates(100) 0.15 = 30.
    # S_gout = 100 (chlore/turbidite parfaits).
    # AVANT LE CORRECTIF : S_securite valait 100 (P_nitrates absent) et le score
    # affichait ~83 (classe B) malgré le dépassement réglementaire.
    # APRES LE CORRECTIF : le score doit être plafonné à ~42 (S_securite arrondi).
    score = score_boisson(s_securite=41.6666667, s_mineraux=30.0, s_gout=100.0, veto=True)
    assert score == 42
    assert score < 50  # doit rester dans le bas du barème, jamais "Bon" (classe B, >=80)
