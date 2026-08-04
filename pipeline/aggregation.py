import math
from datetime import date

from pipeline.models import Mesure

# Demi-vie 180 jours (§2.5.2)
LAMBDA_PONDERATION = math.log(2) / 180


def ponderation_temporelle(delta_jours: int) -> float:
    """w_i = e^(-lambda * delta_t_i), lambda = ln(2)/180 (demi-vie 180 jours)."""
    return math.exp(-LAMBDA_PONDERATION * delta_jours)


def moyenne_ponderee(mesures: list[Mesure], date_reference: date) -> float | None:
    """Moyenne pondérée par ancienneté (§2.5.2). None si aucune mesure."""
    if not mesures:
        return None
    poids_total = 0.0
    somme_ponderee = 0.0
    for m in mesures:
        delta_jours = (date_reference - m.date_prelevement).days
        poids = ponderation_temporelle(delta_jours)
        poids_total += poids
        somme_ponderee += poids * m.valeur
    return somme_ponderee / poids_total


def valeur_somme_reglementaire(total: Mesure | None, composantes: list[Mesure]) -> float | None:
    """Règle de priorité §2.5.3 (v1.3) : le champ total fait foi s'il est
    numérique ; sinon recalcul par sommation des composantes avec LQ/2
    pour celles sous LQ.
    """
    if total is not None and not total.sous_lq:
        return total.valeur
    if not composantes:
        return None
    total_calcule = 0.0
    for c in composantes:
        total_calcule += (c.valeur / 2) if c.sous_lq else c.valeur
    return total_calcule
