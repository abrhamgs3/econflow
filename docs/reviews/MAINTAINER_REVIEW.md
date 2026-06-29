# Maintainer Review — EconFlow

**Reviewer:** External maintainer, handed repository cold  
**Date:** 2026-06-29  
**Repository tag:** unreleased (pyproject.toml: `0.1.0`)  
**Method:** Read every source file, run the CLI, inspect CI, run the test suite

---

## Summary Verdict

EconFlow has a good architectural skeleton and a serious testing foundation (878 tests,
ruff-clean). The plugin framework, provenance recording, and integrity layer are
genuinely well-designed. The ADRs and SDK document represent real intellectual effort.

It is not maintainable in its current state.

The problems are not minor rough edges. The README's primary Quick Start example crashes.
The project contains three different pipelines with overlapping responsibilities and no
clear statement of which one is authoritative. The public API is documented in three
places with three different answers. Core infrastructure raises `NotImplementedError`
at runtime. The package version is `0.1.0` for a codebase that has a full plugin system,
integrity certification, and eight estimators.

An external maintainer handed this repository cannot tell users what command to run,
cannot safely extend the estimator registry (it is bypassed at runtime), and cannot
trust the documentation to describe what the code actually does.

The sections below are ordered by the severity of the confusion they create.

---

## 1. The README Quick Start Is Broken

**This is the first thing any user does.**

The README shows:

```bash
econflow run --data-path examples/getting_started/data/grunfeld.csv \
    --models ols fe re \
    --outputs csv latex
```

Running this command produces:

```
Pipeline error: Data validation failed.
Required columns missing: ['country', 'ln_ai', 'ln_tfp', 'ln_hc', 'ln_gdp']
```

The `--data-path` flag invokes `pipeline.py` — the legacy paper-specific pipeline
hard-coded to the AI & Productivity paper's variable names. It is completely unrelated
to the Grunfeld dataset. The correct command is:

```bash
econflow run --config examples/getting_started/config.yaml \
    --models ols fe re \
    --outputs csv latex
```

This works. It runs the generic pipeline (`pipeline_generic.py`) and produces correct
output. But `--data-path` is what the README shows.

**Impact:** Every new user's first experience is a crash. The error message names
columns from a paper they have never heard of, giving no hint of what went wrong
or how to fix it.

---

## 2. Three Pipelines, No Clear Authority

The repository contains three pipeline implementations:

| File | Purpose | Status |
|------|---------|--------|
| `src/econflow/pipeline.py` | Paper-specific (AI & Productivity) | Active — invoked by `econflow run --data-path` |
| `src/econflow/pipeline_generic.py` | Config-driven generic pipeline | Active — invoked by `econflow run --config` |
| `src/econflow/core/pipeline.py` | Scaffold stub | Exists, does nothing |

A new maintainer opening `src/econflow/` sees three files named `pipeline*.py`. The
README does not explain the distinction. ARCHITECTURE.md lists only `pipeline.py`.
The SDK describes only the generic pipeline. `cli.py` imports from both at lines 414
and 458 without explanation.

**The deeper problem:** `pipeline_generic.py` line 36 imports estimators directly:

```python
from linearmodels.panel import PanelOLS, PooledOLS
```

This bypasses the estimator plugin registry entirely. Installing a custom estimator
via `@register_estimator()` has no effect on what the active pipeline runs. The
entire plugin architecture documented in the SDK is inoperative for the default
execution path.

**What I needed to read to understand this:** `cli.py` (420 lines), `pipeline.py`
(not documented in ARCHITECTURE.md), `pipeline_generic.py`, `core/pipeline.py`, and
the SDK — and then run both commands to see what actually happened.

---

## 3. Two Exception Hierarchies, Two `PipelineError` Classes

`src/econflow/exceptions.py` defines:

```python
class EconFlowError(Exception): ...
class PipelineError(EconFlowError): ...
```

`src/econflow/core/exceptions.py` defines:

```python
class EconFlowCoreError(Exception): ...
class PipelineError(EconFlowCoreError): ...
```

These are two different classes with the same name rooted in two unrelated base
exceptions. User code that writes `except PipelineError` will catch only one of them,
depending on which module they imported from. The other will propagate uncaught.

