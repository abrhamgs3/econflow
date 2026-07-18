# Pipeline–Estimation Integration Design

**Status:** Design only — no implementation  
**Date:** 2026-07-10  
**Scope:** `src/econflow/pipeline_generic.py` — wiring `run_from_config()` through the estimation framework  
**Constraint:** Smallest possible architectural change. No CLI changes. No YAML changes. No output format changes.

---

## Background

`pipeline_generic.py` is the only module invoked by `econflow run`. It directly instantiates `linearmodels.panel.PooledOLS` and `linearmodels.panel.PanelOLS`. It also contains its own implementations of VIF, Breusch-Pagan, and Durbin-Watson. None of the `econflow.estimation.*` or `econflow.diagnostics.*` modules are imported or called during a normal pipeline run.

The goal of this migration is to make `run_from_config()` dispatch through `econflow.estimation.registry.get_estimator()` and `BaseEstimator.run()`, so that the plugin architecture, all 8 registered estimators, and the diagnostic framework are all live during execution — while preserving every existing user-facing contract.

---

## 1. New Runtime Call Graph

```
econflow run --config ... --models ... --outputs ...
  └─ cli.py::run()                              [unchanged]
       ├─ ConfigValidator.validate_strict()      [unchanged — pre-flight only]
       └─ pipeline_generic.run_from_config()
            ├─ _load_yaml × 3                   [unchanged]
            ├─ pd.read_csv()                    [unchanged]
            ├─ _validate_panel_columns()        [unchanged role; new name optional]
            │
            ├─ for each model spec:
            │    └─ _run_model(df, spec, entity_col, time_col)    ← CHANGED
            │         ├─ _resolve_estimator_id(spec)              ← NEW helper
            │         │    (normalises "FE"/"OLS" → "fe"/"ols",
            │         │     applies FE→TWFE adapter if needed)
            │         ├─ _augment_spec(spec, entity_col, time_col)← NEW helper
            │         ├─ get_estimator(estimator_id)              ← FROM REGISTRY
            │         ├─ EstimatorClass(params=augmented_spec)    ← FRAMEWORK
            │         └─ estimator.run(df)                        ← FRAMEWORK
            │              ├─ estimator.validate(df)
            │              ├─ result = estimator.fit(df)          → EstimationResult
            │              └─ result.diagnostic_results =
            │                   estimator.diagnostics(result)     → list[DiagnosticResult]
            │
            ├─ _write_diagnostics(results)      ← CHANGED (reads EstimationResult)
            │    └─ writes diagnostics.csv from result.diagnostic_results
            │
            ├─ _build_comparison_table(results, ...)   ← CHANGED (field names only)
            │
            ├─ _write_csv / _write_latex / ... [unchanged]
            └─ _record_provenance()            [unchanged]
```

---

## 2. Responsibilities of Each Layer

### `cli.py` — No changes

The CLI's run command remains identical. It calls `ConfigValidator.validate_strict()` for pre-flight, then calls `run_from_config()`. No new imports, no new flags, no changed output.

### `econflow.config.validator.ConfigValidator` — No changes

Pre-flight config validation already runs before the pipeline. After the migration, its `KNOWN_ESTIMATORS` frozenset check (finding C-3 in the architectural assessment) becomes a separate concern addressed in a later sprint. For this migration it continues to validate using the static frozenset.

### `pipeline_generic.run_from_config()` — Thin orchestrator

Becomes a pure orchestrator. Its responsibilities:
- Load and decode YAML configs
- Load data via `pd.read_csv()`
- Perform structural panel checks (column presence, null counts)
- Delegate each model spec to `_run_model()` and collect results
- Delegate output writing to the unchanged `_write_*` helpers
- Write provenance metadata

It no longer contains any estimation logic. It no longer imports `linearmodels` directly.

### `pipeline_generic._run_model()` — Adapter + dispatch

Single responsibility: translate a YAML spec dict into a registered `EstimationResult`.

Steps:
1. Normalize the estimator string to a lowercase registry key (see Section 3).
2. Augment the spec with `entity_col` and `time_col` from the top-level config.
3. Look up the estimator class in the registry via `get_estimator(estimator_id)`.
4. Instantiate the class with the augmented spec as `params`.
5. Call `estimator.run(df)` on the flat (non-MultiIndex) DataFrame.
6. Return the `EstimationResult`.

