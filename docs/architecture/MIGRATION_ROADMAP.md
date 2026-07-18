# Pipeline–Estimation Integration: Implementation Roadmap

**Design basis:** `PIPELINE_ESTIMATION_INTEGRATION.md` as revised by principal architect review  
**Architecture:** `EstimationDispatcher` in `econflow.estimation`, `PipelineContext` dataclass  
**Date:** 2026-07-10  
**Constraint:** Every phase leaves EconFlow in a fully working state. Every phase is independently deployable.

---

## Dependency Graph

```
Phase 0 (baseline) ─────────────────────────────────────────────────────────┐
     │                                                                        │
Phase 1 (estimator bug fixes) ──────────────────────────────────────────┐   │
     │                                                                    │   │
Phase 2 (EstimationDispatcher — additive) ──────────────────────────┐   │   │
     │                                                                │   │   │
Phase 3 (estimator diagnostics) ─────────────────────────────────┐   │   │   │
     │                                                             │   │   │   │
Phase 4 (ConfigValidator → dispatcher) ────────────────────────┐  │   │   │   │
     │                                                           │  │   │   │   │
Phase 5 ← DEPENDS ON 0, 1, 2, 4 (wire _run_model)              │  │   │   │   │
     │                                                           │  │   │   │   │
Phase 6 ← DEPENDS ON 3, 5 (replace _run_diagnostics)           │  │   │   │   │
     │                                                           │  │   │   │   │
Phase 7 (cleanup and documentation)                             │  │   │   │   │
                                                                └──┘   └───┘   │
                                                                   all feed 7  └─ feeds all
```

Phases 1, 2, and 3 do not depend on each other and can be developed in parallel. Phases 4 and 5 both require Phase 2. Phase 5 is the only high-risk phase and must not proceed without Phases 0 and 4 complete.

---

## Phase 0 — Numerical Baseline

### Objective

Capture exact numerical output of the current pipeline before any code change. These fixtures become the regression guard for every subsequent phase. No test can prove a migration is safe without a known-good reference to compare against.

### Files Affected

```
tests/integration/fixtures/baseline/
    getting_started_comparison_table.csv   ← new
    getting_started_diagnostics.csv        ← new
    getting_started_rsquared_within.txt    ← new  (one float per model, 10 decimal places)
    getting_started_std_errors.csv         ← new  (all SE values, 10 decimal places)
    getting_started_run_metadata.json      ← new

tests/integration/test_pipeline_baseline.py   ← new
```

No source files change.

### Public API Impact

None.

### Migration Risk

None. This phase is additive test infrastructure only.

### Tests Required

`test_pipeline_baseline.py` must:

1. Run `run_from_config()` on the getting-started config with a deterministic seed.
2. Load the captured fixture files and assert that `run_from_config()` produces output within 1e-10 of every coefficient, every standard error, every p-value, every R², and every diagnostic statistic.
3. Include at least one model with no `cluster` field in its spec so that the `cov_type="robust"` default is captured explicitly. If the getting-started fixtures do not cover this case, create a second fixture set that does.
4. Assert the column names of the comparison table CSV exactly.
5. Assert the column names and row count of `diagnostics.csv` exactly.

These tests must pass on the current codebase before Phase 1 begins. Failing tests here mean the baseline is not yet established.

### Rollback Strategy

Not applicable. No source changes. If the fixture tests cannot be made to pass, the baseline values are wrong and must be corrected before proceeding.

### Completion Criteria

- `tests/integration/fixtures/baseline/` contains all five files with real values, not placeholders.
- `test_pipeline_baseline.py` passes with zero failures.
- The test is added to the CI pipeline and marked as the migration gate.
- The tests are committed to the main branch under a commit message that explicitly records the pre-migration state.

---

## Phase 1 — Fix Pre-existing Estimator Bugs

### Objective

Correct two bugs in the concrete estimator classes that would surface as silent errors after Phase 5 wires the pipeline through the framework. Fix them before migration so that the Phase 5 regression tests have valid references.

**Bug 1:** `EntityFE.fit()` and `TwoWayFE.fit()` set `rsquared_adj = float(res.rsquared)` — the same value as `rsquared`. Adjusted R-squared is a different statistic from R-squared. Setting them equal will produce incorrect output for any consumer of `EstimationResult.rsquared_adj`. The comparison table does not currently display `rsquared_adj`, so this is a latent error, but it should be fixed before the framework is in the primary path.

**Bug 2:** `TwoWayFE.fit()` — verify it makes the same assignment. Apply the same fix.

