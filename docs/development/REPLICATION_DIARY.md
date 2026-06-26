# EconFlow — Blind Replication Diary

**Protocol:** First-year PhD student, given only the repository and README.  
**Objective:** Reproduce the AI & Productivity panel regression results from scratch.  
**Rule:** Do not consult the author. Record everything.

---

## Diary

### Step 1 — Read the README

**Expected:** A README that tells me exactly what to install, what data to download, and what command to run to reproduce the paper.

**What happened:** The README exists and is readable. It describes EconFlow as a platform for panel econometrics. It shows an install command, a `doctor` command, and a `run` command. At the bottom it mentions a live regression test.

**Notes:**
- README clone URL is `https://github.com/abrhamgs3/econflow.git`. The actual git remote is `https://github.com/abrhamgs3/econflow-.git` (trailing dash). Minor mismatch — a fresh clone from the README URL would land on a different (possibly nonexistent) repo.
- No mention of which Python version is required in the main README header. It appears only in the `doctor` command output. A user who skips `doctor` will not know.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-01 | Medium | README clone URL (`econflow.git`) does not match actual remote (`econflow-.git`). A user who copies the clone command will reach the wrong repository. |

---

### Step 2 — Install the package

**Command (from README):**
```
pip install econflow
```

**Expected:** Package installs from PyPI.

**What happened:**
```
ERROR: Could not find a version that satisfies the requirement econflow
ERROR: No matching distribution found for econflow
```

**Confusion:** The README says "install with pip" but the package is not on PyPI. There is no note anywhere in the README that the package is *not* published and must be installed from source.

**Workaround (requires prior knowledge):**
```
git clone <url>
cd econflow
pip install -e .
```
This is standard Python developer workflow, but an economist who is not a software developer will not know to try this. The README does not mention it.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-02 | **Critical** | `pip install econflow` fails — package not on PyPI. README gives no alternative install instructions. A user cannot install the software at all without contacting the author or guessing. |

---

### Step 3 — Install from source

**Command:**
```
pip install -e .
```

**Expected:** Clean install.

**What happened:** Install succeeds.

**Follow-up — run the CLI:**
```
econflow --version
```

**What happened:**
```
-bash: econflow: command not found
```

**Confusion:** The package installed but the CLI is not available. The `econflow` entry point was installed to `~/.local/bin`, which is not on `PATH` in this environment.

**Workaround (requires prior knowledge):**
```
export PATH="$HOME/.local/bin:$PATH"
econflow --version
# EconFlow 0.1.0
```

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-03 | High | After `pip install -e .`, the `econflow` CLI is not on PATH. README does not warn about this or provide a fallback (`python -m econflow` or `uv run econflow`). |

---

### Step 4 — Run `econflow doctor`

**Command:**
```
econflow doctor
```

**Expected:** All checks pass, or at minimum I know what to do to fix each failure.

**What happened:**
```
EconFlow — environment check

  ✔ Python 3.12.x
  ✔ pandas 2.x.x
  ✔ numpy 1.x.x
  ✔ statsmodels 0.x.x
  ✔ linearmodels 5.x.x
  ✔ matplotlib 3.x.x
  ✔ scipy 1.x.x

  Data files
  ✘ data/processed/panel_clean.csv  (missing — run scripts/01_download_data.py)
  ✘ data/raw/wdi.csv                (missing — run scripts/01_download_data.py)
  ✘ data/raw/pwt.csv                (missing — run scripts/01_download_data.py)
  ✘ data/raw/ai_proxy.csv           (missing — run scripts/01_download_data.py)

  Output directories
  ✔ tables/    (writable)
  ✔ figures/   (writable)
  ✔ outputs/   (writable)

✘ Some checks failed.
```

**Confusion:** The error message says to run `scripts/01_download_data.py`. Let me check if that file exists.

```
ls scripts/
ls: cannot access 'scripts/': No such file or directory
```

The `scripts/` directory does not exist in the repository. The `doctor` command points users to a script that doesn't exist.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-04 | **Critical** | `scripts/` directory does not exist. `doctor` tells users to run `scripts/01_download_data.py` — a file that has never been created. Users have no path forward to obtain the required data files. |
| R-05 | **Critical** | All four required data files are missing: `data/processed/panel_clean.csv`, `data/raw/wdi.csv`, `data/raw/pwt.csv`, `data/raw/ai_proxy.csv`. No data means no reproduction. |
| R-06 | High | `doctor` references `scripts/01_download_data.py` for data and `scripts/02_clean_data.py` for the processed panel (mentioned in `run` command output). Neither script exists. |