Error handling: wrap `RegistryError` in `ModelSpecificationError`; wrap `EstimatorError` in `ModelSpecificationError`. Both already exist in `econflow.exceptions`. The caller (`run_from_config`) catches `EconFlowError` and fails cleanly.

### `pipeline_generic._run_diagnostics()` — Replaced by reader

The inline VIF / Breusch-Pagan / DW implementations are removed. The function is replaced by one that reads `EstimationResult.diagnostic_results` (populated by `BaseEstimator.run()`) and writes them to the same `diagnostics.csv` path. The CSV schema stays compatible (see Section 4).

### `pipeline_generic._build_comparison_table()` — Field name patch

The only change is three field name substitutions in the existing table-building logic:
- `result.std_errors` → `result.std_err`
- `result.rsquared_within` (on PanelOLS objects) → `result.rsquared`
- The OLS suppression check (`spec.get("estimator").upper() != "OLS"`) → `result.estimator_id != "ols"`

No structural change to the table format. Output CSV, LaTeX, Markdown, HTML, JSON remain byte-compatible for the same input data.

### `econflow.estimation.*` — No changes

The estimation framework (registry, base classes, all 8 estimators, protocol) is unchanged. The migration is entirely on the consumer side (`pipeline_generic.py`).

### `econflow.diagnostics.*` — No changes

The diagnostic plugins are unchanged. They are already invoked by `BaseEstimator.run()` via `estimator.diagnostics(result)`. The migration makes this path active by importing `econflow.estimation`, which triggers `estimation/__init__.py`, which triggers side-effect imports of all 8 estimators, each of which registers itself in the registry. The diagnostic framework is invoked transitively.

---

## 3. Required Interface Changes

### 3a. String Normalisation — `_resolve_estimator_id(spec)`

The YAML config currently uses uppercase estimator strings ("OLS", "FE"). The registry uses lowercase keys ("ols", "fe", "twfe"). A new private helper translates between them.

The translation also handles the legacy "FE" + `time_effects: true` combination, which the old pipeline treated as a two-way FE model but never named explicitly:

```
Input string (case-insensitive) | Conditions                           | Registry key
"OLS"                           | any                                  | "ols"
"FE"                            | entity_effects=true, time_effects=false | "fe"
"FE"                            | entity_effects=true, time_effects=true  | "twfe"
"FE"                            | entity_effects=false, time_effects=false| "ols" (pooled)
"TWFE"                          | any                                  | "twfe"
"RE"                            | any                                  | "re"
"FD"                            | any                                  | "fd"
"IV"                            | any                                  | "iv"
"GMM"                           | any                                  | "gmm"
"QUANTILE"                      | any                                  | "quantile"
<any other string>              | any                                  | passed through as-is
```

The last row means custom plugin estimators registered with any key are supported without change.

This logic is fully backwards-compatible: all existing YAML files with "OLS" and "FE" keys continue to work exactly as before. Users who already use the registry key directly (e.g., "twfe") also work without change because the normalisation is case-insensitive and the registry key passes through unchanged.

### 3b. Spec Augmentation — `_augment_spec(spec, entity_col, time_col)`

`BaseEstimator.__init__(params=...)` receives the entire spec dict as `params`. Estimators such as `EntityFE._fit_panel_ols()` need `entity_col` and `time_col` to set the MultiIndex. These values live in `config.yaml` (not `models.yaml`) and are not in the spec.

A new private helper merges them into the spec before passing it to the estimator:

```
augmented_spec = {**spec, "entity_col": entity_col, "time_col": time_col}
```

This is a dict merge. The original spec is not mutated. Estimators that do not use these keys ignore them silently (extras in `params` are allowed by `BaseEstimator`).

### 3c. Data Input — from MultiIndex to flat DataFrame

`run_from_config()` currently calls `_prepare_panel()` to set a MultiIndex on `df`, producing `panel_df`. Then `panel_df` is passed to `_run_model()`.

The `BaseEstimator.fit()` implementations in `estimation/fixed_effects.py` call `data.set_index([entity_col, time_col])` internally. They expect a **flat** (non-MultiIndex) DataFrame as input.

The change: `_run_model()` now receives `df` (the flat DataFrame), not `panel_df`. The `_prepare_panel()` call in `run_from_config()` is retained for the null-count check but its output is no longer passed to `_run_model()`.

No YAML change. No user-visible behavior change.