There is no `except EconFlowError` handler that covers both. There is no documentation
that both exist. Neither module imports from the other.

This is a latent runtime bug that will surface whenever `core/pipeline.py` is actually
implemented or whenever any caller uses `except PipelineError` after importing from
the wrong module.

---

## 4. The `register` Name Conflict

`econflow.estimation.__init__` exports a function named `register`.  
`econflow.ingestion.__init__` also exports a function named `register`.

A user who imports both in any order (which any script using the full framework must
eventually do) silently clobbers one with the other. The second import wins.

```python
from econflow.estimation import register   # estimator registrar
from econflow.ingestion import register    # silently overwrites it; now connector registrar

register("my_estimator")                   # registers a connector, not an estimator
```

This fails silently. No error is raised at import time. The `register` that remains
in scope is whichever was imported last.

The SDK (written later) documents `register_estimator()` and `register_connector()` as
the correct API. CONTRIBUTING.md still documents `@register()`. There is no deprecation
notice, no warning, and no `__all__` guard that exposes only the correct name.

---

## 5. `load_config()` Raises `NotImplementedError`

`src/econflow/core/config.py` line 150:

```python
raise NotImplementedError("load_config is not yet implemented.")
```

`load_config()` is the primary entry point for the config-first design philosophy
documented in ADR-002 and DESIGN_PRINCIPLES.md. Every YAML-driven workflow depends
on configuration loading. The generic pipeline reads config via `Settings` (which
has a working path-based loader), so the immediate CLI path does not hit this.
But any caller who follows ADR-002 ("all configuration flows through `load_config()`")
will crash immediately.

The function signature, docstring, and type annotation are fully written. Only the
body is not. There is no `# TODO` comment, no issue link, and no test that verifies
this raises `NotImplementedError` (which would at least make the incompleteness
visible in the test output).

---

## 6. Contradictory Documentation on the Core API

Three documents give three different answers to "how do I register an estimator":

**CONTRIBUTING.md (line 120):**
```python
from econflow.ingestion.registry import register
@register("my_source", ...)
```
This example registers a *connector*, not an estimator. The import path is also
internal (`ingestion.registry`), not the public API.

**API_REVIEW.md:**
```python
register_estimator("ols_v2")
from econflow.estimation import register_estimator
```

**PLUGIN_SDK.md:**
```python
from econflow.estimation import register_estimator
@register_estimator("my_estimator", label="...", version="...")
```

The SDK is the most complete and most recent. CONTRIBUTING.md has not been updated.
A contributor who reads CONTRIBUTING.md first (the natural starting point) will write
code that may behave incorrectly or produce confusing errors.

---

## 7. Three Different Test Counts in Three Documents

| Document | Claimed test count |
|----------|-------------------|
| README.md | 100 tests |
| CONTRIBUTING.md | 371 tests |
| Actual (`pytest --collect-only`) | 878 tests |

These are not rounding differences. They represent three different points in the
project's history, none of which was updated when the suite grew. A new contributor
who reads "100 tests" before running the suite will wonder what is wrong with their
environment.

---

## 8. Integrity Checks Are Opt-In By Default

The `econflow certify` command has:

```
--checks / --no-checks    [default: --no-checks]
```

The project's stated philosophy, from DESIGN_PRINCIPLES.md:

> *Reproducibility is not optional. It is the only mode of operation.*

Integrity checks being disabled by default contradicts this directly. A user who
runs `econflow certify` without reading the help text produces a certificate that
skipped all integrity checks. The certificate file does not prominently indicate
this.

---

## 9. The `processing/` Module Is Unimplemented

`CountryHarmoniser` in `processing/harmonise.py` has a docstring, class definition,
and method stubs. The docstring says "Usage (once implemented)." The `normalise()`
method body is not written.

`ARCHITECTURE.md` lists `processing/` as a first-class active package alongside
`estimation/` and `ingestion/`. There is no indication that it is a stub.

`econflow info` does not mention processing. There are no tests in
`tests/processing/`. It is safe to assume a new maintainer would spend time trying
to understand why `CountryHarmoniser` exists before discovering it does nothing.