---

### Step 5 — Locate the AI & Productivity example

**Action:** Browse the repository. Find `examples/ai_productivity_paper/`.

**Expected:** A self-contained example with data or data-download instructions.

**What happened:** The directory exists. It contains a `README.md` and a `config/` directory with three YAML files. Let me follow the example README.

**From `examples/ai_productivity_paper/README.md`:**
```
econflow run --data examples/ai_productivity_paper/reference_outputs/data/panel_clean.csv
```

**What happened:**
```
Error: No such option: --data
```

**Confusion:** The README shows `--data` but the actual CLI option is `--data-path`. These are different strings. The example README has a typo/stale flag name.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-07 | High | `examples/ai_productivity_paper/README.md` shows `--data` but the correct flag is `--data-path`. Copy-paste from the README fails immediately. |

---

### Step 6 — Inspect the reference data file

**Action:** Open `examples/ai_productivity_paper/reference_outputs/data/panel_clean.csv`.

**Expected:** A CSV file with panel data.

**What happened:**
```
# This file is intentionally excluded from the repository.
# The full panel_clean.csv (2,895 rows × 12 columns) used for the
# AI & Productivity paper is available from the author on request.
# SHA-256: 9a65183a...
# See docs/data_sources.md for construction details.
```

Eight lines. A comment placeholder. The actual data is not included.

**Confusion:** This is the *reference outputs* directory, which I would expect to contain the data used to generate the reference outputs. Instead it contains a placeholder. The data is "available from the author on request" — which directly contradicts the stated goal of independent reproduction.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-08 | **Critical** | `panel_clean.csv` is a placeholder. The real dataset (2,895 rows) is excluded and available "from the author on request." Independent reproduction is impossible without this file or a data-download script that recreates it. |

---

### Step 7 — Try the generic pipeline with the AI & P config

**Command (following example README instructions for the generic pipeline):**
```
econflow run \
    --config  examples/ai_productivity_paper/config/config.yaml \
    --models  examples/ai_productivity_paper/config/models.yaml \
    --outputs examples/ai_productivity_paper/config/outputs.yaml
```

**Expected:** Pipeline runs.

**What happened:**
```
✘ Unexpected error: 'path'
```

**Investigation:** The generic pipeline (`pipeline_generic.py`) expects `config.yaml` to have:
```yaml
data:
  path: "..."
  entity_col: "..."
  time_col: "..."
```

But the AI & P `config.yaml` has:
```yaml
data:
  sources:
    world_bank:
      indicators: [...]
    penn_world_tables:
      version: "10.01"
    ai_proxy:
      source: "..."
```

The schemas are incompatible. The generic pipeline crashes with `KeyError: 'path'`.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-09 | High | `examples/ai_productivity_paper/config/config.yaml` uses a `data.sources.*` schema incompatible with `pipeline_generic.py`, which expects `data.path`. Running the obvious generic-pipeline command crashes with `KeyError: 'path'`. No error message explains the schema mismatch. |

---

### Step 8 — Inspect the AI & P estimation code

**Action:** Read `src/econflow/econometrics/panel.py`.

**Expected:** Working estimation functions.

**What happened:** The file contains function stubs with `raise NotImplementedError`. Counting stubs across the codebase:

```
src/econflow/ingestion/     — NotImplementedError
src/econflow/processing/    — NotImplementedError
src/econflow/econometrics/  — NotImplementedError
src/econflow/sensitivity/   — NotImplementedError
src/econflow/diagnostics/   — NotImplementedError
src/econflow/outputs/       — NotImplementedError
```

Total: **81 `raise NotImplementedError` calls** across the legacy AI & P pipeline. Every function that would actually execute the paper's analysis is a stub.

**The only working estimation path** is `pipeline_generic.py` (the Getting Started tutorial), which uses a different, simpler code path and the Grunfeld (1958) dataset — not the AI & P paper data.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-10 | **Critical** | 81 `NotImplementedError` stubs across ingestion, processing, estimation, sensitivity, diagnostics, and outputs modules. The entire AI & P legacy pipeline body is unimplemented. Running it raises `NotImplementedError` at the first function call. |

---

### Step 9 — Check the models.yaml for the AI & P example

**Action:** Read `examples/ai_productivity_paper/config/models.yaml`.

**What happened:** The models.yaml references estimators that don't exist:
- `TwoWayFE` — stub
- `GMMEstimator` — stub
- `IVEstimator` — stub  
- `PanelQuantile` — stub
- `SensitivityRunner` — stub

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-11 | **Critical** | AI & P `models.yaml` specifies estimator types (`GMMEstimator`, `IVEstimator`, `PanelQuantile`, `SensitivityRunner`) that are stubs raising `NotImplementedError`. Even if data were available, these models cannot run. |