### 3d. Return Type of `_run_model()` — linearmodels object → `EstimationResult`

`_run_model()` currently returns a raw `linearmodels.panel.PanelResults` or `linearmodels.panel.PooledOLSResults` object. After migration it returns an `EstimationResult`.

The `results: dict` in `run_from_config()` changes from `dict[str, linearmodels_result]` to `dict[str, EstimationResult]`. Every consumer of `results` must be updated to use `EstimationResult` field names.

Affected consumers:
- `_run_diagnostics()` — reads `result.diagnostic_results` (see Section 2)
- `_build_comparison_table()` — reads `result.params`, `result.pvalues`, `result.std_err`, `result.nobs`, `result.rsquared`, `result.estimator_id` (see Section 3e)

### 3e. Field Name Map for `_build_comparison_table()`

| Current (linearmodels) | After migration (EstimationResult) | Notes |
|---|---|---|
| `result.params[reg]` | `result.params[reg]` | Same |
| `result.pvalues[reg]` | `result.pvalues[reg]` | Same |
| `result.std_errors[reg]` | `result.std_err[reg]` | Renamed |
| `result.nobs` | `result.nobs` | Same |
| `result.rsquared_within` | `result.rsquared` | FE within-R²; OLS suppressed |
| `spec.get("estimator","FE").upper() != "OLS"` | `result.estimator_id != "ols"` | OLS suppression check |

The `conf_int` field on `EstimationResult` (95% CI DataFrame with "lower"/"upper" columns) is available for future table columns but is not used by the current table format. No change needed.

### 3f. Diagnostics CSV Schema — backwards compatible

Current CSV columns written by `_run_diagnostics()`:
```
model_id | diagnostic | statistic | p_value | conclusion
```

`DiagnosticResult` fields:
```
diagnostic_id | diagnostic_name | statistic | pvalue | conclusion | level | estimator_id | extra
```

Mapping (no column renames in the output — the CSV format is preserved):
```
model_id     ← the key from the results dict (model spec "id")
diagnostic   ← DiagnosticResult.diagnostic_name
statistic    ← DiagnosticResult.statistic
p_value      ← DiagnosticResult.pvalue
conclusion   ← DiagnosticResult.conclusion
```

The CSV is written with the same path (`outputs/tables/diagnostics.csv`) and the same column set. Any downstream tooling that reads this CSV continues to work.

---

## 4. Data Flow

### Before (current state)

```
config.yaml ──┐
models.yaml ──┤ _load_yaml()
outputs.yaml──┘
                          ┌─ raw linearmodels result ──┐
data.csv ──pd.read_csv()──┤                            ├─ _build_comparison_table()──┬─ CSV
              ↓           │ _run_model() [inline       │                              ├─ LaTeX
         _prepare_panel() │ linearmodels.PooledOLS     ├─ _run_diagnostics() [inline │ ...
              ↓           │ linearmodels.PanelOLS]     │  VIF, BP, DW]               │
          panel_df        └────────────────────────────┘                              └─ diagnostics.csv
                                                                                         provenance.json
```

### After (target state)

```
config.yaml ──┐
models.yaml ──┤ _load_yaml()
outputs.yaml──┘
                             ┌─ EstimationResult ──────────────────────────────────────────────┐
data.csv ──pd.read_csv()─────┤                                                                  │
              ↓              │ _run_model()                                                      ├─ _build_comparison_table()
         _validate_columns() │  _resolve_estimator_id(spec)         ← adapter                  │   (reads EstimationResult fields)
              ↓              │  _augment_spec(spec, ecol, tcol)     ← merge                    │   ↓
          null check         │  get_estimator(id)                   ← registry                  │  CSV / LaTeX / MD / HTML / JSON
          (panel_df          │  EstimatorClass(params=augmented_spec)← framework                │
           unchanged         │  estimator.run(df)                   ← framework                 ├─ _write_diagnostics()
           for this)         │   ├─ validate(df)                                                │   (reads EstimationResult.diagnostic_results)
                             │   ├─ fit(df) → EstimationResult                                  │   ↓
                             │   └─ diagnostics(result) → list[DiagnosticResult]               │  diagnostics.csv
                             └──────────────────────────────────────────────────────────────────┘
                                                                                                  provenance.json [unchanged]
```

The entire right half (output writing, provenance) is structurally identical. Only what flows into it changes — from raw linearmodels objects to `EstimationResult` objects.

