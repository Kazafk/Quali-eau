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


@dataclass
class PrelevementInfo:
    code_insee: str
    code_reseau: str
    date_prelevement: date
    conforme_bacterio: bool | None
    conforme_chimique: bool | None


def _parse_conformite(valeur: str) -> bool | None:
    v = valeur.strip()
    if v == "C":
        return True
    if v == "N":
        return False
    return None


def load_prelevements(plv_path: str) -> dict[str, PrelevementInfo]:
    """Parse DIS_PLV_*.txt (§2.1) en index referenceprel -> PrelevementInfo.
    Applique la normalisation PLM (§2.5.5) sur inseecommuneprinc."""
    index: dict[str, PrelevementInfo] = {}
    with open(plv_path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            ref = row.get("referenceprel", "").strip()
            insee = row.get("inseecommuneprinc", "").strip()
            date_str = row.get("dateprel", "").strip()
            if not ref or not insee or not date_str:
                continue
            try:
                date_prelevement = date.fromisoformat(date_str[:10])
            except ValueError:
                continue
            index[ref] = PrelevementInfo(
                code_insee=normaliser_code_insee(insee),
                code_reseau=row.get("cdreseau", "").strip(),
                date_prelevement=date_prelevement,
                conforme_bacterio=_parse_conformite(row.get("plvconformitebacterio", "")),
                conforme_chimique=_parse_conformite(row.get("plvconformitechimique", "")),
            )
    return index


@dataclass
class ReseauRef:
    code_reseau: str
    nom_reseau: str


def load_udi_reseaux(udi_path: str) -> dict[str, list["ReseauRef"]]:
    """Parse DIS_COM_UDI_*.txt (§2.1) en index code_insee -> réseaux (§2.5.4).
    Applique la normalisation PLM : les réseaux des différents arrondissements
    d'une même ville PLM se regroupent sous le code commune parent."""
    index: dict[str, list[ReseauRef]] = {}
    with open(udi_path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            insee = normaliser_code_insee(row.get("inseecommune", "").strip())
            code_reseau = row.get("cdreseau", "").strip()
            nom_reseau = row.get("nomreseau", "").strip()
            if not insee or not code_reseau:
                continue
            index.setdefault(insee, []).append(ReseauRef(code_reseau=code_reseau, nom_reseau=nom_reseau))
    return index


def iter_mesures(result_path: str, prelevements: dict[str, "PrelevementInfo"]):
    """Parse DIS_RESULT_*.txt (§2.1) en flux (générateur, pas de chargement
    intégral en mémoire — ces fichiers pèsent plusieurs centaines de Mo).
    Jointure via referenceprel. Yield (code_insee, code_parametre, Mesure).

    Ignore (§2.1) : lignes sans referenceprel connu dans `prelevements`,
    lignes sans cdparametre (lignes de conclusion/résiduelles), lignes
    dont rqana est vide ou non parseable.
    """
    with open(result_path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            ref = row.get("referenceprel", "").strip()
            info = prelevements.get(ref)
            if info is None:
                continue
            code_parametre = row.get("cdparametre", "").strip()
            if not code_parametre:
                continue
            rqana = row.get("rqana", "").strip()
            if not rqana:
                continue
            try:
                valeur, sous_lq = parse_valeur_rqana(rqana)
            except ValueError:
                continue
            mesure = Mesure(valeur=valeur, sous_lq=sous_lq, date_prelevement=info.date_prelevement)
            yield info.code_insee, code_parametre, mesure


def charger_prelevements_multi(plv_paths: list[str]) -> dict[str, "PrelevementInfo"]:
    """Fusionne plusieurs fichiers DIS_PLV annuels (§2.1) en un seul index
    referenceprel -> PrelevementInfo."""
    index: dict[str, PrelevementInfo] = {}
    for chemin in plv_paths:
        index.update(load_prelevements(chemin))
    return index


def iter_mesures_multi(result_paths: list[str], prelevements: dict):
    """Chaîne le flux de plusieurs fichiers DIS_RESULT annuels (générateur,
    ne charge aucun fichier entier en mémoire — cf. iter_mesures)."""
    for chemin in result_paths:
        yield from iter_mesures(chemin, prelevements)
