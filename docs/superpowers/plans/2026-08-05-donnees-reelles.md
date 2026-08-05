# Pipeline sur Données Réelles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the DIS ingestion pipeline to merge multiple years of data.gouv exports, produce `"indisponible"` fiches for communes with zero measurements (not just zero fiches at all), fix a deferred memory concern, and then actually run the pipeline once against real downloaded data to validate it end-to-end.

**Architecture:** Small signature changes to `pipeline/dis_parser.py` (new multi-file variants of the existing single-file functions) and `pipeline/compute_scores.py` (`construire_fiches` takes lists of paths instead of single paths; `main`'s file resolution searches year-suffixed subdirectories). The final task is not a code task — it's running the real pipeline once and validating the result.

**Tech Stack:** Same as the rest of the project — Python 3.12 stdlib (`csv`, `glob`, `os`), `pytest`.

## Global Constraints

- Reuse `pipeline.dis_parser.load_prelevements`, `load_udi_reseaux`, `iter_mesures` and `pipeline.compute_scores.calculer_fiche_commune` exactly as they exist today — do not modify their internals, only add new functions around them.
- `pipeline/scoring.py`, `pipeline/aggregation.py`, `pipeline/recommendations.py` are frozen — do not touch them in this plan.
- `calculer_fiche_commune` already returns `{"statut_donnees": "indisponible", "scores": None}` for a commune with zero measurements (verified, existing behavior) — Task 2 only needs to make sure `construire_fiches` actually calls it for such communes, not reimplement that guard.
- Consumed SANDRE parameter codes (the only ones worth accumulating in memory): the 17 pesticide molecule codes already in `PESTICIDE_CODES`, the 4 metal codes already in `METAUX_LQ` (`1382`, `1369`, `1388`, `1386`), plus `6276`, `8847`, `1340`, `1339`, `1337`, `1338`, `1398`, `1295`, `1345`, `1399`, `1302`, `1392`, `1393`, `1394`.
- `download_data.py` extracts each year's ZIP into its own subdirectory: `data/raw/{year}/DIS_PLV_{year}.txt` etc. (already true today — verified in the previous plan). File resolution must search this layout, not assume a flat directory.
- `DIS_COM_UDI` is a referential snapshot (current commune↔réseau mapping), not a time series — use only the most recent year's file, never merge multiple years of it.
- No test in this plan may require a live network connection or the real ~900 Mo download — all use small fixtures. The real download only happens in Task 5, which is explicitly flagged for confirmation before running.

---

### Task 1: Fusion multi-années — `pipeline/dis_parser.py`

**Files:**
- Modify: `pipeline/dis_parser.py`
- Create: `tests/fixtures/DIS_PLV_annee1.txt`, `tests/fixtures/DIS_PLV_annee2.txt`, `tests/fixtures/DIS_RESULT_annee1.txt`, `tests/fixtures/DIS_RESULT_annee2.txt`
- Test: `tests/test_dis_parser.py`

**Interfaces:**
- Consumes: `pipeline.dis_parser.load_prelevements`, `iter_mesures` (unchanged, already exist)
- Produces: `pipeline.dis_parser.charger_prelevements_multi(plv_paths: list[str]) -> dict[str, PrelevementInfo]`, `pipeline.dis_parser.iter_mesures_multi(result_paths: list[str], prelevements: dict) -> Iterator[tuple[str, str, Mesure]]`

- [ ] **Step 1: Create the fixture files**

Create `tests/fixtures/DIS_PLV_annee1.txt`:
```
cddept,cdreseau,inseecommuneprinc,nomcommuneprinc,cdreseauamont,nomreseauamont,pourcentdebit,referenceprel,dateprel,heureprel,conclusionprel,ugelib,distrlib,moalib,plvconformitebacterio,plvconformitechimique,plvconformitereferencebact,plvconformitereferencechim
"012","012000001","12345","TESTVILLE","","","","REF-A1","2025-01-10","09h00","x","","","","C","C","C","C"
```

Create `tests/fixtures/DIS_PLV_annee2.txt`:
```
cddept,cdreseau,inseecommuneprinc,nomcommuneprinc,cdreseauamont,nomreseauamont,pourcentdebit,referenceprel,dateprel,heureprel,conclusionprel,ugelib,distrlib,moalib,plvconformitebacterio,plvconformitechimique,plvconformitereferencebact,plvconformitereferencechim
"012","012000001","12345","TESTVILLE","","","","REF-A2","2026-01-10","09h00","x","","","","C","C","C","C"
```

Create `tests/fixtures/DIS_RESULT_annee1.txt`:
```
cddept,referenceprel,cdparametresiseeaux,cdparametre,libmajparametre,libminparametre,libwebparametre,qualitparam,insituana,rqana,cdunitereferencesiseeaux,cdunitereference,limitequal,refqual,valtraduite,casparam,referenceanl
"012","REF-A1","NO3","1340","NITRATES (EN NO3)","Nitrates (en NO3)",,"N","L","10","mg/L","162","<=50 mg/L","","10.000000","14797-55-8","ANL-A1"
```

Create `tests/fixtures/DIS_RESULT_annee2.txt`:
```
cddept,referenceprel,cdparametresiseeaux,cdparametre,libmajparametre,libminparametre,libwebparametre,qualitparam,insituana,rqana,cdunitereferencesiseeaux,cdunitereference,limitequal,refqual,valtraduite,casparam,referenceanl
"012","REF-A2","NO3","1340","NITRATES (EN NO3)","Nitrates (en NO3)",,"N","L","12","mg/L","162","<=50 mg/L","","12.000000","14797-55-8","ANL-A2"
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_dis_parser.py`:

```python
from pipeline.dis_parser import charger_prelevements_multi, iter_mesures_multi


def test_charger_prelevements_multi_fusionne_plusieurs_annees():
    idx = charger_prelevements_multi([
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee1.txt"),
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee2.txt"),
    ])
    assert set(idx) == {"REF-A1", "REF-A2"}
    assert idx["REF-A1"].code_insee == "12345"
    assert idx["REF-A2"].code_insee == "12345"


def test_iter_mesures_multi_chaine_plusieurs_annees():
    prelevements = charger_prelevements_multi([
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee1.txt"),
        os.path.join(FIXTURES_DIR, "DIS_PLV_annee2.txt"),
    ])
    resultats = list(iter_mesures_multi([
        os.path.join(FIXTURES_DIR, "DIS_RESULT_annee1.txt"),
        os.path.join(FIXTURES_DIR, "DIS_RESULT_annee2.txt"),
    ], prelevements))
    valeurs = sorted(m.valeur for _, code, m in resultats if code == "1340")
    assert valeurs == [10.0, 12.0]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_dis_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'charger_prelevements_multi'`

- [ ] **Step 4: Implement the two functions**

Append to `pipeline/dis_parser.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dis_parser.py -v`
Expected: PASS (2 new tests)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/dis_parser.py tests/test_dis_parser.py tests/fixtures/DIS_PLV_annee1.txt tests/fixtures/DIS_PLV_annee2.txt tests/fixtures/DIS_RESULT_annee1.txt tests/fixtures/DIS_RESULT_annee2.txt
git commit -m "feat: add multi-year DIS_PLV/DIS_RESULT merging (§2.1)"
```

---

### Task 2: `construire_fiches` — listes de fichiers, filtre mémoire, fiches "indisponible"

**Files:**
- Modify: `pipeline/compute_scores.py`
- Modify: `tests/fixtures/DIS_COM_UDI_sample.txt` (add one zero-measurement commune)
- Test: `tests/test_compute_scores.py`

**Interfaces:**
- Consumes: `pipeline.dis_parser.charger_prelevements_multi`, `iter_mesures_multi`, `load_udi_reseaux` (Task 1 + existing), `pipeline.compute_scores.calculer_fiche_commune` (existing, unchanged)
- Produces: `pipeline.compute_scores.construire_fiches(plv_paths: list[str], result_paths: list[str], udi_path: str, date_reference: date) -> dict` — **signature changed** from single paths to lists (`plv_path`→`plv_paths`, `result_path`→`result_paths`); `udi_path` stays singular.

- [ ] **Step 1: Add the zero-measurement commune to the UDI fixture**

Append this line to `tests/fixtures/DIS_COM_UDI_sample.txt` (keep the existing 3 rows unchanged):
```
"99999","COMMUNE FANTOME","-","099000001","RESEAU JAMAIS ECHANTILLONNE","2020-01-01"
```
(This commune appears in the réseau referential but has no `DIS_PLV`/`DIS_RESULT` rows at all — the case §2.5.6 requires a `"indisponible"` fiche for, not silence.)

- [ ] **Step 2: Write the failing tests**

Update the two existing calls to `construire_fiches` in `tests/test_compute_scores.py` (`test_construire_fiches_depuis_fixtures_reelles` and `test_construire_fiches_bacterio_resolue_via_paris_plm`) — change:
```python
    fiches = construire_fiches(
        plv_path=os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt"),
        result_path=os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt"),
        udi_path=os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"),
        date_reference=date_ref,
    )
```
to:
```python
    fiches = construire_fiches(
        plv_paths=[os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt")],
        result_paths=[os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt")],
        udi_path=os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"),
        date_reference=date_ref,
    )
```
in BOTH tests (this is the only change needed in those two tests — do not touch their other assertions).

Then append a new test:
```python
def test_construire_fiches_commune_sans_mesure_recoit_fiche_indisponible():
    # §2.5.6 : une commune connue via le référentiel réseau (DIS_COM_UDI)
    # mais sans aucune mesure doit recevoir une fiche "indisponible",
    # pas être silencieusement absente du résultat.
    date_ref = date(2026, 8, 5)
    fiches = construire_fiches(
        plv_paths=[os.path.join(FIXTURES_DIR, "DIS_PLV_sample.txt")],
        result_paths=[os.path.join(FIXTURES_DIR, "DIS_RESULT_sample.txt")],
        udi_path=os.path.join(FIXTURES_DIR, "DIS_COM_UDI_sample.txt"),
        date_reference=date_ref,
    )
    assert "99999" in fiches
    assert fiches["99999"]["statut_donnees"] == "indisponible"
    assert fiches["99999"]["scores"] is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_compute_scores.py -v`
Expected: FAIL — the two updated tests fail with `TypeError: construire_fiches() got an unexpected keyword argument 'plv_paths'`, the new test fails the same way.

- [ ] **Step 4: Implement the changes**

In `pipeline/compute_scores.py`, add this constant near `PESTICIDE_CODES`/`METAUX_LQ`:

```python
# Seuls ces codes SANDRE alimentent calculer_fiche_commune — filtrer dès
# l'accumulation évite de charger ~200 codes jamais utilisés en mémoire
# pour chaque commune (limitation mémoire notée lors de la revue finale
# du plan précédent).
CODES_CONSOMMES = set(PESTICIDE_CODES) | set(METAUX_LQ) | {
    "6276", "8847", "1340", "1339", "1337", "1338", "1398", "1295",
    "1345", "1399", "1302", "1392", "1393", "1394",
}
```

Replace the entire body of `construire_fiches` with:

```python
def construire_fiches(plv_paths: list[str], result_paths: list[str], udi_path: str, date_reference: date) -> dict:
    """Charge PLV+RESULT (fusionnés sur plusieurs années, §2.1) + UDI
    (référentiel réseau, une seule année — la plus récente) et construit
    la fiche de CHAQUE commune connue, y compris celles sans aucune mesure
    (§2.5.6 : fiche "indisponible", jamais une absence silencieuse)."""
    prelevements = charger_prelevements_multi(plv_paths)
    reseaux_par_commune = load_udi_reseaux(udi_path)

    mesures_par_commune: dict = {}
    for code_insee, code_parametre, mesure in iter_mesures_multi(result_paths, prelevements):
        if code_parametre not in CODES_CONSOMMES:
            continue
        mesures_par_commune.setdefault(code_insee, {}).setdefault(code_parametre, []).append(mesure)

    historique_bacterio_par_commune: dict = {}
    for info in prelevements.values():
        if info.conforme_bacterio is None:
            continue
        historique_bacterio_par_commune.setdefault(info.code_insee, []).append(
            ConclusionBacterio(date_prelevement=info.date_prelevement, conforme=info.conforme_bacterio)
        )

    codes_connus = (
        set(mesures_par_commune)
        | set(reseaux_par_commune)
        | {info.code_insee for info in prelevements.values()}
    )

    fiches = {}
    for code_insee in codes_connus:
        mesures_par_parametre = mesures_par_commune.get(code_insee, {})
        historique = historique_bacterio_par_commune.get(code_insee, [])
        fiches[code_insee] = calculer_fiche_commune(code_insee, mesures_par_parametre, historique, date_reference)
    return fiches
```

Add `charger_prelevements_multi, iter_mesures_multi` to the existing `from pipeline.dis_parser import (...)` import line at the top of `pipeline/compute_scores.py` (it currently imports `load_prelevements, load_udi_reseaux, iter_mesures` — add the two new names, keep the existing three since `load_udi_reseaux` is still used directly).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_compute_scores.py -v`
Expected: PASS (all tests in the file, including the 1 new one)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/compute_scores.py tests/test_compute_scores.py tests/fixtures/DIS_COM_UDI_sample.txt
git commit -m "feat: multi-year construire_fiches, memory filter, indisponible fiches (§2.5.6)"
```

---

### Task 3: `main()` — résolution de fichiers multi-années via `_trouver_fichiers`

**Files:**
- Modify: `pipeline/compute_scores.py`
- Test: `tests/test_compute_scores.py`

**Interfaces:**
- Consumes: `pipeline.compute_scores.construire_fiches` (Task 2, list-based signature)
- Produces: `pipeline.compute_scores._trouver_fichiers(raw_dir: str, motif: str) -> list[str]` — **replaces** the previous `_trouver_fichier` (singular) entirely; nothing else in the codebase calls the old name.

- [ ] **Step 1: Write the failing tests**

Replace the existing `test_trouver_fichier_resout_nom_suffixe_annee` and `test_trouver_fichier_leve_si_absent` tests in `tests/test_compute_scores.py` with:

```python
def test_trouver_fichiers_recherche_sous_repertoires_annuels(tmp_path):
    (tmp_path / "2025").mkdir()
    (tmp_path / "2026").mkdir()
    (tmp_path / "2025" / "DIS_PLV_2025.txt").write_text("x", encoding="utf-8")
    (tmp_path / "2026" / "DIS_PLV_2026.txt").write_text("x", encoding="utf-8")
    resultats = _trouver_fichiers(str(tmp_path), "DIS_PLV*.txt")
    assert len(resultats) == 2
    assert resultats[0].endswith("DIS_PLV_2025.txt")
    assert resultats[1].endswith("DIS_PLV_2026.txt")


def test_trouver_fichiers_recherche_aussi_a_plat(tmp_path):
    (tmp_path / "DIS_PLV.txt").write_text("x", encoding="utf-8")
    resultats = _trouver_fichiers(str(tmp_path), "DIS_PLV*.txt")
    assert len(resultats) == 1


def test_trouver_fichiers_leve_si_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        _trouver_fichiers(str(tmp_path), "DIS_PLV*.txt")
```

Update the existing `from pipeline.compute_scores import (...)` import line in the test file: remove `_trouver_fichier`, add `_trouver_fichiers`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compute_scores.py -v`
Expected: FAIL with `ImportError: cannot import name '_trouver_fichiers'`

- [ ] **Step 3: Replace `_trouver_fichier` and update `main`**

In `pipeline/compute_scores.py`, replace the entire `_trouver_fichier` function with:

```python
def _trouver_fichiers(raw_dir: str, motif: str) -> list[str]:
    """Résout tous les fichiers DIS correspondant au motif, à plat dans
    raw_dir OU dans ses sous-répertoires annuels (data/raw/{annee}/...,
    layout réel produit par pipeline/download_data.py). Retourne une liste
    triée (donc chronologique pour des noms suffixés par année)."""
    correspondances = sorted(glob.glob(os.path.join(raw_dir, motif)))
    correspondances += sorted(glob.glob(os.path.join(raw_dir, "*", motif)))
    if not correspondances:
        raise FileNotFoundError(f"Aucun fichier correspondant à {motif!r} dans {raw_dir} (ni ses sous-répertoires)")
    return correspondances
```

Replace `main`'s file-resolution lines:
```python
    plv_path = _trouver_fichier(raw_dir, "DIS_PLV*.txt")
    result_path = _trouver_fichier(raw_dir, "DIS_RESULT*.txt")
    udi_path = _trouver_fichier(raw_dir, "DIS_COM_UDI*.txt")

    fiches = construire_fiches(plv_path, result_path, udi_path, date_reference)
```
with:
```python
    plv_paths = _trouver_fichiers(raw_dir, "DIS_PLV*.txt")
    result_paths = _trouver_fichiers(raw_dir, "DIS_RESULT*.txt")
    udi_path = _trouver_fichiers(raw_dir, "DIS_COM_UDI*.txt")[-1]  # référentiel réseau : année la plus récente uniquement

    fiches = construire_fiches(plv_paths, result_paths, udi_path, date_reference)
```

Update the `__main__` block to point at the PARENT `data/raw` directory (not a specific year subfolder), since `_trouver_fichiers` now searches year-subdirectories itself:
```python
if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main(
        raw_dir=os.path.join(PROJECT_ROOT, "data", "raw"),
        output_dir=os.path.join(PROJECT_ROOT, "public", "data"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compute_scores.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the entire test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests across the whole project — 110 pre-existing plus this plan's new ones so far)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/compute_scores.py tests/test_compute_scores.py
git commit -m "feat: multi-year file resolution via year-subdirectory search (§2.1)"
```

---

### Task 4: Test d'intégration bout-en-bout multi-années via `main()`

**Files:**
- Test: `tests/test_pipeline_integration.py`

**Interfaces:**
- Consumes: `pipeline.compute_scores.main` (Task 3, now multi-year-capable)

- [ ] **Step 1: Write the test**

Append to `tests/test_pipeline_integration.py`:

```python
def test_pipeline_multi_annees_fusionne_via_main(tmp_path):
    import shutil
    from datetime import date

    raw_dir = tmp_path / "raw"
    (raw_dir / "2025").mkdir(parents=True)
    (raw_dir / "2026").mkdir(parents=True)
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_annee1.txt"), raw_dir / "2025" / "DIS_PLV_2025.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_annee1.txt"), raw_dir / "2025" / "DIS_RESULT_2025.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_PLV_annee2.txt"), raw_dir / "2026" / "DIS_PLV_2026.txt")
    shutil.copy(os.path.join(FIXTURES_DIR, "DIS_RESULT_annee2.txt"), raw_dir / "2026" / "DIS_RESULT_2026.txt")

    udi_contenu = (
        "inseecommune,nomcommune,quartier,cdreseau,nomreseau,debutalim\n"
        '"12345","TESTVILLE","-","012000001","RESEAU TEST","2010-01-01"\n'
    )
    (raw_dir / "2026" / "DIS_COM_UDI_2026.txt").write_text(udi_contenu, encoding="utf-8")

    output_dir = tmp_path / "output"
    main(raw_dir=str(raw_dir), output_dir=str(output_dir), date_reference=date(2026, 8, 5))

    fiche = json.loads((output_dir / "communes" / "12345.json").read_text(encoding="utf-8"))
    assert fiche["statut_donnees"] == "complet"
    # nitrates 10 (2025) et 12 (2026), tous deux bien en dessous de 50 -> pas de veto,
    # peu importe le poids relatif exact des deux années dans la moyenne pondérée.
    assert fiche["scores"]["boisson"]["veto_sanitaire"] is False
```

(`FIXTURES_DIR`, `main`, `json`, `os` should already be imported/defined earlier in this test file from the previous plan's Task 10 — reuse them, don't redefine.)

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `pytest tests/test_pipeline_integration.py -v`
Expected: Should PASS immediately if Tasks 1-3 are correctly implemented (this is a wiring-verification test, like Task 10 of the previous plan — if it fails, diagnose against Tasks 1-3's code, do not adjust this test's expectations without understanding why).

- [ ] **Step 3: Run the entire test suite one final time**

Run: `pytest tests/ -v`
Expected: PASS (all tests, full project)

- [ ] **Step 4: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add tests/test_pipeline_integration.py
git commit -m "test: add multi-year end-to-end integration test via main()"
```

---

### Task 5: Exécution réelle et validation (opérationnel, pas de code)

**This task is not a TDD task — it is running the real pipeline once and checking the result.** It involves downloading real data.gouv exports (~900 Mo total across 4 years) and processing multi-million-row files, which takes real time and bandwidth. **Confirm with the human before running this task** — do not run it automatically just because Tasks 1-4 completed.

- [ ] **Step 1: Download the real data**

```bash
cd "C:/Repos/Quali'eau"
python pipeline/download_data.py
```
Expected: 4 ZIPs downloaded to `data/raw/` (`dis-2023.zip` .. `dis-2026.zip`, ~900 Mo total) and extracted into `data/raw/2023/` .. `data/raw/2026/`, each containing `DIS_PLV_{year}.txt`, `DIS_RESULT_{year}.txt`, `DIS_COM_UDI_{year}.txt`. This will take a while depending on connection speed — let it run to completion.

- [ ] **Step 2: Run the real scoring pipeline, timed and memory-tracked**

```bash
cd "C:/Repos/Quali'eau"
python -c "
import time, tracemalloc, sys
sys.path.insert(0, '.')
from pipeline.compute_scores import main
import os
tracemalloc.start()
t0 = time.time()
main(raw_dir=os.path.join('data', 'raw'), output_dir=os.path.join('public', 'data'))
elapsed = time.time() - t0
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(f'Terminé en {elapsed:.1f}s, pic mémoire {peak/1e6:.0f} Mo')
"
```
Expected: completes without crashing, prints elapsed time and peak memory. If peak memory is in the multiple-GB range despite the `CODES_CONSOMMES` filter from Task 2, stop and report back before proceeding — that would mean the filter isn't working as expected, not something to silently work around.

- [ ] **Step 3: Sanity-check the output**

```bash
cd "C:/Repos/Quali'eau"
python -c "
import json, os
files = os.listdir('public/data/communes')
print(f'{len(files)} fiches communales générées')
with open('public/data/index.json', encoding='utf-8') as f:
    print(json.load(f))
# Inspecte une commune connue (Paris, déjà utilisée comme exemple dans SPECIFICATION.md)
with open('public/data/communes/75056.json', encoding='utf-8') as f:
    fiche = json.load(f)
    print(json.dumps(fiche, indent=2, ensure_ascii=False)[:2000])
"
```
Expected: a plausible number of fiches (tens of thousands), `index.json` with sensible `nb_communes_scorees`/`nb_communes_sans_donnees` counts, and Paris's fiche (`75056`) showing a `statut_donnees: "complet"` with scores that look plausible (not `null`, not obviously wrong given what's publicly known about Paris tap water — e.g. a "durete_calcaire" note reflecting genuinely hard water).

- [ ] **Step 4: Decide on committing the output**

`public/data/` will contain ~35 000 JSON files. Check `.gitignore` — if `public/data/` (or `data/raw/`) isn't already ignored, ask the human whether these generated files should be committed now (useful for a first deployable site) or left generated-only (regenerated by the CI workflow in a future plan). Do not commit ~35 000 files without explicit confirmation.

---

## Out of Scope (separate future plan)

- **Réseau-principal filtering inside `construire_fiches`** — still not wired in (carried over from the previous plan); a genuinely multi-réseau commune still has all its réseaux' measurements merged together rather than scored per-réseau.
- **`national.geojson` / map geometry, the full §5.3 fiche schema (`reseaux[]`, `historique`, `indicateurs_cles`, `commune.nom/departement/population`), and the static site itself** — all Phase 2, a separate plan.
- **N1 from the previous plan's final review** (weighted-formula duplication between `pipeline/scoring.py` and `pipeline/compute_scores.py`) — unaffected by this plan, still needs a decision before either file is next touched.
- **GitHub Actions workflow** (`update-data.yml`) to automate Task 5's steps on a weekly schedule — mechanical once Task 5 is proven to work manually.