**Bug 3:** Verify `PooledOLS.fit()` (the framework class in `estimation/ols.py`) correctly populates `rsquared_adj` as the standard OLS adjusted R-squared formula: `1 - (1 - R²) * (n-1) / (n-k-1)`.

### Files Affected

```
src/econflow/estimation/fixed_effects.py   ← fix EntityFE.fit(), TwoWayFE.fit()
src/econflow/estimation/ols.py             ← verify PooledOLS.fit()
tests/unit/test_estimation_fixed_effects.py ← add rsquared_adj assertions
tests/unit/test_estimation_ols.py          ← add rsquared_adj assertions
```

### Public API Impact

`EstimationResult.rsquared_adj` gains a correct value where it previously held a duplicate of `rsquared`. This is a **bug fix**, not an API change. No public method signatures change. The change is backwards-compatible because `rsquared_adj` was previously wrong; correct values cannot break existing correct usage.

### Migration Risk

**Low.** The `estimation/` package is currently dead code at runtime (the pipeline does not call it). Fixing these methods in isolation has zero user-visible effect until Phase 5. The only risk is introducing a new bug while fixing the existing one, which the new tests will catch.

### Tests Required

1. Assert that for an entity-FE model, `result.rsquared_adj < result.rsquared` (adjusted is always smaller or equal, never larger, for models with more than one parameter).
2. Assert that `result.rsquared_adj` is not equal to `result.rsquared` for any FE model with more than one regressor (the case where they would be equal is degenerate).
3. Assert the formula: `rsquared_adj ≈ 1 - (1 - rsquared) * (n_total - 1) / (n_total - k - 1)` where `k` is the number of free parameters. For within estimators the denominator should use degrees of freedom from the linearmodels result object.
4. All pre-existing tests continue to pass.

### Rollback Strategy

Revert `fixed_effects.py` and `ols.py` to their pre-Phase-1 state. Two-line git revert. No impact on any other component.

### Completion Criteria

- `result.rsquared_adj != result.rsquared` for all implemented FE estimators on the test fixture.
- All existing tests in `tests/unit/test_estimation_*.py` pass.
- New assertions added to the relevant test files.

---

## Phase 2 — Create `EstimationDispatcher` and `PipelineContext`

### Objective

Create the new module `econflow/estimation/dispatcher.py` containing the `EstimationDispatcher` class and `PipelineContext` dataclass. This module is purely additive — nothing imports it yet. Its purpose in this phase is to be fully implemented, reviewed, and tested in isolation before any production code depends on it.

This phase implements:

**`PipelineContext`** — a dataclass carrying project-level configuration that estimators need but that does not appear in the model spec. For the current migration scope: `entity_col: str` and `time_col: str`. Declared as `@dataclass(frozen=True)`.

**`EstimationDispatcher.resolve_id(spec: dict) -> str`** — the single authoritative location for all YAML-string-to-registry-key translation. Implements:
- Case normalization: `"OLS"` → `"ols"`, `"FE"` → `"fe"`, etc.
- The FE→TWFE adapter: `"FE"` with `entity_effects: true, time_effects: true` → `"twfe"`
- The FE with no effects adapter: `"FE"` with `entity_effects: false, time_effects: false` → `"ols"` (with a logged deprecation warning)
- Pass-through for all other strings (custom plugin keys)
- Called by both the pipeline and `ConfigValidator`

**`EstimationDispatcher.build(spec: dict, context: PipelineContext) -> BaseEstimator`** — constructs the augmented params dict and returns an instantiated but unrun estimator. Handles:
- Merging `context.entity_col` and `context.time_col` into the params dict
- Translating the YAML `cluster` field into the estimator's `cov_type`/`cluster_entity`/`cluster_time` params, preserving the current pipeline defaults exactly:
  - `cluster: "entity"` → `cov_type: "clustered"`, `cluster_entity: True`
  - `cluster: "time"` → `cov_type: "clustered"`, `cluster_time: True`
  - absent `cluster` key → `cov_type: "robust"` (matches current pipeline default)

**`EstimationDispatcher.dispatch(spec: dict, df: pd.DataFrame, context: PipelineContext) -> EstimationResult`** — calls `build()` then `estimator.run(df)`. The full execution in two lines.

Export `PipelineContext` and `EstimationDispatcher` from `estimation/__init__.py`.

### Files Affected

```
src/econflow/estimation/dispatcher.py        ← new
src/econflow/estimation/__init__.py          ← add PipelineContext, EstimationDispatcher exports

tests/unit/test_estimation_dispatcher.py     ← new (comprehensive)
```