---

## 10. `VERSIONING.md` Does Not Exist

`pyproject.toml` says `version = "0.1.0"`. The project makes semver claims in
multiple documents. The roadmap targets v1.0 as a defined release milestone.

There is no `VERSIONING.md`. There is no policy document explaining what constitutes
a breaking change, what triggers a major/minor/patch increment, or when the project
will reach 1.0.

CONTRIBUTING.md mentions semver but does not link to a versioning document because
none exists.

---

## 11. `VERSIONING.md` Omission Is Symptomatic of a Broader Documentation Gap

The `docs/` root directory, the first place any maintainer looks for documentation
structure, contains:

```
docs/
├── MIGRATION_PLAN.md          # internal sprint artifact
├── SPRINT6_RC1_REVIEW.md      # internal sprint artifact
├── SPRINT_MIGRATION_ROADMAP.md # internal sprint artifact
├── architecture/
├── development/
├── maintenance/
├── release_notes/
├── roadmap/
└── sdk/
```

The three files in the root are sprint-planning internal documents. They are not
navigation aids. A maintainer who opens `docs/` looking for "where do I start" finds
sprint review notes.

There is no `docs/index.md`, no top-level `DOCUMENTATION.md`, and no README in
`docs/` explaining what each subdirectory contains and who it is for.

`docs/development/` contains Python source files (`agents/*.py`) alongside Markdown.
Source files do not belong in `docs/`.

---

## 12. `ARCHITECTURE.md` Describes a Different Codebase

`ARCHITECTURE.md` Package Structure section:

```
├── data/             Panel CSV validation and loading
├── econometrics/     Active panel econometrics suites
├── features/         Feature engineering
├── visualization/    Publication-quality figures
```

All four packages listed above are deprecated. `grep -r "from econflow.data"
src/tests/` returns only legacy backward-compat shims. `econflow.visualization`,
`econflow.features`, and `econflow.econometrics` are dead code retained for import
compatibility.

The packages that are actually active and maintained — `estimation/`, `ingestion/`,
`integrity/`, `diagnostics/`, `sensitivity/` — receive less description in
ARCHITECTURE.md than the dead packages.

A new contributor who reads ARCHITECTURE.md to understand the codebase will study
four packages that do nothing.

---

## 13. The Backward-Compat Shims Point to Dead Code

`agents/data_agent.py`:
```python
from econflow.data import load_panel_data    # deprecated → shim
```

`econflow.data` is a backward-compat shim for the old API. The shim points to
`econflow.ingestion`. But `econflow.data` itself also re-exports from
`econflow.visualization`, which is separately deprecated. The chain is:

```
agents/ → econflow.data (shim) → econflow.visualization (deprecated)
```

There is no test verifying this chain works. `agents/` is not in the CI import
check. If `econflow.visualization` is deleted (recommended by the repository audit),
`agents/` breaks silently at import time.

---

## 14. `sensitivity/` Is Documented But Not Importable as Documented

`src/econflow/sensitivity/__init__.py` documents `SensitivityRunner` and
`ResultsComparison` as the public API. `ARCHITECTURE.md` lists sensitivity as an
active package.

The import path `from econflow.sensitivity import SensitivityRunner` does not work
because `__init__.py` does not import `SensitivityRunner` at the package level.
A user must know the submodule path.

This is a minor issue but illustrates a pattern: the documented API and the
importable API diverge in several packages without any automated test catching the
gap.

---

## 15. `.github/agents/econometrics.agent.md` Is Unexplained

This file is a Claude-style AI agent definition with tool assignments (`read`,
`search`, `edit`, `execute`) and workflow instructions. It is not a GitHub Actions
workflow. There is no documentation explaining what it is, how it is used, or
whether it is part of the repository's development process.

A new maintainer will not know whether this is:
- An operational CI artifact
- An experimental development aid
- An unused leftover from a prototype

It has no README, no reference in CONTRIBUTING.md, and no test.

---

## 16. The `core/` Split Creates Unresolvable Ambiguity

`src/econflow/core/` contains its own registry, exceptions, config, and pipeline
stubs. `src/econflow/` contains a different registry, exceptions, config approach,
and pipeline. Both are active.

