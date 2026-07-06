# EconFlow Beta Readiness — Audit Response

**Date:** 2026-07-06  
**Audit reviewed:** External Release Audit (conducted prior to this document)  
**Methodology:** Each finding was independently reproduced against the current HEAD
(`223eb57 feat: Architecture Stabilization Milestone 4`).  
Every claim is backed by a specific file path, line number, and (where relevant) a
runnable Python snippet.

---

## Summary table

| Issue ID | Reviewer verdict | Our finding | Blocker? |
|----------|-----------------|-------------|----------|
| C-1      | 4 stub estimators | **Partially confirmed — 2 stubs, not 4** | Yes |
| C-2      | run skips validation | **Confirmed** | Yes |
| C-3      | DiagnosticReport all stubs | **Confirmed** | High |
| A-1      | Exception hierarchy not unified | **Confirmed — task 213 was never implemented** | Yes |
| A-2      | Two pipeline systems | **Confirmed** | High |
| A-3      | core/ stubs | **Confirmed** | Low |
| S-1      | register_estimator missing | **Confirmed** | Yes |
| S-2      | No entry-point loading | **Confirmed** | Yes |
| CF-1     | pydantic not in deps | **Confirmed** | Yes |
| CF-2     | run skips validation (duplicate of C-2) | **Confirmed** | Yes |
| D-1      | TECHNICAL_DEBT.md "Critical: 0" | **Confirmed** | Low |
| D-2      | SDK "Stability: Stable" on broken API | **Confirmed** | High |
| D-3      | __init__.py lists stub subpackages | **Confirmed** | Low |
| R-1      | DiagnosticReport blocks replication | **Confirmed — narrower impact than stated** | High |
| M-1      | Coverage omits computation engine | **Confirmed** | Medium |
| M-2      | cli_scaffold/ in source tree | **Confirmed** | Low |

---

## Detailed findings

### C-1 — Stub estimators

**Reviewer claim:** 4 of 8 estimators raise `NotImplementedError` (`SystemGMM`, `IV2SLS`,
`RandomEffects`, `PanelQuantile`).

**Finding: PARTIALLY CONFIRMED — 2 stubs, not 4.**

`IV2SLS` and `RandomEffects` are fully implemented using `linearmodels`:

- `src/econflow/estimation/iv.py` line 72: `from linearmodels.iv import IV2SLS as _IV2SLS`
- `src/econflow/estimation/random_effects.py` line 63: `from linearmodels import RandomEffects as _RE`

Both are registered with `status="implemented"` in the registry and confirmed by:

```
python -c "from econflow.estimation.registry import list_estimators; \
           print({e['id']: e['status'] for e in list_estimators()})"
# {'fd': 'implemented', 'fe': 'implemented', 'gmm': 'stub',
#  'iv': 'implemented', 'ols': 'implemented', 'quantile': 'stub',
#  're': 'implemented', 'twfe': 'implemented'}
```

`gmm` and `quantile` are confirmed stubs:

- `src/econflow/estimation/gmm.py` line 65: `raise NotImplementedError("SystemGMM.fit() is not yet implemented...")`
- `src/econflow/estimation/quantile.py` line 71: `raise NotImplementedError("PanelQuantile.fit() is not yet implemented...")`

**Additional finding not in original audit:** `src/econflow/commands/validate.py` line 42
contains the fix hint `"Fix: Use one of: ols, fe, twfe, re, fd, iv, gmm, quantile"` — this
lists `gmm` and `quantile` as valid options despite both being stubs, which is actively
misleading to users who follow the hint.

**Breaking change if fixed:** No. Removing `gmm`/`quantile` from the hint text is
documentation-only. Removing them from `_CANONICAL_ESTIMATORS` in `config/linter.py`
line 132 changes linter behaviour (currently accepts `gmm` without warning) but is
non-breaking for users not using stubs.

**Smallest safe fix:**
1. Remove `"gmm"` and `"quantile"` from `_CANONICAL_ESTIMATORS` in `config/linter.py` line 132.
2. Remove `gmm, quantile` from the fix hint in `commands/validate.py` line 42.
3. Add a new linter check: if an estimator resolves to a stub ID, emit an `error` —
   `"Estimator 'gmm' is not yet implemented. Available estimators: ols, fe, twfe, re, fd, iv."`

---

### C-2 / CF-2 — `econflow run` does not validate before executing

**Finding: CONFIRMED.**

`src/econflow/cli.py` line 477 calls `run_from_config()` directly with no prior
`run_validate()` call. The only pre-flight check is a file-existence test (lines
462–466). Semantic validation and cross-file validation are skipped entirely.

The `run_validate` import at line 298 is inside the `validate` command function body,
not the `run` command.