No changes to `pipeline_generic.py`, `config/validator.py`, or any CLI file.

### Public API Impact

**Additive.** `PipelineContext` and `EstimationDispatcher` become new public exports from `econflow.estimation`. No existing exports change. No existing callers are affected.

### Migration Risk

**None.** No production code imports the new module. The dispatcher sits in the estimation package but is unused until Phase 4 and Phase 5.

### Tests Required

`test_estimation_dispatcher.py` must cover:

**`resolve_id()` — 12 minimum test cases:**
1. `"OLS"` → `"ols"`
2. `"ols"` → `"ols"` (already lowercase, must not fail)
3. `"FE"` with `entity_effects: true, time_effects: false` → `"fe"`
4. `"FE"` with `entity_effects: true, time_effects: true` → `"twfe"`
5. `"FE"` with `entity_effects: false, time_effects: false` → `"ols"` (with deprecation warning)
6. `"TWFE"` → `"twfe"` (explicit key, no adapter needed)
7. `"RE"` → `"re"` (pass-through)
8. `"my_custom_estimator"` → `"my_custom_estimator"` (unknown key, pass-through)
9. Mixed case: `"Fe"` → `"fe"`
10. `"FE"` with no effect fields → treated as FE (default entity_effects=False → adapter emits warning and returns "ols")
11. `"IV"` → `"iv"`
12. `"QUANTILE"` → `"quantile"`

**`build()` — cov_type mapping:**
1. Spec with `cluster: "entity"` → instantiated estimator has `params["cov_type"] == "clustered"` and `params["cluster_entity"] == True`
2. Spec with `cluster: "time"` → `params["cov_type"] == "clustered"`, `params["cluster_time"] == True`
3. Spec with no `cluster` key → `params["cov_type"] == "robust"`
4. Context injection: `context.entity_col` appears in `params["entity_col"]`
5. Original spec dict is not mutated (assert `spec["entity_col"]` raises `KeyError` after `build()`)

**`dispatch()` integration test:**
1. Run against the getting-started Grunfeld data with the `entity_fe` spec. Assert that the returned `EstimationResult` has the same `params`, `std_err`, and `pvalues` as the baseline fixture (Phase 0) within 1e-10.
2. Run with an unregistered estimator key. Assert `RegistryError` is raised (not a generic `KeyError`).
3. Run with `estimator: "gmm"`. Assert `NotImplementedError` propagates (will be wrapped in Phase 5; here we test the raw dispatcher).

### Rollback Strategy

Delete `dispatcher.py`. Remove the two new exports from `estimation/__init__.py`. Four-line change. Zero impact on any production code path.

### Completion Criteria

- All 15+ tests in `test_estimation_dispatcher.py` pass.
- `dispatch()` integration test produces output numerically consistent with Phase 0 baseline.
- `PipelineContext` and `EstimationDispatcher` are importable from `econflow.estimation`.
- `ruff check src/econflow/estimation/dispatcher.py` passes.

---

## Phase 3 — Implement Estimator-Level Diagnostics

### Objective

Implement the `diagnostics()` method on `EntityFE` and `TwoWayFE`. The current implementation returns `[]`. This phase makes it return the three tests that `pipeline_generic._run_diagnostics()` currently computes inline: VIF (variance inflation factor), Breusch-Pagan heteroskedasticity test, and Durbin-Watson serial correlation proxy.

This is the prerequisite for Phase 6, which deletes the inline `_run_diagnostics()` function. Phase 6 cannot be merged before Phase 3 is complete and the diagnostic output has been verified to match.

Also verify `PooledOLS.diagnostics()` in `estimation/ols.py`. If it also returns `[]`, implement the same three tests.

The implementation of `diagnostics()` has access to the `EstimationResult` object, which contains `extra` for any data the estimator needs to pass through. If residuals are needed and are not already in `result.extra`, this is where they must be added — either as a new field on `EstimationResult` or as a key in `result.extra`. The decision must be made in this phase before Phase 6 attempts to consume them.

### Files Affected

```
src/econflow/estimation/fixed_effects.py   ← implement EntityFE.diagnostics(), TwoWayFE.diagnostics()
src/econflow/estimation/ols.py             ← implement PooledOLS.diagnostics()
src/econflow/estimation/result.py          ← possibly add residuals to EstimationResult or extra spec
tests/unit/test_estimation_diagnostics.py  ← new
tests/integration/fixtures/baseline/       ← cross-check: diagnostics from framework must match
```

