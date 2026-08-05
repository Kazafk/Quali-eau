"""Parsing des fichiers DIS_PLV/DIS_RESULT/DIS_COM_UDI (§2.1) — format réel
vérifié le 05/08/2026 sur dis-2026.zip, PAS les noms de champs de l'API
Hub'eau (qui diffèrent). Aucune fonction ici ne connaît le moteur de scoring :
ce module ne fait que produire des pipeline.models.Mesure / ConclusionBacterio.
"""
import csv
from dataclasses import dataclass
from datetime import date

from pipeline.models import Mesure

# §2.5.5 — normalisation PLM (arrondissements -> commune parente)
PLM_ARRONDISSEMENTS: dict[str, str] = {}
for _code in range(75101, 75121):
    PLM_ARRONDISSEMENTS[str(_code)] = "75056"
for _code in range(69381, 69390):
    PLM_ARRONDISSEMENTS[str(_code)] = "69123"
for _code in range(13201, 13217):
    PLM_ARRONDISSEMENTS[str(_code)] = "13055"


def normaliser_code_insee(code_insee: str) -> str:
    """§2.5.5 — normalise les codes d'arrondissement PLM vers le code commune parent."""
    return PLM_ARRONDISSEMENTS.get(code_insee, code_insee)


def parse_valeur_rqana(rqana: str) -> tuple[float, bool]:
    """Parse le champ rqana de DIS_RESULT (résultat brut labo, §2.1).
    Retourne (valeur, sous_lq).

    ATTENTION (piège vérifié §2.1) : ne jamais utiliser valtraduite pour
    détecter le sous-LQ ou en tirer la valeur de LQ — valtraduite vaut
    0.000000 pour toute ligne sous LQ, quel que soit le paramètre. La LQ
    réelle et le signe `<` ne sont disponibles que dans rqana (décimales
    en virgule, ex. "<0,020")."""
    brut = rqana.strip()
    sous_lq = brut.startswith("<")
    if sous_lq:
        brut = brut[1:]
    valeur = float(brut.replace(",", "."))
    return valeur, sous_lq
