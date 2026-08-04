from datetime import date

from pipeline.aggregation import ponderation_temporelle, moyenne_ponderee
from pipeline.models import Mesure


def test_ponderation_temporelle_demi_vie_180_jours():
    # A la demi-vie (180 jours), le poids doit valoir exactement 0.5.
    poids = ponderation_temporelle(180)
    assert abs(poids - 0.5) < 1e-9


def test_ponderation_temporelle_jour_zero():
    assert ponderation_temporelle(0) == 1.0


def test_moyenne_ponderee_deux_mesures():
    # v=10 aujourd'hui (poids 1.0), v=20 il y a 180 jours (poids 0.5)
    # attendu : (1.0*10 + 0.5*20) / (1.0 + 0.5) = 20 / 1.5 = 13.333...
    date_ref = date(2026, 6, 15)
    mesures = [
        Mesure(valeur=10.0, sous_lq=False, date_prelevement=date(2026, 6, 15)),
        Mesure(valeur=20.0, sous_lq=False, date_prelevement=date(2025, 12, 17)),  # -180j
    ]
    resultat = moyenne_ponderee(mesures, date_ref)
    assert resultat is not None
    assert abs(resultat - 13.3333333) < 1e-4


def test_moyenne_ponderee_liste_vide():
    assert moyenne_ponderee([], date(2026, 6, 15)) is None
