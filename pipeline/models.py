from dataclasses import dataclass
from datetime import date


@dataclass
class Mesure:
    """Une mesure agrégée pour un paramètre donné (déjà résolue depuis DIS_RESULT)."""
    valeur: float
    sous_lq: bool
    date_prelevement: date


@dataclass
class ConclusionBacterio:
    """Une conclusion de conformité bactériologique officielle (DIS_PLV)."""
    date_prelevement: date
    conforme: bool  # True = 'C', False = 'N'