---

### Step 10 — Inspect the live regression test

**From README:**
```
ECONFLOW_RUN_LIVE_REGRESSION=1 pytest tests/regression/test_live_data_reproduction.py
```

**Command:**
```
pytest tests/regression/test_live_data_reproduction.py
```

**What happened:**
```
ERROR: file or directory not found: tests/regression/test_live_data_reproduction.py
```

**Confusion:** The README documents a reproducibility test. The test file does not exist.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-12 | High | `tests/regression/test_live_data_reproduction.py` does not exist. The README's primary reproducibility check command fails immediately. |

---

### Step 11 — Check metadata

**Action:** Read `examples/ai_productivity_paper/config/config.yaml` author field.

**What happened:**
```yaml
authors:
  - name: "Ab"
    email: "abrhamgs3@gmail.com"
```

The author name is `"Ab"` — appears to be a placeholder or abbreviation, not the author's full name (Abrha Megos Meressa). A third party attempting to contact the author would have incomplete information.

**Issues found:**

| ID | Severity | Description |
|----|----------|-------------|
| R-13 | Low | `config.yaml` lists `authors[0].name: "Ab"` — should be the full author name. |

---

## Issue Register

| ID | Severity | Category | Description | Affects Reproduction? |
|----|----------|----------|-------------|----------------------|
| R-01 | Medium | Documentation | README clone URL uses `econflow.git`; actual remote is `econflow-.git` | Indirectly (wrong repo) |
| R-02 | **Critical** | Installation | `pip install econflow` fails — not on PyPI; no source-install instructions | Yes — cannot install |
| R-03 | High | Installation | CLI not on PATH after install; no `python -m econflow` fallback documented | Yes — cannot run CLI |
| R-04 | **Critical** | Missing files | `scripts/` directory does not exist; `doctor` points users there | Yes — dead end |
| R-05 | **Critical** | Data | All 4 required data files missing from repo | Yes — no data to run |
| R-06 | High | Missing files | `scripts/01_download_data.py` and `scripts/02_clean_data.py` referenced but absent | Yes — no download path |
| R-07 | High | Documentation | AI & P README uses `--data` (stale); correct flag is `--data-path` | Yes — copy-paste fails |
| R-08 | **Critical** | Data | `panel_clean.csv` is a placeholder; real data excluded; "request from author" | Yes — no data |
| R-09 | High | Config | AI & P `config.yaml` schema incompatible with `pipeline_generic.py` | Yes — KeyError crash |
| R-10 | **Critical** | Code | 81 `NotImplementedError` stubs in AI & P pipeline modules | Yes — cannot execute |
| R-11 | **Critical** | Code | AI & P models.yaml lists stub estimators (`GMM`, `IV`, `PanelQuantile`) | Yes — cannot run models |
| R-12 | High | Missing files | `tests/regression/test_live_data_reproduction.py` does not exist | Yes — test unreachable |
| R-13 | Low | Metadata | Author name `"Ab"` in config.yaml — not full name | No |

---

## What Is Actually Working

To be precise about the current state: **the Getting Started tutorial works end-to-end.**

```
econflow run \
    --config  examples/getting_started/config/config.yaml \
    --models  examples/getting_started/config/models.yaml \
    --outputs examples/getting_started/config/outputs.yaml
```

This runs the Grunfeld (1958) investment dataset through three panel models (Pooled OLS, Entity FE, Two-Way FE) and produces correct regression tables. The expected outputs are committed and match.

**What does not work:** reproducing *the AI & Productivity paper* — which is the stated purpose of the repository.

---

## Minimal Fix Set

The following changes are the **smallest set** that would allow an independent economist to reproduce the paper without contacting the author. They are ordered by dependency.

### Fix 1 — Publish to PyPI or document source install (blocks everything)

**Addresses:** R-02

Add to README under **Installation:**
```
# From PyPI (once published):
pip install econflow

# From source (current):
git clone https://github.com/abrhamgs3/econflow-.git
cd econflow
pip install -e .
# or:  uv pip install -e .
```

Until PyPI publication, the source-install path must be the documented primary method.

---

### Fix 2 — Document PATH fix or provide fallback (blocks CLI use)

**Addresses:** R-03

Add to README:
```
If `econflow` is not found after install, add ~/.local/bin to PATH:
    export PATH="$HOME/.local/bin:$PATH"
Or use the module entrypoint:
    python -m econflow --version
```

