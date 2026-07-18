# EconFlow — Post-Phase-6 Consistency Report

**Date:** 2026-07-11
**Scope:** Repository-wide audit following the Phase 6 migration (replacing
`_run_diagnostics()` with `_write_diagnostics()`). All items identified in
`PRODUCT_AUDIT_POST_MIGRATION.md` that could be fixed without architectural
change have been resolved.
**Architecture Freeze:** Invariants I-1 through I-8 are untouched. The
dispatcher, estimation framework, and diagnostic pipeline are unchanged.

---

## Summary

| Issue | Severity | Status |
|-------|----------|--------|
| I-01 | Critical | ✔ Resolved |
| I-02 | Critical | ✔ Resolved |
| I-03 | Medium   | ✔ Resolved |
| I-04 | High     | ✔ Resolved |
| I-05 | High     | ✔ Resolved |
| I-06 | Medium   | ✔ Resolved |
| I-07 | Medium   | ✔ Resolved |
| I-08 | Medium   | ✔ Resolved |
| I-09 | Medium   | ✔ Resolved |
| I-10 | Medium   | ✔ Resolved (template already present; verified) |
| I-11 | Low      | ✔ Resolved |
| I-12 | Low      | ✔ Resolved |

All **Critical** and **High** release blockers are eliminated.

---

## Files Changed

### I-01 — Installation instructions assumed a non-existent PyPI package

`pip install econflow` was written in four user-facing files. Because EconFlow
is not published to PyPI, every first-time user following these instructions
would receive a `pip` error before running a single command.

**Files changed:**

| File | Change |
|------|--------|
| `examples/getting_started/README.md` | Step 1 rewritten: `pip install econflow` → `git clone … && pip install -e ".[dev]"` |
| `src/econflow/__init__.py` | Quick-start docstring updated to source install |
| `docs/release_notes/v0.1.0.md` | Installation section rewritten to source install |
| `src/econflow/commands/init.py` | Scaffold README template updated to source install |

---

### I-02 — Committed diagnostics.csv contained pre-Phase-6 values

The Phase 6 migration changed the OLS Breusch-Pagan path (old inline
computation → `EstimationResult.diagnostic_results`), shifting the OLS BP
statistic from 65.228 to 82.203. The VIF conclusion string also changed from
`"< 10"` to `"< 10.0"` (matching `_VIF_THRESHOLD = 10.0` in
`_diagnostics.py`). The committed artifact had not been regenerated.

**Files changed:**

| File | Change |
|------|--------|
| `examples/getting_started/outputs/tables/diagnostics.csv` | All nine rows regenerated with Phase 6 numerical pins |

**Phase 6 pin values (4 dp, matching `_write_diagnostics()` rounding):**

| Model | Diagnostic | Value |
|-------|------------|-------|
| pooled_ols | Breusch-Pagan | 82.2029 |
| pooled_ols | DW | 0.3815 |
| pooled_ols | VIF (max) | 1.3562 |
| entity_fe | Breusch-Pagan | 77.8714 |
| entity_fe | DW | 0.9718 |
| entity_fe | VIF (max) | 1.3562 |
| twoway_fe | Breusch-Pagan | 68.776 |
| twoway_fe | DW | 0.9161 |
| twoway_fe | VIF (max) | 1.3562 |

---

### I-03 — Stale "dead code" comment in `estimation/__init__.py`

Two places in `estimation/__init__.py` described `EstimationDispatcher` as
"Phase 2 (purely additive; no production code imports these yet)". Since Phase
5C, `EstimationDispatcher` is the **sole production path** for all
`econflow run` dispatch. The comments were false and would mislead any developer
reading the file.

**Files changed:**

| File | Change |
|------|--------|
| `src/econflow/estimation/__init__.py` | Module docstring "Pipeline integration (Phase 2)" section rewritten to "Phase 5C+" with accurate description |
| `src/econflow/estimation/__init__.py` | Inline comment before the dispatcher import updated from "Phase 2 (purely additive…)" to "Phase 5C+: EstimationDispatcher is the sole production path" |
| `src/econflow/estimation/__init__.py` | `__all__` entry comment updated from "Phase 2" to "Phase 5C+" |