The intent appears to be that `core/` provides the framework layer and the top-level
packages provide domain implementations. But the boundary is not documented anywhere.
`core/__init__.py` does not explain this. No ADR addresses it.

In practice:
- Estimators use `src/econflow/estimation/registry.py` (not `core/registry.py`)
- Connectors use `src/econflow/ingestion/registry.py` (not `core/registry.py`)
- `core/registry.py` manages plugin discovery via entry points

Whether this is intentional three-layer architecture or accidental duplication is
not determinable from reading the code and documentation.

---

## Summary of Findings

### Critical — Breaks Existing Users or Maintainers

| ID | Finding |
|----|---------|
| C-01 | README Quick Start command crashes on the provided example dataset |
| C-02 | Active pipeline (`pipeline_generic.py`) bypasses the estimator plugin registry |
| C-03 | Two `PipelineError` classes in separate hierarchies — latent runtime bug |
| C-04 | `register` name conflict between `estimation` and `ingestion` public APIs |

### High — Creates Significant Confusion or False Assumptions

| ID | Finding |
|----|---------|
| H-01 | `load_config()` raises `NotImplementedError` with no warning in documentation |
| H-02 | CONTRIBUTING.md, API_REVIEW.md, and PLUGIN_SDK.md give contradictory registration API |
| H-03 | ARCHITECTURE.md describes deprecated dead packages as active |
| H-04 | Test count claimed in README (100) and CONTRIBUTING (371) both wrong (actual: 878) |
| H-05 | Integrity checks opt-in by default despite integrity-first design philosophy |
| H-06 | `VERSIONING.md` missing; semver claims are made but not defined |

### Medium — Causes Wasted Time for New Contributors

| ID | Finding |
|----|---------|
| M-01 | `docs/` root contains sprint planning artifacts, no navigation index |
| M-02 | `processing/CountryHarmoniser` documented as active, body not implemented |
| M-03 | Three pipeline files with no clear statement of which is authoritative |
| M-04 | Backward-compat shim chain (`agents/ → data → visualization`) has no tests |
| M-05 | `sensitivity/` public API not importable from package level |
| M-06 | `core/` vs top-level split purpose undocumented; appears to be unintentional duplication |
| M-07 | Python source files (`agents/*.py`) exist inside `docs/development/` |
| M-08 | `pyproject.toml version = "0.1.0"` does not reflect actual development stage |

### Low — Minor Inconsistencies

| ID | Finding |
|----|---------|
| L-01 | CI matrix covers Ubuntu only; no macOS or Windows |
| L-02 | `.github/agents/econometrics.agent.md` unexplained to new maintainers |
| L-03 | `econflow info` does not surface that two estimators (`gmm`, `quantile`) are stubs |
| L-04 | `docs/architecture/` has no index README mapping ADRs to current code status |

---

## What Would Need to Happen Before I Could Maintain This

In priority order:

1. **Fix the README Quick Start** — change `--data-path` to `--config`, or add a
   note that `--data-path` requires specific column names. This takes 10 minutes
   and is the single highest-leverage change in the repository.

2. **Wire the pipeline to the registry** — `pipeline_generic.py` must call
   `registry.get()` to retrieve estimators, not import from `linearmodels` directly.
   Until this is done, the plugin architecture is decorative.

3. **Resolve the exception hierarchy** — either merge both into one root or rename
   one hierarchy and document the split explicitly. The two `PipelineError` classes
   cannot coexist safely.

4. **Rename `register` to `register_estimator` / `register_connector`** — the name
   conflict is a correctness bug, not a style issue. Update CONTRIBUTING.md at the
   same time.

5. **Write `VERSIONING.md`** and update ARCHITECTURE.md to reflect what the packages
   actually do.

6. **Add a `docs/index.md`** and move sprint planning documents out of `docs/`.

Until items 1–4 are addressed, I would not feel comfortable accepting issues or PRs
from users, because I cannot tell users what commands are safe to run.

---

*This review reflects the state of the repository as of 2026-06-29. All findings were
verified by running the CLI, reading source files, and running the test suite.*