### Public API Impact

`BaseEstimator.diagnostics()` gains non-empty implementations. `EstimationResult` may gain a documented key in `extra` for residuals. No method signatures change. Additive.

### Migration Risk

**Medium.** Changes to the concrete estimators could affect `estimator.run()` output (specifically `result.diagnostic_results`). This does not affect the pipeline yet (which still uses `_run_diagnostics()`), so risk is contained to the estimation package in isolation.

The specific risk: if `diagnostics()` raises an uncaught exception, `BaseEstimator.run()` propagates it. Since `run()` is not yet called by the pipeline, this surfaces only in the estimation unit tests.

### Tests Required

1. After `EntityFE(params=spec).run(df)`, assert `len(result.diagnostic_results) >= 3`.
2. Assert that one `DiagnosticResult` has `diagnostic_id == "vif"` or similar.
3. Assert that one `DiagnosticResult` has `diagnostic_id == "breuschpagan"` or similar.
4. Assert that one `DiagnosticResult` has `diagnostic_id == "durbin_watson"` or similar.
5. **Cross-check against Phase 0 baseline:** for the `entity_fe` Grunfeld spec, run `EntityFE.run()` and compare the VIF statistic, BP statistic, and DW statistic against the values in `getting_started_diagnostics.csv`. Assert within 1e-6.
6. Assert that `diagnostics()` does not raise when the data has fewer observations than regressors (degenerate case — should return empty list or partial results, not crash).
7. All Phase 0 baseline tests continue to pass (pipeline still uses `_run_diagnostics()` at this point).

### Rollback Strategy

Revert `fixed_effects.py` and `ols.py` `diagnostics()` methods to `return []`. The pipeline is unaffected because `_run_diagnostics()` is still the active diagnostic path. Zero user-visible impact.

### Completion Criteria

- `EntityFE.diagnostics()` and `TwoWayFE.diagnostics()` return at least three `DiagnosticResult` objects per model.
- The VIF, BP, and DW values from `estimator.diagnostics()` match the Phase 0 baseline to within 1e-6.
- Phase 0 baseline tests still pass (pipeline unchanged).

---

## Phase 4 — Wire ConfigValidator to EstimationDispatcher

### Objective

Replace the `KNOWN_ESTIMATORS` frozenset check in `ConfigValidator` with a call to `EstimationDispatcher.resolve_id()` followed by `get_estimator()`. This change makes the validator plugin-aware: any estimator registered in the registry (including external plugins loaded via entry points) will pass validation.

Without this phase, the plugin architecture remains blocked: a user who installs a plugin and adds `estimator: my_custom_estimator` to their YAML will pass Phase 5's pipeline dispatch but fail pre-flight validation. Plugin extensibility requires both this phase and Phase 5. They should be merged in the same sprint, with this phase first.

The change is: in `ConfigValidator._validate_models_estimators()` (or wherever estimator keys are checked), replace:
```
if estimator_key not in KNOWN_ESTIMATORS: record error
```
with:
```
resolved_id = dispatcher.resolve_id(spec)
try: get_estimator(resolved_id)
except RegistryError: record error with list of available estimators
```

The error message should list the currently registered estimators, not a hardcoded list.

`KNOWN_ESTIMATORS` in `config/models.py` may be retained as a legacy export if it is part of the public API (it is used in type annotations). If it is internal, it can be deleted. If retained, add a deprecation note.

### Files Affected

```
src/econflow/config/validator.py           ← replace frozenset check with dispatcher call
src/econflow/config/models.py              ← KNOWN_ESTIMATORS: deprecate or remove if internal
tests/unit/test_config_validation.py       ← add plugin estimator test cases
tests/integration/test_validator_registry.py ← new: validator accepts registry estimators
```

`estimation/dispatcher.py` is imported for the first time by production code in this phase.

### Public API Impact

**Behavior change visible to plugin authors:** A custom estimator registered via `@register_estimator("my_key")` now passes `econflow validate`. Previously it would fail. This is the intended behavior — it is a bug fix, not a breaking change.

**Behavior change for invalid estimators:** The error message now lists all currently-registered estimators (from the live registry) instead of the hardcoded frozenset. Message wording changes; the error code and exit behavior do not.

`KNOWN_ESTIMATORS` status: if currently exported from a public `__all__`, mark deprecated. If private, remove.

### Migration Risk