---

### I-04 — Plugin SDK required `econflow>=1.0,<2.0` (phantom version)

EconFlow is at v0.1.0. The SDK instructed plugin developers to depend on
`econflow>=1.0,<2.0`, a version that does not exist and cannot be installed.
This affected seven locations in the SDK document.

**Files changed:**

| File | Change |
|------|--------|
| `docs/sdk/PLUGIN_SDK.md` §1 Quick Start | `econflow>=1.0,<2.0` → `econflow>=0.1.0` |
| `docs/sdk/PLUGIN_SDK.md` §9.1 `pip install` example | `econflow>=1.0,<2.0` → `econflow>=0.1.0` |
| `docs/sdk/PLUGIN_SDK.md` §9.2 `pyproject.toml` example | `econflow>=1.0,<2.0` → `econflow>=0.1.0` |
| `docs/sdk/PLUGIN_SDK.md` §9.6 CI workflow | `econflow>=1.0,<2.0` → `econflow>=0.1.0` |
| `docs/sdk/PLUGIN_SDK.md` §11.1 pinning guidance | Prose updated: "use `econflow>=0.1.0` until v1.0; tighten to `econflow>=1.0,<2.0` once semver applies" |
| `docs/sdk/PLUGIN_SDK.md` §13.7 compatibility verification | `econflow>=1.0,<2.0` → `econflow>=0.1.0` |
| `docs/sdk/PLUGIN_SDK.md` §14 release checklist | Checklist item updated to note v1.0 tightening |

---

### I-05 — Core estimation classes not re-exported from the root package

`from econflow import PooledOLS` failed. Economists reaching the package via
`import econflow` had no discoverable path to the estimator classes without
knowing to look in `econflow.estimation`. All core classes are pure-Python and
do not require `linearmodels` at import time, so the re-export is safe.

**Files changed:**

| File | Change |
|------|--------|
| `src/econflow/__init__.py` | Added `from econflow.estimation import BaseEstimator, DiagnosticResult, EntityFE, EstimationResult, PooledOLS, TwoWayFE, list_estimators, register_estimator` |
| `src/econflow/__init__.py` | Added the eight names to `__all__` |
| `src/econflow/__init__.py` | Docstring updated: "(v1.0)" label removed; "Core estimation API (v0.1.0+)" quick-import example added; "v1.x" stub references changed to "v0.2+" |

---

### I-06 — `econflow run` docstring showed fabricated per-model output

The `run` command docstring showed `[1/3] entity_fe — Fixed Effects (Entity) ✔`
per-model ticks. The actual pipeline emits `log.info()` messages in the
`[N/5]` stage format; there is no per-model tick line in the real output.

**Files changed:**

| File | Change |
|------|--------|
| `src/econflow/cli.py` | `run` command "Expected output" block replaced with actual `[1/5]`…`[5/5]` log stage format |

---

### I-07 — `FIRST_FIVE_MINUTES.md` showed fabricated "Stage N" output

Step 2 showed `Stage 1 Load data ✔`, `Stage 2 Validate ✔` etc. — a format
that does not exist in any version of the pipeline code.

**Files changed:**

| File | Change |
|------|--------|
| `docs/release/FIRST_FIVE_MINUTES.md` | Expected output block replaced with actual `[1/5]`…`[5/5]` abbreviated log output |

---

### I-08 — `econflow report` help text said "project directory" (ambiguous)

