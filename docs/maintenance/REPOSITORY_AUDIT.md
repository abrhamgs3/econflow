# EconFlow Repository Audit

**Date:** 2026-06-28  
**Auditor:** TSC (Claude, Sprint 9)  
**Scope:** Every top-level directory and file; all source sub-packages  
**Method:** Static analysis — import graphs, stub detection, duplicate diffing, dead-import tracing  
**Output:** Authoritative disposition for every artefact. Findings are actionable, not aspirational.

---

## Table of Contents

1. [Summary Scorecard](#1-summary-scorecard)
2. [Top-Level Directory Dispositions](#2-top-level-directory-dispositions)
3. [Source Package Audit (`src/econflow/`)](#3-source-package-audit-srceconflow)
4. [Test Audit (`tests/`)](#4-test-audit-tests)
5. [Documentation Audit (`docs/`)](#5-documentation-audit-docs)
6. [Root-Level File Audit](#6-root-level-file-audit)
7. [Findings Register](#7-findings-register)
8. [Cleanup Roadmap](#8-cleanup-roadmap)

---

## 1. Summary Scorecard

| Category | Total artefacts | Keep as-is | Relocate | Refactor | Delete |
|---|---|---|---|---|---|
| Top-level directories | 9 | 4 | 2 | 1 | 2 |
| Source sub-packages | 22 | 8 | 0 | 5 | 9 |
| Test files | 44 | 34 | 3 | 4 | 3 |
| Documentation files | 28 | 13 | 4 | 2 | 9 |
| Root-level files | 14 | 9 | 0 | 1 | 4 |

**Critical findings:** 4  
**High findings:** 8  
**Medium findings:** 11  
**Low findings:** 7

**Estimated total cleanup effort:** 14–20 developer-hours across 3 sprints.

---

## 2. Top-Level Directory Dispositions

### 2.1 `src/` → **core/** ✅ Keep

The installed package. All active code lives here. Structure is correct.
No action required at the directory level; sub-package issues are catalogued in §3.

### 2.2 `tests/` → **core/** ✅ Keep

Complete, well-organized. Sub-issues catalogued in §4.

### 2.3 `docs/` → **docs/** ✅ Keep (with internal cleanup)

Architecture docs, ADRs, SDK, roadmap — all correctly placed. Three stale sprint
artefacts at `docs/` root (not under a subdirectory) must be moved. See §5.

### 2.4 `examples/` → **examples/** ✅ Keep

Two examples (`ai_productivity_paper/`, `getting_started/`) — both correctly placed.
`examples/ai_productivity_paper/reference_outputs/` is large binary/data content
(PDFs, PNGs, CSVs) that should be excluded from the wheel and tracked via Git LFS.
No immediate action required.

### 2.5 `agents/` → **deprecated/** 🔴 Delete

**Finding A-01 (Critical).** Four files (`data_agent.py`, `econometrics_agent.py`,
`visualization_agent.py`, `writing_agent.py`) are **backward-compatibility shims**:
each file contains only a module docstring declaring itself a shim and re-exports
from the live packages. No file outside `agents/` imports from `agents/`. The shims
are not tested and are not installed by the wheel (absent from `pyproject.toml`
`packages`). They are dead code with no callers.

An identical copy exists at `docs/development/agents/` (diff confirmed identical).
That copy is also dead.

**Disposition:** Delete `agents/` entirely. Delete `docs/development/agents/`.

### 2.6 `app/` → **deprecated/** 🟡 Relocate or delete

**Finding A-02 (Medium).** `app/streamlit_app.py` is a placeholder stub. Its entire
body is a docstring and a `st.set_page_config()` call that prints "The full dashboard
has moved to `examples/ai_productivity_paper/app/streamlit_app.py`." The file has no
callers, is not registered in `pyproject.toml`, and is not tested. The real Streamlit
app lives in `examples/ai_productivity_paper/app/`.

`.streamlit/config.toml` provides the Streamlit theme — it is needed only if
Streamlit is run from the repo root. If `app/` is deleted, `.streamlit/` can also
be removed unless the examples app relies on it.

**Disposition:** Delete `app/streamlit_app.py`. Evaluate whether `.streamlit/config.toml`
should move to `examples/ai_productivity_paper/`. If yes, delete `.streamlit/`.

### 2.7 `outputs/` → **internal/** 🟡 Gitignore or move

**Finding A-03 (Medium).** `outputs/` at the repository root is a **runtime artefact
directory** created by an early pipeline run. It contains:

- `outputs/provenance/REPRODUCIBILITY_REPORT.md` — a dated Sprint 6 report
- `outputs/provenance/schema.json` — the provenance JSON schema

The schema belongs in `src/econflow/` or `docs/architecture/` (as a versioned
artefact). The reproducibility report belongs in `docs/` or should not be committed.
The directory itself should be gitignored (it is a pipeline output, not source).

**Disposition:** Move `schema.json` to `docs/architecture/schemas/provenance_schema.json`.
Move `REPRODUCIBILITY_REPORT.md` to `docs/development/` or delete. Add `outputs/` to
`.gitignore`.

### 2.8 `dist/` → **internal/** 🟡 Gitignore

**Finding A-04 (Low).** `dist/econflow-0.1.0-py3-none-any.whl` and
`dist/econflow-0.1.0.tar.gz` are build artefacts committed to the repository.
Built distributions must not be committed; they should be produced by CI and
uploaded to PyPI or a release page. Committing them bloats the repository
(1.2 MB), causes stale wheels to be served when users clone, and conflicts with
the wheel-verification step in the release process.

**Disposition:** Add `dist/` to `.gitignore`. Delete the committed files from git
history on the next housekeeping commit (`git rm --cached dist/`).

### 2.9 `.github/` → **core/** ✅ Keep (with minor note)

`ci.yml` is the only workflow — appropriate for the current stage.
`agents/econometrics.agent.md` is a Claude agent definition used for AI-assisted
development. Correctly placed.

---

## 3. Source Package Audit (`src/econflow/`)

### 3.1 Duplicate pipeline modules

**Finding S-01 (Critical).**

| File | Status | Callers |
|---|---|---|
| `src/econflow/pipeline.py` | Paper-specific, hardcoded AI productivity paper logic | `cli.py` (legacy mode) |
| `src/econflow/pipeline_generic.py` | Config-driven generic implementation | `cli.py` (active), tests |
| `src/econflow/core/pipeline.py` | Scaffold stub — `NotImplementedError` throughout | Nothing |

`pipeline.py` imports `econflow.data`, `econflow.econometrics`, and `econflow.visualization` —
all of which are themselves deprecated (see §3.3–3.5). It is the root of the legacy
paper-specific execution path. `pipeline_generic.py` is the active implementation.
`core/pipeline.py` is a stub that declares the architecture but implements nothing
and has no callers.

**Disposition:**  
- Rename `pipeline_generic.py` → `pipeline.py` (after removing the legacy `pipeline.py`).  
- Delete legacy `pipeline.py`.  
- Keep `core/pipeline.py` as the future scaffold implementation — clearly mark
  `status = "stub"` in the module docstring and add to `coverage.omit`.

**Effort:** 2 hours (rename, update `cli.py` import, verify tests pass).

---

### 3.2 Duplicate provenance modules

**Finding S-02 (High).**

| File | Status | Callers |
|---|---|---|
| `src/econflow/provenance.py` | Active, tested, 35 tests pass | `integrity/fingerprint.py`, `tests/test_provenance.py` |
| `src/econflow/core/provenance.py` | Scaffold stub — one `NotImplementedError` | Nothing |

Two modules claim to own provenance recording. `econflow.provenance` is the live
implementation. `core/provenance.py` is an architecture placeholder that describes
a future `RunRecord` / `record_run` design that has not been built.

**Disposition:** Keep `econflow.provenance`. Rename `core/provenance.py` to
`core/provenance_STUB.py` or convert it to a one-line comment in `core/__init__.py`
referencing `econflow.provenance`. Add to `coverage.omit` if kept.

**Effort:** 30 minutes.

---

### 3.3 Duplicate exception hierarchies

**Finding S-03 (Critical).**

| File | Root class | Contains |
|---|---|---|
| `src/econflow/exceptions.py` | `EconFlowError` | `DataValidationError`, `MergeError`, `PipelineError`, `ModelSpecificationError`, `AIProdError` (alias) |
| `src/econflow/core/exceptions.py` | `EconFlowCoreError` | `ConfigurationError`, `RegistryError`, `PipelineError`, `IngestionError`, `EstimationError`, `DiagnosticsError`, `OutputError`, `IntegrityError`, `CertificateError`, … |

Two separate `PipelineError` classes exist — one in `econflow.exceptions`, one in
`econflow.core.exceptions` — that are **different Python objects**. Code catching
`econflow.exceptions.PipelineError` will silently miss exceptions raised as
`econflow.core.exceptions.PipelineError` and vice versa. This is a latent bug
that will manifest the moment any scaffold code raises `core.exceptions.PipelineError`.

`EconFlowCoreError` is not a subclass of `EconFlowError`. The two hierarchies are
incompatible: `except EconFlowError` does not catch `EconFlowCoreError` exceptions.

**Disposition:**  
- Merge both hierarchies into `src/econflow/exceptions.py`. `EconFlowCoreError`
  should become an alias for `EconFlowError` (same pattern as `AIProdError`).
- Each exception class from `core/exceptions.py` should become a subclass of its
  `econflow.exceptions` counterpart where one exists (`PipelineError` → `PipelineError`),
  or a new leaf class where none exists (`CertificateError`, `RegistryError`, etc.).
- Export from both `econflow.exceptions` and `econflow.core.exceptions` for
  backward compatibility.

**Effort:** 3 hours (merge hierarchy, update all imports, run full test suite).

---

### 3.4 Deprecated: `src/econflow/data/`

**Finding S-04 (High).**  
`econflow.data` (`loaders.py`, `cleaning.py`, `validators.py`) is a paper-specific
data loading layer hardcoded to the AI productivity paper's column names
(`REQUIRED_COLUMNS`, `NON_SOVEREIGN_ENTITIES`, `AGGREGATE_ENTITIES`).
Its only caller is the legacy `pipeline.py` (itself deprecated by S-01).
The generic connector framework (`econflow.ingestion`) supersedes it.
`pyproject.toml` explicitly lists `src/econflow/data/*` under `coverage.omit`
as "dead-code stub packages".

**Disposition:** Delete `src/econflow/data/`. Update `coverage.omit` accordingly.

**Effort:** 30 minutes (verify no imports survive after `pipeline.py` is removed).

---

### 3.5 Deprecated: `src/econflow/econometrics/`

**Finding S-05 (High).**  
`econflow.econometrics.panel` is a 411-line paper-specific panel estimator
(hardcoded column names, paper-specific model specs). Its only caller is the
legacy `pipeline.py`. The generic estimator registry (`econflow.estimation`)
supersedes it. `coverage.omit` lists it explicitly.

**Disposition:** Delete `src/econflow/econometrics/`. Confirm it is absent from
`econflow/__init__.py` `__all__`.

**Effort:** 20 minutes.

---

### 3.6 Deprecated: `src/econflow/visualization/`

**Finding S-06 (High).**  
`econflow.visualization.figures` (360 lines) contains paper-specific functions
(`ai_tfp_scatter`, `ai_tfp_trend`, `ai_coefficient_comparison`,
`missingness_profile`) named after the AI productivity paper. Its only caller
is the legacy `pipeline.py`. The generic figure builder framework
(`econflow.outputs.figures/`) supersedes it. The `visualization/style.py`
module provides matplotlib style configuration that could be extracted to
`econflow.outputs` if needed. `coverage.omit` lists it.

**Disposition:** Delete `src/econflow/visualization/`. If `style.py` styling is
needed, move the relevant constants to `econflow.outputs`.

**Effort:** 30 minutes.

---

### 3.7 Deprecated: `src/econflow/features/`

**Finding S-07 (Medium).**  
`econflow.features.engineering` (126 lines) contains feature engineering utilities
(lag/lead creation, polynomial expansion, interaction terms). It has **no callers**
outside itself — `grep` finds zero imports from any file except its own
`__init__.py`. It is likely an intermediate artefact from the paper's pre-generic
pipeline. `coverage.omit` lists it.

**Disposition:** Delete `src/econflow/features/`.

**Effort:** 10 minutes.

---

### 3.8 Deprecated: `src/econflow/reporting/`

**Finding S-08 (Medium).**  
`econflow.reporting.narrative` (142 lines) generates LaTeX narrative sections
for the AI productivity paper. Its only caller is the legacy `pipeline.py`.
Generic narrative generation does not yet exist in the platform.
`coverage.omit` lists it.

**Disposition:** Delete `src/econflow/reporting/`. If narrative generation is
needed generically, design it as a plugin type in the SDK (§7 of PLUGIN_SDK.md)
rather than resurrecting this module.

**Effort:** 10 minutes.

---

### 3.9 Dead: `src/econflow/ml/`

**Finding S-09 (Low).**  
`src/econflow/ml/__init__.py` contains only the string `"""Reserved for future use."""`.
No other files exist in the directory. It is an empty namespace placeholder.

**Disposition:** Delete `src/econflow/ml/`. If ML integration is planned, create
the directory when actual code is ready; an empty directory adds no value.

**Effort:** 5 minutes.

---

### 3.10 Dead stubs: `src/econflow/processing/`

**Finding S-10 (High).**  
Six processing modules totalling 634 lines contain paper-specific logic with
`raise NotImplementedError` throughout:

- `ai_index.py` — AI Proxy Index construction (5 `NotImplementedError`)
- `tfp.py` — TFP computation from PWT (3 `NotImplementedError`)
- `harmonise.py` — multi-source panel harmonisation (3 `NotImplementedError`)
- `merge.py`, `quality.py`, `transform.py` — additional stubs

None are imported by any live code. `coverage.omit` lists the entire package.

**Disposition:** These modules have value as **architecture documentation** (they
describe planned interfaces) but must not remain as unimplemented code in the
`src/` tree. Options:
1. (Recommended) Move to `docs/sdk/examples/` as annotated reference designs.
2. Implement them under the plugin SDK pattern as `BasePipelineProcessor` plugins.
3. Delete if the planned functionality is not on the v1.0 roadmap.

**Effort:** 1 hour (extract documentation, delete code).

---

### 3.11 Dead stubs: `src/econflow/diagnostics/` flat files

**Finding S-11 (Medium).**  
Five flat diagnostic files coexist with the active `diagnostics/plugins/` directory:

| File | Lines | `NotImplementedError` count | Caller |
|---|---|---|---|
| `specification.py` | 84 | 1 | itself only |
| `serial.py` | 73 | 1 | itself only |
| `reporter.py` | 110 | 1 | itself only |
| `dependence.py` | 78 | 1 | itself only |
| `overid.py` | 76 | 1 | itself only |

The active implementations for `hausman`, `pesaran_cd`, `serial_correlation`
are in `diagnostics/plugins/`. The flat files are pre-migration stubs that
were never connected to the plugin registry.

**Disposition:** Delete the five flat files. The implementations in
`diagnostics/plugins/` already cover `hausman` (≡ specification), `pesaran_cd`
(≡ dependence), `serial_correlation` (≡ serial). `overid` (Sargan-Hansen) and
`reporter` are not yet implemented in plugins — add placeholder stub files in
`diagnostics/plugins/` with clear `status = "stub"` markers.

**Effort:** 1 hour.

---

### 3.12 Duplicate ingestion flat files

**Finding S-12 (High).**  
Three flat connector files coexist alongside fully-implemented connector classes
in `ingestion/connectors/`:

| Flat file | Lines | Status | Counterpart in `connectors/` |
|---|---|---|---|
| `ingestion/oecd.py` | 86 | Stub (4 `NotImplementedError`) | `connectors/oecd.py` (342 lines, implemented) |
| `ingestion/pwt.py` | 99 | Stub (4 `NotImplementedError`) | `connectors/pwt.py` (375 lines, implemented) |
| `ingestion/world_bank.py` | 92 | Stub (4 `NotImplementedError`) | `connectors/world_bank.py` (298 lines, implemented) |

The flat stubs were written before the `connectors/` sub-package was created.
They have no callers. `coverage.omit` names them individually.

**Disposition:** Delete `ingestion/oecd.py`, `ingestion/pwt.py`,
`ingestion/world_bank.py`. Remove them from `coverage.omit`.

**Effort:** 15 minutes.

---

### 3.13 Naming conflict: `register` function exported from two packages

**Finding S-13 (Critical).** *(Documented in `docs/architecture/API_REVIEW.md`)*  
`econflow.ingestion.__init__` exports `register` (for connectors).  
`econflow.estimation.__init__` exports `register` (for estimators).

Any code that does:

```python
from econflow.estimation import register
from econflow.ingestion import register   # silently clobbers the above
```

now has a connector registrar masquerading as an estimator registrar. This is
a silent, untestable API bug.

**Disposition:** Rename in both `__init__` files:
- `econflow.estimation.register` → `register_estimator`
- `econflow.ingestion.register` → `register_connector`

Keep `register` as a deprecated alias emitting `DeprecationWarning` for
2 minor versions. This is already recommended in `docs/architecture/API_REVIEW.md`
and required by the Plugin SDK (§2.4, §3.1).

**Effort:** 1 hour (rename, add aliases, update all internal call sites, add test).

---

### 3.14 Duplicate CLI: `cli_scaffold/`

**Finding S-14 (Medium).**  
`src/econflow/cli_scaffold/` is a **future CLI scaffold** explicitly documented
as not active (`cli_scaffold/main.py` docstring: "NOT YET ACTIVE. NOT registered
in pyproject.toml"). It is excluded from the wheel (`pyproject.toml`:
`exclude = ["src/econflow/cli_scaffold"]`) and from ruff and coverage.

The active CLI is `src/econflow/cli.py`. The scaffold's sub-commands reference
`econflow.cli.commands` (a path that does not exist) and would fail on import.

**Disposition:** This is intentional technical debt, correctly excluded from
production. No action required until the scaffold migration begins. Confirm it
remains in `coverage.omit` and ruff `exclude`.

---

### 3.15 Duplicate `outputs/figures.py` (flat) vs `outputs/figures/` (directory)

**Finding S-15 (Medium).**

| Path | Lines | Contents |
|---|---|---|
| `outputs/figures.py` | 116 | Imports from `sensitivity.comparison`, provides `TFPFigureBuilder`, `CoeffCompareFigureBuilder` |
| `outputs/figures/` | 422 total | `BaseFigureBuilder`, `CIPlot`, `CoefficientPlot`, `Distribution`, `EventStudy`, `Residual`, `RobustnessComparison` |

`outputs/__init__.py` imports from **both** `figures.py` and `figures/`. The flat
`figures.py` imports `from econflow.sensitivity.comparison import ResultsComparison`,
making `sensitivity/` a live transitive dependency of `outputs/`. The flat file
contains two figure builders that appear to predate the `figures/` sub-directory.
`test_figure_builders.py` imports from `outputs.__init__` which re-exports from both.

**Disposition:** Migrate `TFPFigureBuilder` and `CoeffCompareFigureBuilder` from
`figures.py` into `outputs/figures/` as `tfp_figure.py` and `coeff_compare_figure.py`.
Delete `outputs/figures.py`. Update `outputs/__init__.py`.

**Effort:** 2 hours (migrate, update imports, verify 29 figure builder tests pass).

---

### 3.16 Duplicate `outputs/tables.py` (flat) vs `outputs/tables/` (directory)

**Finding S-16 (Medium).**

| Path | Lines | Contents |
|---|---|---|
| `outputs/tables.py` | 118 | Imports from `outputs.tables.*` and re-exports everything |
| `outputs/tables/` | 748 total | 8 concrete table builders |

`outputs/tables.py` is a **pure re-export shim** — it imports from `outputs.tables.*`
and puts everything in `__all__`. This creates a circular-import risk
(`tables.py` imports from `tables/__init__.py` which imports from `tables/*.py`).
It exists to provide a backward-compatible `from econflow.outputs import tables`
import. Since there are no external callers (the only callers are the table builder
files themselves and `outputs/__init__.py`), the shim provides no value.

**Disposition:** Delete `outputs/tables.py`. Update `outputs/__init__.py` to
import directly from `outputs.tables`. Update any test that imports from
`econflow.outputs.tables` to confirm it still works through `outputs/__init__`.

**Effort:** 30 minutes.

---

### 3.17 Empty stubs: `src/econflow/config/` and `src/econflow/utils/`

**Finding S-17 (Low).**

- `src/econflow/config/__init__.py` — `"""Reserved for future use."""`
- `src/econflow/utils/__init__.py` — `"""Reserved for future use."""`

Both directories contain only an `__init__.py` with a reservation docstring
and no other files. They have no callers.

**Disposition:** Delete both directories. When actual configuration or utility
code is needed, create the directories then. Empty reserved directories create
confusion about what is and isn't implemented.

**Effort:** 5 minutes each.

---

### 3.18 `src/econflow/sensitivity/` — partially orphaned

**Finding S-18 (Low).**  
`sensitivity/runner.py` (`SensitivityRunner`, 103 lines) and
`sensitivity/comparison.py` (`ResultsComparison`, 85 lines) are used only by
`outputs/figures.py` (the flat file identified in S-15). Once S-15 is resolved,
the downstream caller in `figures.py` is migrated into `outputs/figures/`, and
`sensitivity/` should be evaluated for whether `SensitivityRunner` and
`ResultsComparison` are still needed as standalone modules or should be
integrated into the estimation framework. They are currently not registered
as plugins.

**Disposition:** Defer until S-15 is resolved. After the migration, grep for
remaining callers and delete if none.

---

## 4. Test Audit (`tests/`)

### 4.1 Overview

| Suite | Files | Tests | Status |
|---|---|---|---|
| `tests/unit/` | 24 | ~530 | Active, well-organized |
| `tests/integration/` | 8 | ~170 | Active |
| `tests/regression/` | 3 | 49 | Active (regression helpers) |
| `tests/` root | 2 | 51 | Active (`test_provenance.py`, `test_exceptions.py`) |

Total: approximately 800 tests. 878 reported passing in Sprint 8.

---

### 4.2 `tests/test_provenance.py` — location mismatch

**Finding T-01 (Low).**  
`tests/test_provenance.py` (35 tests) tests `src/econflow/provenance.py`. It lives
at the `tests/` root rather than in `tests/unit/`. All other unit tests are in
`tests/unit/`. This is a minor organizational inconsistency.

**Disposition:** Move to `tests/unit/test_provenance.py`.

**Effort:** 5 minutes (move file, verify pytest still discovers it).

---

### 4.3 `tests/test_exceptions.py` — location mismatch

**Finding T-02 (Low).**  
Same as T-01. `tests/test_exceptions.py` (16 tests) tests `econflow.exceptions`
and belongs in `tests/unit/`.

**Disposition:** Move to `tests/unit/test_exceptions.py`.

**Effort:** 5 minutes.

---

### 4.4 `tests/regression/` — naming confusion

**Finding T-03 (Medium).**  
`tests/regression/` does not contain regression tests in the classical sense
(tests that guard against numerical regressions to reference values). It contains:
- `helpers.py` — comparison utilities (`assert_csv_equal`, `assert_coefficient_equal`, etc.)
- `test_helpers.py` — 49 unit tests for those comparison utilities
- `conftest.py` — fixtures for the helper tests

The directory name suggests it holds regression/numerical pinning tests (which
would be appropriate in `tests/regression/`), but the content is test infrastructure.
This misleads contributors who look for numerical regression pinning.

**Disposition:** Rename `tests/regression/` → `tests/test_helpers/` or
`tests/regression_helpers/`. Alternatively, move `helpers.py` to `tests/` root
as `tests/regression_helpers.py` and fold the tests into `tests/unit/`.

**Effort:** 30 minutes.

---

### 4.5 Missing tests for deprecated sub-packages

**Finding T-04 (Medium).**  
The deprecated sub-packages (`data/`, `econometrics/`, `visualization/`,
`features/`, `reporting/`, `processing/`) have no unit tests — none in
`tests/unit/` target them. This means deleting them (as recommended in §3)
carries zero test-suite risk. No tests need updating.

**Disposition:** No action (confirmed safe for deletion).

---

### 4.6 `tests/fixtures/reference_outputs/` — empty directory

**Finding T-05 (Low).**  
`tests/fixtures/reference_outputs/` contains only a `README.md` with no reference
output files. The `REPRODUCIBILITY_REPORT.md` in `outputs/provenance/` references
these as the Sprint 2 regression baseline, but the actual reference CSVs and tables
are in `examples/ai_productivity_paper/reference_outputs/`, not here.

**Disposition:** Either populate this directory with the intended reference outputs,
or delete it and update `tests/regression/helpers.py` to point to
`examples/ai_productivity_paper/reference_outputs/`. The `README.md` explains the
intent and is worth keeping as documentation of the planned structure.

**Effort:** 30 minutes to resolve ambiguity.

---

## 5. Documentation Audit (`docs/`)

### 5.1 Duplicate sprint artefacts at `docs/` root vs `docs/development/`

**Finding D-01 (Medium).**  
Three files exist simultaneously at `docs/` root and in `docs/development/`:

| File at `docs/` | File in `docs/development/` | Diff |
|---|---|---|
| `docs/MIGRATION_PLAN.md` | `docs/development/MIGRATION_PLAN.md` | **Identical** |
| `docs/SPRINT_MIGRATION_ROADMAP.md` | `docs/development/SPRINT_MIGRATION_ROADMAP.md` | **Identical** |
| `docs/MIGRATION_PLAN.md` | — | — |

`MIGRATION_CHECKLIST.md` also exists both at the repository root and at
`docs/development/MIGRATION_CHECKLIST.md` (identical).

**Disposition:** Delete the `docs/` root copies. The canonical location is
`docs/development/`. Delete the root-level `MIGRATION_CHECKLIST.md` as well
(keeping `docs/development/MIGRATION_CHECKLIST.md`).

**Effort:** 10 minutes.

---

### 5.2 `docs/SPRINT6_RC1_REVIEW.md` — internal sprint artefact

**Finding D-02 (Medium).**  
`docs/SPRINT6_RC1_REVIEW.md` (410 lines) is the internal RC1 review document
for Sprint 6. It is correctly placed in spirit (a review document belongs in
`docs/development/`), but it sits at `docs/` root rather than in the subdirectory.

**Disposition:** Move to `docs/development/SPRINT6_RC1_REVIEW.md`.

**Effort:** 5 minutes.

---

### 5.3 `docs/development/NEXT_SESSION.md` — stale session plan

**Finding D-03 (Low).**  
`docs/development/NEXT_SESSION.md` (294 lines, dated 2026-06-26) is a task plan
for a specific development session that has since been completed. It describes
git index corruption and pre-release tasks for v0.1.0 that are now done. It has
no ongoing value.

**Disposition:** Delete. If session logs are worth retaining, adopt a naming
convention like `docs/development/sessions/2026-06-26-session.md`.

**Effort:** 5 minutes.

---

### 5.4 `docs/development/2026-06-25.md` — session journal

**Finding D-04 (Low).**  
A date-stamped journal entry for 2026-06-25. Valuable as a historical record but
inconsistently named (other sessions are named `NEXT_SESSION.md`, `SPRINT_3B.md`).
Consider a consistent `docs/development/sessions/` subdirectory for all session
logs.

**Disposition:** Move to `docs/development/sessions/2026-06-25.md`. No deletion.

**Effort:** 5 minutes.

---

### 5.5 `docs/development/agents/` — duplicate of `agents/`

**Finding D-05 (Medium).** *(See also A-01)*  
`docs/development/agents/` contains four `.py` files (`data_agent.py`,
`econometrics_agent.py`, `visualization_agent.py`, `writing_agent.py`)
that are byte-for-byte identical to `agents/*.py`. Both copies are backward-
compatibility shims with no callers. One set of dead-code duplicates in the
repository is bad; two sets are worse.

**Disposition:** Delete `docs/development/agents/` alongside `agents/` (A-01).
Python source files in a `docs/` directory are architecturally wrong regardless.

**Effort:** 5 minutes.

---

### 5.6 Root-level `ARCHITECTURE.md` vs `docs/architecture/`

**Finding D-06 (Low).**  
`ARCHITECTURE.md` (169 lines) at the repository root is an overview document that
describes the package layout and design goals. `docs/architecture/` now contains
a more detailed and current set: `MILESTONE_v0.7.md`, all eight ADRs, `API_REVIEW.md`,
plus domain-specific documents. The root `ARCHITECTURE.md` is partially superseded.

**Disposition:** Update `ARCHITECTURE.md` to be a 1-page index/overview that links
to `docs/architecture/` rather than duplicating its content. Keep at root (it is
a common convention for open-source projects to have `ARCHITECTURE.md` or
`ARCHITECTURE.rst` at root for quick orientation).

**Effort:** 1 hour (rewrite as index).

---

## 6. Root-Level File Audit

### 6.1 Root-level `.md` files

| File | Lines | Status | Note |
|---|---|---|---|
| `README.md` | 153 | ✅ Keep | Public-facing. Needs update once v1.0 nears. |
| `CHANGELOG.md` | 303 | ✅ Keep | Needed for PyPI and contributors. |
| `CONTRIBUTING.md` | 190 | ✅ Keep | Standard open-source file. |
| `CODE_OF_CONDUCT.md` | 124 | ✅ Keep | Standard open-source file. |
| `SECURITY.md` | 59 | ✅ Keep | Standard open-source file. |
| `LICENSE` | — | ✅ Keep | Required. |
| `CITATION.cff` | — | ✅ Keep | Academic citation. Note: ORCID and affiliation are placeholder values (per `NEXT_SESSION.md`). |
| `VISION.md` | 260 | ✅ Keep | Long-term direction document; does not overlap ROADMAP.md in content. |
| `DESIGN_PRINCIPLES.md` | 377 | ✅ Keep | Orthogonal to ROADMAP.md; records principles not strategy. |
| `ROADMAP.md` | 423 | ✅ Keep | Strategic narrative (not superseded by V1_RELEASE_CRITERIA.md — different purposes). |
| `ARCHITECTURE.md` | 169 | 🟡 Refactor | See D-06. |
| `MIGRATION_CHECKLIST.md` | 288 | 🔴 Delete | Duplicate of `docs/development/MIGRATION_CHECKLIST.md`. |
| `requirements.txt` | 10 | 🟡 Medium | See §6.2. |

### 6.2 `requirements.txt` — kept in sync with `pyproject.toml`?

**Finding R-01 (Medium).**  
`requirements.txt` duplicates the `[project.dependencies]` list from `pyproject.toml`
and adds `streamlit>=1.35` (which is in `pyproject.toml` as `[project.optional-dependencies].app`).
Its stated purpose is "Streamlit Cloud deployment." However, Streamlit Cloud reads
`requirements.txt` directly, so this file is necessary for that deployment path.

The risk is drift: if `pyproject.toml` dependencies are updated and `requirements.txt`
is not, the Streamlit deployment will diverge from the package specification.

**Disposition:** Keep `requirements.txt`, but add a comment referencing `pyproject.toml`
and add a CI check (e.g., `pip-compile` or a simple diff step) that fails if the
two diverge. Alternatively, generate `requirements.txt` from `pyproject.toml` in CI.

**Effort:** 1 hour (add CI check).

---

## 7. Findings Register

All findings sorted by priority. Each has an ID, severity, title, location,
estimated effort, and recommended sprint.

### Critical (must fix before v1.0)

| ID | Finding | Location | Effort | Sprint |
|---|---|---|---|---|
| S-13 | `register` name conflict: same function name exported from `estimation` and `ingestion` | `estimation/__init__.py`, `ingestion/__init__.py` | 1 h | 10 |
| S-03 | Duplicate exception hierarchies: `EconFlowError` vs `EconFlowCoreError`, two `PipelineError` objects | `exceptions.py`, `core/exceptions.py` | 3 h | 10 |
| S-01 | Three pipeline modules: legacy paper-specific, active generic, unimplemented scaffold | `pipeline.py`, `pipeline_generic.py`, `core/pipeline.py` | 2 h | 10 |
| A-01 | `agents/` — four dead backward-compat shims with no callers, duplicated in `docs/development/agents/` | `agents/`, `docs/development/agents/` | 0.5 h | 10 |

### High (fix before v1.0 beta)

| ID | Finding | Location | Effort | Sprint |
|---|---|---|---|---|
| S-02 | Duplicate provenance modules (`provenance.py` active, `core/provenance.py` stub) | `provenance.py`, `core/provenance.py` | 0.5 h | 10 |
| S-04 | Deprecated `data/` sub-package — paper-specific, zero callers outside legacy pipeline | `src/econflow/data/` | 0.5 h | 10 |
| S-05 | Deprecated `econometrics/` sub-package — paper-specific, zero callers | `src/econflow/econometrics/` | 0.5 h | 10 |
| S-06 | Deprecated `visualization/` sub-package — paper-specific, zero callers | `src/econflow/visualization/` | 0.5 h | 10 |
| S-10 | Dead stubs: `processing/` — 6 modules, 634 lines, all `NotImplementedError`, zero callers | `src/econflow/processing/` | 1 h | 11 |
| S-12 | Duplicate ingestion flat files (stubs) alongside implemented `connectors/` | `ingestion/oecd.py`, `ingestion/pwt.py`, `ingestion/world_bank.py` | 0.25 h | 10 |
| S-15 | Duplicate `outputs/figures.py` alongside `outputs/figures/` | `outputs/figures.py`, `outputs/figures/` | 2 h | 11 |
| A-04 | Built distributions committed to git (`dist/`) | `dist/` | 0.25 h | 10 |

### Medium (fix before v1.0 RC)

| ID | Finding | Location | Effort | Sprint |
|---|---|---|---|---|
| S-07 | Dead `features/` sub-package — zero callers anywhere | `src/econflow/features/` | 0.25 h | 11 |
| S-08 | Dead `reporting/` sub-package — only caller is legacy pipeline | `src/econflow/reporting/` | 0.25 h | 11 |
| S-11 | 5 dead diagnostic flat files alongside active `diagnostics/plugins/` | `diagnostics/specification.py` etc. | 1 h | 11 |
| S-14 | `cli_scaffold/` — future CLI not yet active, already excluded from wheel | `src/econflow/cli_scaffold/` | 0 h | — |
| S-16 | `outputs/tables.py` shim — pure re-export alongside `outputs/tables/` | `outputs/tables.py` | 0.5 h | 11 |
| A-02 | `app/` — placeholder stub pointing to `examples/` | `app/streamlit_app.py` | 0.25 h | 10 |
| A-03 | `outputs/` runtime artifact at repo root — must be gitignored | `outputs/` | 0.5 h | 10 |
| D-01 | Three duplicate docs at `docs/` root vs `docs/development/` | `docs/MIGRATION_PLAN.md` etc. | 0.25 h | 10 |
| D-02 | `SPRINT6_RC1_REVIEW.md` at wrong level | `docs/SPRINT6_RC1_REVIEW.md` | 0.1 h | 10 |
| D-05 | `docs/development/agents/*.py` — Python source in docs directory | `docs/development/agents/` | 0.1 h | 10 |
| T-03 | `tests/regression/` misnamed — contains helpers, not regression pinning tests | `tests/regression/` | 0.5 h | 11 |

### Low (housekeeping, fix before v1.0 GA)

| ID | Finding | Location | Effort | Sprint |
|---|---|---|---|---|
| S-09 | Empty `ml/` namespace placeholder | `src/econflow/ml/` | 0.1 h | 11 |
| S-17 | Empty `config/` and `utils/` namespace placeholders | `src/econflow/config/`, `src/econflow/utils/` | 0.1 h | 11 |
| S-18 | `sensitivity/` — partially orphaned after S-15 resolution | `src/econflow/sensitivity/` | 0.5 h | 12 |
| D-03 | `NEXT_SESSION.md` — stale session plan | `docs/development/NEXT_SESSION.md` | 0.1 h | 10 |
| D-04 | `2026-06-25.md` — inconsistent naming convention | `docs/development/2026-06-25.md` | 0.1 h | 10 |
| D-06 | `ARCHITECTURE.md` at root partially superseded by `docs/architecture/` | `ARCHITECTURE.md` | 1 h | 11 |
| T-01 | `test_provenance.py` at `tests/` root, not in `tests/unit/` | `tests/test_provenance.py` | 0.1 h | 10 |
| T-02 | `test_exceptions.py` at `tests/` root, not in `tests/unit/` | `tests/test_exceptions.py` | 0.1 h | 10 |
| R-01 | `requirements.txt` not validated against `pyproject.toml` in CI | `requirements.txt`, `ci.yml` | 1 h | 11 |

---

## 8. Cleanup Roadmap

### Sprint 10: Safe deletions (low-risk, high-impact) — ~6 hours

These can all be done in a single PR with no test changes required (deprecated
packages have no tests, stubs have no callers).

1. Delete `agents/` (A-01, 0.5 h)
2. Delete `docs/development/agents/` (D-05, 0.1 h)
3. Delete `app/streamlit_app.py` and evaluate `.streamlit/` (A-02, 0.25 h)
4. Gitignore `dist/`; `git rm --cached dist/` (A-04, 0.25 h)
5. Gitignore `outputs/`; move schema.json to `docs/architecture/schemas/` (A-03, 0.5 h)
6. Delete `ingestion/oecd.py`, `ingestion/pwt.py`, `ingestion/world_bank.py` (S-12, 0.25 h)
7. Delete `src/econflow/data/` (S-04, 0.5 h)
8. Delete `src/econflow/econometrics/` (S-05, 0.5 h)
9. Delete `src/econflow/visualization/` (S-06, 0.5 h)
10. Rename `register` → `register_estimator` / `register_connector` + deprecation aliases (S-13, 1 h)
11. Move duplicate docs: delete `docs/MIGRATION_PLAN.md`, `docs/SPRINT_MIGRATION_ROADMAP.md`, `MIGRATION_CHECKLIST.md` (D-01, 0.25 h)
12. Move `docs/SPRINT6_RC1_REVIEW.md` → `docs/development/` (D-02, 0.1 h)
13. Delete `docs/development/NEXT_SESSION.md` (D-03, 0.1 h)
14. Move `tests/test_provenance.py` → `tests/unit/` (T-01, 0.1 h)
15. Move `tests/test_exceptions.py` → `tests/unit/` (T-02, 0.1 h)

**Sprint 10 risk:** Very low. All deletions are dead code or duplicates with zero live callers.

### Sprint 11: Structural refactors — ~8 hours

These require code changes and test verification.

1. Merge exception hierarchies (S-03, 3 h) — highest effort, highest value before SDK stabilizes
2. Resolve `pipeline.py` / `pipeline_generic.py` duplicate: rename and update CLI (S-01, 2 h)
3. Migrate `outputs/figures.py` content into `outputs/figures/`; delete flat file (S-15, 2 h)
4. Delete `outputs/tables.py` shim (S-16, 0.5 h)
5. Delete `src/econflow/features/`, `src/econflow/reporting/` (S-07, S-08, 0.5 h)
6. Clean diagnostic flat files; add stub markers in plugins (S-11, 1 h)
7. Archive or delete `processing/` stubs (S-10, 1 h)
8. Delete `src/econflow/ml/`, `src/econflow/config/`, `src/econflow/utils/` (S-09, S-17, 0.25 h)
9. Add `requirements.txt` drift check to CI (R-01, 1 h)
10. Resolve `tests/regression/` naming (T-03, 0.5 h)

**Sprint 11 risk:** Medium. Exception hierarchy merge and pipeline rename both touch
many files and require full test suite passage.

### Sprint 12: Documentation housekeeping — ~2 hours

1. Rewrite `ARCHITECTURE.md` as an index (D-06, 1 h)
2. Create `docs/development/sessions/` and move/rename session logs (D-04, 0.25 h)
3. Resolve `core/provenance.py` stub (S-02, 0.5 h)
4. Evaluate `sensitivity/` after S-15 resolution (S-18, 0.5 h)
5. Confirm `CITATION.cff` ORCID and affiliation are correct before PyPI push

---

## Appendix: Files Confirmed for Deletion

The following files have no live callers, are not tested, are not exported
from any `__init__.py` in the active package, and may be deleted in Sprint 10
with confidence:

```
agents/data_agent.py
agents/econometrics_agent.py
agents/visualization_agent.py
agents/writing_agent.py
app/streamlit_app.py
MIGRATION_CHECKLIST.md
docs/MIGRATION_PLAN.md
docs/SPRINT_MIGRATION_ROADMAP.md
docs/SPRINT6_RC1_REVIEW.md              # move to docs/development/
docs/development/agents/data_agent.py
docs/development/agents/econometrics_agent.py
docs/development/agents/visualization_agent.py
docs/development/agents/writing_agent.py
docs/development/NEXT_SESSION.md
src/econflow/data/__init__.py
src/econflow/data/cleaning.py
src/econflow/data/loaders.py
src/econflow/data/validators.py
src/econflow/econometrics/__init__.py
src/econflow/econometrics/panel.py
src/econflow/features/__init__.py
src/econflow/features/engineering.py
src/econflow/ingestion/oecd.py
src/econflow/ingestion/pwt.py
src/econflow/ingestion/world_bank.py
src/econflow/ml/__init__.py
src/econflow/outputs/tables.py
src/econflow/visualization/__init__.py
src/econflow/visualization/figures.py
src/econflow/visualization/style.py
dist/econflow-0.1.0-py3-none-any.whl   # gitignore dist/
dist/econflow-0.1.0.tar.gz
```

Deferred to Sprint 11 (require code changes before deletion):
```
src/econflow/pipeline.py                # after pipeline_generic.py is renamed
src/econflow/reporting/__init__.py
src/econflow/reporting/narrative.py
src/econflow/outputs/figures.py         # after content migrated to outputs/figures/
src/econflow/diagnostics/specification.py
src/econflow/diagnostics/serial.py
src/econflow/diagnostics/reporter.py
src/econflow/diagnostics/dependence.py
src/econflow/diagnostics/overid.py
src/econflow/processing/*               # archive or delete
```

---

*EconFlow Technical Steering Committee — 2026-06-28*  
*Next audit scheduled: before v1.0 RC1*