**Medium.** The validator now loads the estimation framework (via `dispatcher.py` importing `get_estimator`). This triggers `_load_entry_point_plugins()` at import time of the registry module, which loads all installed plugins. A badly-written plugin that crashes on load would have previously been invisible to `econflow validate`. After this phase, a crashing plugin will be caught at import time and emit a `RuntimeWarning`. The warning is already handled by the try/except in `_load_entry_point_plugins()` — it does not crash the validator.

The more concrete risk: a test that mocks the registry or patches `KNOWN_ESTIMATORS` will break and must be updated.

### Tests Required

1. `econflow validate` with `estimator: ols` still passes (regression).
2. `econflow validate` with `estimator: fe` still passes (regression).
3. `econflow validate` with `estimator: unknown_xyz` fails validation with code that lists available estimators.
4. Register a mock estimator in the test via `@register_estimator("test_custom")`, then run the validator with `estimator: test_custom` — assert it passes.
5. Unregister `test_custom` after the test (use `unregister_estimator` in teardown).
6. All existing `test_config_validation.py` tests pass.
7. The error message for an unknown estimator is non-empty and contains at least one known estimator name.

### Rollback Strategy

Revert `config/validator.py` to the frozenset check. `config/models.py` is unchanged or trivially reverted. The `estimation/dispatcher.py` module remains in place (it was additive in Phase 2) but is now unused again. Zero impact on the pipeline.

### Completion Criteria

- `econflow validate` with a custom-registered estimator key passes without modification to the frozenset.
- `econflow validate` with an unknown key emits a helpful error listing registered estimators.
- All existing validation tests pass.
- New plugin-awareness tests pass.

---

## Phase 5 — Wire `_run_model()` Through `EstimationDispatcher` ✓ COMPLETE

**Completed:** 2026-07-10 (Phase 5A: dual-path with `_USE_DISPATCHER` flag; Phase 5B: numerical
equivalence verification; Phase 5C: legacy path removed, dispatcher is sole production path.)

**Deviation from roadmap:** The roadmap assumed a single-step migration. Actual implementation
used three sub-phases (5A, 5B, 5C) to de-risk the change. The end state is identical to what
this phase specified.

### Objective

This is the core migration step. Replace `pipeline_generic._run_model()` with a call through `EstimationDispatcher.dispatch()`. The function goes from 89 lines of inline linearmodels code to approximately 10 lines of delegation.

**Specifically:**
- Remove `from linearmodels.panel import PanelOLS, PooledOLS` from the module-level imports.
- Remove `import statsmodels.api as sm` from the module-level imports (it was used only in `_run_model()` for `sm.add_constant()`).
- Add `from econflow.estimation.dispatcher import EstimationDispatcher, PipelineContext`.
- Instantiate one `EstimationDispatcher` at the top of `run_from_config()`, reused for all models.
- Construct `PipelineContext(entity_col=entity_col, time_col=time_col)` once, reused for all models.
- Replace each `results[mid] = _run_model(panel_df, spec)` call with `results[mid] = dispatcher.dispatch(spec, df, context)`.
- Update `_build_comparison_table()` for the three field-name changes: `std_errors` → `std_err`, `rsquared_within` → `rsquared`, OLS detection from spec string → `result.estimator_id == "ols"`.
- Wrap `RegistryError` from the dispatcher as `ModelSpecificationError`. Wrap `NotImplementedError` (stub estimators) as `ModelSpecificationError` with the message *"Estimator '{id}' is a stub and is not yet implemented. Remove it from models.yaml."*
- Retain `_run_diagnostics()` intact and unchanged. It is still called and still writes `diagnostics.csv`. It will be removed in Phase 6.

**What does NOT change in this phase:**
- `_run_diagnostics()` — still present, still called.
- `_build_comparison_table()` structure — only field name reads change.
- `_write_csv()`, `_write_latex()`, `_write_markdown()`, `_write_html()`, `_write_json()` — unchanged.
- `_record_provenance()` — unchanged.
- The function signature of `run_from_config()` — unchanged.
- All CLI commands — unchanged.
- All YAML formats — unchanged.

### Files Affected

```
src/econflow/pipeline_generic.py           ← primary change
    - remove linearmodels import
    - remove statsmodels.api import
    - add dispatcher imports
    - replace _run_model() body (~89 lines → ~10 lines)
    - update _build_comparison_table() (3 field-name reads)
    - update run_from_config() call site (pass df + context)

tests/integration/test_pipeline_baseline.py ← must pass after this change
tests/unit/test_pipeline_generic.py        ← new or extended: mock get_estimator call
```