The `output_dir` argument help text said "Defaults to outputs/econflow/ inside
the project directory." The actual default is `Path.cwd() / "outputs" /
"econflow"`, which is relative to the current working directory (not a named
"project directory"). The text also did not clarify that the canonical
publication tables are in `outputs/tables/` from `econflow run`.

**Files changed:**

| File | Change |
|------|--------|
| `src/econflow/cli.py` | `output_dir` help text updated: "current working directory" + note that `outputs/tables/` is the canonical publication path |

---

### I-09 — Plugin SDK test fixture imported private `_unregister_estimator`

The §12.4 test fixture example used `_unregister_estimator` (underscore
prefix — internal convention). The public stable API is `unregister_estimator`
(no underscore), which is exported from `econflow.estimation.__all__`.

**Files changed:**

| File | Change |
|------|--------|
| `docs/sdk/PLUGIN_SDK.md` §12.4 | `from econflow.estimation import register_estimator, _unregister_estimator` → `unregister_estimator`; call site updated; stale "# underscore: internal" comment removed |

---

### I-10 — Init scaffold README (verification)

The `econflow init` scaffold already writes a complete `README.md` via the
`_README` template in `src/econflow/commands/init.py` (lines 240–298). The
template includes quick-start commands, project structure, configuration
guidance, and a "Reproduce results" section. No change was required; this item
was verified as already resolved.

---

### I-11 — `expected_outputs/` missing `diagnostics.csv` baseline

The `expected_outputs/README.md` listed only `table_fe_investment.csv` and
`.tex` as verifiable outputs. There was no reference baseline for the
diagnostics CSV, and no verification instruction for it.

**Files changed:**

| File | Change |
|------|--------|
| `examples/getting_started/expected_outputs/diagnostics.csv` | **New file.** Nine-row baseline with Phase 6 pin values, matching `outputs/tables/diagnostics.csv` exactly |
| `examples/getting_started/expected_outputs/README.md` | Added `diagnostics.csv` to the file table; added `diff` verification command; added diagnostics interpretation table with per-model expected statistics |

---

### I-12 — `econflow certify` silently accepted an empty `--project-name`

A certificate with an empty project name cannot identify the study. The command
accepted `""` with no feedback, making it easy to produce anonymous
certificates by accident.

**Files changed:**

| File | Change |
|------|--------|
| `src/econflow/cli.py` | Added warning block: if `project_name == ""`, print yellow ⚠ warning and usage tip before delegating to `run_certify()` |

---

## Regression Tests Added

**File:** `tests/unit/test_consistency_regression.py`

| Test | Guards against |
|------|---------------|
| `test_no_bare_pip_install_econflow[README.md]` | I-01 returning in the getting_started README |
| `test_no_bare_pip_install_econflow[FIRST_FIVE_MINUTES.md]` | I-01 returning in FIRST_FIVE_MINUTES.md |
| `test_no_bare_pip_install_econflow[v0.1.0.md]` | I-01 returning in the release notes |
| `test_no_bare_pip_install_econflow[__init__.py]` | I-01 returning in the package docstring |
| `test_no_bare_pip_install_econflow[init.py]` | I-01 returning in the scaffold README template |
| `test_committed_diagnostics_csv_matches_phase6_pins` | I-02: stale diagnostics.csv values re-appearing |
| `test_plugin_sdk_no_phantom_v1_constraint` | I-04: phantom `econflow>=1.0` constraint re-appearing in install context |
| `test_root_package_exports_estimation_classes` | I-05: estimation classes removed from the root package |
| `test_root_package_all_contains_estimation_classes` | I-05: estimation classes dropped from `__all__` |

---

## Release Blocker Status

| Blocker | Description | Status |
|---------|-------------|--------|
| I-01 | `pip install econflow` fails (not on PyPI) | ✔ Eliminated |
| I-02 | Committed example outputs mismatch Phase 6 numerics | ✔ Eliminated |
| I-04 | SDK instructs plugin devs to depend on phantom v1.0 | ✔ Eliminated |

**All three Critical/High release blockers are confirmed eliminated.**
The remaining items (I-03, I-05 through I-12) were Medium/Low severity
documentation and discoverability improvements that are now also resolved.

---

## Architecture Freeze Verification

No changes were made to:
- `src/econflow/estimation/dispatcher.py`
- `src/econflow/estimation/ols.py`
- `src/econflow/estimation/fixed_effects.py`
- `src/econflow/estimation/_diagnostics.py`
- `src/econflow/pipeline_generic.py` (the `_write_diagnostics` function)
- Any test that pins Phase 6 numerical values

The Architecture Freeze invariants I-1 through I-8 are intact.
`EstimationDispatcher` remains the sole production path for `econflow run`.
