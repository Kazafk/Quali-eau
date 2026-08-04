import math


def arrondi(x: float) -> int:
    """Arrondi à l'entier, moitié vers le haut (§3 intro)."""
    return math.floor(x + 0.5)


def score_bacteriologie(conforme_dernier: bool, resolu: bool) -> float:
    """§3.1.1 P_bact."""
    if conforme_dernier:
        return 100.0
    if resolu:
        return 50.0
    return 0.0


def score_pesticides(total: float, molecule_max: float) -> float:
    """§3.1.1 P_pest."""
    if total > 0.5 or molecule_max > 0.1:
        candidats = []
        if total > 0.5:
            candidats.append(50.0 * (0.5 / total))
        if molecule_max > 0.1:
            candidats.append(50.0 * (0.1 / molecule_max))
        return max(0.0, min(candidats))
    if total < 0.05 and molecule_max < 0.05:
        return 100.0
    # Bande linéaire 100 (à 0.05) -> 70 (à 0.5), bornée pour les cas où
    # total < 0.05 mais molecule_max est entre 0.05 et 0.1.
    return min(100.0, max(70.0, 100.0 - (total - 0.05) / 0.45 * 30.0))


def score_pfas(valeur: float) -> float:
    """§3.1.1 P_pfas."""
    if valeur < 0.02:
        return 100.0
    if valeur <= 0.10:
        return 90.0 - (valeur - 0.02) / 0.08 * 30.0
    return min(30.0, 60.0 * 0.10 / valeur)


def score_metal(valeur: float, rq: float, lq: float) -> float:
    """§3.1.1 P_métaux, pour un métal donné (Pb/As/Cd/Ni)."""
    if valeur <= rq:
        return 100.0
    if valeur <= lq:
        return 100.0 - (valeur - rq) / (lq - rq) * 30.0
    return max(0.0, 70.0 * lq / valeur)


def score_nitrates_securite(nitrates: float, nitrites: float) -> float:
    """§3.1.1 P_nitrates (ajouté en v1.3 — corrige le veto sanitaire
    qui n'avait auparavant aucun effet sur les dépassements nitrates/nitrites,
    P_nitrates étant absent de S_sécurité en v1.1/v1.2)."""
    notes = []
    if nitrates > 50:
        notes.append(50.0 * (50.0 / nitrates))
    if nitrites > 0.1:
        notes.append(50.0 * (0.1 / nitrites))
    if not notes:
        return 100.0
    return max(0.0, min(notes))


def score_securite(p_bact: float, p_pest: float, p_pfas: float, p_metaux: float, p_nitrates: float) -> float:
    """§3.1.1 S_sécurité = min(P_bact, P_pest, P_pfas, P_métaux, P_nitrates)."""
    return min(p_bact, p_pest, p_pfas, p_metaux, p_nitrates)


def score_nitrates_mineraux(valeur: float) -> float:
    """§3.1.2 N_nitrates (gustatif/confort — distinct de P_nitrates en §3.1.1)."""
    if valeur < 10:
        return 100.0
    if valeur < 25:
        return 85.0
    if valeur < 40:
        return 65.0
    if valeur <= 50:
        return 40.0
    return 0.0


def score_chlorures(valeur: float) -> float:
    """§3.1.2 N_chlorures."""
    if valeur <= 100:
        return 100.0
    if valeur <= 200:
        return 100.0 - (valeur - 100) / 100.0 * 60.0
    return max(0.0, 40.0 * 200.0 / valeur)


def score_sulfates(valeur: float) -> float:
    """§3.1.2 N_sulfates."""
    if valeur <= 150:
        return 100.0
    if valeur <= 250:
        return 100.0 - (valeur - 150) / 100.0 * 60.0
    return max(0.0, 40.0 * 250.0 / valeur)


def score_mineraux(nitrates: float, chlorures: float, sulfates: float) -> float:
    """§3.1.2 S_mineraux = 0.70*N_nitrates + 0.15*N_chlorures + 0.15*N_sulfates."""
    return (0.70 * score_nitrates_mineraux(nitrates)
            + 0.15 * score_chlorures(chlorures)
            + 0.15 * score_sulfates(sulfates))


def score_chlore_gout(valeur: float) -> float:
    """§3.1.3 N_chlore."""
    if valeur < 0.05:
        return 100.0
    if valeur <= 0.15:
        return 80.0
    if valeur <= 0.30:
        return 50.0
    return 20.0