### Public API Impact

None. `run_from_config()` signature is unchanged. CLI unchanged. YAML format unchanged. Output file format unchanged.

The internal `results` dict changes type from `dict[str, linearmodels_PanelResults]` to `dict[str, EstimationResult]`. This is a private implementation detail. Any test that directly inspects the `results` dict using linearmodels attribute names will break. Audit and update those tests before merging.

### Migration Risk

**High.** This is the only phase that changes the numerical execution path. Two specific risks were identified in the architectural review:

**Risk A — Covariance type mismatch (highest probability):** The dispatcher handles the `cluster` → `cov_type` mapping in `build()`. Verify before merging that the dispatcher's `cov_type` mapping exactly matches the old pipeline's dispatch table (which was verified in the Phase 2 tests). If Phase 0 baseline tests fail after Phase 5, the cov_type mapping is the first place to look.

**Risk B — R² field (verified lower risk):** `EntityFE.fit()` uses `res.rsquared`, which for linearmodels PanelOLS is the within-R². The old pipeline used `res.rsquared_within`. For the current linearmodels version these are the same value. Verify by running Phase 0 baseline against the R² fixture.

**Detection:** The Phase 0 baseline tests are the primary guard. They must pass before this phase is marked complete. If any numerical value deviates by more than 1e-10, the phase fails and must be debugged before merging.

**Scope of failure if this phase regresses:** Only `econflow run` is affected. All other commands (validate, certify, verify, package, reproduce, compare, doctor, info, fetch, datasets, cache) are unaffected. The blast radius is a single command.

### Tests Required

1. **Phase 0 baseline tests must pass, unchanged.** This is the primary gate. Every coefficient, SE, p-value, R², and diagnostic statistic must match within 1e-10. A single deviation in any value fails the phase.
2. `mock.patch('econflow.estimation.registry.get_estimator')` in a unit test: call `run_from_config()` and assert that `get_estimator` was called exactly `N` times where `N` is the number of model specs.
3. Assert that `pipeline_generic.py` no longer imports `PanelOLS` or `PooledOLS` directly: `grep "from linearmodels" src/econflow/pipeline_generic.py` returns no results.
4. Run `econflow run` end-to-end with `estimator: gmm` — assert exit code 1, error message contains "stub", no traceback visible to user.
5. Run `econflow run` end-to-end with `estimator: unknown_xyz` — assert exit code 1, error message lists known estimators.
6. Run the full getting-started example end-to-end and assert that the output files are created, non-empty, and contain the expected column headers.
7. All Acceptance Criteria B through J from `PIPELINE_ESTIMATION_INTEGRATION.md`.

### Rollback Strategy

This phase touches one function (`_run_model()`) and three field-name reads in `_build_comparison_table()`. A targeted revert of `pipeline_generic.py` to its pre-Phase-5 state fully restores the old behavior. Phases 0–4 remain in place.

The revert is a single `git revert` or manual restoration. The dispatcher, `PipelineContext`, estimator diagnostics, and the validator fix from Phases 2–4 remain active and correct. The pipeline returns to inline linearmodels temporarily while the regression is debugged.

### Completion Criteria

- Phase 0 baseline tests pass with zero numerical deviations.
- `grep "from linearmodels" src/econflow/pipeline_generic.py` returns no matches.
- `grep "from econflow.estimation.dispatcher" src/econflow/pipeline_generic.py` returns exactly one match.
- `get_estimator` mock test confirms registry is called once per model spec.
- `econflow run` on all three example projects (getting_started, blind_replication, ai_productivity_paper) completes without error.
- All CI checks pass.

---

## Phase 6 — Replace `_run_diagnostics()` with EstimationResult ✓ COMPLETE

**Completed:** 2026-07-10 (previously marked deferred; executed after Phase 5 formal freeze).

**Summary:** `pipeline_generic._run_diagnostics()` (173 lines of inline VIF/BP/DW computation)
was deleted and replaced with `_write_diagnostics()` (~60 lines), a thin CSV writer that reads
`EstimationResult.diagnostic_results`.  The `diagnostics.csv` schema is unchanged.  See
`docs/architecture/PHASE6_COMPLETION_REPORT.md` for the full audit.

**Known behavioral change:** OLS BP and DW values in `diagnostics.csv` change (see
PHASE6_COMPLETION_REPORT.md §4).  FE and TWFE values are numerically identical.

### Objective

