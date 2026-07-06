# EconFlow — Technical Debt Assessment

**Date:** 2026-06-27  
**Scope:** `src/econflow/` (excluding `cli_scaffold/`, which is a
development prototype not shipped in the wheel)  
**Test suite at assessment:** 200+ tests, ruff clean

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| Critical | 0 | No blockers — the live pipeline (`pipeline_generic.py`) is fully implemented |
| High | 3 | Stub subpackages that `info` advertises as available |
| Medium | 6 | Dead-code layers that shadow the real implementation |
| Low | 8 | Documentation gaps, minor inconsistencies, missing type annotations |

---

## High — Stub packages advertised in `econflow info`

These items appear in `ESTIMATOR_REGISTRY` or `DATA_CONNECTOR_REGISTRY` with
status `"stub"`.  They are visible to users who run `econflow info` and could
cause confusion if users try to reference them in `models.yaml`.

### TD-H1 — GMM, IV, RE, Quantile estimators

**Files:** `src/econflow/estimation/gmm.py`, `iv.py`, `random_effects.py`, `quantile.py`  
**Problem:** Each file contains a class that raises `NotImplementedError` on
every method.  Any `models.yaml` that references `estimator: GMM` will fail
at runtime with an unhelpful traceback.  The `validate` command checks for
supported estimators but its `SUPPORTED_ESTIMATORS` set only includes `OLS`
and `FE`, so unsupported estimators are flagged at validation time — this is
good, but the user still sees stub entries in `econflow info`.

**Payoff:** Implement or remove.  If implementation is deferred to Sprint 5+,
add a `validate` check that explicitly fails (not warns) when a stub estimator
is used, with a clear message: `"GMM is not yet available. Use OLS or FE."`.

**Effort estimate:** 2–4 sprints per estimator to implement correctly.

### TD-H2 — World Bank, OECD, PWT data connectors

**Files:** `src/econflow/ingestion/world_bank.py`, `oecd.py`, `pwt.py`  
**Problem:** Each raises `NotImplementedError`.  The `info` command shows them
as stubs.  There is no `config.yaml` key to select a connector yet (`data.source`
is not implemented), so users cannot accidentally trigger them through config —
but the `ingestion/` package is advertised in `ARCHITECTURE.md` and
`DATA_CONNECTOR_REGISTRY`.

**Payoff:** Either implement the World Bank connector (most commonly needed)
or add a `"coming-soon"` status to the registry display so users aren't
misled about availability.

**Effort estimate:** 1 sprint per connector (requires `pandas-datareader` or
`wbgapi` dependency).

### TD-H3 — `cli_scaffold/` prototype code included in source tree

**Files:** `src/econflow/cli_scaffold/` (commands: `project.py`, `reproduce.py`,
`run.py`, `validate.py`)  
**Problem:** These files contain 5 `NotImplementedError` stubs that duplicate
the Sprint 3B commands.  The scaffold is excluded from the wheel
(`tool.hatch.build.targets.wheel.exclude`) and from ruff, but it lives in the
source tree and creates confusion about which implementation is canonical.

**Payoff:** Delete `cli_scaffold/` entirely, or move it to
`docs/architecture/cli_scaffold_reference/` as documentation only.

**Effort estimate:** 15 minutes (deletion + git).

---

## Medium — Dead-code layers that shadow real implementation

### TD-M1 — `core/pipeline.py` abstract base vs `pipeline_generic.py`

**File:** `src/econflow/core/pipeline.py`  
**Problem:** Defines `AbstractPipeline` and `PipelineStage` with
`NotImplementedError` abstract methods.  These are *not* used by
`pipeline_generic.py`, which is the real implementation.  The abstraction
adds no value currently and misleads developers who expect it to be the
entry point.

**Payoff:** Either (a) make `pipeline_generic.py` inherit from `AbstractPipeline`
to close the loop, or (b) delete `core/pipeline.py` and reserve the class
hierarchy for Sprint 6 (multi-pipeline support).

**Effort estimate:** 30 minutes to wire, or 5 minutes to delete.

### TD-M2 — `core/config.py` `load_config()` stub

**File:** `src/econflow/core/config.py` line 150  
**Problem:** `load_config()` raises `NotImplementedError`.  Configuration is
loaded directly with `yaml.safe_load()` in `pipeline_generic.py` and all
`commands/` modules — there is no central config loader.

**Payoff:** Implement `load_config(path) -> ProjectConfig` as a Pydantic
model load, and have all call sites use it.  This would centralise validation
and allow typed config access (`cfg.data.entity_col` vs `cfg["data"]["entity_col"]`).

**Effort estimate:** 1 sprint.

### TD-M3 — `core/registry.py` unused registry

**File:** `src/econflow/core/registry.py`  
**Problem:** Defines `BaseRegistry` and `EstimatorRegistry` with abstract
`register`/`get` methods.  Not used anywhere — `info.py` uses a plain list.

**Payoff:** Either adopt as the plugin discovery mechanism in Sprint 5, or delete.

### TD-M4 — `core/provenance.py` stub vs `provenance.py` implementation

**Files:** `src/econflow/core/provenance.py` (stub), `src/econflow/provenance.py`  
**Problem:** Two provenance modules exist.  `core/provenance.py` raises
`NotImplementedError`.  `provenance.py` is the real implementation used by
`pipeline_generic.py`.  Having both in the tree creates confusion.

