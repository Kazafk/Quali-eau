# Pipeline d'Ingestion DIS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse the real data.gouv DIS export files (DIS_PLV/DIS_RESULT/DIS_COM_UDI) into the `Mesure`/`ConclusionBacterio` objects the already-built scoring engine expects, then orchestrate window selection, multi-réseau/PLM resolution and the full scoring+recommendation call chain into the commune-fiche JSON (§5.3), without a map/geometry component.

**Architecture:** Two new modules — `pipeline/dis_parser.py` (pure parsing: CSV → structured records, streaming, no knowledge of scoring) and `pipeline/compute_scores.py` (orchestration: window/réseau selection + wiring into `pipeline.scoring`/`pipeline.aggregation`/`pipeline.recommendations`, already built and tested) — plus an adapted `pipeline/download_data.py` (network I/O, adapted from the proven *Pesticides Water Map* precursor). All parsing logic is validated against small **fixture files that reproduce the real, verified DIS column format byte-for-byte** (not against a live 900 Mo download), so every test in this plan runs in milliseconds with no network access.

**Tech Stack:** Python 3.12, stdlib `csv`/`zipfile`/`dataclasses`/`datetime` + `requests` (already a precursor-proven dependency) for `download_data.py`, `pytest` (+ `pytest`'s built-in `monkeypatch` fixture — no new test dependency) for mocking network calls.

## Global Constraints

- All parsing must match the **real, verified** DIS batch format from `SPECIFICATION.md` v1.5.0 §2.1 — not the Hub'eau API's field names, which differ (e.g. batch `plvconformitebacterio` vs API `conformite_limites_bact_prelevement`).
- **LQ trap (critical, §2.1):** `valtraduite` is `0.000000` for every sub-LQ row, regardless of parameter. The actual LQ value and the `<` sign live only in `rqana` (French comma-decimal, e.g. `"<0,020"`). Every parsing function in this plan must read `rqana`, never `valtraduite`, to detect sous-LQ.
- Reuse `pipeline.models.Mesure(valeur, sous_lq, date_prelevement)` and `pipeline.models.ConclusionBacterio(date_prelevement, conforme)` — do not invent parallel types.
- Reuse the already-built, already-tested scoring engine (`pipeline.scoring`, `pipeline.aggregation`, `pipeline.recommendations`) exactly as it exists today (post-fix, `score_metal_toxique(valeur, lq)` — no RQ parameter). Do not modify those modules in this plan.
- Metal LQ values (§2.3, no RQ — v1.5 correction): Plomb (`1382`) 10 µg/L, Arsenic (`1369`) 10 µg/L, Cadmium (`1388`) 5 µg/L, Nickel (`1386`) 20 µg/L.
- Pesticide molecule codes (§2.4, 17 validated codes): `1107, 1108, 1113, 1129, 1177, 1208, 1209, 1473, 1506, 1667, 1877, 1907, 2974, 6894, 6895, 7717, 8865`.
- PLM normalization (§2.5.5): Paris arrondissements `75101`–`75120` → `75056`; Lyon `69381`–`69389` → `69123`; Marseille `13201`–`13216` → `13055`.
- Window selection (§2.5.1): 12 months (365 days), extended to 24 months (730 days) if fewer than 4 sampling dates fall in the 12-month window.
- No `national.geojson`/map geometry work in this plan (see Out of Scope) — only `communes/{code_insee}.json` and a minimal `index.json`.
- No external network access during tests — every test uses fixture files or `monkeypatch`-mocked `requests` calls.

## ⚠️ Open interpretation flagged for human review

§3.1.1 defines three bacteriological cases ("dernier conforme" = 100, "non-conformité résolue" = 50, "non-conformité active" = 0), but the real `DIS_PLV` export has no field distinguishing a routine sample from a control/follow-up sample. Task 6 implements a specific, documented reading (see its docstring) to make "résolue" reachable at all rather than dead code — **flag this to the human before merging Task 6**; it's a judgment call, not a verified fact like the other decisions in this plan.

---

### Task 1: Adapter `pipeline/download_data.py` (téléchargement + extraction)

**Files:**
- Create: `pipeline/download_data.py`
- Test: `tests/test_download_data.py`

**Interfaces:**
- Produces: `pipeline.download_data.ZIPS: list[dict]`, `pipeline.download_data.download_all(force: bool = False) -> None`, `pipeline.download_data._extract(zip_path: str, year: int) -> str`

This is adapted from the proven `pesticides-water-map/pipeline/download_data.py` (same data.gouv dataset, same file structure) — only the `RAW_DIR` project-root resolution changes automatically since it's derived from `__file__`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_download_data.py`:

```python
import os
import zipfile

from pipeline.download_data import _extract, download_all, RAW_DIR


def test_extract_creates_year_directory_with_files(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.download_data.RAW_DIR", str(tmp_path))
    zip_path = tmp_path / "dis-2099.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("DIS_PLV_2099.txt", "cddept,referenceprel\n001,ABC\n")
        z.writestr("DIS_RESULT_2099.txt", "cddept,referenceprel\n001,ABC\n")

    dest_dir = _extract(str(zip_path), 2099)

    assert os.path.isdir(dest_dir)
    assert set(os.listdir(dest_dir)) == {"DIS_PLV_2099.txt", "DIS_RESULT_2099.txt"}


def test_download_all_skips_when_local_size_matches_remote(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.download_data.RAW_DIR", str(tmp_path))
    monkeypatch.setattr("pipeline.download_data.ZIPS", [
        {"year": 2099, "filename": "dis-2099.zip", "url": "https://example.invalid/dis-2099.zip"},
    ])
    zip_path = tmp_path / "dis-2099.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("DIS_PLV_2099.txt", "x\n")
    local_size = os.path.getsize(zip_path)

    calls = {"download": 0}

    def fake_remote_size(url):
        return local_size

    def fake_download(url, dest):
        calls["download"] += 1

    monkeypatch.setattr("pipeline.download_data._remote_size", fake_remote_size)
    monkeypatch.setattr("pipeline.download_data._download", fake_download)

    download_all()

    assert calls["download"] == 0  # size matches -> no re-download
    assert os.path.isdir(tmp_path / "2099")  # but extraction still ran
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_download_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.download_data'`

- [ ] **Step 3: Write `pipeline/download_data.py`**

```python
"""Télécharge et extrait les ZIPs annuels du contrôle sanitaire eau potable
(SISE-EAUX / data.gouv.fr) — §2.1. Adapté de Pesticides Water Map."""
import os, sys, zipfile
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")

ZIPS = [
    {"year": 2026, "filename": "dis-2026.zip",
     "url": "https://static.data.gouv.fr/resources/resultats-du-controle-sanitaire-de-leau-distribuee-commune-par-commune/20260601-162255/dis-2026.zip"},
    {"year": 2025, "filename": "dis-2025.zip",
     "url": "https://static.data.gouv.fr/resources/resultats-du-controle-sanitaire-de-leau-distribuee-commune-par-commune/20260422-070223/dis-2025.zip"},
    {"year": 2024, "filename": "dis-2024.zip",
     "url": "https://static.data.gouv.fr/resources/resultats-du-controle-sanitaire-de-leau-distribuee-commune-par-commune/20260422-071620/dis-2024.zip"},
    {"year": 2023, "filename": "dis-2023.zip",
     "url": "https://static.data.gouv.fr/resources/resultats-du-controle-sanitaire-de-leau-distribuee-commune-par-commune/20241014-073810/dis-2023.zip"},
]


def _remote_size(url):
    try:
        r = requests.head(url, timeout=15, allow_redirects=True)
        cl = r.headers.get("Content-Length")
        return int(cl) if cl else None
    except Exception:
        return None


def _download(url, dest):
    print(f"  Téléchargement {os.path.basename(dest)}...", flush=True)
    r = requests.get(url, stream=True, timeout=300)
    r.raise_for_status()
    total = int(r.headers.get("Content-Length", 0))
    done = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done/1e6:.0f}/{total/1e6:.0f} MB", end="", flush=True)
    print()


def _extract(zip_path, year):
    dest_dir = os.path.join(RAW_DIR, str(year))
    os.makedirs(dest_dir, exist_ok=True)
    print(f"  Extraction vers {dest_dir}...", flush=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest_dir)
    files = os.listdir(dest_dir)
    print(f"  OK — {len(files)} fichiers: {files}", flush=True)
    return dest_dir


def download_all(force=False):
    os.makedirs(RAW_DIR, exist_ok=True)
    for entry in ZIPS:
        zip_path = os.path.join(RAW_DIR, entry["filename"])
        extract_dir = os.path.join(RAW_DIR, str(entry["year"]))

        if not force and os.path.exists(zip_path):
            local_size = os.path.getsize(zip_path)
            remote_size = _remote_size(entry["url"])
            if remote_size and local_size == remote_size:
                print(f"[{entry['year']}] ZIP à jour ({local_size/1e6:.0f} MB), skip")
                if not os.path.exists(extract_dir) or not os.listdir(extract_dir):
                    _extract(zip_path, entry["year"])
                continue

        print(f"[{entry['year']}] Téléchargement...")
        _download(entry["url"], zip_path)
        _extract(zip_path, entry["year"])
        print(f"[{entry['year']}] Terminé")


if __name__ == "__main__":
    download_all(force="--force" in sys.argv)
    print("Tous les ZIPs téléchargés et extraits.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_download_data.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Add `data/` to `.gitignore` and commit**

The `data/raw/` directory will hold multi-hundred-MB downloads — must never be committed.

```bash
cd "C:/Repos/Quali'eau"
echo "data/raw/" >> .gitignore
git add pipeline/download_data.py tests/test_download_data.py .gitignore
git commit -m "feat: add DIS download/extraction pipeline (§2.1), adapted from precursor"
```

---

### Task 2: `pipeline/dis_parser.py` — normalisation PLM & parsing LQ (`rqana`)

**Files:**
- Create: `pipeline/dis_parser.py`
- Test: `tests/test_dis_parser.py`

**Interfaces:**
- Produces: `pipeline.dis_parser.normaliser_code_insee(code_insee: str) -> str`
- Produces: `pipeline.dis_parser.parse_valeur_rqana(rqana: str) -> tuple[float, bool]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dis_parser.py`:

```python
from pipeline.dis_parser import normaliser_code_insee, parse_valeur_rqana


def test_normaliser_code_insee_paris_arrondissement():
    assert normaliser_code_insee("75101") == "75056"
    assert normaliser_code_insee("75120") == "75056"


def test_normaliser_code_insee_lyon_arrondissement():
    assert normaliser_code_insee("69381") == "69123"
    assert normaliser_code_insee("69389") == "69123"


def test_normaliser_code_insee_marseille_arrondissement():
    assert normaliser_code_insee("13201") == "13055"
    assert normaliser_code_insee("13216") == "13055"


def test_normaliser_code_insee_commune_normale_inchangee():
    assert normaliser_code_insee("34116") == "34116"
    assert normaliser_code_insee("01007") == "01007"


def test_parse_valeur_rqana_sous_lq():
    # Cas réel vérifié §2.1 : glyphosate "<0,020" -> valtraduite=0 à IGNORER,
    # la vraie LQ (0.020) et le sous-LQ ne sont lisibles que dans rqana.
    valeur, sous_lq = parse_valeur_rqana("<0,020")
    assert sous_lq is True
    assert abs(valeur - 0.020) < 1e-9


def test_parse_valeur_rqana_quantifie():
    # Cas réel vérifié §2.1 : nitrates "3,2" (pas de préfixe <)
    valeur, sous_lq = parse_valeur_rqana("3,2")
    assert sous_lq is False
    assert abs(valeur - 3.2) < 1e-9


def test_parse_valeur_rqana_entier_sans_virgule():
    # Cas réel vérifié §2.1 : nitrates "14"
    valeur, sous_lq = parse_valeur_rqana("14")
    assert sous_lq is False
    assert valeur == 14.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dis_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dis_parser'`

- [ ] **Step 3: Write `pipeline/dis_parser.py` (part 1)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dis_parser.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/dis_parser.py tests/test_dis_parser.py
git commit -m "feat: add PLM normalization and rqana LQ parsing (§2.1, §2.5.5)"
```

---

### Task 3: `pipeline/dis_parser.py` — `load_prelevements` (DIS_PLV)

**Files:**
- Modify: `pipeline/dis_parser.py`
- Create: `tests/fixtures/DIS_PLV_sample.txt`
- Test: `tests/test_dis_parser.py`

**Interfaces:**
- Consumes: `pipeline.dis_parser.normaliser_code_insee`
- Produces: `pipeline.dis_parser.PrelevementInfo(code_insee: str, code_reseau: str, date_prelevement: date, conforme_bacterio: bool | None, conforme_chimique: bool | None)`
- Produces: `pipeline.dis_parser.load_prelevements(plv_path: str) -> dict[str, PrelevementInfo]`

- [ ] **Step 1: Create the fixture file**

Create `tests/fixtures/DIS_PLV_sample.txt` — header and rows reproduce the **real, verified** column order and quoting style from `dis-2026.zip`:

```
cddept,cdreseau,inseecommuneprinc,nomcommuneprinc,cdreseauamont,nomreseauamont,pourcentdebit,referenceprel,dateprel,heureprel,conclusionprel,ugelib,distrlib,moalib,plvconformitebacterio,plvconformitechimique,plvconformitereferencebact,plvconformitereferencechim
"034","034000123","34116","GRABELS","","","","REF-001","2026-02-10","09h00","Eau conforme.","UGE TEST","DISTR TEST","MOA TEST","C","C","C","C"
"034","034000123","34116","GRABELS","","","","REF-002","2026-05-15","10h30","Eau conforme.","UGE TEST","DISTR TEST","MOA TEST","C","C","C","C"
"075","075000221","75101","PARIS 1ER ARRONDISSEMENT","","","","REF-003","2026-03-01","08h00","Eau conforme.","EAU DE PARIS","EAU DE PARIS","EAU DE PARIS","N","C","C","C"
"075","075000221","75101","PARIS 1ER ARRONDISSEMENT","","","","REF-004","2026-06-01","08h00","Eau conforme.","EAU DE PARIS","EAU DE PARIS","EAU DE PARIS","C","C","C","C"
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_dis_parser.py`:

```python
import os

from pipeline.dis_parser import load_prelevements

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_load_prelevements_parse_champs_reels():
    idx = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    assert len(idx) == 4
    info = idx["REF-001"]
    assert info.code_insee == "34116"
    assert info.code_reseau == "034000123"
    assert info.date_prelevement == date(2026, 2, 10)
    assert info.conforme_bacterio is True
    assert info.conforme_chimique is True


def test_load_prelevements_normalise_plm():
    # REF-003/REF-004 sont sur Paris 1er (75101) -> doit remonter à 75056
    idx = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    assert idx["REF-003"].code_insee == "75056"
    assert idx["REF-004"].code_insee == "75056"


def test_load_prelevements_conformite_non_conforme():
    idx = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    assert idx["REF-003"].conforme_bacterio is False
```

Add `from datetime import date` to the top of `tests/test_dis_parser.py` if not already present (it is not yet — this is its first use in the file).

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_dis_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_prelevements'`

- [ ] **Step 4: Implement `load_prelevements`**

Append to `pipeline/dis_parser.py`:

```python
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
            index[ref] = PrelevementInfo(
                code_insee=normaliser_code_insee(insee),
                code_reseau=row.get("cdreseau", "").strip(),
                date_prelevement=date.fromisoformat(date_str[:10]),
                conforme_bacterio=_parse_conformite(row.get("plvconformitebacterio", "")),
                conforme_chimique=_parse_conformite(row.get("plvconformitechimique", "")),
            )
    return index
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dis_parser.py -v`
Expected: PASS (10 tests)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/dis_parser.py tests/test_dis_parser.py tests/fixtures/DIS_PLV_sample.txt
git commit -m "feat: parse DIS_PLV into prelevement index with PLM normalization"
```

---

### Task 4: `pipeline/dis_parser.py` — `load_udi_reseaux` (DIS_COM_UDI)

**Files:**
- Modify: `pipeline/dis_parser.py`
- Create: `tests/fixtures/DIS_COM_UDI_sample.txt`
- Test: `tests/test_dis_parser.py`

**Interfaces:**
- Produces: `pipeline.dis_parser.ReseauRef(code_reseau: str, nom_reseau: str)`
- Produces: `pipeline.dis_parser.load_udi_reseaux(udi_path: str) -> dict[str, list[ReseauRef]]`

- [ ] **Step 1: Create the fixture file**

Create `tests/fixtures/DIS_COM_UDI_sample.txt` (real column order verified §2.1):

```
inseecommune,nomcommune,quartier,cdreseau,nomreseau,debutalim
"34116","GRABELS","-","034000123","RESEAU GRABELS PRINCIPAL","2010-01-01"
"75101","PARIS 1ER ARRONDISSEMENT","-","075000221","CENTRE","2015-01-01"
"75101","PARIS 1ER ARRONDISSEMENT","-","075000999","RESEAU SECONDAIRE","2018-01-01"
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_dis_parser.py`:

```python
from pipeline.dis_parser import load_udi_reseaux


def test_load_udi_reseaux_commune_simple():
    idx = load_udi_reseaux(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"))
    reseaux = idx["34116"]
    assert len(reseaux) == 1
    assert reseaux[0].code_reseau == "034000123"
    assert reseaux[0].nom_reseau == "RESEAU GRABELS PRINCIPAL"


def test_load_udi_reseaux_commune_multi_reseaux_normalise_plm():
    # Paris 1er (75101) -> normalisé vers 75056, les deux réseaux du même
    # arrondissement doivent se regrouper sous 75056 (§2.5.4)
    idx = load_udi_reseaux(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"))
    reseaux = idx["75056"]
    assert len(reseaux) == 2
    codes = {r.code_reseau for r in reseaux}
    assert codes == {"075000221", "075000999"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_dis_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_udi_reseaux'`

- [ ] **Step 4: Implement `load_udi_reseaux`**

Append to `pipeline/dis_parser.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dis_parser.py -v`
Expected: PASS (12 tests)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/dis_parser.py tests/test_dis_parser.py tests/fixtures/DIS_COM_UDI_sample.txt
git commit -m "feat: parse DIS_COM_UDI into commune-to-reseaux index (§2.5.4)"
```

---

### Task 5: `pipeline/dis_parser.py` — `iter_mesures` (DIS_RESULT, jointure + LQ)

**Files:**
- Modify: `pipeline/dis_parser.py`
- Create: `tests/fixtures/DIS_RESULT_sample.txt`
- Test: `tests/test_dis_parser.py`

**Interfaces:**
- Consumes: `pipeline.dis_parser.parse_valeur_rqana`, `pipeline.dis_parser.PrelevementInfo`, `pipeline.models.Mesure`
- Produces: `pipeline.dis_parser.iter_mesures(result_path: str, prelevements: dict[str, PrelevementInfo]) -> Iterator[tuple[str, str, Mesure]]` — yields `(code_insee, code_parametre, Mesure)`

- [ ] **Step 1: Create the fixture file**

Create `tests/fixtures/DIS_RESULT_sample.txt` (real column order verified §2.1; rows cover a quantified nitrate, a sous-LQ glyphosate matching the real §2.1 example, a row with no matching `referenceprel` in PLV — must be skipped — and a row with empty `cdparametre` — must be skipped per §2.1's own note):

```
cddept,referenceprel,cdparametresiseeaux,cdparametre,libmajparametre,libminparametre,libwebparametre,qualitparam,insituana,rqana,cdunitereferencesiseeaux,cdunitereference,limitequal,refqual,valtraduite,casparam,referenceanl
"034","REF-001","NO3","1340","NITRATES (EN NO3)","Nitrates (en NO3)",,"N","L","14","mg/L","162","<=50 mg/L","","14.000000","14797-55-8","ANL-001"
"034","REF-001","GPST","1506","GLYPHOSATE","Glyphosate",,"N","L","<0,020","µg/L","133","<=0,1 µg/L","","0.000000","1071-83-6","ANL-002"
"034","REF-002","NO3","1340","NITRATES (EN NO3)","Nitrates (en NO3)",,"N","L","17","mg/L","162","<=50 mg/L","","17.000000","14797-55-8","ANL-003"
"034","REF-999","NO3","1340","NITRATES (EN NO3)","Nitrates (en NO3)",,"N","L","20","mg/L","162","<=50 mg/L","","20.000000","14797-55-8","ANL-004"
"034","REF-001","","","CONCLUSION",,,,,,,,,,,"",""
```

(`REF-999` has no matching entry in `DIS_PLV_sample.txt` from Task 3 — must be dropped silently. The last row has an empty `cdparametre` — a real, documented case per §2.1's note "certaines lignes n'ont pas de code_parametre" — must also be dropped.)

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_dis_parser.py`:

```python
from pipeline.dis_parser import iter_mesures


def test_iter_mesures_valeur_quantifiee():
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    nitrates = [(insee, m) for insee, code, m in resultats if code == "1340"]
    assert len(nitrates) == 2  # REF-001 et REF-002 (REF-999 exclu, pas de jointure PLV)
    insee, mesure = nitrates[0]
    assert insee == "34116"
    assert mesure.valeur == 14.0
    assert mesure.sous_lq is False
    assert mesure.date_prelevement == date(2026, 2, 10)


def test_iter_mesures_sous_lq_lit_rqana_pas_valtraduite():
    # BUG POTENTIEL évité : valtraduite="0.000000" pour ce glyphosate sous LQ.
    # Si le parseur lisait valtraduite au lieu de rqana, on obtiendrait
    # (valeur=0.0, sous_lq=False) au lieu de (0.020, True) — silencieusement faux.
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    glyphosate = [(insee, m) for insee, code, m in resultats if code == "1506"]
    assert len(glyphosate) == 1
    _, mesure = glyphosate[0]
    assert mesure.sous_lq is True
    assert abs(mesure.valeur - 0.020) < 1e-9


def test_iter_mesures_ignore_referenceprel_inconnu():
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    # 5 lignes dans la fixture (REF-001 x2, REF-002, REF-999, ligne sans cdparametre) ;
    # REF-999 (pas de jointure PLV) et la ligne sans cdparametre doivent être exclues.
    assert len(resultats) == 3  # 2 nitrates (REF-001, REF-002) + 1 glyphosate (REF-001)


def test_iter_mesures_ignore_ligne_sans_code_parametre():
    prelevements = load_prelevements(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"))
    resultats = list(iter_mesures(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), prelevements))
    codes = {code for _, code, _ in resultats}
    assert "" not in codes
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_dis_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'iter_mesures'`

- [ ] **Step 4: Implement `iter_mesures`**

Append to `pipeline/dis_parser.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dis_parser.py -v`
Expected: PASS (16 tests)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/dis_parser.py tests/test_dis_parser.py tests/fixtures/DIS_RESULT_sample.txt
git commit -m "feat: stream-parse DIS_RESULT with PLV join and rqana LQ handling"
```

---

### Task 6: `pipeline/compute_scores.py` — fenêtre temporelle & évaluation bactériologique

**Files:**
- Create: `pipeline/compute_scores.py`
- Test: `tests/test_compute_scores.py`

**Interfaces:**
- Consumes: `pipeline.models.ConclusionBacterio`
- Produces: `pipeline.compute_scores.selectionner_fenetre_jours(dates_prelevements: list[date], date_reference: date) -> int`
- Produces: `pipeline.compute_scores.evaluer_bacteriologie(historique: list[ConclusionBacterio]) -> tuple[bool, bool]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_compute_scores.py`:

```python
from datetime import date

from pipeline.models import ConclusionBacterio
from pipeline.compute_scores import selectionner_fenetre_jours, evaluer_bacteriologie


def test_fenetre_12_mois_si_4_prelevements_ou_plus():
    date_ref = date(2026, 6, 15)
    dates = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    assert selectionner_fenetre_jours(dates, date_ref) == 365


def test_fenetre_etendue_24_mois_si_moins_de_4():
    date_ref = date(2026, 6, 15)
    dates = [date(2026, 1, 1), date(2026, 2, 1)]  # seulement 2
    assert selectionner_fenetre_jours(dates, date_ref) == 730


def test_fenetre_ignore_dates_hors_12_mois_pour_le_comptage():
    date_ref = date(2026, 6, 15)
    dates = [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1)]  # trop vieilles
    assert selectionner_fenetre_jours(dates, date_ref) == 730


def test_evaluer_bacteriologie_conforme_sans_historique_non_conforme():
    historique = [
        ConclusionBacterio(date_prelevement=date(2026, 1, 1), conforme=True),
        ConclusionBacterio(date_prelevement=date(2026, 3, 1), conforme=True),
    ]
    conforme_dernier, resolu = evaluer_bacteriologie(historique)
    assert conforme_dernier is True
    assert resolu is False


def test_evaluer_bacteriologie_resolue():
    # Non-conformité en janvier, mais le dernier prélèvement (mars) est conforme.
    historique = [
        ConclusionBacterio(date_prelevement=date(2026, 1, 1), conforme=False),
        ConclusionBacterio(date_prelevement=date(2026, 3, 1), conforme=True),
    ]
    conforme_dernier, resolu = evaluer_bacteriologie(historique)
    assert conforme_dernier is True
    assert resolu is True


def test_evaluer_bacteriologie_active():
    historique = [
        ConclusionBacterio(date_prelevement=date(2026, 1, 1), conforme=True),
        ConclusionBacterio(date_prelevement=date(2026, 3, 1), conforme=False),
    ]
    conforme_dernier, resolu = evaluer_bacteriologie(historique)
    assert conforme_dernier is False
    assert resolu is False


def test_evaluer_bacteriologie_aucun_historique():
    conforme_dernier, resolu = evaluer_bacteriologie([])
    assert conforme_dernier is True
    assert resolu is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compute_scores.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.compute_scores'`

- [ ] **Step 3: Write `pipeline/compute_scores.py` (part 1)**

```python
"""Orchestrateur : fenêtre temporelle, résolution réseau/PLM, puis calcul
complet de la fiche communale (§5.3) via le moteur de scoring déjà testé
(pipeline.scoring / pipeline.aggregation / pipeline.recommendations)."""
from datetime import date

from pipeline.models import ConclusionBacterio


def selectionner_fenetre_jours(dates_prelevements: list, date_reference: date) -> int:
    """§2.5.1 — 12 mois (365j), étendu à 24 (730j) si moins de 4 dates de
    prélèvement distinctes tombent dans les 12 derniers mois. Utilise le
    nombre de dates distinctes comme proxy du nombre d'analyses (une même
    date peut porter plusieurs paramètres)."""
    dates_12_mois = {d for d in dates_prelevements if (date_reference - d).days <= 365}
    return 365 if len(dates_12_mois) >= 4 else 730


def evaluer_bacteriologie(historique: list) -> tuple[bool, bool]:
    """§3.1.1 — évalue (conforme_dernier, resolu) à partir de l'historique
    ConclusionBacterio de la fenêtre, pour alimenter score_bacteriologie.

    ⚠️ INTERPRÉTATION RETENUE (à valider) : le fichier DIS_PLV ne distingue
    pas prélèvement de routine / prélèvement de contrôle. On lit donc :
    - dernier enregistrement de la fenêtre non conforme -> actif (0)
    - dernier enregistrement conforme, mais au moins une non-conformité
      plus tôt dans la même fenêtre -> résolu (50)
    - dernier enregistrement conforme et aucune non-conformité antérieure
      dans la fenêtre -> conforme (100)
    Sans cette lecture, le cas "résolu" de §3.1.1 serait inatteignable
    (si le dernier enregistrement est conforme, il n'y a par construction
    aucun contrôle postérieur à comparer)."""
    if not historique:
        return True, False
    historique_trie = sorted(historique, key=lambda c: c.date_prelevement)
    dernier = historique_trie[-1]
    if not dernier.conforme:
        return False, False
    y_a_eu_non_conformite = any(not c.conforme for c in historique_trie[:-1])
    return True, y_a_eu_non_conformite
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compute_scores.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/compute_scores.py tests/test_compute_scores.py
git commit -m "feat: add window selection and bacteriological history evaluation (§2.5.1, §3.1.1)"
```

**Flag to human before proceeding:** the bacteriological interpretation above is a judgment call, not a verified fact. Confirm it's acceptable (or correct it) before this becomes load-bearing in Task 8.

---

### Task 7: `pipeline/compute_scores.py` — résolution du réseau principal (multi-UDI)

**Files:**
- Modify: `pipeline/compute_scores.py`
- Test: `tests/test_compute_scores.py`

**Interfaces:**
- Consumes: `pipeline.dis_parser.ReseauRef`
- Produces: `pipeline.compute_scores.choisir_reseau_principal(reseaux: list[ReseauRef], nb_prelevements_par_reseau: dict[str, int]) -> str | None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_compute_scores.py`:

```python
from pipeline.dis_parser import ReseauRef
from pipeline.compute_scores import choisir_reseau_principal


def test_choisir_reseau_principal_le_plus_de_prelevements():
    reseaux = [ReseauRef("R1", "Réseau 1"), ReseauRef("R2", "Réseau 2")]
    nb = {"R1": 5, "R2": 20}
    assert choisir_reseau_principal(reseaux, nb) == "R2"


def test_choisir_reseau_principal_un_seul_reseau():
    reseaux = [ReseauRef("R1", "Réseau unique")]
    assert choisir_reseau_principal(reseaux, {"R1": 3}) == "R1"


def test_choisir_reseau_principal_aucun_reseau():
    assert choisir_reseau_principal([], {}) is None


def test_choisir_reseau_principal_reseau_sans_prelevement_compte_zero():
    reseaux = [ReseauRef("R1", "Réseau 1"), ReseauRef("R2", "Réseau 2")]
    nb = {"R1": 5}  # R2 absent du dict -> 0 prélèvements
    assert choisir_reseau_principal(reseaux, nb) == "R1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compute_scores.py -v`
Expected: FAIL with `ImportError: cannot import name 'choisir_reseau_principal'`

- [ ] **Step 3: Implement `choisir_reseau_principal`**

Append to `pipeline/compute_scores.py`:

```python
def choisir_reseau_principal(reseaux: list, nb_prelevements_par_reseau: dict) -> str | None:
    """§2.5.4 — retourne le code du réseau ayant le plus de prélèvements
    récents parmi ceux desservant la commune. None si aucun réseau connu."""
    if not reseaux:
        return None
    return max(
        (r.code_reseau for r in reseaux),
        key=lambda code: nb_prelevements_par_reseau.get(code, 0),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compute_scores.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/compute_scores.py tests/test_compute_scores.py
git commit -m "feat: add principal-reseau resolution for multi-UDI communes (§2.5.4)"
```

---

### Task 8: `pipeline/compute_scores.py` — `calculer_fiche_commune` (assemblage complet)

**Files:**
- Modify: `pipeline/compute_scores.py`
- Test: `tests/test_compute_scores.py`

**Interfaces:**
- Consumes: everything from `pipeline.scoring` (`score_bacteriologie`, `score_pesticides`, `score_pfas`, `score_metal_toxique`, `score_nitrates_securite`, `score_securite`, `score_mineraux`, `score_gout`, `score_boisson`, `score_cosmetique`, `veto_sanitaire`, `arrondi`), `pipeline.aggregation.moyenne_ponderee`, `pipeline.recommendations.generate_recommendations`, `pipeline.models.Mesure`
- Produces: `pipeline.compute_scores.calculer_fiche_commune(code_insee: str, mesures_par_parametre: dict[str, list[Mesure]], historique_bacterio: list[ConclusionBacterio], date_reference: date) -> dict`

**Scoping note:** `6276`/`8847` (pesticide/PFAS totals) are read as ordinary individual parameters (weighted average of the lab-reported value). `pipeline.aggregation.valeur_somme_reglementaire`'s full priority rule (recompute from the 17/20 individual molecule codes with LQ/2 substitution, only when the total field *itself* is reported under LQ) is **not** wired in here — see "Out of Scope".

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compute_scores.py`:

```python
from pipeline.models import Mesure
from pipeline.compute_scores import calculer_fiche_commune


def _mesure(valeur, jours_avant_ref, date_reference, sous_lq=False):
    from datetime import timedelta
    return Mesure(valeur=valeur, sous_lq=sous_lq, date_prelevement=date_reference - timedelta(days=jours_avant_ref))


def test_calculer_fiche_commune_eau_bonne_qualite():
    date_ref = date(2026, 6, 15)
    mesures = {
        "1345": [_mesure(10.0, 30, date_ref), _mesure(10.0, 60, date_ref), _mesure(10.0, 90, date_ref), _mesure(10.0, 120, date_ref)],
        "1398": [_mesure(0.03, 30, date_ref)],
        "1399": [_mesure(0.03, 30, date_ref)],
        "1302": [_mesure(7.0, 30, date_ref)],
        "1295": [_mesure(0.1, 30, date_ref)],
        "1340": [_mesure(5.0, 30, date_ref)],
    }
    historique = [ConclusionBacterio(date_prelevement=date_ref, conforme=True)]

    fiche = calculer_fiche_commune("34116", mesures, historique, date_ref)

    assert fiche["statut_donnees"] == "complet"
    assert fiche["scores"]["boisson"]["score"] >= 90
    assert fiche["scores"]["boisson"]["veto_sanitaire"] is False
    assert fiche["scores"]["cosmetique"]["score"] >= 90
    assert fiche["scores"]["cosmetique"]["sous_scores"]["durete_calcaire"] == 100


def test_calculer_fiche_commune_veto_nitrates_plafonne_le_score():
    # Régression directe du bug corrigé en v1.3 (§3.1) : un dépassement
    # nitrates doit réellement plafonner le score boisson, pas juste
    # cosmétiquement apparaître dans un sous-score.
    date_ref = date(2026, 6, 15)
    mesures = {
        "1345": [_mesure(10.0, 30, date_ref)],
        "1398": [_mesure(0.03, 30, date_ref)],
        "1399": [_mesure(0.03, 30, date_ref)],
        "1302": [_mesure(7.0, 30, date_ref)],
        "1295": [_mesure(0.1, 30, date_ref)],
        "1340": [_mesure(60.0, 30, date_ref)],  # > 50 mg/L : veto
    }
    historique = [ConclusionBacterio(date_prelevement=date_ref, conforme=True)]

    fiche = calculer_fiche_commune("34116", mesures, historique, date_ref)

    assert fiche["scores"]["boisson"]["veto_sanitaire"] is True
    assert fiche["scores"]["boisson"]["score"] < 50


def test_calculer_fiche_commune_aucune_mesure_statut_indisponible():
    fiche = calculer_fiche_commune("99999", {}, [], date(2026, 6, 15))
    assert fiche["statut_donnees"] == "indisponible"
    assert fiche["scores"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compute_scores.py -v`
Expected: FAIL with `ImportError: cannot import name 'calculer_fiche_commune'`

- [ ] **Step 3: Implement `calculer_fiche_commune`**

Append to `pipeline/compute_scores.py`:

```python
from pipeline.aggregation import moyenne_ponderee
from pipeline.scoring import (
    score_bacteriologie, score_pesticides, score_pfas, score_metal_toxique,
    score_nitrates_securite, score_securite, score_mineraux, score_gout,
    score_boisson, score_cosmetique, veto_sanitaire, arrondi,
)
from pipeline.recommendations import generate_recommendations

# §2.4 — 17 codes pesticides validés
PESTICIDE_CODES = [
    "1107", "1108", "1113", "1129", "1177", "1208", "1209", "1473",
    "1506", "1667", "1877", "1907", "2974", "6894", "6895", "7717", "8865",
]

# §2.3 / §3.1.1 v1.5 — LQ seule, pas de RQ documentée pour ces métaux toxiques
METAUX_LQ = {
    "1382": 10.0,  # Plomb, µg/L
    "1369": 10.0,  # Arsenic, µg/L
    "1388": 5.0,   # Cadmium, µg/L
    "1386": 20.0,  # Nickel, µg/L
}


def _moyenne_ou_zero(mesures: list, date_reference: date) -> float:
    if not mesures:
        return 0.0
    valeur = moyenne_ponderee(mesures, date_reference)
    return valeur if valeur is not None else 0.0


def calculer_fiche_commune(code_insee: str, mesures_par_parametre: dict,
                            historique_bacterio: list, date_reference: date) -> dict:
    """Assemble la fiche communale complète (§5.3) pour une commune, à partir
    des Mesure déjà jointes (dict[code_parametre, list[Mesure]]) et de
    l'historique de conformité bactériologique de la fenêtre."""

    toutes_dates = [m.date_prelevement for mesures in mesures_par_parametre.values() for m in mesures]
    if not toutes_dates:
        return {"commune": {"code_insee": code_insee}, "statut_donnees": "indisponible", "scores": None}

    fenetre_jours = selectionner_fenetre_jours(toutes_dates, date_reference)

    def fenetre(mesures):
        return [m for m in mesures if (date_reference - m.date_prelevement).days <= fenetre_jours]

    # --- Sécurité sanitaire (§3.1.1) ---
    conforme_dernier, resolu = evaluer_bacteriologie(historique_bacterio)
    p_bact = score_bacteriologie(conforme_dernier, resolu)

    # 6276 est lui-même un paramètre mesuré et rapporté par le labo (confirmé
    # sur données réelles §2.1) : on le lit comme un paramètre individuel
    # (moyenne pondérée directe), sans recalcul par sommation des 17
    # molécules — cf. note de simplification dans "Out of Scope" (le
    # recalcul LQ/2 de valeur_somme_reglementaire, quand le champ total
    # lui-même est sous LQ, est un raffinement futur, pas encore câblé ici).
    pesticide_total = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("6276", [])), date_reference)
    pesticide_molecule_max = 0.0
    for code in PESTICIDE_CODES:
        m = fenetre(mesures_par_parametre.get(code, []))
        if m:
            pesticide_molecule_max = max(pesticide_molecule_max, moyenne_ponderee(m, date_reference))
    p_pest = score_pesticides(pesticide_total, pesticide_molecule_max)

    pfas_total = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("8847", [])), date_reference)
    p_pfas = score_pfas(pfas_total)

    valeurs_metaux = {}
    notes_metaux = []
    for code, lq in METAUX_LQ.items():
        m = fenetre(mesures_par_parametre.get(code, []))
        if m:
            v = moyenne_ponderee(m, date_reference)
            valeurs_metaux[code] = v
            notes_metaux.append(score_metal_toxique(v, lq))
    p_metaux = min(notes_metaux) if notes_metaux else 100.0

    nitrates = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1340", [])), date_reference)
    nitrites = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1339", [])), date_reference)
    p_nitrates = score_nitrates_securite(nitrates, nitrites)

    s_securite = score_securite(p_bact, p_pest, p_pfas, p_metaux, p_nitrates)

    # --- Minéraux & goût (§3.1.2, §3.1.3) ---
    chlorures = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1337", [])), date_reference)
    sulfates = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1338", [])), date_reference)
    s_mineraux = score_mineraux(nitrates, chlorures, sulfates)

    chlore_libre = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1398", [])), date_reference)
    turbidite = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1295", [])), date_reference)
    s_gout = score_gout(chlore_libre, turbidite)

    bact_actif = (not conforme_dernier) and (not resolu)
    veto = veto_sanitaire(
        bact_actif=bact_actif, nitrates=nitrates, nitrites=nitrites,
        pb=valeurs_metaux.get("1382", 0.0), as_=valeurs_metaux.get("1369", 0.0),
        cd=valeurs_metaux.get("1388", 0.0),
        pesticide_molecule_max=pesticide_molecule_max, pesticide_total=pesticide_total,
        pfas=pfas_total,
    )
    score_boisson_val = score_boisson(s_securite, s_mineraux, s_gout, veto)

    # --- Cosmétique (§3.2) ---
    th = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1345", [])), date_reference)
    chlore_total = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1399", [])), date_reference)
    ph_mesures = fenetre(mesures_par_parametre.get("1302", []))
    ph = moyenne_ponderee(ph_mesures, date_reference) if ph_mesures else 7.0
    cuivre = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1392", [])), date_reference)
    fer = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1393", [])), date_reference)
    manganese = _moyenne_ou_zero(fenetre(mesures_par_parametre.get("1394", [])), date_reference)
    score_cosmetique_val, sous_scores_cosmetique = score_cosmetique(th, chlore_total, ph, cuivre, fer, manganese)

    # --- Recommandations (§4) ---
    mesures_recommandations = {
        "1345": th, "1398": chlore_libre, "1399": chlore_total, "1340": nitrates,
        "1339": nitrites, "6276": pesticide_total, "8847": pfas_total,
        "1393": fer, "1392": cuivre, "_pesticide_molecule_max": pesticide_molecule_max,
    }
    recommandations = generate_recommendations(mesures_recommandations, bact_actif=bact_actif)

    return {
        "commune": {"code_insee": code_insee},
        "statut_donnees": "complet",
        "scores": {
            "boisson": {
                "score": score_boisson_val,
                "veto_sanitaire": veto,
                "sous_scores": {
                    "securite_sanitaire": arrondi(s_securite),
                    "mineraux_equilibre": arrondi(s_mineraux),
                    "gout_organoleptique": arrondi(s_gout),
                },
            },
            "cosmetique": {
                "score": score_cosmetique_val,
                "sous_scores": sous_scores_cosmetique,
            },
        },
        "recommandations": recommandations,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compute_scores.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/compute_scores.py tests/test_compute_scores.py
git commit -m "feat: assemble full commune fiche (§5.3) wiring aggregation+scoring+recommendations"
```

---

### Task 9: `pipeline/compute_scores.py` — `main()` : accumulation multi-communes + écriture JSON

**Files:**
- Modify: `pipeline/compute_scores.py`
- Test: `tests/test_compute_scores.py`

**Interfaces:**
- Consumes: `pipeline.dis_parser.load_prelevements`, `load_udi_reseaux`, `iter_mesures`, `pipeline.compute_scores.calculer_fiche_commune`
- Produces: `pipeline.compute_scores.construire_fiches(plv_path: str, result_path: str, udi_path: str, date_reference: date) -> dict[str, dict]`, `pipeline.compute_scores.main(raw_dir: str, output_dir: str, date_reference: date | None = None) -> None`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compute_scores.py`:

```python
import os

from pipeline.dis_parser import load_prelevements, load_udi_reseaux
from pipeline.compute_scores import construire_fiches

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_construire_fiches_depuis_fixtures_reelles():
    # Bout-en-bout : PLV + RESULT + UDI (fixtures Tasks 3-5) -> fiches multi-communes
    date_ref = date(2026, 8, 5)
    fiches = construire_fiches(
        plv_path=os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"),
        result_path=os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"),
        udi_path=os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"),
        date_reference=date_ref,
    )
    assert "34116" in fiches
    fiche = fiches["34116"]
    assert fiche["statut_donnees"] == "complet"
    # nitrates moyens ~ (14+17)/2-ish pondéré, bien en dessous de 50 -> pas de veto
    assert fiche["scores"]["boisson"]["veto_sanitaire"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compute_scores.py -v`
Expected: FAIL with `ImportError: cannot import name 'construire_fiches'`

- [ ] **Step 3: Implement `construire_fiches` and `main`**

Append to `pipeline/compute_scores.py`:

```python
import json
import os
from datetime import datetime, timezone

from pipeline.dis_parser import load_prelevements, load_udi_reseaux, iter_mesures
from pipeline.models import ConclusionBacterio


def construire_fiches(plv_path: str, result_path: str, udi_path: str, date_reference: date) -> dict:
    """Charge PLV+RESULT+UDI et construit la fiche de chaque commune connue.
    Le réseau principal (§2.5.4) n'est pas encore filtré ici : toutes les
    mesures de toutes les communes du fichier sont agrégées ensemble (une
    commune multi-réseaux verra ses réseaux fusionnés — affinage laissé à
    un futur plan si un cas réel l'exige)."""
    prelevements = load_prelevements(plv_path)
    _reseaux_par_commune = load_udi_reseaux(udi_path)  # réservé pour affinage futur

    mesures_par_commune: dict = {}
    for code_insee, code_parametre, mesure in iter_mesures(result_path, prelevements):
        mesures_par_commune.setdefault(code_insee, {}).setdefault(code_parametre, []).append(mesure)

    historique_bacterio_par_commune: dict = {}
    for info in prelevements.values():
        if info.conforme_bacterio is None:
            continue
        historique_bacterio_par_commune.setdefault(info.code_insee, []).append(
            ConclusionBacterio(date_prelevement=info.date_prelevement, conforme=info.conforme_bacterio)
        )

    fiches = {}
    for code_insee, mesures_par_parametre in mesures_par_commune.items():
        historique = historique_bacterio_par_commune.get(code_insee, [])
        fiches[code_insee] = calculer_fiche_commune(code_insee, mesures_par_parametre, historique, date_reference)
    return fiches


def main(raw_dir: str, output_dir: str, date_reference: date | None = None) -> None:
    """Point d'entrée batch : lit les 3 fichiers DIS de `raw_dir` (année la
    plus récente uniquement — l'agrégation multi-années glissantes est un
    raffinement futur), écrit une fiche JSON par commune sous
    `output_dir/communes/{code_insee}.json` + un `index.json` global."""
    date_reference = date_reference or datetime.now(timezone.utc).date()
    plv_path = os.path.join(raw_dir, "DIS_PLV.txt")
    result_path = os.path.join(raw_dir, "DIS_RESULT.txt")
    udi_path = os.path.join(raw_dir, "DIS_COM_UDI.txt")

    fiches = construire_fiches(plv_path, result_path, udi_path, date_reference)

    communes_dir = os.path.join(output_dir, "communes")
    os.makedirs(communes_dir, exist_ok=True)
    for code_insee, fiche in fiches.items():
        with open(os.path.join(communes_dir, f"{code_insee}.json"), "w", encoding="utf-8") as f:
            json.dump(fiche, f, ensure_ascii=False, indent=2)

    index = {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "nb_communes_scorees": sum(1 for f in fiches.values() if f["statut_donnees"] == "complet"),
        "nb_communes_sans_donnees": sum(1 for f in fiches.values() if f["statut_donnees"] == "indisponible"),
    }
    with open(os.path.join(output_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main(
        raw_dir=os.path.join(PROJECT_ROOT, "data", "raw", "2026"),
        output_dir=os.path.join(PROJECT_ROOT, "public", "data"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compute_scores.py -v`
Expected: PASS (15 tests)

- [ ] **Step 5: Run the entire test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests across all files — 70 pre-existing scoring-engine tests + this plan's new tests)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/compute_scores.py tests/test_compute_scores.py
git commit -m "feat: add multi-commune orchestration and JSON output writer (§5.2, §5.3)"
```

---

### Task 10: Test d'intégration bout-en-bout sur les fixtures réelles

**Files:**
- Test: `tests/test_pipeline_integration.py`

**Interfaces:**
- Consumes: `pipeline.compute_scores.main`

- [ ] **Step 1: Write the integration test**

Create `tests/test_pipeline_integration.py`:

```python
import json
import os

from pipeline.compute_scores import main

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_pipeline_bout_en_bout_ecrit_fiches_json(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # main() attend DIS_PLV.txt / DIS_RESULT.txt / DIS_COM_UDI.txt (noms
    # génériques, sans suffixe d'année) dans raw_dir — on y copie les
    # fixtures qui reproduisent le format réel vérifié §2.1.
    import shutil
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"), raw_dir / "DIS_PLV.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"), raw_dir / "DIS_RESULT.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"), raw_dir / "DIS_COM_UDI.txt")

    output_dir = tmp_path / "output"
    from datetime import date
    main(raw_dir=str(raw_dir), output_dir=str(output_dir), date_reference=date(2026, 8, 5))

    fiche_path = output_dir / "communes" / "34116.json"
    assert fiche_path.exists()
    fiche = json.loads(fiche_path.read_text(encoding="utf-8"))
    assert fiche["commune"]["code_insee"] == "34116"
    assert fiche["statut_donnees"] == "complet"
    assert "boisson" in fiche["scores"]
    assert "cosmetique" in fiche["scores"]

    index_path = output_dir / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["nb_communes_scorees"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_integration.py -v`
Expected: FAIL — either an import error (if any earlier task's function is missing) or an assertion failure. This test should only be run after Tasks 1-9 are complete; if all prior tasks passed their own tests, this should mostly need no new implementation, only wiring verification.

- [ ] **Step 3: Fix any wiring issues found**

If the test fails on something not caused by a missing implementation (e.g. a path or dict-key mismatch between `calculer_fiche_commune`'s output and what this test expects), fix the mismatch in `pipeline/compute_scores.py`. Do not change the fixture files (Tasks 3-5) — they reproduce verified real-world format and must stay accurate.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_integration.py -v`
Expected: PASS

- [ ] **Step 5: Run the entire test suite one final time**

Run: `pytest tests/ -v`
Expected: PASS (all tests, full project)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add tests/test_pipeline_integration.py
git commit -m "test: add end-to-end pipeline integration test on real-format fixtures"
```

---

## Out of Scope (separate future plan)

- **Recalcul LQ/2 des sommes réglementaires quand le champ total lui-même est sous LQ** (§2.5.3) — `pipeline.aggregation.valeur_somme_reglementaire` (déjà construit et testé dans le plan précédent) implémente la règle de priorité complète, mais Task 8 lit `6276`/`8847` comme de simples paramètres individuels (moyenne pondérée directe du champ tel que rapporté par le labo). Le recalcul par sommation des 17/20 molécules individuelles avec LQ/2 ne s'applique donc que si un futur raffinement câble explicitement `valeur_somme_reglementaire` par prélèvement (elle opère sur un instantané, pas sur une série temporelle — il faudrait grouper par `referenceprel` avant l'agrégation pondérée, plus complexe que la portée retenue ici).
- **`national.geojson` / map geometry** — requires sourcing and simplifying ~35 000 commune polygons (geo.api.gouv.fr / IGN), an unrelated, substantially separate technical problem from DIS parsing/scoring. The precursor projects (`sca-water-map`, `pesticides-water-map`) already solved commune-geometry integration — reuse that work rather than re-deriving it.
- **Multi-année glissante réelle (§2.1: "≥ 24 mois")** — `main()` currently reads one year's worth of files (`DIS_PLV.txt`/`DIS_RESULT.txt` without year suffix). Extending to merge 2-4 years of yearly files (`DIS_PLV_2023.txt` + `DIS_PLV_2024.txt` + ...) before calling `construire_fiches` is a small, mechanical follow-up once this plan's single-year path is proven.
- **Fiches "indisponible" pour les communes sans aucune mesure** (§2.5.6) — `construire_fiches` (Task 9) ne construit une fiche que pour les communes trouvées via `iter_mesures` (au moins une ligne DIS_RESULT jointe). Une commune connue seulement via `DIS_PLV`/`DIS_COM_UDI` (prélèvements enregistrés mais aucun résultat de labo joignable, ou commune du référentiel UDI jamais échantillonnée) n'obtient aujourd'hui aucune fiche du tout, plutôt qu'une fiche `statut_donnees: "indisponible"` — `calculer_fiche_commune` gère déjà ce cas (`test_calculer_fiche_commune_aucune_mesure_statut_indisponible`, Task 8) mais `construire_fiches` ne l'appelle jamais pour ces communes. Itérer sur l'union des codes commune connus (PLV ∪ UDI), pas seulement ceux avec mesures, est le raffinement nécessaire.
- **Réseau-principal filtering inside `construire_fiches`** — Task 9 aggregates all measurements per commune without yet splitting by réseau for genuinely multi-UDI communes (per-réseau scoring, §2.5.4's full requirement). `choisir_reseau_principal` (Task 7) is built and tested but not yet wired into `construire_fiches` — flagged explicitly rather than silently incomplete.
- **50-commune representative test suite** (§8 roadmap) — needs either real downloaded data (Task 1's `download_all()`, network-dependent) or a larger, hand-curated fixture set; out of scope for this plan's fixture-based unit/integration tests.
- Frontend (`public/index.html` etc.) — Phase 2.
- **Final whole-branch review findings deferred (2026-08-05 fix round, diff `07d3a3d..5131b38`):** I1 (memory use at multi-year production scale — irrelevant at current single-year/fixture scale, tied to the multi-année-glissante limitation above), I4 (whether a sub-LQ individual reading should bypass normal scoring bands entirely — a further product decision beyond this fix round's authorization), I6 (the commune-fiche JSON schema is intentionally minimal — full §5.3 fields like `reseaux[]`/`historique`/`indicateurs_cles` are for the frontend plan), and 8 Minor polish items from the final review (import placement, dead imports, a couple of dead/unreachable micro-branches, `load_udi_reseaux` not deduplicating, unconsumed fields, a redundant test). Only the Critical (C1-C3) and Important (I2/I3/I5) findings, plus a pre-existing `evaluer_bacteriologie`/`score_bacteriologie` contract mismatch surfaced while fixing I5, were addressed in that round.
- **Re-review findings deferred (2026-08-05, diff `5131b38..2500455`, "Ready to merge: Yes"):**
  - **N1 (Important) — the spec's weighted formulas now live in two places.** Fixing C1 (renormalization) required `pipeline/compute_scores.py` to stop calling `score_securite`/`score_mineraux`/`score_gout`/`score_boisson`/`score_cosmetique`/`score_metaux_depots` from the frozen `pipeline/scoring.py` (those wrappers can't skip a missing component) and instead re-implement their weights (0.55/0.25/0.20, 0.70/0.15/0.15, 0.60/0.40, 0.45/0.25/0.15/0.15) and round-before-combine convention directly in the orchestrator. Those 6 `scoring.py` functions are no longer called by any production path — only their own unit tests still exercise them — so a future weight change in `scoring.py` would silently diverge from what's actually published. Fixing this properly means exposing renormalization-aware variants from `scoring.py` itself, which was out of scope for this fix round (frozen module). Needs a decision before the next plan touches either file.
  - Minor: `_moyenne_ou_zero` is now dead code (superseded by `_valeur_disponible`) and should be removed rather than invite reuse of the pattern that caused C1. `_trouver_fichier` picks the alphabetically-first match on multiple hits (oldest year), contradicting `main()`'s docstring ("année la plus récente uniquement") — harmless today (one file per year per directory) but silently wrong if ever given an ambiguous `raw_dir`. `tests/test_pipeline_integration.py`'s comment claiming `main()` expects generic filenames is now false (C3 made it glob-based) — the test still passes but doesn't exercise the real year-suffixed filename path. `donnees_partielles` will be `true` for nearly every real commune (requires all 5 security P-terms present, including PFAS and 4 toxic metals) — correct per the decision, but low discriminative power; worth knowing before the frontend surfaces it. `score_pesticides`/`score_nitrates_securite` still pass a literal `0.0` for one missing sub-argument when the other is available (`pesticide_total or 0.0`, `nitrates or 0.0`) — safe for the nitrates/nitrites case (a `min`-style violation check, absence ≡ no violation) but slightly optimistic for the pesticide linear band, same bug family as C1 at a finer grain than the human's decision covered.