Delete `pipeline_generic._run_diagnostics()`. Replace it with a new private function `_write_diagnostics()` that reads `DiagnosticResult` objects from `EstimationResult.diagnostic_results` and writes them to the same `diagnostics.csv` file with the same column schema.

**This phase is blocked on Phase 3.** Do not proceed until Phase 3's cross-check confirms that `EntityFE.diagnostics()` and `TwoWayFE.diagnostics()` produce VIF, BP, and DW values that match the Phase 0 baseline within 1e-6.

The CSV output format — column names, column order, row structure — must be identical to the format produced by the deleted function. Downstream code that reads `diagnostics.csv` (replication engine, integrity certificates) must not require any changes.

Also update `run_from_config()` to remove the `_run_diagnostics()` call and replace it with `_write_diagnostics(results, out_cfg, outputs_path)`.

Remove the remaining `import statsmodels.api` if it has no remaining callers in this file after `_run_diagnostics()` is deleted. Remove the inline `from statsmodels.stats.outliers_influence import variance_inflation_factor` and `from statsmodels.stats.diagnostic import het_breuschpagan` which were inside `_run_diagnostics()`.

### Files Affected

```
src/econflow/pipeline_generic.py
    - delete _run_diagnostics() (~156 lines)
    - add _write_diagnostics() (~30 lines)
    - update run_from_config() call site
    - remove residual statsmodels imports if any remain
```

No other files change.

### Public API Impact

None. `diagnostics.csv` is produced at the same path with the same columns. The values change only if Phase 3's implementation differs from the old inline implementation, which the Phase 3 cross-check must have verified. Users do not observe the internal mechanism that produces the file.

### Migration Risk

**Medium.** The risk is that `diagnostics.csv` changes value for some model types. Specifically:
- Models with fewer regressors than the VIF threshold (VIF requires ≥2 regressors) may produce different diagnostic sets.
- The Durbin-Watson calculation may differ if `result.extra` provides residuals in a different shape than `result.resids` from linearmodels.

Both of these were validated in Phase 3. If Phase 3's cross-check passed, Phase 6 is low risk. If Phase 3's cross-check could not be made to pass, Phase 6 must not proceed.

An additional risk: if any test directly mocks or inspects `_run_diagnostics()` by name, it will fail. Audit test files before merging.

### Tests Required

1. Phase 0 baseline diagnostic test: assert that `diagnostics.csv` after Phase 6 is byte-identical to the Phase 0 fixture (within floating-point tolerance on numeric fields).
2. Assert `_run_diagnostics` is no longer defined in `pipeline_generic.py`: `grep "_run_diagnostics" src/econflow/pipeline_generic.py` returns no matches.
3. Run the full getting-started pipeline and assert `diagnostics.csv` is produced, has the expected column names, has at least 3 rows per model (VIF, BP, DW), and has correct `model_id` values.
4. All Phase 0 baseline tests pass.
5. Full test suite passes.

### Rollback Strategy

Restore `_run_diagnostics()` from git history. Replace the `_write_diagnostics()` call with the old `_run_diagnostics()` call. The diagnostics return to the inline implementation. Phase 3's estimator-level diagnostics remain in place (not rolled back) because they are correct and do not affect the pipeline independently.

### Completion Criteria

- `diagnostics.csv` output is byte-compatible with the Phase 0 fixture.
- `pipeline_generic.py` contains no reference to `linearmodels`, `PanelOLS`, `PooledOLS`, `variance_inflation_factor`, or `het_breuschpagan`.
- All CI checks pass.

---

## Phase 7 — Clean Up, Document, and Harden ◷ IN PROGRESS

**Started:** 2026-07-10. Phase 5C delivers items 7a (architecture docs), 7e (CHANGELOG), and
7f (release-check); items 7b–7d are pending.

### Objective

Close the remaining loose ends identified during the migration. No behavior changes.

**7a — Update ARCHITECTURE.md.** Replace the stale module descriptions with the actual structure including `EstimationDispatcher`, `PipelineContext`, and the new call graph. This is the document that was identified as Critical defect C-3 in the architectural assessment.

**7b — Fix coverage configuration.** Remove the production subpackages from the `omit` list in `pyproject.toml`. The packages previously excluded (`src/econflow/estimation/*`, `src/econflow/diagnostics/*`, etc.) are now in the active execution path and must be measured. Expect measured coverage to drop initially; this is correct behavior revealing the true state.

**7c — Deprecate `KNOWN_ESTIMATORS`.** If `KNOWN_ESTIMATORS` was retained as an exported symbol in Phase 4, add a `DeprecationWarning` to its usage in any public-facing code and document that it will be removed in v0.3.0. The authoritative source is now the live registry.

