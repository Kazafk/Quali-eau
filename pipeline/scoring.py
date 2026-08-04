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
