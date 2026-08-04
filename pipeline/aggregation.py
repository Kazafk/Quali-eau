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
