# Moteur de Scoring & Recommandations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pure-Python domain logic of Quali'eau — temporal aggregation, the two scoring formulas (`S_boisson`, `S_cosmetique`), the cost-estimation module, and the recommendation engine — as fully tested, dependency-free functions that `pipeline/compute_scores.py` will later orchestrate against real data.gouv data.

**Architecture:** Five small modules under `pipeline/`, each with one responsibility (data models, temporal aggregation, boisson/cosmétique scoring, cost estimation, recommendations). No I/O, no network, no pandas — every function takes plain values or dataclasses and returns plain values, so every rule from `SPECIFICATION.md` v1.3.0 §2.5/§3/§4.1/§5.6 is testable in isolation with hand-computed expected values.

**Tech Stack:** Python 3.12, stdlib only (`dataclasses`, `math`, `datetime`), `pytest` for tests. No pandas/requests — those belong to the separate data-ingestion pipeline (`download_data.py` + DIS parsing), out of scope for this plan.

## Global Constraints

- All formulas must match `SPECIFICATION.md` v1.3.0 exactly — §2.5 (agrégation/LQ), §3.1 (boisson, incl. the v1.3 `P_nitrates` fix), §3.2 (cosmétique, incl. the v1.3 hardness-continuity wording), §4.1/§5.6 (cost estimation).
- Rounding: "arrondi à l'entier" (§3 intro) is round-half-up, implemented once as `arrondi(x) = floor(x + 0.5)` — never rely on Python's banker's-rounding `round()`.
- Sub-scores are **rounded before** being combined into a parent formula (this is what the spec's own worked examples do: `0.55×95 + 0.25×85 + 0.20×80 = 89.5 → 90` uses the rounded sub-scores 95/85/80, not raw floats).
- All final and intermediate scores are bounded to `[0, 100]`.
- No external dependencies beyond `pytest` for this plan.
- Package root is `pipeline/` at the repo root (`C:\Repos\Quali'eau\`); tests live in `tests/`, run from the repo root.

---

### Task 1: Modèles de données & pondération temporelle

**Files:**
- Create: `pipeline/__init__.py` (empty)
- Create: `pipeline/models.py`
- Create: `pipeline/aggregation.py`
- Create: `pipeline/requirements.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Test: `tests/test_aggregation.py`

**Interfaces:**
- Produces: `pipeline.models.Mesure(valeur: float, sous_lq: bool, date_prelevement: date)`, `pipeline.models.ConclusionBacterio(date_prelevement: date, conforme: bool)`
- Produces: `pipeline.aggregation.ponderation_temporelle(delta_jours: int) -> float`
- Produces: `pipeline.aggregation.moyenne_ponderee(mesures: list[Mesure], date_reference: date) -> float | None`

- [ ] **Step 1: Create package scaffolding**

```bash
mkdir -p "C:/Repos/Quali'eau/pipeline" "C:/Repos/Quali'eau/tests"
```

Create `pipeline/__init__.py` (empty file) and `tests/__init__.py` (empty file).

Create `pipeline/requirements.txt`:
```
pytest>=8.0
```

Create `pytest.ini` at the repo root:
```ini
[pytest]
pythonpath = .
```

- [ ] **Step 2: Create `pipeline/models.py`**

```python
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
```

- [ ] **Step 3: Write the failing test for weighted averaging**

Create `tests/test_aggregation.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_aggregation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.aggregation'`

- [ ] **Step 5: Implement `pipeline/aggregation.py` (weighted average part)**

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_aggregation.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/ tests/ pytest.ini
git commit -m "feat: add data models and temporal-weighting aggregation (§2.5)"
```

---

### Task 2: Règle de recalcul des sommes réglementaires (LQ)

**Files:**
- Modify: `pipeline/aggregation.py`
- Test: `tests/test_aggregation.py`

**Interfaces:**
- Consumes: `pipeline.models.Mesure`
- Produces: `pipeline.aggregation.valeur_somme_reglementaire(total: Mesure | None, composantes: list[Mesure]) -> float | None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_aggregation.py`:

```python
from pipeline.aggregation import valeur_somme_reglementaire


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aggregation.py -v`
Expected: FAIL with `ImportError: cannot import name 'valeur_somme_reglementaire'`

- [ ] **Step 3: Implement the function**

Append to `pipeline/aggregation.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aggregation.py -v`
Expected: PASS (8 tests total)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/aggregation.py tests/test_aggregation.py
git commit -m "feat: add LQ priority rule for regulatory sums (§2.5.3 v1.3)"
```

---

### Task 3: Sous-score Sécurité Sanitaire ($S_{\text{sécurité}}$) — inclut le correctif `P_nitrates`

**Files:**
- Create: `pipeline/scoring.py`
- Test: `tests/test_scoring_securite.py`

**Interfaces:**
- Produces: `pipeline.scoring.arrondi(x: float) -> int`
- Produces: `pipeline.scoring.score_bacteriologie(conforme_dernier: bool, resolu: bool) -> float`
- Produces: `pipeline.scoring.score_pesticides(total: float, molecule_max: float) -> float`
- Produces: `pipeline.scoring.score_pfas(valeur: float) -> float`
- Produces: `pipeline.scoring.score_metal(valeur: float, rq: float, lq: float) -> float`
- Produces: `pipeline.scoring.score_nitrates_securite(nitrates: float, nitrites: float) -> float`
- Produces: `pipeline.scoring.score_securite(p_bact: float, p_pest: float, p_pfas: float, p_metaux: float, p_nitrates: float) -> float`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring_securite.py`:

```python
from pipeline.scoring import (
    arrondi,
    score_bacteriologie,
    score_pesticides,
    score_pfas,
    score_metal,
    score_nitrates_securite,
    score_securite,
)


def test_arrondi_moitie_monte():
    assert arrondi(89.5) == 90
    assert arrondi(75.8) == 76
    assert arrondi(59.43) == 59


def test_bacteriologie_conforme():
    assert score_bacteriologie(conforme_dernier=True, resolu=False) == 100.0


def test_bacteriologie_resolue():
    assert score_bacteriologie(conforme_dernier=False, resolu=True) == 50.0


def test_bacteriologie_active():
    assert score_bacteriologie(conforme_dernier=False, resolu=False) == 0.0


def test_pesticides_parfait():
    assert score_pesticides(total=0.03, molecule_max=0.01) == 100.0


def test_pesticides_bande_lineaire():
    # total=0.05 -> 100, total=0.5 -> 70 (bornes de la bande linéaire)
    assert abs(score_pesticides(total=0.05, molecule_max=0.02) - 100.0) < 1e-9
    assert abs(score_pesticides(total=0.5, molecule_max=0.05) - 70.0) < 1e-9
    # milieu de bande : total=0.275 -> 85
    assert abs(score_pesticides(total=0.275, molecule_max=0.05) - 85.0) < 1e-6


def test_pesticides_depassement_total():
    # total=1.0 > 0.5 -> 50 * (0.5/1.0) = 25
    assert abs(score_pesticides(total=1.0, molecule_max=0.05) - 25.0) < 1e-9


def test_pesticides_depassement_molecule():
    # molecule=0.2 > 0.1 -> 50 * (0.1/0.2) = 25, même si le total est bas
    assert abs(score_pesticides(total=0.1, molecule_max=0.2) - 25.0) < 1e-9


def test_pfas_parfait():
    assert score_pfas(0.01) == 100.0


def test_pfas_bande_lineaire():
    assert abs(score_pfas(0.02) - 90.0) < 1e-9
    assert abs(score_pfas(0.10) - 60.0) < 1e-9


def test_pfas_depassement_plafonne():
    # 0.10 -> 60 (borne exacte de la bande linéaire, cf. test précédent)
    # 0.20 -> 60*0.10/0.20 = 30 (plafond atteint)
    assert abs(score_pfas(0.20) - 30.0) < 1e-9
    # 0.15 -> 60*0.10/0.15 = 40, sous le plafond de 30 -> doit être plafonné à 30
    assert abs(score_pfas(0.15) - 30.0) < 1e-9


def test_metal_conforme():
    assert score_metal(valeur=0.5, rq=1.0, lq=2.0) == 100.0


def test_metal_interpolation():
    # RQ=1, LQ=2 : à mi-chemin (1.5) -> 100 - 0.5/1.0*30 = 85
    assert abs(score_metal(valeur=1.5, rq=1.0, lq=2.0) - 85.0) < 1e-9


def test_metal_depassement():
    # LQ=2, valeur=4 -> 70 * 2/4 = 35
    assert abs(score_metal(valeur=4.0, rq=1.0, lq=2.0) - 35.0) < 1e-9


def test_nitrates_securite_conforme():
    assert score_nitrates_securite(nitrates=40.0, nitrites=0.05) == 100.0


def test_nitrates_securite_depassement_nitrates():
    # BUG CRITIQUE v1.1/v1.2 : ce test aurait été impossible à écrire correctement
    # avant le correctif v1.3, car P_nitrates n'existait pas.
    # 60 mg/L > 50 -> 50 * (50/60) = 41.666...
    resultat = score_nitrates_securite(nitrates=60.0, nitrites=0.05)
    assert abs(resultat - 41.6666667) < 1e-4


def test_nitrates_securite_depassement_nitrites():
    # 0.2 mg/L > 0.1 -> 50 * (0.1/0.2) = 25
    resultat = score_nitrates_securite(nitrates=20.0, nitrites=0.2)
    assert abs(resultat - 25.0) < 1e-9


def test_nitrates_securite_double_depassement_prend_le_pire():
    # nitrates -> 50*50/60=41.67 ; nitrites -> 50*0.1/0.2=25 -> min = 25
    resultat = score_nitrates_securite(nitrates=60.0, nitrites=0.2)
    assert abs(resultat - 25.0) < 1e-9


def test_securite_est_le_minimum():
    assert score_securite(p_bact=100, p_pest=100, p_pfas=100, p_metaux=100, p_nitrates=41.67) == 41.67
    assert score_securite(p_bact=0, p_pest=100, p_pfas=100, p_metaux=100, p_nitrates=100) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scoring_securite.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.scoring'`

- [ ] **Step 3: Implement `pipeline/scoring.py` (sécurité sanitaire part)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring_securite.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/scoring.py tests/test_scoring_securite.py
git commit -m "feat: implement S_securite scoring incl. P_nitrates fix (§3.1.1 v1.3)"
```

---

### Task 4: Sous-scores Minéraux & Goût

**Files:**
- Modify: `pipeline/scoring.py`
- Test: `tests/test_scoring_mineraux_gout.py`

**Interfaces:**
- Produces: `pipeline.scoring.score_nitrates_mineraux(valeur: float) -> float`
- Produces: `pipeline.scoring.score_chlorures(valeur: float) -> float`
- Produces: `pipeline.scoring.score_sulfates(valeur: float) -> float`
- Produces: `pipeline.scoring.score_mineraux(nitrates: float, chlorures: float, sulfates: float) -> float`
- Produces: `pipeline.scoring.score_chlore_gout(valeur: float) -> float`
- Produces: `pipeline.scoring.score_turbidite(valeur: float) -> float`
- Produces: `pipeline.scoring.score_gout(chlore: float, turbidite: float) -> float`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring_mineraux_gout.py`:

```python
from pipeline.scoring import (
    score_nitrates_mineraux,
    score_chlorures,
    score_sulfates,
    score_mineraux,
    score_chlore_gout,
    score_turbidite,
    score_gout,
)


def test_nitrates_mineraux_bandes():
    assert score_nitrates_mineraux(5.0) == 100.0
    assert score_nitrates_mineraux(15.0) == 85.0
    assert score_nitrates_mineraux(30.0) == 65.0
    assert score_nitrates_mineraux(45.0) == 40.0
    assert score_nitrates_mineraux(60.0) == 0.0


def test_chlorures_bandes():
    assert score_chlorures(50.0) == 100.0
    assert abs(score_chlorures(150.0) - 70.0) < 1e-9  # milieu 100-200 -> 100-60*0.5=70
    assert abs(score_chlorures(400.0) - 20.0) < 1e-9  # 40*200/400=20


def test_sulfates_bandes():
    assert score_sulfates(100.0) == 100.0
    assert abs(score_sulfates(200.0) - 70.0) < 1e-9  # milieu 150-250 -> 70
    assert abs(score_sulfates(500.0) - 20.0) < 1e-9  # 40*250/500=20


def test_mineraux_ponderation():
    # nitrates=100 (0.70), chlorures=100 (0.15), sulfates=100 (0.15) -> 100
    assert abs(score_mineraux(nitrates=5.0, chlorures=50.0, sulfates=100.0) - 100.0) < 1e-9
    # nitrates=0 (60mg/L), chlorures=100, sulfates=100 -> 0.70*0+0.15*100+0.15*100=30
    assert abs(score_mineraux(nitrates=60.0, chlorures=50.0, sulfates=50.0) - 30.0) < 1e-9


def test_chlore_gout_bandes():
    assert score_chlore_gout(0.03) == 100.0
    assert score_chlore_gout(0.10) == 80.0
    assert score_chlore_gout(0.20) == 50.0
    assert score_chlore_gout(0.40) == 20.0


def test_turbidite_bandes():
    assert score_turbidite(0.1) == 100.0
    assert score_turbidite(0.5) == 80.0
    assert score_turbidite(1.5) == 55.0
    assert score_turbidite(3.0) == 30.0


def test_gout_ponderation():
    # chlore=100 (0.60), turbidite=100 (0.40) -> 100
    assert abs(score_gout(chlore=0.03, turbidite=0.1) - 100.0) < 1e-9
    # chlore=20 (0.60), turbidite=30 (0.40) -> 0.6*20+0.4*30=12+12=24
    assert abs(score_gout(chlore=0.40, turbidite=3.0) - 24.0) < 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scoring_mineraux_gout.py -v`
Expected: FAIL with `ImportError: cannot import name 'score_nitrates_mineraux'`

- [ ] **Step 3: Implement the functions**

Append to `pipeline/scoring.py`:

```python
def score_nitrates_mineraux(valeur: float) -> float:
    """§3.1.2 N_nitrates (gustatif/confort — distinct de P_nitrates en §3.1.1)."""
    if valeur < 10:
        return 100.0
    if valeur < 25:
        return 85.0
    if valeur < 40:
        return 65.0
    if valeur <= 50:
        return 40.0
    return 0.0


def score_chlorures(valeur: float) -> float:
    """§3.1.2 N_chlorures."""
    if valeur <= 100:
        return 100.0
    if valeur <= 200:
        return 100.0 - (valeur - 100) / 100.0 * 60.0
    return max(0.0, 40.0 * 200.0 / valeur)


def score_sulfates(valeur: float) -> float:
    """§3.1.2 N_sulfates."""
    if valeur <= 150:
        return 100.0
    if valeur <= 250:
        return 100.0 - (valeur - 150) / 100.0 * 60.0
    return max(0.0, 40.0 * 250.0 / valeur)


def score_mineraux(nitrates: float, chlorures: float, sulfates: float) -> float:
    """§3.1.2 S_mineraux = 0.70*N_nitrates + 0.15*N_chlorures + 0.15*N_sulfates."""
    return (0.70 * score_nitrates_mineraux(nitrates)
            + 0.15 * score_chlorures(chlorures)
            + 0.15 * score_sulfates(sulfates))


def score_chlore_gout(valeur: float) -> float:
    """§3.1.3 N_chlore."""
    if valeur < 0.05:
        return 100.0
    if valeur <= 0.15:
        return 80.0
    if valeur <= 0.30:
        return 50.0
    return 20.0


def score_turbidite(valeur: float) -> float:
    """§3.1.3 N_turbidite."""
    if valeur < 0.3:
        return 100.0
    if valeur <= 1.0:
        return 80.0
    if valeur <= 2.0:
        return 55.0
    return 30.0


def score_gout(chlore: float, turbidite: float) -> float:
    """§3.1.3 S_gout = 0.60*N_chlore + 0.40*N_turbidite."""
    return 0.60 * score_chlore_gout(chlore) + 0.40 * score_turbidite(turbidite)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring_mineraux_gout.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/scoring.py tests/test_scoring_mineraux_gout.py
git commit -m "feat: implement S_mineraux and S_gout scoring (§3.1.2, §3.1.3)"
```

---

### Task 5: Score Boisson global (avec veto sanitaire)

**Files:**
- Modify: `pipeline/scoring.py`
- Test: `tests/test_scoring_boisson.py`

**Interfaces:**
- Consumes: `pipeline.scoring.arrondi`
- Produces: `pipeline.scoring.veto_sanitaire(bact_actif: bool, nitrates: float, nitrites: float, pb: float, as_: float, cd: float, pesticide_molecule_max: float, pesticide_total: float, pfas: float) -> bool`
- Produces: `pipeline.scoring.score_boisson(s_securite: float, s_mineraux: float, s_gout: float, veto: bool) -> int`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring_boisson.py`:

```python
from pipeline.scoring import veto_sanitaire, score_boisson


def test_veto_declenche_par_nitrates():
    assert veto_sanitaire(
        bact_actif=False, nitrates=60.0, nitrites=0.05,
        pb=1.0, as_=1.0, cd=1.0,
        pesticide_molecule_max=0.01, pesticide_total=0.1, pfas=0.01,
    ) is True


def test_veto_non_declenche_cas_conforme():
    assert veto_sanitaire(
        bact_actif=False, nitrates=20.0, nitrites=0.05,
        pb=1.0, as_=1.0, cd=1.0,
        pesticide_molecule_max=0.01, pesticide_total=0.1, pfas=0.01,
    ) is False


def test_score_boisson_exemple_spec_paris():
    # Reprend l'exemple de la fiche communale (§5.3) : 95/85/80, sans veto -> 90
    assert score_boisson(s_securite=95, s_mineraux=85, s_gout=80, veto=False) == 90


def test_score_boisson_veto_nitrates_plafonne_reellement():
    # Régression du bug critique v1.1/v1.2 : nitrates=60mg/L (dépassement),
    # tout le reste parfait. P_nitrates = 50*(50/60) = 41.67 -> S_securite = 41.67.
    # S_mineraux : nitrates(0) 0.70 + chlorures(100) 0.15 + sulfates(100) 0.15 = 30.
    # S_gout = 100 (chlore/turbidite parfaits).
    # AVANT LE CORRECTIF : S_securite valait 100 (P_nitrates absent) et le score
    # affichait ~83 (classe B) malgré le dépassement réglementaire.
    # APRES LE CORRECTIF : le score doit être plafonné à ~42 (S_securite arrondi).
    score = score_boisson(s_securite=41.6666667, s_mineraux=30.0, s_gout=100.0, veto=True)
    assert score == 42
    assert score < 50  # doit rester dans le bas du barème, jamais "Bon" (classe B, >=80)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scoring_boisson.py -v`
Expected: FAIL with `ImportError: cannot import name 'veto_sanitaire'`

- [ ] **Step 3: Implement the functions**

Append to `pipeline/scoring.py`:

```python
def veto_sanitaire(bact_actif: bool, nitrates: float, nitrites: float,
                    pb: float, as_: float, cd: float,
                    pesticide_molecule_max: float, pesticide_total: float,
                    pfas: float) -> bool:
    """§3.1 — conditions de veto sanitaire (facteur limitant)."""
    return (
        bact_actif
        or nitrates > 50 or nitrites > 0.1
        or pb > 10 or as_ > 10 or cd > 5
        or pesticide_molecule_max > 0.1 or pesticide_total > 0.5
        or pfas > 0.1
    )


def score_boisson(s_securite: float, s_mineraux: float, s_gout: float, veto: bool) -> int:
    """§3.1 S_boisson = 0.55*S_securite + 0.25*S_mineraux + 0.20*S_gout,
    plafonné à S_securite en cas de veto sanitaire (correctif v1.3 : ce
    plafond n'a d'effet réel que parce que P_nitrates fait maintenant
    partie de S_securite, cf. score_nitrates_securite)."""
    s_securite_r = arrondi(s_securite)
    s_mineraux_r = arrondi(s_mineraux)
    s_gout_r = arrondi(s_gout)
    brut = 0.55 * s_securite_r + 0.25 * s_mineraux_r + 0.20 * s_gout_r
    if veto:
        brut = min(brut, s_securite_r)
    return arrondi(max(0.0, min(100.0, brut)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring_boisson.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/scoring.py tests/test_scoring_boisson.py
git commit -m "feat: implement S_boisson with working sanitary veto (§3.1 v1.3)"
```

---

### Task 6: Sous-scores Cosmétique (dureté, chlore, pH, métaux/dépôts)

**Files:**
- Modify: `pipeline/scoring.py`
- Test: `tests/test_scoring_cosmetique.py`

**Interfaces:**
- Produces: `pipeline.scoring.score_durete(th: float) -> float`
- Produces: `pipeline.scoring.score_chlore_cosmetique(valeur: float) -> float`
- Produces: `pipeline.scoring.score_ph(ph: float) -> float`
- Produces: `pipeline.scoring.score_cuivre(valeur: float) -> float`
- Produces: `pipeline.scoring.score_fer(valeur: float) -> float`
- Produces: `pipeline.scoring.score_manganese(valeur: float) -> float`
- Produces: `pipeline.scoring.score_metaux_depots(cu: float, fe: float, mn: float) -> float`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring_cosmetique.py`:

```python
from pipeline.scoring import (
    score_durete,
    score_chlore_cosmetique,
    score_ph,
    score_cuivre,
    score_fer,
    score_manganese,
    score_metaux_depots,
)


def test_durete_reperes_spec():
    # Repères documentés en §3.2.1
    assert abs(score_durete(4.0) - 90.0) < 1e-9
    assert abs(score_durete(10.0) - 100.0) < 1e-9
    assert abs(score_durete(20.0) - 87.5) < 1e-9
    assert abs(score_durete(30.0) - 60.0) < 1e-9
    assert abs(score_durete(40.0) - 30.0) < 1e-9
    assert score_durete(50.0) == 0.0
    assert score_durete(60.0) == 0.0  # plancher, ne devient pas négatif


def test_durete_exemple_paris():
    # TH=30.19 -> 75 - 3.0*(30.19-25) = 59.43 (arrondi -> 59, cf. fiche §5.3)
    resultat = score_durete(30.19)
    assert abs(resultat - 59.43) < 1e-2


def test_durete_paliers_bas():
    assert score_durete(1.0) == 85.0
    assert score_durete(5.0) == 90.0
    assert score_durete(12.0) == 100.0


def test_chlore_cosmetique_bandes():
    assert score_chlore_cosmetique(0.03) == 100.0
    assert score_chlore_cosmetique(0.10) == 80.0
    assert score_chlore_cosmetique(0.20) == 50.0
    assert score_chlore_cosmetique(0.40) == 20.0


def test_ph_bandes():
    assert score_ph(7.0) == 100.0
    assert score_ph(6.6) == 85.0
    assert score_ph(7.6) == 80.0
    assert score_ph(8.0) == 55.0
    assert score_ph(9.0) == 25.0
    assert score_ph(6.0) == 25.0


def test_cuivre_bandes():
    assert score_cuivre(0.05) == 100.0
    assert abs(score_cuivre(0.3) - 75.0) < 1e-9  # milieu 0.1-0.5 -> 100-0.5*50=75
    assert score_cuivre(1.0) == 30.0


def test_fer_bandes():
    assert score_fer(30.0) == 100.0
    assert abs(score_fer(125.0) - 70.0) < 1e-9  # milieu 50-200 -> 100-0.5*60=70
    assert score_fer(300.0) == 20.0


def test_manganese_bandes():
    assert score_manganese(5.0) == 100.0
    assert abs(score_manganese(30.0) - 70.0) < 1e-9  # milieu 10-50 -> 70
    assert score_manganese(60.0) == 20.0


def test_metaux_depots_est_le_minimum():
    assert abs(score_metaux_depots(cu=0.08, fe=62.5, mn=5.0) - 95.0) < 1e-6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scoring_cosmetique.py -v`
Expected: FAIL with `ImportError: cannot import name 'score_durete'`

- [ ] **Step 3: Implement the functions**

Append to `pipeline/scoring.py`:

```python
def score_durete(th: float) -> float:
    """§3.2.1 S_durete — par paliers en dessous de 15 °fH, continue au-delà
    (correction de formulation v1.3 : la fonction n'est PAS continue en
    dessous de 15 °fH, contrairement à ce qu'affirmait la v1.1/v1.2)."""
    if th < 3:
        return 85.0
    if th < 8:
        return 90.0
    if th <= 15:
        return 100.0
    if th <= 25:
        return 100.0 - 2.5 * (th - 15)
    if th <= 35:
        return 75.0 - 3.0 * (th - 25)
    return max(0.0, 45.0 - 3.0 * (th - 35))


def score_chlore_cosmetique(valeur: float) -> float:
    """§3.2.2 S_chlore (chlore total 1399, même barème que N_chlore boisson)."""
    if valeur <= 0.05:
        return 100.0
    if valeur <= 0.15:
        return 80.0
    if valeur <= 0.30:
        return 50.0
    return 20.0


def score_ph(ph: float) -> float:
    """§3.2.3 S_pH."""
    if 6.8 <= ph <= 7.4:
        return 100.0
    if 6.5 <= ph < 6.8:
        return 85.0
    if 7.4 < ph <= 7.8:
        return 80.0
    if 7.8 < ph <= 8.2:
        return 55.0
    return 25.0


def score_cuivre(valeur: float) -> float:
    """§3.2.4 N_Cu."""
    if valeur < 0.1:
        return 100.0
    if valeur <= 0.5:
        return 100.0 - (valeur - 0.1) / 0.4 * 50.0
    return 30.0


def score_fer(valeur: float) -> float:
    """§3.2.4 N_Fe."""
    if valeur < 50:
        return 100.0
    if valeur <= 200:
        return 100.0 - (valeur - 50) / 150.0 * 60.0
    return 20.0


def score_manganese(valeur: float) -> float:
    """§3.2.4 N_Mn."""
    if valeur < 10:
        return 100.0
    if valeur <= 50:
        return 100.0 - (valeur - 10) / 40.0 * 60.0
    return 20.0


def score_metaux_depots(cu: float, fe: float, mn: float) -> float:
    """§3.2.4 S_metaux_depots = min(N_Cu, N_Fe, N_Mn)."""
    return min(score_cuivre(cu), score_fer(fe), score_manganese(mn))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring_cosmetique.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/scoring.py tests/test_scoring_cosmetique.py
git commit -m "feat: implement cosmetique sub-scores (§3.2), fix hardness continuity wording"
```

---

### Task 7: Score Cosmétique global

**Files:**
- Modify: `pipeline/scoring.py`
- Test: `tests/test_scoring_cosmetique.py`

**Interfaces:**
- Consumes: `score_durete`, `score_chlore_cosmetique`, `score_ph`, `score_metaux_depots`, `arrondi` (Task 5/6)
- Produces: `pipeline.scoring.score_cosmetique(th: float, chlore_total: float, ph: float, cu: float, fe: float, mn: float) -> int`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scoring_cosmetique.py`:

```python
from pipeline.scoring import score_cosmetique


def test_score_cosmetique_exemple_spec_paris():
    # Reprend l'exemple de la fiche communale (§5.3) :
    # durete=59 (arrondi de 59.43), chlore=80, pH=100, metaux_depots=95 -> 76
    resultat = score_cosmetique(th=30.19, chlore_total=0.12, ph=7.0, cu=0.08, fe=62.5, mn=5.0)
    assert resultat == 76
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring_cosmetique.py::test_score_cosmetique_exemple_spec_paris -v`
Expected: FAIL with `ImportError: cannot import name 'score_cosmetique'`

- [ ] **Step 3: Implement the function**

Append to `pipeline/scoring.py`:

```python
def score_cosmetique(th: float, chlore_total: float, ph: float, cu: float, fe: float, mn: float) -> int:
    """§3.2 S_cosmetique = 0.45*S_durete + 0.25*S_chlore + 0.15*S_pH + 0.15*S_metaux_depots.
    Les sous-scores sont arrondis avant combinaison (convention de l'exemple §5.3)."""
    s_durete = arrondi(score_durete(th))
    s_chlore = arrondi(score_chlore_cosmetique(chlore_total))
    s_ph = arrondi(score_ph(ph))
    s_metaux = arrondi(score_metaux_depots(cu, fe, mn))
    brut = 0.45 * s_durete + 0.25 * s_chlore + 0.15 * s_ph + 0.15 * s_metaux
    return arrondi(max(0.0, min(100.0, brut)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scoring_cosmetique.py -v`
Expected: PASS (10 tests total in this file)

- [ ] **Step 5: Run the full scoring test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests across test_aggregation.py, test_scoring_securite.py, test_scoring_mineraux_gout.py, test_scoring_boisson.py, test_scoring_cosmetique.py)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/scoring.py tests/test_scoring_cosmetique.py
git commit -m "feat: implement S_cosmetique global score (§3.2)"
```

---

### Task 8: Module d'Estimation des Coûts

**Files:**
- Create: `pipeline/cost_estimate.py`
- Test: `tests/test_cost_estimate.py`

**Interfaces:**
- Produces: `pipeline.cost_estimate.VETO_THRESHOLDS: dict[str, float]`
- Produces: `pipeline.cost_estimate.estimate_cost(param_code: str, value: float) -> dict | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cost_estimate.py`:

```python
from pipeline.cost_estimate import estimate_cost


def test_durete_palier_modere():
    resultat = estimate_cost("1345", 20.0)
    assert resultat is not None
    assert resultat["niveau_severite"] == "modere"
    assert resultat["achat_eur"] == "700-900"


def test_durete_palier_eleve():
    # TH=30.19, cas de l'exemple Paris (§5.3) -> "eleve", 1200-1600
    resultat = estimate_cost("1345", 30.19)
    assert resultat is not None
    assert resultat["niveau_severite"] == "eleve"
    assert resultat["achat_eur"] == "1200-1600"


def test_durete_palier_extreme():
    resultat = estimate_cost("1345", 45.0)
    assert resultat is not None
    assert resultat["niveau_severite"] == "extreme"
    assert resultat["achat_eur"] == "1600-2000"


def test_durete_sous_seuil_pas_de_recommandation():
    assert estimate_cost("1345", 10.0) is None


def test_nitrates_palier_modere():
    # ratio = 20/50 = 0.4 < 0.5 -> modere
    resultat = estimate_cost("1340", 20.0)
    assert resultat["niveau_severite"] == "modere"
    assert resultat["materiel"] == "Filtre sous-évier à charbon actif"


def test_nitrates_palier_eleve():
    # ratio = 40/50 = 0.8 -> eleve
    resultat = estimate_cost("1340", 40.0)
    assert resultat["niveau_severite"] == "eleve"


def test_nitrates_palier_extreme_veto_atteint():
    # ratio = 60/50 = 1.2 >= 1.0 -> extreme
    resultat = estimate_cost("1340", 60.0)
    assert resultat["niveau_severite"] == "extreme"
    assert resultat["materiel"] == "Osmoseur à pompe de perméat + reminéralisation"


def test_pfas_palier_eleve_borne():
    # ratio = 0.05/0.1 = 0.5 -> eleve (borne inclusive)
    resultat = estimate_cost("8847", 0.05)
    assert resultat["niveau_severite"] == "eleve"


def test_code_inconnu_retourne_none():
    assert estimate_cost("9999", 42.0) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_estimate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.cost_estimate'`

- [ ] **Step 3: Implement `pipeline/cost_estimate.py`**

```python
# Seuils de veto sanitaire réutilisés depuis §3.1 — source unique de vérité,
# pour que le score affiché et la recommandation chiffrée restent cohérents
# sur un même dépassement (§4.1, §5.6).
VETO_THRESHOLDS = {
    "1340": 50.0,   # Nitrates, mg/L
    "1339": 0.1,    # Nitrites, mg/L
    "6276": 0.5,    # Pesticides total, µg/L
    "8847": 0.1,    # PFAS total, µg/L
}


def estimate_cost(param_code: str, value: float) -> dict | None:
    """Estimation CAPEX/OPEX par palier technologique (§4.1).
    Résultat destiné à recommandations[].estimation_cout de la fiche commune,
    calculé une fois par commune au batch — jamais interrogé en direct côté client.
    """
    if param_code == "1345":  # Titre hydrotimétrique (TH) — dureté, seuils = §3.2.1
        if value > 40:
            return {
                "materiel": "Adoucisseur haute capacité (> 25 L)",
                "achat_eur": "1600-2000",
                "entretien_annuel_eur": "70-100 (8+ sacs de sel/an)",
                "niveau_severite": "extreme",
            }
        if value > 25:
            return {
                "materiel": "Adoucisseur renforcé (20-25 L)",
                "achat_eur": "1200-1600",
                "entretien_annuel_eur": "50-70 (4-5 sacs de sel/an)",
                "niveau_severite": "eleve",
            }
        if value > 15:
            return {
                "materiel": "Adoucisseur standard (10-15 L)",
                "achat_eur": "700-900",
                "entretien_annuel_eur": "15 (2 sacs de sel/an)",
                "niveau_severite": "modere",
            }
        return None  # < 15 °fH : pas de recommandation d'adoucisseur

    seuil_veto = VETO_THRESHOLDS.get(param_code)
    if seuil_veto is None:
        return None
    ratio = value / seuil_veto
    if ratio >= 1.0:  # seuil de veto sanitaire atteint (§3.1)
        return {
            "materiel": "Osmoseur à pompe de perméat + reminéralisation",
            "achat_eur": "450-700",
            "entretien_annuel_eur": "90 (membrane 0,0001 µm saturée plus vite)",
            "niveau_severite": "extreme",
        }
    if ratio >= 0.5:  # approche du seuil de veto
        return {
            "materiel": "Osmoseur inverse basique (3 étages)",
            "achat_eur": "200-300",
            "entretien_annuel_eur": "60 (cartouches + membrane)",
            "niveau_severite": "eleve",
        }
    return {
        "materiel": "Filtre sous-évier à charbon actif",
        "achat_eur": "80-120",
        "entretien_annuel_eur": "30 (1 cartouche/an)",
        "niveau_severite": "modere",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_estimate.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/cost_estimate.py tests/test_cost_estimate.py
git commit -m "feat: implement cost-estimation module (§4.1, §5.6)"
```

---

### Task 9: Moteur de Recommandations

**Files:**
- Create: `pipeline/recommendations.py`
- Test: `tests/test_recommendations.py`

**Interfaces:**
- Consumes: `pipeline.cost_estimate.estimate_cost`
- Produces: `pipeline.recommendations.generate_recommendations(mesures: dict, bact_actif: bool) -> list[dict]`

`mesures` is a flat `dict[str, float]` keyed by code SANDRE (`"1345"`, `"1398"`, `"1399"`, `"1340"`, `"6276"`, `"8847"`, `"1393"`, `"1392"`), plus the optional key `"_pesticide_molecule_max"` for the highest individual pesticide molecule value. Missing parameters are simply absent from the dict (use `mesures.get(code)`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recommendations.py`:

```python
from pipeline.recommendations import generate_recommendations


def test_recommandations_exemple_paris():
    # Reprend l'exemple de la fiche communale (§5.3) : TH=30.19 (>25, palier "eleve"),
    # chlore libre=0.12 (>0.05 -> carafe), chlore total=0.12 (<=0.15 -> pas de pommeau),
    # nitrates=18.4 (<=25 -> pas de reco nitrates), pas de pollution chimique significative.
    mesures = {
        "1345": 30.19,
        "1398": 0.12,
        "1399": 0.12,
        "1340": 18.4,
        "6276": 0.01,
        "8847": 0.005,
        "_pesticide_molecule_max": 0.0,
    }
    recos = generate_recommendations(mesures, bact_actif=False)
    types = {r["type"] for r in recos}
    assert types == {"carafe", "adoucisseur"}

    adoucisseur = next(r for r in recos if r["type"] == "adoucisseur")
    assert adoucisseur["estimation_cout"]["niveau_severite"] == "eleve"
    assert adoucisseur["estimation_cout"]["achat_eur"] == "1200-1600"


def test_recommandations_bacterio_active_prioritaire():
    mesures = {"1345": 5.0}
    recos = generate_recommendations(mesures, bact_actif=True)
    assert recos[0]["type"] == "alerte_bacteriologique"


def test_recommandations_pollution_chimique_declenche_filtration():
    mesures = {
        "1345": 5.0,
        "6276": 0.4,
        "8847": 0.01,
        "_pesticide_molecule_max": 0.02,
    }
    recos = generate_recommendations(mesures, bact_actif=False)
    filtration = next(r for r in recos if r["type"] == "filtration_chimique")
    # total pesticides = 0.4 -> ratio 0.8 vs seuil 0.5 -> "eleve"
    assert filtration["estimation_cout"]["niveau_severite"] == "eleve"


def test_recommandations_eau_parfaite_liste_vide():
    mesures = {
        "1345": 10.0, "1398": 0.02, "1399": 0.02, "1340": 5.0,
        "6276": 0.0, "8847": 0.0, "_pesticide_molecule_max": 0.0,
    }
    assert generate_recommendations(mesures, bact_actif=False) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_recommendations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.recommendations'`

- [ ] **Step 3: Implement `pipeline/recommendations.py`**

```python
from pipeline.cost_estimate import estimate_cost


def generate_recommendations(mesures: dict, bact_actif: bool) -> list[dict]:
    """Matrice de recommandations personnalisées (§4), avec estimation
    budgétaire attachée (§4.1) pour les recommandations d'équipement.
    `mesures` : dict[code_sandre, valeur] pour le réseau principal de la commune.
    """
    recos: list[dict] = []

    if bact_actif:
        recos.append({
            "usage": "boisson",
            "type": "alerte_bacteriologique",
            "titre": "Non-conformité bactériologique active",
            "description": (
                "Relayez la consigne officielle ARS/préfecture "
                "(ébullition ou restriction) — ne jamais minimiser."
            ),
        })

    th = mesures.get("1345")
    chlore_libre = mesures.get("1398")
    chlore_total = mesures.get("1399")
    nitrates = mesures.get("1340")
    pesticide_total = mesures.get("6276", 0.0)
    pesticide_molecule_max = mesures.get("_pesticide_molecule_max", 0.0)
    pfas = mesures.get("8847", 0.0)
    fer = mesures.get("1393")
    cuivre = mesures.get("1392")

    if pesticide_total > 0.05 or pesticide_molecule_max > 0.1 or pfas > 0.02:
        pollution_ratio_pest = pesticide_total / 0.5
        pollution_ratio_pfas = pfas / 0.1
        if pollution_ratio_pest >= pollution_ratio_pfas:
            code_ref, valeur_ref = "6276", pesticide_total
        else:
            code_ref, valeur_ref = "8847", pfas
        reco = {
            "usage": "boisson",
            "type": "filtration_chimique",
            "titre": "Filtration recommandée (pesticides/PFAS)",
            "description": (
                "Filtration sous évier (bloc charbon actif haute densité "
                "ou osmose inverse selon le niveau de dépassement)."
            ),
        }
        cout = estimate_cost(code_ref, valeur_ref)
        if cout:
            reco["estimation_cout"] = cout
        recos.append(reco)

    if nitrates is not None and nitrates > 25:
        reco = {
            "usage": "boisson",
            "type": "nitrates_biberons",
            "titre": "Précaution nourrissons",
            "description": (
                "Éviter pour les biberons (< 15 mg/L conseillé). "
                "Osmoseur recommandé si > 40 mg/L."
            ),
        }
        cout = estimate_cost("1340", nitrates)
        if cout:
            reco["estimation_cout"] = cout
        recos.append(reco)

    if th is not None and th > 25:
        reco = {
            "usage": "cosmetique",
            "type": "adoucisseur",
            "titre": "Dimensionner un adoucisseur adapté",
            "description": (
                f"TH de {th:.2f} °fH : un équipement dimensionné à ce niveau "
                "de dureté limite les régénérations trop fréquentes."
            ),
        }
        cout = estimate_cost("1345", th)
        if cout:
            reco["estimation_cout"] = cout
        recos.append(reco)

    if chlore_total is not None and chlore_total > 0.15:
        recos.append({
            "usage": "cosmetique",
            "type": "pommeau_filtrant",
            "titre": "Protéger la peau du chlore",
            "description": "Pommeau de douche avec filtre KDF ou billes céramiques recommandé.",
        })

    if chlore_libre is not None and chlore_libre > 0.05:
        recos.append({
            "usage": "boisson",
            "type": "carafe",
            "titre": "Optimiser le goût de l'eau",
            "description": (
                "Laissez reposer l'eau 20 minutes au frais en carafe ouverte "
                "pour éliminer le chlore avant dégustation."
            ),
        })

    if (fer is not None and fer > 200) or (cuivre is not None and cuivre > 0.5):
        recos.append({
            "usage": "cosmetique",
            "type": "metaux_traces",
            "titre": "Fer/cuivre élevé",
            "description": (
                "Laissez couler l'eau 30 s le matin avant consommation ; "
                "masque capillaire chélatant pour cheveux clairs/décolorés."
            ),
        })

    return recos
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_recommendations.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the entire test suite one last time**

Run: `pytest tests/ -v`
Expected: PASS (all tests, ~50+ across all files)

- [ ] **Step 6: Commit**

```bash
cd "C:/Repos/Quali'eau"
git add pipeline/recommendations.py tests/test_recommendations.py
git commit -m "feat: implement recommendation engine with attached cost estimates (§4)"
```

---

## Out of Scope (separate future plan)

- `pipeline/download_data.py` and DIS_PLV/DIS_RESULT parsing (§2.1, §5.2) — a distinct subsystem (network I/O, real dataset joins), independently testable via fixture TXT files without any of the scoring logic above.
- `pipeline/compute_scores.py` orchestrator wiring parsed data → aggregation → scoring → recommendations → `national.geojson`/`index.json`/`communes/{code}.json` output. This orchestrator, not the pure functions above, is the right place for:
  - **Sélection de fenêtre temporelle** (§2.5.1) : filtrer les mesures brutes sur 12 mois, étendre à 24 si moins de 4 analyses — nécessite l'historique complet d'une commune, que les fonctions pures de ce plan ne voient jamais (elles reçoivent déjà une liste filtrée de `Mesure`).
  - **Renormalisation des poids si un paramètre est absent** (§3 intro, `donnees_partielles`) — l'orchestrateur sait quels paramètres bruts existent réellement pour une commune ; les fonctions de scoring de ce plan supposent toutes leurs entrées présentes.
  - **Communes multi-réseaux (UDI) et PLM** (§2.5.4, §2.5.5) et **absence de données** (§2.5.6) — logique de sélection/normalisation de commune, pas de calcul de score.
- **Indice Café/Thé SCA** (§3.1.4, avec les estimations TDS/GH de §2.5.7/§2.5.8) — explicitement Phase 3 dans la roadmap de la spec (§8), hors score global, non nécessaire au MVP.
- La suite de tests sur 50 communes représentatives (§8 roadmap) — nécessite des données de fixture réelles ou réalistes issues du sous-système d'ingestion ci-dessus.
- Frontend (`public/`) — Phase 2.