**7d — Enhance provenance recording.** Update `_record_provenance()` to include `estimator_id`, `estimator_name`, and `backend` from each `EstimationResult`. This is an additive change to the provenance JSON and does not break `econflow verify` (which checks hashes of data and config files, not the provenance JSON structure).

**7e — Update CHANGELOG.md** with all phases of this migration under a single entry.

**7f — Update the release quality gate.** The `econflow release-check` command has a check for the estimation registry. Verify that after this migration it correctly reports all 8 estimators as registered and the dispatcher as the active dispatch path.

### Files Affected

```
ARCHITECTURE.md
CHANGELOG.md
pyproject.toml                              ← coverage omit list
src/econflow/config/models.py               ← KNOWN_ESTIMATORS deprecation warning
src/econflow/pipeline_generic.py            ← _record_provenance() enhancement
src/econflow/commands/release_check.py      ← verify estimator count check still valid
docs/architecture/PIPELINE_ESTIMATION_INTEGRATION.md  ← mark as "implemented"
```

### Public API Impact

The `KNOWN_ESTIMATORS` deprecation warning is the only behavior change. It is a warning, not an error. All other changes are documentation or configuration.

### Migration Risk

**Low.** No execution path changes. ARCHITECTURE.md and CHANGELOG.md are documentation. The coverage configuration change reveals previously hidden information but does not change behavior. The provenance JSON gains new fields; `econflow verify` does not validate JSON structure.

### Tests Required

1. `pyproject.toml` omit list does not contain `src/econflow/estimation/*` or `src/econflow/diagnostics/*`.
2. `pytest --co` (collect-only) confirms that estimation and diagnostics tests are included in the coverage run.
3. The provenance JSON written by a `run_from_config()` call contains `estimator_id` and `backend` for each model.
4. `econflow release-check` exits 0.
5. No existing tests broken by the provenance field additions.

### Rollback Strategy

Each sub-task in Phase 7 is independent and can be reverted individually. None affect the execution path. Rollback is a file revert with no downstream impact.

### Completion Criteria

- `ARCHITECTURE.md` accurately describes the `EstimationDispatcher` as the dispatch layer.
- `pyproject.toml` coverage `omit` list contains no production subpackage paths.
- `KNOWN_ESTIMATORS` emits `DeprecationWarning` if still used.
- Provenance JSON includes `estimator_id` and `backend` per model.
- Full test suite passes. CI green.

---

## Summary Table

| Phase | Name | Risk | PR Size | Blocks | Key Gate |
|---|---|---|---|---|---|
| 0 | Numerical baseline | None | Small | All | Phase 0 tests pass on unmodified codebase |
| 1 | Estimator bug fixes | Low | Small | Phase 5 (indirect) | `rsquared_adj != rsquared` for FE models |
| 2 | Create EstimationDispatcher | None | Medium | 4, 5 | `dispatch()` matches Phase 0 baseline |
| 3 | Estimator diagnostics | Medium | Medium | 6 | Diagnostic values match Phase 0 baseline ±1e-6 |
| 4 | Validator → dispatcher | Medium | Small | 5 | Plugin key passes `econflow validate` |
| 5 | Wire `_run_model()` | **High** | Medium | 6 | Phase 0 baseline tests pass, no linearmodels import |
| 6 ✓ | Replace `_run_diagnostics()` | Medium | Small | 7 | `diagnostics.csv` byte-compatible with Phase 0 |
| 7 | Cleanup and documentation | Low | Small | — | CI green, coverage measures production code |

**Total estimated scope:** 8 pull requests. Each independently reviewable. Each independently deployable. The only phase that requires careful gate management is Phase 5, which must have Phase 0 baseline tests running in CI before it can be safely merged.

---

## What Remains Out of Scope After This Roadmap

The following issues from the architectural assessment are **not** addressed by this roadmap and require separate work:

- `SystemGMM` and `PanelQuantile` implementation (stub estimators remain stubs; Phase 5 gives them a clear error message instead of a silent wrong result)
- `__author__ = "Ab"` truncation in `__init__.py`
- `AIProdError` in `__all__`
- `requests` missing from `pyproject.toml` dependencies
- Legacy `--data-path` pipeline in `econflow.pipeline` — it still uses inline linearmodels after this roadmap; it should be deprecated and removed in a subsequent sprint
- `py.typed` marker missing
- `uv.lock` commit/gitignore inconsistency