---

## 5. Error Handling

### Estimator not found in registry

`get_estimator(estimator_id)` raises `RegistryError` (from `econflow.core.exceptions`) if the key is not registered.

Handling: `_run_model()` catches `RegistryError` and re-raises as `ModelSpecificationError` with a message that names the unknown estimator and lists available ones. `run_from_config()` already propagates `ModelSpecificationError` (an `EconFlowError` subclass) to the CLI's `except EconFlowError` block, which prints a red error and exits with code 1. No change to the CLI error path.

### Estimator is a stub (raises `NotImplementedError`)

`SystemGMM.fit()` and `PanelQuantile.fit()` raise `NotImplementedError`. This propagates out of `estimator.run()`.

Handling: `_run_model()` catches `NotImplementedError` and re-raises as `ModelSpecificationError` with a message: "Estimator '{id}' is not yet implemented (stub). Remove it from models.yaml or wait for a future release." This is surfaced to the user cleanly via the CLI error path. **This is strictly better behavior than the current silent fallback to PanelOLS for GMM/Quantile.**

### Estimator validation failure

`estimator.validate(df)` may raise `EstimatorError`.

Handling: `_run_model()` catches `EstimatorError` and re-raises as `ModelSpecificationError` with the model id prepended. Same CLI error path.

### Plugin estimator load failure

`_load_entry_point_plugins()` in `estimation/registry.py` already wraps failed plugin loads in a `RuntimeWarning` and continues. Failed plugins do not crash the pipeline; they simply aren't in the registry. If a user references an unloadable plugin, they get a `RegistryError` → `ModelSpecificationError` with a helpful message.

### Diagnostic failure

`BaseDiagnostic` implementations should not raise — they return a `DiagnosticResult` with the failure captured in `conclusion`. If an exception does escape, `_write_diagnostics()` catches it per-result and logs a warning, writing whatever results are available. The pipeline continues. This matches the current `_run_diagnostics()` behavior, which wraps each test in `try/except` with `log.debug()`.

---

## 6. Migration Sequence

The migration is designed to be a single atomic commit to `pipeline_generic.py`. No other files change. The sequence below describes execution order, not file order.

### Step 1 — Add imports (pipeline_generic.py top-level)

Add:
- `from econflow.estimation.registry import get_estimator`
- `from econflow.estimation.result import EstimationResult`
- `from econflow.core.exceptions import RegistryError`

Remove:
- `from linearmodels.panel import PanelOLS, PooledOLS`
- `import statsmodels.api as sm` (if it is only used for `sm.add_constant()` inside `_run_model()`, which is removed; if used elsewhere keep it)

Note: `import statsmodels.api as sm` is currently used on line 146 of `_run_model()` for `sm.add_constant()`. After migration, the estimator handles its own data preparation. If `sm` is used nowhere else in the file, it can be removed from the top-level import and moved inside any remaining function that needs it.

### Step 2 — Add `_resolve_estimator_id()` (new private function)

Implements the case-insensitive normalisation and FE→TWFE adapter from Section 3a. Pure function; no side effects. Can be unit-tested in isolation.

### Step 3 — Add `_augment_spec()` (new private function)

Implements the spec dict merge from Section 3b. Trivial; no side effects.

### Step 4 — Replace `_run_model()`

The existing 89-line function (including the PooledOLS/PanelOLS dispatch, the `sm.add_constant()` call, and the coefficient log loop) is replaced by the new dispatch logic:
- call `_resolve_estimator_id(spec)`
- call `_augment_spec(spec, entity_col, time_col)`
- call `get_estimator(estimator_id)`
- instantiate, call `.run(df)`, return `EstimationResult`

The new function is shorter. The function signature changes: it now takes `df` instead of `panel_df`, and takes `entity_col`/`time_col` as explicit arguments (since they are needed for `_augment_spec`).

### Step 5 — Update `run_from_config()` call site for `_run_model()`

Change the call at line 670 from:
```
results[mid] = _run_model(panel_df, spec)
```
to:
```
results[mid] = _run_model(df, spec, entity_col, time_col)
```

The `panel_df` variable is still produced by `_prepare_panel()` for the null-count check. It is simply not passed to `_run_model()` anymore.

### Step 6 — Replace `_run_diagnostics()`