**Payoff:** Delete `core/provenance.py`.

**Effort estimate:** 5 minutes.

### TD-M5 — `diagnostics/` package — all stubs

**Files:** `src/econflow/diagnostics/` (dependence, overid, reporter, serial,
specification)  
**Problem:** All functions raise `NotImplementedError`.  The package is
imported by nothing in the live pipeline.

**Payoff:** Either implement as part of Sprint 6 (post-estimation diagnostics)
or remove from the wheel until ready.

**Effort estimate:** 3–5 sprints to implement properly.

### TD-M6 — `data/` package vs `validators.py` / `ingestion/`

**Files:** `src/econflow/data/cleaning.py`, `data/loaders.py`, `data/validators.py`  
**Problem:** A second data layer exists alongside `validators.py` and
`ingestion/csv_loader.py`.  The live pipeline uses `ingestion/csv_loader.py`
and `validators.py`, not `data/`.  The `data/` package appears to be a
future refactoring target.

**Payoff:** Either migrate the live code to use `data/` (requires Sprint 4+
work), or clearly mark `data/` as `__future_use__` and document the
intended migration path.

---

## Low — Documentation and minor inconsistencies

### TD-L1 — `econflow info` advertises `Project path` as CWD

The `Project path` line in `econflow info` shows `Path.cwd()`, which is
correct when the user runs the command from the project root but misleading
if they are in a subdirectory.  A future improvement would be to resolve
the path from the `--config` flag's parent directory.

### TD-L2 — `econflow validate` has no `--strict` mode

All current checks either pass or fail.  Some checks (e.g., duplicate panel
keys) produce a `warn` instead of `fail`.  A `--strict` flag that promotes
all warnings to failures would be useful for CI.

### TD-L3 — Test coverage on `pipeline_generic.py` relies on integration tests

The `run_from_config()` function is only exercised by integration tests, not
unit tests.  If the integration tests are skipped (no fixture data), coverage
on this path drops significantly.

**Payoff:** Add a unit test using the `tests/fixtures/synthetic/sample_panel.csv`
fixture that patches the output directory to tmp_path.

### TD-L4 — `ESTIMATOR_REGISTRY` is duplicated between `info.py` and `validate.py`

`info.py` has `ESTIMATOR_REGISTRY` (for display).  `validate.py` has
`SUPPORTED_ESTIMATORS = {"OLS", "FE"}` (for validation).  These need to be
kept in sync manually.

**Payoff:** Import `ESTIMATOR_REGISTRY` in `validate.py` and derive
`SUPPORTED_ESTIMATORS = {e["id"] for e in ESTIMATOR_REGISTRY if e["status"] == "implemented"}`.

**Effort estimate:** 10 minutes.

### TD-L5 — No type stubs for `linearmodels`

`pipeline_generic.py` uses `linearmodels.PooledOLS` and `PanelOLS` without
type annotations on the return values, causing mypy to flag these as `Any`.
`linearmodels` does not ship type stubs.

**Payoff:** Add `py.typed` marker and inline type ignores, or wait for
upstream stubs.

### TD-L6 — `_get_ram_gb()` uses a raw `ctypes` struct on Windows

The Windows fallback in `doctor.py` uses `ctypes.windll.kernel32` which
mypy cannot verify.  A `# type: ignore[attr-defined]` comment suppresses the
error but leaves the code unverified.

**Payoff:** Install `psutil` as a hard dependency (it is cross-platform and
well-maintained) rather than using the three-path fallback.  Adds ~1 MB to
the install.

### TD-L7 — `examples/ai_productivity_paper/` config files still use absolute paths

The `data.path` keys in the AI&P example config files use relative paths
that assume the working directory is the repository root.  If a user
`cd`s to `examples/ai_productivity_paper/` and runs `econflow validate`,
the data paths will resolve incorrectly.

**Payoff:** Resolve `data.path` relative to the config file's parent directory
in `pipeline_generic.py` (currently resolved relative to CWD).

### TD-L8 — `econflow init` starter test uses `subprocess` to run the pipeline

`tests/test_pipeline.py` (generated by `econflow init`) uses `subprocess.run`
to invoke `econflow.cli`.  A direct call to `run_from_config()` would be
faster and produce better error messages.

---

## Recommended payoff order

| Priority | Item | Effort | Value |
|----------|------|--------|-------|
| 1 | TD-H3: delete `cli_scaffold/` | 15 min | Removes confusion immediately |
| 2 | TD-M4: delete `core/provenance.py` | 5 min | One less dead file |
| 3 | TD-L4: unify estimator registry | 10 min | Eliminates sync bug risk |
| 4 | TD-M2: implement `load_config()` | 1 sprint | Enables typed config access |
| 5 | TD-L3: add unit test for `pipeline_generic` | 2h | Raises coverage on critical path |
| 6 | TD-L7: resolve data paths from config parent | 2h | Fixes confusing behaviour |
| 7 | TD-M1: wire `AbstractPipeline` | 30 min | Completes design intent |
| 8 | TD-H1: validate stub estimators with better message | 1h | Better UX |
| 9 | TD-M3/M5/M6: future layers | Sprints 5–7 | Implement when roadmap reaches them |
| 10 | TD-H2: data connectors | Sprints 5–7 | Only needed when non-CSV data sources are required |
