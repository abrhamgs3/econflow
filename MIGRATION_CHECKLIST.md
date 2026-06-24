# EconFlow Migration Checklist

**Repository:** `econflow`  
**Extracted from:** `AI and Productivity` (refactor-platform branch, commit `6321923`)  
**Date:** 2026-06-24  
**Initial commit:** `6da2d48`  
**Status:** Phase 1 complete — platform files copied and committed.

---

## What Has Been Done

149 files copied from `AI and Productivity/` into this repository. All internal
imports updated from `ai_productivity` → `econflow`. A new `pyproject.toml`
registers the package as `econflow` with entry point `econflow.cli:app`.
An independent Git history was started (`git init` → initial commit on `main`).

The source repository (`AI and Productivity/`) was **not modified**.

---

## Copied Files (149 total)

### Package — src/econflow/

| File | Source | Notes |
|------|--------|-------|
| `src/econflow/__init__.py` | `src/ai_productivity/__init__.py` | Rewritten; version bumped to 0.2.0 |
| `src/econflow/cli.py` | `src/ai_productivity/cli.py` | Active CLI entry point |
| `src/econflow/pipeline.py` | `src/ai_productivity/pipeline.py` | Active orchestrator |
| `src/econflow/provenance.py` | `src/ai_productivity/provenance.py` | ProvenanceRecorder (Sprint 2) |
| `src/econflow/exceptions.py` | `src/ai_productivity/exceptions.py` | AIProdError hierarchy |
| `src/econflow/logging.py` | `src/ai_productivity/logging.py` | Structured logging |
| `src/econflow/config/__init__.py` | `src/ai_productivity/config/__init__.py` | Config stub |
| `src/econflow/data/` (3 files) | `src/ai_productivity/data/` | loaders, validators, cleaning |
| `src/econflow/econometrics/panel.py` | `src/ai_productivity/econometrics/panel.py` | Four model suites |
| `src/econflow/features/engineering.py` | `src/ai_productivity/features/engineering.py` | Variable transforms |
| `src/econflow/visualization/` (2 files) | `src/ai_productivity/visualization/` | figures.py, style.py |
| `src/econflow/reporting/narrative.py` | `src/ai_productivity/reporting/narrative.py` | LaTeX narrative |
| `src/econflow/ml/__init__.py` | `src/ai_productivity/ml/__init__.py` | Reserved stub |
| `src/econflow/utils/__init__.py` | `src/ai_productivity/utils/__init__.py` | Reserved stub |
| **Scaffold — core/** (5 files) | `ai_productivity/core/` | config, exceptions, pipeline, provenance, registry |
| **Scaffold — ingestion/** (5 files) | `ai_productivity/ingestion/` | base, cache, world_bank, oecd, pwt |
| **Scaffold — processing/** (6 files) | `ai_productivity/processing/` | harmonise, merge, transform, ai_index, tfp, quality |
| **Scaffold — estimation/** (7 files) | `ai_productivity/estimation/` | base, ols, fixed_effects, random_effects, iv, gmm, quantile |
| **Scaffold — diagnostics/** (5 files) | `ai_productivity/diagnostics/` | specification, overid, dependence, serial, reporter |
| **Scaffold — sensitivity/** (2 files) | `ai_productivity/sensitivity/` | runner, comparison |
| **Scaffold — outputs/** (4 files) | `ai_productivity/outputs/` | base, tables, figures, reports |
| **Scaffold — cli_scaffold/** (6 files) | `ai_productivity/cli/` | main, commands (run, validate, reproduce, project) |

### Tests

| File | Source | Notes |
|------|--------|-------|
| `tests/conftest.py` | `tests/conftest.py` | Imports updated to econflow |
| `tests/test_exceptions.py` | `tests/test_exceptions.py` | Imports updated |
| `tests/test_provenance.py` | `tests/test_provenance.py` | Imports updated |
| `tests/regression/helpers.py` | `tests/regression/helpers.py` | Six comparison utilities |
| `tests/regression/conftest.py` | `tests/regression/conftest.py` | Imports updated |
| `tests/regression/test_helpers.py` | `tests/regression/test_helpers.py` | 49 regression helper tests |
| `tests/unit/__init__.py` | `tests/unit/__init__.py` | Reserved stub |
| `tests/integration/__init__.py` | `tests/integration/__init__.py` | Reserved stub |
| `tests/fixtures/synthetic/sample_panel.csv` | *new* | Generic 150-row synthetic panel (15 entities × 10 years) |
| `tests/fixtures/reference_outputs/tables/` (25 files) | `tests/fixtures/reference_outputs/tables/` | Sprint 2 baseline tables |
| `tests/fixtures/reference_outputs/figures/` (8 files) | `tests/fixtures/reference_outputs/figures/` | Sprint 2 baseline figures |
| `tests/fixtures/reference_outputs/paper_sections/` (2 files) | `tests/fixtures/reference_outputs/paper_sections/` | Sprint 2 baseline narratives |
| `tests/fixtures/reference_outputs/manifest.yaml` | `tests/fixtures/reference_outputs/manifest.yaml` | SHA-256 checksums |
| `tests/fixtures/reference_outputs/data/panel_clean.csv` | *placeholder* | **See Decision 2 below — action required** |

### Infrastructure

| File | Source | Notes |
|------|--------|-------|
| `pyproject.toml` | `pyproject.toml` | Rewritten: name=econflow, entry point econflow.cli:app |
| `.gitignore` | `.gitignore` | Platform rules only; paper-specific rules removed |
| `requirements.txt` | `requirements.txt` | Unchanged (Streamlit Cloud runtime) |
| `uv.lock` | `uv.lock` | Copied as-is; regenerate after installing |
| `ARCHITECTURE.md` | `ARCHITECTURE.md` | Rewritten: paper-specific facts removed |
| `README.md` | *new* | Platform-facing documentation |
| `CHANGELOG.md` | `CHANGELOG.md` | Unchanged |
| `docs/MIGRATION_PLAN.md` | `docs/MIGRATION_PLAN.md` | Unchanged |
| `docs/SPRINT_MIGRATION_ROADMAP.md` | `docs/SPRINT_MIGRATION_ROADMAP.md` | Unchanged |
| `app/streamlit_app.py` | `app/streamlit_app.py` | Imports updated to econflow |
| `.streamlit/config.toml` | `.streamlit/config.toml` | Unchanged |
| `outputs/provenance/schema.json` | `outputs/provenance/schema.json` | ProvenanceRecorder JSON Schema |
| `outputs/provenance/REPRODUCIBILITY_REPORT.md` | `outputs/provenance/REPRODUCIBILITY_REPORT.md` | Sprint 2 audit |
| `projects/example/config.yaml` | `projects/ai_productivity/config.yaml` | Renamed; project name updated to example_project |
| `projects/example/models.yaml` | `projects/ai_productivity/models.yaml` | Renamed |
| `projects/example/outputs.yaml` | `projects/ai_productivity/outputs.yaml` | Renamed |
| `.github/agents/econometrics.agent.md` | `.github/agents/research-data-analysis.agent.md` | Renamed; APRP → EconFlow |
| `.github/workflows/ci.yml` | `.github/workflows/ci.yml` | Package name updated |
| `agents/data_agent.py` | `agents/data_agent.py` | Shims updated to econflow |
| `agents/econometrics_agent.py` | `agents/econometrics_agent.py` | Shims updated |
| `agents/visualization_agent.py` | `agents/visualization_agent.py` | Shims updated |
| `agents/writing_agent.py` | `agents/writing_agent.py` | Shims updated |

---

## What Was NOT Copied (Paper Repository Only)

| Path | Reason |
|------|--------|
| `paper/` | LaTeX manuscript source — belongs to ai-productivity-paper |
| `AI_and_Productivity_v*.docx` (×13) | Paper draft versions |
| `Referee_Reports_v13.md` | Peer review correspondence |
| `submission_package/` | Journal submission bundle |
| `strategy/` | Paper positioning documents |
| `figures/` | Generated paper figures (reproduced on each run) |
| `tables/` | Generated paper tables (reproduced on each run) |
| `data/raw/` | Raw source data — paper-specific dataset |
| `data/processed/panel_clean.csv` | Scientific ground truth — stays with paper repo |
| `data/demo/` | Paper demo data |
| `scripts/` | Numbered ETL pipeline (01–07) — paper-specific |
| `run_pipeline.py` | Paper's ground-truth orchestrator |
| `notebooks/` | Paper-specific EDA |
| `FORENSIC_REPORT_ai_index_levels_fe.md` | Paper-specific scientific investigation |
| `outputs/FORENSIC_REPORT_ai_index_levels_fe.md` | Canonical copy of the above |
| `outputs/provenance/run_metadata.json` | Generated artefact |
| `__pycache__/`, `.venv/`, `.pytest_cache/` | Never migrated |

---

## Remaining Manual Steps

### Decision 1 — Create GitHub repository and push  ⚠️ ACTION REQUIRED

```powershell
# On Windows, from the econflow directory:
cd "C:\Users\Lenovo\Desktop\Courses\EconWithAi\econflow"
git remote add origin https://github.com/abrhamgs3/econflow.git
git push -u origin main
```

Create the `econflow` repository on GitHub first (no README, no .gitignore —
the repo is already initialized).

---

### Decision 2 — Replace placeholder panel_clean.csv  ⚠️ ACTION REQUIRED

`tests/fixtures/reference_outputs/data/panel_clean.csv` is currently a
text placeholder. The Sprint 2 regression baseline (`tests/regression/conftest.py`)
loads this file to compare against live outputs.

**What to do:**

Option A (recommended) — Use the synthetic fixture. Update `tests/regression/conftest.py`
to load `tests/fixtures/synthetic/sample_panel.csv` (generic 150-row panel,
columns: entity, time, outcome, ai_proxy, human_capital, log_gdp) instead of
the paper's real panel. This fully decouples the platform from the paper dataset.

Option B — Copy the real panel but acknowledge coupling. Copy the real
`panel_clean.csv` from the paper repo into this fixture path. The regression
tests will then test against the actual AI & Productivity panel schema, which
means the platform tests are still coupled to the paper.

Option A is the correct long-term choice. Option B is acceptable as a temporary
measure while the paper repo migration is in progress.

---

### Decision 3 — Update tests/conftest.py sample_panel fixture  ⚠️ ACTION REQUIRED

The `sample_panel` pytest fixture in `tests/conftest.py` creates a DataFrame
with paper-specific columns (`ln_tfp`, `AI_index`, `ln_hc`, `country`, `year`).
For the platform to be fully generic, this fixture should use configurable
column names matching the `tests/fixtures/synthetic/sample_panel.csv` schema
(`entity`, `time`, `outcome`, `ai_proxy`, `human_capital`, `log_gdp`).

This change will require updating any test that unpacks specific column names
from the fixture. Defer to Sprint 3 if tests are needed immediately with the
current schema.

---

### Decision 4 — Regenerate uv.lock  ✅ LOW URGENCY

The copied `uv.lock` was generated for the `ai-productivity` package. After
confirming `pyproject.toml` is correct:

```bash
cd "C:\Users\Lenovo\Desktop\Courses\EconWithAi\econflow"
uv pip install -e ".[dev]"
uv lock    # regenerates uv.lock for the econflow package
```

---

### Decision 5 — Merge exceptions hierarchies  📋 SPRINT 3 TASK

Two exception hierarchies currently coexist in this repo:

| Location | Root | Used by |
|----------|------|---------|
| `src/econflow/exceptions.py` | `AIProdError` | Active production code (all 109 tests) |
| `src/econflow/core/exceptions.py` | `APRPError` | Scaffold modules (stubs only) |

Action in Sprint 3: promote `APRPError` and its richer sub-types
(`DownloadError`, `CacheError`, `HarmonisationError`, `ConvergenceError`)
into `src/econflow/exceptions.py`. Make `AIProdError` an alias of `APRPError`
for backward compatibility. Update all active code to catch `APRPError`.

---

### Decision 6 — Wire projects/example/ into tests  📋 SPRINT 3 TASK

`projects/example/config.yaml` references `ai_productivity` as the project
name in several places (data source URLs, indicator lists). Update the example
project to use a publicly available, small dataset so that `econflow run example`
works in a clean environment without access to the paper's private data.

Suggested: use World Bank API indicators for 10 countries, 5 years — the
ingestion connectors are already stubbed in `src/econflow/ingestion/`.

---

### Decision 7 — Retire agents/ after paper repo migration  📋 SPRINT 7 TASK

`agents/` contains backward-compatibility shims that re-export from
`src/econflow/`. These exist only for `run_pipeline.py` in the paper repo.
Once the paper repo updates its imports to use `econflow` directly (Sprint 7),
delete `agents/` from this repo in a single commit:

```bash
git rm -r agents/
git commit -m "Remove agents/ shims: paper repo now imports from econflow directly (Sprint 7)"
```

Gate condition: paper repo's `run_pipeline.py` must import from `econflow`
and pass the Sprint 5 live-data regression test before this deletion.

---

### Decision 8 — Split README for the paper repo  📋 PHASE 4 TASK

When the `ai-productivity-paper` repo is created, write a research-facing
README covering: paper citation, replication instructions, data provenance,
and a note that the platform is powered by econflow. The current repo's
README is platform-facing only.

---

## Verification Steps

Run these commands after completing Decision 1 and Decision 4:

```bash
cd "C:\Users\Lenovo\Desktop\Courses\EconWithAi\econflow"

# 1. Install in editable mode
uv pip install -e ".[dev]"

# 2. Confirm CLI entry point
econflow --help
econflow --version

# 3. Run the test suite (84 tests pass without panel_clean.csv fix)
pytest tests/test_exceptions.py tests/test_provenance.py -v

# 4. Run regression helper tests
pytest tests/regression/test_helpers.py -v

# 5. Full suite (after Decision 2 and 3)
pytest
```

Expected after full setup: 109 tests pass (84 unit + 25 regression helper —
same count as the source repo, all green).

---

## Source Repository State

The source repository `AI and Productivity/` is **untouched**.

- Branch: `refactor-platform`  
- HEAD commit: `6321923 Complete Sprint 2: establish reproducible baseline and regression framework`  
- All 149 files were copied, not moved.
- The source `.git/index.lock` issue (stale, June 21) remains — resolve by
  deleting it from Windows PowerShell:
  ```powershell
  del "C:\Users\Lenovo\Desktop\Courses\EconWithAi\AI and Productivity\.git\index.lock"
  git push origin refactor-platform
  ```

---

*Generated by automated migration — 2026-06-24*