**Breaking change if fixed:** No. Adding pre-flight validation is additive. The only
visible change is that some previously-silent config errors now produce an early abort
instead of a mid-pipeline traceback.

**Smallest safe fix:** In `cli.py`, immediately before the `run_from_config()` call
(line 477):

```python
from econflow.commands.validate import run_validate
_exit = run_validate(config_path=config, models_path=models,
                     outputs_path=outputs, check_data=False, console=console)
if _exit != 0:
    raise typer.Exit(code=_exit)
```

---

### C-3 — `DiagnosticReport` methods are all stubs

**Finding: CONFIRMED.**

`src/econflow/diagnostics/reporter.py`:

- Line 56: `def print(self) -> None: raise NotImplementedError`
- Line 60: `def to_dict(self) -> dict[str, Any]: raise NotImplementedError`
- Line 64: `def to_latex(self) -> str: raise NotImplementedError`
- Line 110: `DiagnosticReporter.run_all()` also raises `NotImplementedError`

The individual diagnostic plugins (`hausman.py`, `breusch_pagan.py`, etc.) are
implemented and return `DiagnosticResult` objects, but there is no code path that
collects those results into a rendered `DiagnosticReport`.

**Breaking change if fixed:** No. These methods currently always raise; any
implementation is strictly additive.

**Smallest safe fix:** Implement `to_dict()` first — iterate over the dataclass
fields and serialise each result. `print()` can then be a single Rich table call
over `to_dict()`. `run_all()` orchestrates the plugins and populates the fields.
`to_latex()` can remain a stub explicitly noted for v1.1.

---

### A-1 — Exception hierarchy not unified

**Finding: CONFIRMED. Task 213 was marked complete but no code change was ever made.**

Runtime proof:

```python
from econflow.exceptions import EconFlowError
from econflow.core.exceptions import EconFlowCoreError, RegistryError
issubclass(EconFlowCoreError, EconFlowError)  # → False
issubclass(RegistryError, EconFlowError)       # → False
```

- `src/econflow/core/exceptions.py` line 45: `class EconFlowCoreError(Exception)`
- `src/econflow/exceptions.py` line 35: `class EconFlowError(Exception)`

Neither class imports from or references the other. The git log confirms no commit
between the Milestone 2 tag and today touched either of these lines — both files
last changed in `9e9746b` (Category-1 release blockers, well before task 213 was
assigned).

**Consequence:** Any `try/except EconFlowError` in user code silently misses
`RegistryError`, `IngestionError`, `EstimationError`, `CertificateError`, and all
other `EconFlowCoreError` children.

**Breaking change if fixed:** No. `class EconFlowCoreError(EconFlowError)` is
backward compatible — existing `except EconFlowCoreError` clauses continue to work
unchanged.

**Smallest safe fix:** One line in `src/econflow/core/exceptions.py` line 45:

```python
# Before
class EconFlowCoreError(Exception):

# After  (add the import at the top of the file)
from econflow.exceptions import EconFlowError
class EconFlowCoreError(EconFlowError):
```

Run the test suite to confirm no catch clause is inadvertently broadened.

---

### A-2 — Two pipeline systems coexist

**Finding: CONFIRMED.**

- `src/econflow/pipeline.py` line 200: hardcoded default path
  `data/processed/panel_clean.csv` — paper-specific, meaningless to external users.
- `src/econflow/cli.py` lines 515–545: legacy mode branch still active; calls
  `from econflow.pipeline import run as _run`.
- `econflow run` help text documents both modes with equal prominence.

**Breaking change if fixed:** Yes, for any existing user of legacy mode. Must be
handled as a deprecation, not an immediate removal.

**Smallest safe fix:** In `cli.py`, at the top of the legacy mode branch, add:

