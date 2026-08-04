from datetime import date

from pipeline.aggregation import ponderation_temporelle, moyenne_ponderee, valeur_somme_reglementaire
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


def test_somme_reglementaire_total_numerique_fait_foi():
    # Le champ total est numérique (non sous LQ) : il fait foi, peu importe les composantes.
    total = Mesure(valeur=0.30, sous_lq=False, date_prelevement=date(2026, 6, 15))
    composantes = [Mesure(valeur=999.0, sous_lq=False, date_prelevement=date(2026, 6, 15))]
    assert valeur_somme_reglementaire(total, composantes) == 0.30


def test_somme_reglementaire_recalcul_par_composantes():
    # Total absent -> recalcul : LQ/2 pour les composantes sous LQ, valeur brute sinon.
    composantes = [
        Mesure(valeur=0.05, sous_lq=True, date_prelevement=date(2026, 6, 15)),   # -> 0.025
        Mesure(valeur=0.08, sous_lq=False, date_prelevement=date(2026, 6, 15)),  # -> 0.08
    ]
    resultat = valeur_somme_reglementaire(None, composantes)
    assert resultat is not None
    assert abs(resultat - 0.105) < 1e-9


def test_somme_reglementaire_total_sous_lq_retombe_sur_composantes():
    total = Mesure(valeur=0.5, sous_lq=True, date_prelevement=date(2026, 6, 15))
    composantes = [Mesure(valeur=0.05, sous_lq=True, date_prelevement=date(2026, 6, 15))]
    resultat = valeur_somme_reglementaire(total, composantes)
    assert abs(resultat - 0.025) < 1e-9


def test_somme_reglementaire_aucune_donnee():
    assert valeur_somme_reglementaire(None, []) is None