Alternatively, document `uv run econflow` as the canonical invocation (it handles PATH automatically).

---

### Fix 3 — Add data download scripts or include the data (blocks all analysis)

**Addresses:** R-04, R-05, R-06, R-08

**Option A (preferred for reproducibility):** Add `scripts/01_download_data.py` that downloads World Bank WDI indicators, Penn World Tables 10.01, and the AI proxy via their public APIs. Include `scripts/02_clean_data.py` that merges and cleans to `panel_clean.csv`. The scripts already have documented SHA-256 checksums — add integrity verification.

**Option B (acceptable):** Include `data/` directory in the repository under a data license. At 2,895 rows × 12 columns this is a small CSV (~200 KB).

Without one of these options, independent reproduction is structurally impossible.

---

### Fix 4 — Implement the AI & P pipeline (or remove the claim)

**Addresses:** R-10, R-11

81 `NotImplementedError` stubs must be implemented, or the repository documentation must be updated to state clearly that the AI & P pipeline is not yet functional. The current state — a README that implies a working pipeline over data that can't be obtained running code that raises `NotImplementedError` — gives a false picture of reproducibility.

Minimum viable scope to implement:
- `ingestion/`: load WDI, PWT, AI proxy CSVs into a merged panel
- `processing/`: log-transform variables, handle missing, balance the panel
- `econometrics/panel.py`: implement `TwoWayFE` (within estimator with year dummies) and a basic `GMMEstimator` or substitute with `FE` + clustered SEs
- `outputs/tables.py`: format a comparison table

`IVEstimator`, `PanelQuantile`, and `SensitivityRunner` could remain stubs if clearly marked as *extensions not required for baseline replication*.

---

### Fix 5 — Fix CLI flag in AI & P README

**Addresses:** R-07

In `examples/ai_productivity_paper/README.md`, change:
```
econflow run --data examples/...
```
to:
```
econflow run --data-path examples/...
```

---

### Fix 6 — Fix AI & P config.yaml schema or add a config adapter

**Addresses:** R-09

Either:

**(a)** Update `pipeline_generic.py` to detect and handle the `data.sources.*` schema used by the AI & P config, or

**(b)** Add a `data.path` key to the AI & P `config.yaml` pointing to the (eventually included) processed panel CSV:
```yaml
data:
  path: "examples/ai_productivity_paper/reference_outputs/data/panel_clean.csv"
  entity_col: "country"
  time_col: "year"
  sources:   # retained for documentation
    ...
```

---

### Fix 7 — Add the live regression test file

**Addresses:** R-12

Create `tests/regression/test_live_data_reproduction.py` with at minimum:
- A test that loads the processed panel CSV (skipped if file absent)
- Runs each model in `examples/ai_productivity_paper/config/models.yaml`
- Asserts key coefficients match reference values (within tolerance)

This is what turns "the author says it works" into "CI says it works."

---

### Fix 8 — Correct README clone URL

**Addresses:** R-01

Change:
```
git clone https://github.com/abrhamgs3/econflow.git
```
to:
```
git clone https://github.com/abrhamgs3/econflow-.git
```

Or rename the GitHub repository to remove the trailing dash.

---

### Fix 9 — Update author name in config.yaml

**Addresses:** R-13

```yaml
authors:
  - name: "Abrha Megos Meressa"
    email: "abrhamgs3@gmail.com"
```

---

## Reproduction Verdict

**Can an independent economist reproduce the AI & Productivity paper from this repository?**

**No.** The pipeline cannot be run in its current state due to six independent blocking issues (R-02, R-05, R-08, R-10, R-11, and R-04/R-06 as a group). Each one is individually sufficient to prevent reproduction; together they represent a complete gap between what the repository claims to offer and what it currently delivers.

**What works today:** the Getting Started tutorial (Grunfeld dataset, three FE specifications). This is a legitimate, correct, well-documented teaching example. It is the foundation the AI & P pipeline should be built on.

**Estimated effort to close the gap:** Fixes 1–3 and 5–8 are documentation and scripting tasks (roughly 1–2 days). Fix 4 (implementing 81 stubs) is the substantive engineering task; the estimation core (FE + clustered SEs) is straightforward given `pipeline_generic.py` as a template, but data ingestion and cleaning for three heterogeneous international databases will take additional time depending on API stability.

---

*Diary compiled: 2026-06-25*  
*Protocol: blind replication, no author contact*  
*Examiner: simulated first-year PhD student*