```python
import warnings
warnings.warn(
    "Legacy mode (--data-path) is deprecated and will be removed in EconFlow v2.0. "
    "Use --config / --models / --outputs instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

Move `pipeline.py` to `examples/ai_productivity_paper/` in the same commit, update
the legacy import path accordingly. This preserves backward compatibility while
signalling intent.

---

### A-3 — `core/` package is a non-functional stub layer

**Finding: CONFIRMED.**

- `src/econflow/core/pipeline.py` line 81: `raise NotImplementedError`
  (`AbstractPipeline.from_config`)
- `src/econflow/core/pipeline.py` line 106: `raise NotImplementedError`
  (`AbstractPipeline.run`)
- `src/econflow/core/config.py` line 150: `raise NotImplementedError("load_config is
  not yet implemented.")`

The entire `core/` package is excluded from coverage (`pyproject.toml` line 57). No
live code path runs through `core/pipeline.py` or `core/config.py`.

Note: `core/exceptions.py` and `core/registry.py` have active consumers and must be
retained.

**Breaking change if fixed (deletion approach):** No — nothing calls these stubs.

**Smallest safe fix:** Delete `src/econflow/core/pipeline.py` and
`src/econflow/core/config.py`. Update `ARCHITECTURE.md` to describe the actual
orchestration path (`pipeline_generic.py`). Remove `"src/econflow/core/*"` from the
coverage omit list — the remaining `core/` files (`exceptions.py`, `registry.py`)
are testable. This is lower risk than attempting to implement the stubs.

---

### S-1 — `register_estimator` does not exist

**Finding: CONFIRMED.**

```python
from econflow.estimation import register_estimator
# → ImportError: cannot import name 'register_estimator'
#   from 'econflow.estimation'
```

The actual exported name is `register`, defined at
`src/econflow/estimation/registry.py` line 64, re-exported from
`src/econflow/estimation/__init__.py` line 68.

`docs/sdk/PLUGIN_SDK.md` references `register_estimator` at lines 58, 94, 118,
136, 401, and 408. Every code example in §1 (Quick Start) and §2 (Estimator
Plugins) fails on the first import line.

**Breaking change if fixed:** No. Adding an alias is backward compatible.
Renaming `register` to `register_estimator` would break internal callers — use an
alias instead.

**Smallest safe fix:** In `src/econflow/estimation/__init__.py`, after the
`register` import:

```python
register_estimator = register  # SDK-documented alias
```

Add `"register_estimator"` to `__all__`. Two lines, no renames required.

---

### S-2 — Plugin entry-point loading not implemented

**Finding: CONFIRMED.**

A full search across `src/econflow/` for `entry_points.*econflow.plugins` returns
zero results. `importlib.metadata` is used in six files — all for version
introspection only, never for plugin loading.

`docs/sdk/PLUGIN_SDK.md` §9.3 documents `[project.entry-points."econflow.plugins"]`
as the canonical plugin installation path. Plugins declared this way are silently
never loaded.

**Breaking change if fixed:** No.

**Smallest safe fix (implement):** Add to `src/econflow/estimation/registry.py` at
module level after `_REGISTRY` is defined:

```python
def _load_entry_point_plugins() -> None:
    try:
        import importlib.metadata as _meta
        for ep in _meta.entry_points(group="econflow.plugins"):
            try:
                ep.load()
            except Exception as exc:  # noqa: BLE001
                import warnings
                warnings.warn(
                    f"Failed to load plugin '{ep.name}': {exc}",
                    RuntimeWarning, stacklevel=2,
                )
    except Exception:  # pragma: no cover
        pass

_load_entry_point_plugins()
```

**Smallest safe fix (retract):** If implementation before v1.0 is not feasible,
replace SDK §9.3 with: *"Entry-point auto-loading is planned for v1.1. In v1.0,
add `import my_plugin` at the top of your script before calling `econflow run`."*

---

### CF-1 — `pydantic` missing from `pyproject.toml` dependencies

**Finding: CONFIRMED.**

`pyproject.toml` lines 14–25 list `[project.dependencies]` with nine packages.
`pydantic` is not among them. The full dependency list: `pandas`, `numpy`,
`statsmodels`, `linearmodels`, `matplotlib`, `scipy`, `typer`, `rich`, `pyyaml`.

Pydantic v2 is a hard import in `src/econflow/config/models.py`,
`config/linter.py`, `config/docs.py`, and `core/config.py`.

**Breaking change if fixed:** No.

**Smallest safe fix:** Add `"pydantic>=2.0"` to `[project.dependencies]`. One line.

---

### D-1 — `TECHNICAL_DEBT.md` self-assessment claims "Critical: 0"

**Finding: CONFIRMED.**

`docs/development/TECHNICAL_DEBT.md` line 14:
`| Critical | 0 | No blockers — the live pipeline (pipeline_generic.py) is fully implemented |`

This was accurate when the assessment was written (the pipeline is implemented)
but does not account for the Plugin SDK, exception unification, or pydantic
dependency issues found in this audit.

**Breaking change if fixed:** N/A — documentation only.

**Smallest safe fix:** Update the summary table to reflect the confirmed blockers.
Add a "Last reviewed" date header to prevent future staleness.

---

### D-2 — `PLUGIN_SDK.md` claims `Stability: Stable` for a broken API

**Finding: CONFIRMED.**

`docs/sdk/PLUGIN_SDK.md` line 4: `**Stability:** Stable`

The SDK's first code example fails with `ImportError` (S-1). The entry-point
path in §9.3 is unimplemented (S-2). The "Stable" label creates false confidence.

**Breaking change if fixed:** No.

**Smallest safe fix:** Change line 4 to `**Stability:** Beta` and add a note:
*"Known issues: see docs/release/BETA_READINESS_RESPONSE.md (S-1, S-2)."* Restore
to `Stable` once S-1 and S-2 are resolved.

---

### D-3 — `__init__.py` docstring lists stub subpackages

**Finding: CONFIRMED.**

`src/econflow/__init__.py` lines 18–23 list `processing`, `sensitivity`, and
`reporting` as available subpackages with concrete API descriptions. All three
packages contain only `NotImplementedError` stubs (confirmed: `processing/` has
24 `NotImplementedError` instances across 6 files; `sensitivity/` has 6 across
2 files).

**Breaking change if fixed:** No — docstring only.

**Smallest safe fix:** Annotate stub packages in the docstring:
`processing  [stub — not yet available]`. Add an explicit "Available in v1.0"
list that enumerates only packages with working implementations.

---

### R-1 — `DiagnosticReport` blocks replication provenance

**Finding: CONFIRMED — but narrower impact than the audit stated.**

`diagnostics/reporter.py` line 60 raises `NotImplementedError`. However, no code
in `replication/` or `integrity/` references `DiagnosticReport`. The replication
package uses `replication/models.py` dataclasses (which have working `to_dict()`
methods) and does not call into `diagnostics/reporter.py`. The consequence is not
a crash in the replication system — it is an absence: diagnostic results are simply
not included in any provenance record.

**Fix:** Same as C-3.

---

### M-1 — Coverage configuration omits the computation engine

**Finding: CONFIRMED.**

`pyproject.toml` lines 53–67 omit `core/*`, `data/*`, `diagnostics/*`,
`estimation/*`, `econometrics/*`, `features/*`, `ml/*`, `processing/*`,
`reporting/*`, `sensitivity/*`, and `outputs/*` from coverage. Line 84 additionally
excludes `"raise NotImplementedError"` lines from coverage counts. The `fail_under
= 70` threshold is met entirely by covering config, CLI, integrity, ingestion
connectors, and replication scaffolding.

**Breaking change if fixed:** No.

**Smallest safe fix:** Remove the omit entries for packages that have real
implementations (`estimation/`, `diagnostics/`, `outputs/`). Run the test suite;
adjust `fail_under` to the value that passes today (likely 50–60%) and document
the target trajectory. Do not keep `raise NotImplementedError` in `exclude_lines`
for any package that has been removed from `omit`.

---

### M-2 — `cli_scaffold/` shadow CLI in source tree

**Finding: CONFIRMED.**

`src/econflow/cli_scaffold/commands/` contains `project.py`, `reproduce.py`,
`run.py`, and `validate.py` — all stubs duplicating Sprint 3B commands. Excluded
from the wheel and from ruff, but present in the source tree with no maintenance
guarantee.

**Breaking change if fixed:** No — already excluded from the wheel.

**Smallest safe fix:** `git rm -r src/econflow/cli_scaffold/`. Copy any design
rationale from the docstrings to `docs/architecture/` first.

---

## Blocker summary — must be resolved before v1.0 public release

| Priority | Issue | File | Fix effort |
|----------|-------|------|-----------|
| 1 | **CF-1** pydantic missing from dependencies | `pyproject.toml` | 1 line |
| 2 | **S-1** `register_estimator` alias missing | `estimation/__init__.py` | 2 lines |
| 3 | **A-1** exception hierarchy not unified | `core/exceptions.py` line 45 | 1 line + import |
| 4 | **C-2** `run` skips config validation | `cli.py` line 477 | ~6 lines |
| 5 | **S-2** entry-point loading unimplemented | `estimation/registry.py` | ~15 lines OR retract SDK §9.3 |
| 6 | **C-1** gmm/quantile listed as valid in fix hint | `config/linter.py` line 132, `commands/validate.py` line 42 | 2 lines |

---

## High priority, not hard blockers

| Issue | File | Fix effort |
|-------|------|-----------|
| **C-3 / R-1** DiagnosticReport all stubs | `diagnostics/reporter.py` | 1–2 days |
| **D-2** SDK "Stability: Stable" inaccurate | `docs/sdk/PLUGIN_SDK.md` line 4 | 1 line |
| **A-2** legacy pipeline deprecation | `cli.py` lines 515–545, `pipeline.py` | ~10 lines + DeprecationWarning |
| **M-1** coverage omits computation engine | `pyproject.toml` lines 53–67 | Remove omit lines for implemented packages |

---

## Post-release, low risk

| Issue | Fix effort |
|-------|-----------|
| **A-3** delete `core/pipeline.py` and `core/config.py` stubs | 15 min |
| **D-1** update TECHNICAL_DEBT.md | 30 min |
| **D-3** fix `__init__.py` docstring | 5 min |
| **M-2** delete `cli_scaffold/` | 5 min |

---

*Document generated: 2026-07-06. Re-run verification against HEAD before each
release candidate.*