Remove the 156-line function with its inline statsmodels calls. Add the new function that iterates over `result.diagnostic_results` for each result in the dict and writes the same CSV.

Update the call site in `run_from_config()` to pass `results: dict[str, EstimationResult]` (the signature changes slightly since `panel_df`, `dependent`, and `regressors` are no longer needed as arguments — all that information is now in the `EstimationResult` objects).

### Step 7 — Patch `_build_comparison_table()`

Apply the three field name substitutions from Section 3e. These are local variable reads; no structural change to the function.

### Step 8 — Remove dead imports

Remove `from linearmodels.panel import PanelOLS, PooledOLS` from line 36. Remove `import statsmodels.api as sm` from line 34 if it has no remaining callers. Keep `numpy`, `pandas`, `yaml` — all still used.

---

## 7. Risk Assessment

### Risk 1 — `EstimationResult` missing residuals for diagnostics (Medium)

The inline `_run_diagnostics()` accesses `result.resids` (a linearmodels attribute). `EstimationResult` has no `residuals` or `resids` field in its declared schema. After migration, diagnostics come from `BaseEstimator.diagnostics()` which uses whatever the estimator puts in `result.extra` or computes directly from the fit object.

**Mitigation:** The estimator's `diagnostics()` method has full access to the underlying fit object (the raw linearmodels result) before constructing `EstimationResult`. Residuals are available at that point. The concrete estimators must include the diagnostic tests that the current `_run_diagnostics()` provides (VIF, BP, DW). Verify before migration that `EntityFE.diagnostics()` returns these tests. If it does not, augment `EntityFE.diagnostics()` as a separate preparatory step before this migration.

**Detection:** Running the getting_started tutorial after migration and comparing `diagnostics.csv` against the existing expected output will immediately detect any missing diagnostics.

### Risk 2 — R-squared field mismatch (Low)

`pipeline_generic.py` uses `rsquared_within` (a linearmodels attribute). `EstimationResult.rsquared` is documented as "R-squared or within-R-squared for FE models." The concrete `EntityFE.fit()` must populate `rsquared` with the within-R² value.

**Mitigation:** Verify by reading `EntityFE.fit()` that it stores the within-R² in `EstimationResult.rsquared`. If it stores overall R², the table will show the wrong value. This is a testable assertion: run the getting_started tutorial, compare the R² column in the output table against the known expected values.

**Detection:** Comparison table golden-output test.

### Risk 3 — `entity_col`/`time_col` not expected by all estimators (Low)

`_augment_spec()` unconditionally injects `entity_col` and `time_col` into the spec dict. Estimators that use a Dataset object (rather than a flat DataFrame) may not expect these. `BaseEstimator` allows extra keys in `params` silently. Stub estimators (`SystemGMM`, `PanelQuantile`) raise `NotImplementedError` before accessing params at all.

**Mitigation:** No action needed. Extra keys in params do not cause errors; they are simply unused.

### Risk 4 — Plugin side-effect import order (Low)

Importing `econflow.estimation.registry` triggers `_load_entry_point_plugins()` at module load time (line 85 of `registry.py`). This runs before `pipeline_generic.py` is fully initialised. Any plugin that fails to load emits a `RuntimeWarning`. If a plugin import crashes hard (uncaught exception), it could prevent the pipeline from starting.

**Mitigation:** The try/except in `_load_entry_point_plugins()` is already written to catch all exceptions. No additional work needed. The risk exists today whenever `econflow.estimation` is imported anywhere; this migration does not increase it.

### Risk 5 — FE→TWFE adapter is imprecise (Low)

The adapter maps "FE" + (entity_effects=True, time_effects=True) → "twfe". A user who has `estimator: FE, entity_effects: false, time_effects: false` in their YAML would be mapped to "ols" under the current adapter logic. This user probably intended pooled OLS (which matches "ols") but specified it using "FE" without effects — an unusual configuration.

**Mitigation:** The adapter should log a deprecation warning when "FE" with no effects is detected, telling the user to specify `estimator: OLS` explicitly. This preserves behavior while alerting users to the imprecision.

### Risk 6 — Getting-started expected outputs diverge (Medium)

`examples/getting_started/expected_outputs/` contains pre-computed reference outputs. If the estimation framework and the inline linearmodels calls produce identical numerical results (which they should, since both ultimately call the same linearmodels backend), expected outputs will match. If they differ even in floating-point rounding, golden tests will fail.