def score_turbidite(valeur: float) -> float:
    """§3.1.3 N_turbidite."""
    if valeur < 0.3:
        return 100.0
    if valeur <= 1.0:
        return 80.0
    if valeur <= 2.0:
        return 55.0
    return 30.0


def score_gout(chlore: float, turbidite: float) -> float:
    """§3.1.3 S_gout = 0.60*N_chlore + 0.40*N_turbidite."""
    return 0.60 * score_chlore_gout(chlore) + 0.40 * score_turbidite(turbidite)


def veto_sanitaire(bact_actif: bool, nitrates: float, nitrites: float,
                    pb: float, as_: float, cd: float,
                    pesticide_molecule_max: float, pesticide_total: float,
                    pfas: float) -> bool:
    """§3.1 — conditions de veto sanitaire (facteur limitant)."""
    return (
        bact_actif
        or nitrates > 50 or nitrites > 0.1
        or pb > 10 or as_ > 10 or cd > 5
        or pesticide_molecule_max > 0.1 or pesticide_total > 0.5
        or pfas > 0.1
    )


def score_boisson(s_securite: float, s_mineraux: float, s_gout: float, veto: bool) -> int:
    """§3.1 S_boisson = 0.55*S_securite + 0.25*S_mineraux + 0.20*S_gout,
    plafonné à S_securite en cas de veto sanitaire (correctif v1.3 : ce
    plafond n'a d'effet réel que parce que P_nitrates fait maintenant
    partie de S_securite, cf. score_nitrates_securite)."""
    s_securite_r = arrondi(s_securite)
    s_mineraux_r = arrondi(s_mineraux)
    s_gout_r = arrondi(s_gout)
    brut = 0.55 * s_securite_r + 0.25 * s_mineraux_r + 0.20 * s_gout_r
    if veto:
        brut = min(brut, s_securite_r)
    return arrondi(max(0.0, min(100.0, brut)))


def score_durete(th: float) -> float:
    """§3.2.1 S_durete — par paliers en dessous de 15 °fH, continue au-delà
    (correction de formulation v1.3 : la fonction n'est PAS continue en
    dessous de 15 °fH, contrairement à ce qu'affirmait la v1.1/v1.2)."""
    if th < 3:
        return 85.0
    if th < 8:
        return 90.0
    if th <= 15:
        return 100.0
    if th <= 25:
        return 100.0 - 2.5 * (th - 15)
    if th <= 35:
        return 75.0 - 3.0 * (th - 25)
    return max(0.0, 45.0 - 3.0 * (th - 35))


def score_chlore_cosmetique(valeur: float) -> float:
    """§3.2.2 S_chlore (chlore total 1399, même barème que N_chlore boisson)."""
    if valeur <= 0.05:
        return 100.0
    if valeur <= 0.15:
        return 80.0
    if valeur <= 0.30:
        return 50.0
    return 20.0


def score_ph(ph: float) -> float:
    """§3.2.3 S_pH."""
    if 6.8 <= ph <= 7.4:
        return 100.0
    if 6.5 <= ph < 6.8:
        return 85.0
    if 7.4 < ph <= 7.8:
        return 80.0
    if 7.8 < ph <= 8.2:
        return 55.0
    return 25.0


def score_cuivre(valeur: float) -> float:
    """§3.2.4 N_Cu."""
    if valeur < 0.1:
        return 100.0
    if valeur <= 0.5:
        return 100.0 - (valeur - 0.1) / 0.4 * 50.0
    return 30.0


def score_fer(valeur: float) -> float:
    """§3.2.4 N_Fe."""
    if valeur < 50:
        return 100.0
    if valeur <= 200:
        return 100.0 - (valeur - 50) / 150.0 * 60.0
    return 20.0


def score_manganese(valeur: float) -> float:
    """§3.2.4 N_Mn."""
    if valeur < 10:
        return 100.0
    if valeur <= 50:
        return 100.0 - (valeur - 10) / 40.0 * 60.0
    return 20.0


def score_metaux_depots(cu: float, fe: float, mn: float) -> float:
    """§3.2.4 S_metaux_depots = min(N_Cu, N_Fe, N_Mn)."""
    return min(score_cuivre(cu), score_fer(fe), score_manganese(mn))