**Mitigation:** Run the getting-started tutorial immediately after migration on a known dataset and diff the output against the reference. A numerical difference would indicate a bug in one of the estimators' construction of `EstimationResult`, not in the migration design.

---

## 8. Acceptance Criteria

The migration is complete when all of the following hold:

### A — Runtime call graph

1. `grep -r "from linearmodels" src/econflow/pipeline_generic.py` returns no results.
2. `grep -r "from econflow.estimation.registry import get_estimator" src/econflow/pipeline_generic.py` returns one result.
3. A `print`-tracing run confirms `get_estimator()` is called once per model spec during `econflow run`.

### B — Backwards compatibility

4. `econflow run --config examples/getting_started/config/config.yaml --models examples/getting_started/config/models.yaml --outputs examples/getting_started/config/outputs.yaml` completes without error.
5. The comparison table (CSV and LaTeX) produced by B-4 is numerically identical to the pre-migration expected output (within floating-point tolerance, e.g., 1e-8).
6. `examples/getting_started/config/config.yaml`, `models.yaml`, and `outputs.yaml` are unchanged.

### C — YAML format preserved

7. All three YAML estimator string values in the getting-started example ("OLS", "FE" with entity effects, "FE" with entity+time effects) are correctly resolved: to "ols", "fe", "twfe" respectively.
8. A YAML with `estimator: TWFE` also resolves correctly.
9. A YAML with `estimator: my_custom_estimator` (where the estimator is registered via plugin) resolves correctly.

### D — Diagnostics preserved

10. `outputs/tables/diagnostics.csv` is produced after every `econflow run`.
11. The CSV has the same columns: `model_id`, `diagnostic`, `statistic`, `p_value`, `conclusion`.
12. VIF, Breusch-Pagan, and serial correlation results are present for all FE and OLS models.

### E — Publication outputs preserved

13. LaTeX output includes `\begin{threeparttable}`, significance note, and `\toprule`/`\midrule`/`\bottomrule`.
14. CSV, Markdown, HTML, JSON formats are all produced when specified in `outputs.yaml`.
15. Table values (coefficients, SEs, significance stars, N, R²) are identical to pre-migration values.

### F — Integrity and replication preserved

16. `econflow certify` succeeds after a migration-produced run.
17. `econflow verify` succeeds against a certificate produced by F-16.
18. `econflow package` succeeds.
19. `econflow reproduce` on a package produced by F-18 succeeds and produces matching outputs.

### G — Plugin architecture live

20. A custom estimator registered via `@register_estimator("custom_ols")` is reachable from YAML `estimator: custom_ols` and is invoked during `econflow run`.
21. `econflow info` shows the full estimator registry (unchanged command; now reflects all estimators including custom ones).

### H — Error handling

22. `estimator: gmm` in models.yaml causes the pipeline to exit with code 1 and print a clear message that SystemGMM is a stub, not a cryptic `NotImplementedError` traceback.
23. `estimator: unknown_xyz` in models.yaml causes the pipeline to exit with code 1 and list available estimators.
24. An estimator plugin that raises an exception during `validate()` causes the pipeline to exit with code 1 and name the failing model.

### I — Existing test suite

25. `pytest tests/` passes with zero failures.
26. `ruff check src/` passes with zero violations.

### J — No regression in other commands

27. `econflow validate`, `econflow doctor`, `econflow info`, `econflow fetch`, `econflow certify`, `econflow verify`, `econflow package`, `econflow reproduce`, `econflow compare`, `econflow inspect`, `econflow release-check` all continue to function as before.

---

## What Is Deliberately Out of Scope

The following issues identified in the architectural assessment are **not** addressed by this migration. They require separate work:

- `KNOWN_ESTIMATORS` frozenset in `config/models.py` (finding H-3): the validator still uses the frozenset. Fixing it to consult the live registry is a separate, later change.
- `SystemGMM` and `PanelQuantile` stubs (finding C-4): this migration makes them produce a clear user-facing error instead of a silent wrong result, which is an improvement — but they remain unimplemented.
- `ARCHITECTURE.md` staleness (finding C-3): update separately.
- Coverage configuration (finding C-2): update `pyproject.toml` separately.
- Missing `requests` dependency (finding C-5): fix `pyproject.toml` separately.
- `__author__` truncation and `AIProdError` in `__all__` (findings H-4, H-2): fix `__init__.py` separately.
