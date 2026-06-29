# EconFlow: Roadmap to v1.0

**Document type:** Technical Steering Committee Governing Roadmap  
**Authority:** EconFlow TSC  
**Date issued:** 2026-06-28  
**Baseline state:** v0.7 — 878 tests passing, Sprint 9 complete  
**Governing inputs:** `ROADMAP.md`, `docs/architecture/MILESTONE_v0.7.md`,
`docs/roadmap/V1_RELEASE_CRITERIA.md`, `docs/maintenance/REPOSITORY_AUDIT.md`

---

> **How to read this document.** This is a milestone roadmap, not a sprint plan.
> Each milestone is a strategically significant state of the repository — a point
> at which EconFlow's capabilities, stability, or quality changes in a material way.
> Milestones are ordered by dependency, not by calendar. A milestone is complete when
> every item in its Exit Criteria is verified true by the TSC.
>
> Sprint plans are derived from milestones, not the reverse. A sprint that does not
> advance at least one milestone's exit criteria is not aligned with the v1.0 path.

---

## Current State (v0.7 Baseline)

**What works.** The plugin registries for estimators, diagnostics, connectors, renderers,
and integrity checks are implemented and tested. Six core estimators, five renderers,
four diagnostics, three integrity checks, and five data connectors are registered and
functional. The provenance recorder, drift detector, reproducibility certificate,
and `econflow package` command are implemented. 878 tests pass. Ruff is clean.
The Plugin SDK is documented (`docs/sdk/PLUGIN_SDK.md`).

**What blocks v1.0.** Sixteen of twenty-six blocking requirements are Missing; ten are
Partial; none are Complete. The five structural blockers:

1. **Pipeline-registry disconnection.** `econflow run` imports `linearmodels` directly
   and bypasses the estimator registry. The plugin architecture is real in every
   sub-system except the one path researchers actually use.

2. **`load_config()` unimplemented.** Configuration validation is structural (YAML
   parses) rather than semantic (values are valid). A misspelled column name is caught
   at runtime, inside estimation, not at configuration load.

3. **Five figure builder stubs.** `DistributionPlot`, `EventStudyPlot`, `ResidualPlot`,
   `HeteroscedasticityPlot`, `PanelTrendsPlot` raise `NotImplementedError`. The
   `econflow report` command cannot produce a complete publication bundle.

4. **Repository carries dead weight.** Eleven deprecated sub-packages, three duplicate
   pipeline modules, two incompatible exception hierarchies, a committed `dist/`
   directory. These signal to contributors that the project does not know what it is.

5. **Packaging and CI are absent.** No CI pipeline; `requests` and `openpyxl` absent
   from `pyproject.toml`; version is `0.1.0`; no cross-platform test matrix.

---

## Milestones Overview

| # | Milestone | Strategic purpose | Approximate sprint |
|---|---|---|---|
| M1 | Foundation Cleanup | Remove all dead code; one coherent codebase | 10 |
| M2 | Pipeline–Registry Wiring | Close the central architectural gap | 10–11 |
| M3 | Feature Completeness | Implement every registered stub | 11 |
| M4 | API Stabilization | Declare, audit, and freeze the public surface | 11 |
| M5 | Packaging & CI | Make EconFlow a real installable package | 11–12 |
| M6 | Reproducibility Closure | Close provenance and integrity gaps | 12 |
| M7 | Documentation Completeness | All public surfaces documented and current | 12 |
| M8 | RC1 Gate | TSC sign-off; frozen interfaces; final testing | 12–13 |
| M9 | v1.0 Release | Public commitment to stability | 13 |

**Critical path:** M1 → M2 → M4 → M8 → M9  
**Parallel path:** M3, M5, M6, M7 (can run in parallel with M2–M4 after M1)

---

## M1 — Foundation Cleanup

### Goal

Remove every piece of dead, duplicate, or conflicting code from the repository so that
the codebase presents a single coherent implementation. After M1, a new contributor
reading `src/econflow/` sees exactly one implementation of every concept, with no
ambiguity about which file is canonical.

### Deliverables

**Code deletions (zero-risk — confirmed no live callers):**
- Delete `agents/` (four backward-compat shims with no importers)
- Delete `docs/development/agents/` (identical copies)
- Delete `app/streamlit_app.py` (placeholder stub)
- Delete `src/econflow/data/` (paper-specific, superseded by `ingestion/`)
- Delete `src/econflow/econometrics/` (paper-specific, superseded by `estimation/`)
- Delete `src/econflow/visualization/` (paper-specific, superseded by `outputs/figures/`)
- Delete `src/econflow/features/` (zero callers)
- Delete `src/econflow/ml/` (empty namespace placeholder)
- Delete `src/econflow/config/` (empty namespace placeholder)
- Delete `src/econflow/utils/` (empty namespace placeholder)
- Delete `src/econflow/ingestion/oecd.py`, `ingestion/pwt.py`, `ingestion/world_bank.py`
  (stubs superseded by `ingestion/connectors/`)
- Delete `dist/` content; add `dist/` and `outputs/` to `.gitignore`

**Structural refactors (require test verification):**
- Merge `EconFlowError` and `EconFlowCoreError` into a single hierarchy rooted at
  `EconFlowError`. Every class from `core/exceptions.py` becomes either an alias or
  a subclass of its counterpart in `exceptions.py`. Remove the duplicate `PipelineError`.
- Rename `register` → `register_estimator` in `estimation/__init__.py`;
  rename `register` → `register_connector` in `ingestion/__init__.py`. Keep deprecated
  aliases emitting `DeprecationWarning` for two minor versions.
- Delete `src/econflow/pipeline.py` (paper-specific, superseded by `pipeline_generic.py`).
  Rename `pipeline_generic.py` → `pipeline.py`. Update `cli.py` import.
- Delete five diagnostic flat stubs (`specification.py`, `serial.py`, `reporter.py`,
  `dependence.py`, `overid.py`). Add `status = "stub"` marker files in
  `diagnostics/plugins/` for `overid` and `reporter`.
- Delete `outputs/tables.py` shim. Update `outputs/__init__.py` to import directly
  from `outputs/tables/`.
- Move `tests/test_provenance.py` → `tests/unit/test_provenance.py`.
  Move `tests/test_exceptions.py` → `tests/unit/test_exceptions.py`.
- Delete duplicate docs: `docs/MIGRATION_PLAN.md`, `docs/SPRINT_MIGRATION_ROADMAP.md`,
  root-level `MIGRATION_CHECKLIST.md`, `docs/development/NEXT_SESSION.md`.
- Move `docs/SPRINT6_RC1_REVIEW.md` → `docs/development/SPRINT6_RC1_REVIEW.md`.
- Move `outputs/provenance/schema.json` → `docs/architecture/schemas/provenance_schema.json`.

### Acceptance Criteria

1. `find src/ -name "oecd.py" -o -name "pwt.py" -o -name "world_bank.py" | grep -v connectors` → zero results.
2. `ls src/econflow/data/ src/econflow/econometrics/ src/econflow/visualization/ src/econflow/features/ src/econflow/ml/` → all "No such file or directory".
3. `python3 -c "from econflow.exceptions import EconFlowError, PipelineError, RegistryError, ConfigurationError, EstimationError; print('OK')"` → OK.
4. `python3 -c "from econflow.core.exceptions import EconFlowCoreError; from econflow.exceptions import EconFlowError; assert issubclass(EconFlowCoreError, EconFlowError)"` → passes.
5. `from econflow.estimation import register` emits `DeprecationWarning`.
6. `from econflow.ingestion import register` emits `DeprecationWarning`.
7. `python3 -c "from econflow.estimation import register_estimator; from econflow.ingestion import register_connector; print('OK')"` → OK without warning.
8. `from econflow.pipeline import run_from_config` succeeds (previously `pipeline_generic`).
9. `pytest --tb=short -q` → all tests pass (count ≥ 878).
10. `ruff check src/` → zero errors.
11. `git status` → `dist/` and `outputs/` are gitignored; no built artifacts tracked.

### Dependencies

- None. M1 is the prerequisite for everything else; it has no upstream dependencies.
- Requires: reading `docs/maintenance/REPOSITORY_AUDIT.md` for the complete deletion list.

### Estimated Effort

**6–8 hours** across two sessions.

| Task | Hours |
|---|---|
| Code deletions (no callers, no tests to update) | 1.5 |
| Exception hierarchy merge | 3.0 |
| Pipeline rename + CLI update | 1.0 |
| `register` rename + deprecation aliases | 1.0 |
| Table shim deletion + diagnostic stub cleanup | 0.5 |
| Doc moves and gitignore updates | 0.5 |
| Test verification pass | 0.5 |

### Risks

**Risk M1-R1 (Medium).** Exception hierarchy merge touches import sites across the
entire codebase. A missed `except EconFlowCoreError` clause that should become
`except EconFlowError` will silently stop catching exceptions in that path.
*Mitigation:* `grep -rn "EconFlowCoreError\|APRPError" src/ tests/` must return zero
after the merge.

**Risk M1-R2 (Low).** Renaming `register` will break any code in `examples/` or user
scripts that imports the old name without going through `__init__.py`.
*Mitigation:* Keep `register` as an alias emitting `DeprecationWarning` rather than
removing it immediately. Search `examples/` for direct `register` imports and update them.

**Risk M1-R3 (Low).** Deleting `src/econflow/reporting/narrative.py` removes the
paper-specific narrative generation capability. No generic replacement exists.
*Mitigation:* This capability was never public API and had no registered users outside
`pipeline.py` (itself deleted). Accept the loss; narrative generation is out of scope
for v1.0.

### Exit Criteria

All eleven acceptance criteria above pass. The TSC reviews the PR diff and confirms
no production code was deleted that had live callers. `pytest -q` reports a test count
≥ 878 with zero failures.

---

## M2 — Pipeline–Registry Wiring

### Goal

Wire `econflow run` through the estimator registry so that the plugin architecture is
functional in the primary user-facing workflow. After M2, a researcher who writes
`@register_estimator("my_method")` and specifies `estimator: my_method` in `models.yaml`
will see their estimator execute when they run `econflow run` — without modifying any
EconFlow source file. Simultaneously, implement `load_config()` so that configuration
errors are caught before any computation begins.

This milestone closes the two most severe architectural deficiencies identified in
`V1_RELEASE_CRITERIA.md` (Requirements 1.1 and 1.4).

### Deliverables

**`core/config.py` — implement `load_config()`:**
- `load_config(path: Path) -> Settings` reads the three YAML files (`config.yaml`,
  `models.yaml`, `outputs.yaml`), validates them against the Pydantic `Settings`,
  `ModelSpec`, and `OutputsConfig` schemas, and raises `ConfigurationError` with a
  field-level message on any validation failure.
- `MissingConfigKeyError` (subclass of `ConfigurationError`) is raised when a required
  key is absent.
- Every CLI command that currently calls `_load_yaml()` directly is updated to call
  `load_config()` instead.

**`pipeline.py` (formerly `pipeline_generic.py`) — wire registry dispatch:**
- Remove all direct imports of `linearmodels`, `statsmodels`, and any estimation
  sub-module from the pipeline module.
- `run_from_config(settings: Settings)` calls
  `estimation.registry.get_estimator(spec.estimator)` for each model spec.
  No estimator class name appears in the pipeline module.
- The pipeline calls `estimator.run(data)` and collects `EstimationResult` objects.
  It does not inspect or manipulate `EstimationResult` fields itself.
- Plugin discovery: if `settings.plugins` is non-empty, `pipeline.py` imports each
  module listed, triggering registration before `get_estimator()` is called.

**`ingestion/` — manifest–provenance link:**
- `ProvenanceRecorder.__exit__` writes `manifest_path` into `run_metadata.json`,
  pointing to the `DatasetManifest` file written during the same run.
  If no manifest was written, `manifest_path: null`.

**Integration test:**
- `tests/integration/test_full_cli_workflow.py` — exercises the complete CLI path:
  `econflow init` → populate `config.yaml` → `econflow fetch --connector csv` →
  `econflow run` → `econflow certify` → `econflow package`.
  Uses `subprocess.run(["econflow", ...])` throughout. Asserts the output archive
  contains `run_metadata.json`, `certificate.json`, and at least one CSV table.

### Acceptance Criteria

1. Install EconFlow in a clean venv. Place a `@register_estimator("test_pass")` stub
   that returns a known `EstimationResult`. Specify `estimator: test_pass` in
   `models.yaml`. Run `econflow run`. The output table contains the known coefficient.
2. `grep -n "import linearmodels\|import statsmodels" src/econflow/pipeline.py` → zero results.
3. Create `config.yaml` with `year_start: "not_a_year"`. Run `econflow validate`.
   Exit code non-zero. Output contains the field name and invalid value. No Python
   traceback in the output (unless `--debug`).
4. Run `econflow run` with a valid config. `run_metadata.json` contains
   `"manifest_path": "<path_to_manifest.json>"` or `"manifest_path": null`.
5. `pytest tests/integration/test_full_cli_workflow.py -v` → all tests pass.
6. `pytest tests/integration/ -q` → all integration tests pass.

### Dependencies

- **M1 must be complete.** The pipeline rename (`pipeline_generic.py` →
  `pipeline.py`) and exception hierarchy merge must be in place before the registry
  wiring is implemented. Doing M2 before M1 means wiring against a module that will
  be renamed.

### Estimated Effort

**8–10 hours.**

| Task | Hours |
|---|---|
| Implement `load_config()` with Pydantic validation | 3.0 |
| Update all CLI commands to call `load_config()` | 1.5 |
| Pipeline registry dispatch (remove direct imports, wire `get_estimator`) | 2.5 |
| Plugin discovery from `settings.plugins` | 0.5 |
| Manifest–provenance link | 0.5 |
| Full-pipeline CLI integration test | 2.0 |

### Risks

**Risk M2-R1 (High).** The pipeline currently controls estimation logic directly
(applying fixed effects, clustering, etc.). Moving to `estimator.run(data)` requires
that all six core estimators accept the full panel dataset and extract their required
columns from `params`. If any estimator has implicit assumptions about which columns
are present, those assumptions must be made explicit in `validate()`.
*Mitigation:* Run the full integration test against the `getting_started` example.
Any failed assumption surfaces immediately.

**Risk M2-R2 (Medium).** `load_config()` validation may be too strict for the
`getting_started` example's current `config.yaml`, which may have fields that the
Pydantic schema marks as required but that researchers typically set at runtime.
*Mitigation:* Audit `examples/getting_started/config/config.yaml` against the
`Settings` schema before implementing; add appropriate `Optional` fields with defaults.

**Risk M2-R3 (Low).** If `ProvenanceRecorder` currently writes `run_metadata.json`
before the manifest is written (ordering dependency), the `manifest_path` link will
point to a file that does not yet exist at write time.
*Mitigation:* Write `manifest_path` as `null` initially; update it after the manifest
is written by appending to the JSON atomically.

### Exit Criteria

All six acceptance criteria pass. The getting-started example (`examples/getting_started/`)
runs end-to-end via `econflow run` without modification and produces output matching
the reference files. The full-pipeline CLI integration test passes. No direct estimation
library imports remain in `pipeline.py`.

---

## M3 — Feature Completeness

### Goal

Implement every capability that is registered in the plugin registries but currently
raises `NotImplementedError`. After M3, the registries make no promises that the
platform cannot keep: `list_estimators()`, `list_figure_builders()`, and
`list_diagnostics()` return only implemented, tested items.

This milestone closes Requirement 6.2 (figure builder stubs) and the stub portions of
Requirements 4.1 (GMM, Quantile estimators) and the unimplemented diagnostic plugins
(`serial_correlation`, `wooldridge`).

### Deliverables

**Figure builders — implement five stubs:**
- `DistributionPlot`: histogram + KDE of a named column from the estimation data.
  Parameters: `column`, `bins`, `confidence_level`.
- `EventStudyPlot`: coefficient plot across event-time periods.
  Parameters: `event_col`, `pre_periods`, `post_periods`, `zero_period`.
- `ResidualPlot`: scatter of residuals vs. fitted values with a LOESS smoother.
  Parameters: `entity_col`, `time_col`.
- `HeteroscedasticityPlot`: absolute residuals vs. fitted values (White test companion).
  Parameters: `entity_col`.
- `PanelTrendsPlot`: line chart of the dependent variable over time by entity group.
  Parameters: `entity_col`, `time_col`, `group_col`, `max_entities`.

Each figure builder: subclasses `BaseFigureBuilder`, is decorated with
`@register_figure_builder(id)`, produces a `ReportFigure` with JSON-serializable
`data` dict, has ≥ 5 unit tests covering at least one valid call and one error case.

**Estimators — implement two stubs:**
- `SystemGMMEstimator` (registered as `"system_gmm"`): System GMM for dynamic panels.
  Uses `linearmodels.PanelOLS` with appropriate instrument structure as a first pass;
  full Blundell-Bond implementation may be deferred to v1.1 with clear documentation.
- `PanelQuantileEstimator` (registered as `"panel_quantile"`): Quantile regression
  for panels. Uses `statsmodels.regression.quantile_regression.QuantReg` applied
  within-entity.

Both estimators must implement `validate()`, `fit()`, and `diagnostics()` fully.
`validate()` must raise `EstimatorError` (not `NotImplementedError`) on invalid input.

**Diagnostics — implement two stubs:**
- `SerialCorrelationTest` (registered as `"serial_correlation"`): Wooldridge test for
  serial correlation in panel residuals.
- `WooldridgeTest` (registered as `"wooldridge"`): Wooldridge first-difference test
  for unobserved heterogeneity.

**Outputs:**
- Migrate `TFPFigureBuilder` and `CoeffCompareFigureBuilder` from `outputs/figures.py`
  (flat file) into `outputs/figures/tfp_figure.py` and
  `outputs/figures/coeff_compare_figure.py`. Delete `outputs/figures.py`.
- After migration, evaluate `sensitivity/` for remaining callers; delete
  `sensitivity/runner.py` and `sensitivity/comparison.py` if no live callers remain.

**Integrity package:**
- Implement the auto-generated `README` section in the replication package that
  summarizes integrity check outcomes in human-readable form (Requirement 7.2).
  A package produced from a run with any `fail`-status check must include a
  visible "Integrity Warnings" section.

### Acceptance Criteria

1. `python3 -c "from econflow.outputs import list_figure_builders; builders = list_figure_builders(); assert all(b['status'] == 'implemented' for b in builders), builders"` → passes.
2. For each of the seven figure builder IDs: `get_figure_builder(id).build(valid_result)` returns a `ReportFigure` with `data` non-empty.
3. `get_estimator("system_gmm").run(panel_data)` returns an `EstimationResult` with `estimator_id == "system_gmm"` and `len(params) >= 1`.
4. `get_estimator("panel_quantile").run(panel_data)` returns an `EstimationResult` with `estimator_id == "panel_quantile"`.
5. `get_diagnostic("serial_correlation").run(fe_result, data)` returns `DiagnosticResult` with `level in ("info", "warn", "error")`.
6. `get_diagnostic("wooldridge").run(fe_result, data)` returns `DiagnosticResult`.
7. `econflow report --output-dir ./out` produces at minimum: five CSV files, five LaTeX files, and at least one figure JSON file in `./out`.
8. `pytest tests/unit/test_figure_builders.py -q` → ≥ 50 tests, zero failures.
9. `find src/econflow/outputs -name "figures.py" -maxdepth 1` → zero results (flat file deleted).
10. A replication package produced from a run with a `fail`-status integrity check contains a README section titled "Integrity Warnings".

### Dependencies

- **M1 must be complete** (dead sub-packages deleted; no conflicts with old `visualization/`).
- **M2 should be in progress or complete.** Figure builders receive `EstimationResult`
  objects; the quality of those results depends on proper registry dispatch. M3 can
  begin in parallel with M2 but must be integration-tested after M2.
- No dependency on M4, M5, M6, or M7.

### Estimated Effort

**12–16 hours.**

| Task | Hours |
|---|---|
| Five figure builders + tests (avg 1.5h each) | 7.5 |
| SystemGMM estimator + tests | 2.5 |
| PanelQuantile estimator + tests | 2.0 |
| SerialCorrelation diagnostic + tests | 1.0 |
| Wooldridge diagnostic + tests | 1.0 |
| `figures.py` migration; `sensitivity/` cleanup | 1.0 |
| Integrity package README section | 1.0 |

### Risks

**Risk M3-R1 (High).** System GMM is one of the most technically demanding estimators
in panel econometrics. A full Blundell-Bond implementation with optimal GMM weighting
and instrument collapse is not achievable in a single sprint. The stub must be replaced
with a functional (if simplified) implementation that passes the acceptance criteria.
*Mitigation:* Document explicitly in the `SystemGMMEstimator` docstring what the
current implementation does and does not support. Add "full Blundell-Bond" to the
v1.1 roadmap.

**Risk M3-R2 (Medium).** The `EventStudyPlot` requires `EstimationResult` to carry
event-time coefficients in a structured form (e.g., in `extra["event_time_params"]`).
If the fixed-effects estimator does not populate this field, the figure builder
cannot be tested end-to-end.
*Mitigation:* Add `event_time_params` as an optional field in `EstimationResult.extra`
and document it in the SDK. The figure builder returns a `ReportFigure` with empty
`data` if the field is absent, rather than raising.

**Risk M3-R3 (Low).** Moving figure builders out of `outputs/figures.py` breaks any
external code that imports `from econflow.outputs.figures import TFPFigureBuilder`.
*Mitigation:* Add a deprecated shim to `outputs/__init__.py` that re-exports the moved
classes with a `DeprecationWarning`.

### Exit Criteria

All ten acceptance criteria pass. `econflow report` produces a complete publication
bundle from the `getting_started` example with at least one figure. The test count
rises by at least 60 from M1's baseline (new figure builder and estimator tests).

---

## M4 — API Stabilization

### Goal

Declare, audit, and freeze the public API surface of EconFlow before the v1.0 release
makes that surface a long-term commitment. After M4, every symbol in `__all__` is
documented, every `_private` reference across package boundaries is eliminated, and the
backward compatibility contract is written and published.

This milestone closes Requirements 1.2, 2.1, 2.2, and 2.3 from `V1_RELEASE_CRITERIA.md`.

### Deliverables

**`VERSIONING.md` (new file, repository root):**
- States that EconFlow follows Semantic Versioning 2.0.0.
- Defines breaking change: signature changes to `__all__` symbols; removal of `__all__`
  symbols; changes to YAML schema required keys; changes to JSON artifact schema without
  version bump; changes to plugin base class abstract method signatures; changes to CLI
  command names or required arguments.
- Defines non-breaking: new optional parameters with defaults; new optional fields in
  dataclasses; new concrete (non-abstract) methods; new plugin types.
- Defines deprecation policy: minimum two minor versions with `DeprecationWarning`
  before removal; deprecation notice in `CHANGELOG.md`.
- States what is explicitly excluded from the breaking-change definition: `_private`
  names, stub implementations, documentation, error message text.

**Public API audit:**
- Every sub-package `__init__.py` defines `__all__` listing only names that belong to
  the public API. Names not in `__all__` are internal.
- `grep -rn "from econflow\.[a-z_]*\._" src/econflow/` returns zero results. No module
  imports a `_private` name from a different sub-package.
- `AIProdError` alias is removed from `econflow.__init__.__all__` and from
  `econflow.exceptions`. (The exception class object itself may remain as a deprecated
  internal alias until v1.2 to not break any `except AIProdError` clauses in the wild,
  but it must not appear in `__all__`.)
- `unregister_estimator`, `unregister_connector`, etc. are removed from all `__all__`
  lists. They remain importable (for test use) but are not public API.

**TSC API review:**
- TSC formally reviews the combined `__all__` surface across all sub-packages.
  The review is documented as a comment in the PR that merges M4.
- All Plugin SDK import paths in `docs/sdk/PLUGIN_SDK.md` §13.4 are verified against
  the actual `__init__.py` files. Discrepancies are corrected.

**`EstimationResult` schema frozen:**
- Add a `RESULT_SCHEMA_VERSION = "1.0.0"` constant to `estimation/result.py`.
- Document in `VERSIONING.md` that `EstimationResult` fields listed in
  `docs/sdk/PLUGIN_SDK.md` §13.3 may not be removed or renamed in any v1.x release.

### Acceptance Criteria

1. `grep -rn "from econflow\.[a-z_]*\._" src/econflow/` → zero results.
2. For every `__init__.py` in `src/econflow/*/`: `python3 -c "import ast; tree = ast.parse(open(f).read()); assert any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in n.targets) for n in ast.walk(tree)), f + ' missing __all__'"` → passes for all files.
3. `cat VERSIONING.md` at repository root — must address all four points in Requirement 2.3.
4. `grep "__all__" src/econflow/estimation/__init__.py` must not contain `unregister`.
5. `grep "__all__" src/econflow/__init__.py` must not contain `AIProdError`.
6. `python3 -c "from econflow.estimation import RESULT_SCHEMA_VERSION; assert RESULT_SCHEMA_VERSION == '1.0.0'"` → passes.
7. TSC review documented in the merge PR (or a linked `docs/architecture/API_SIGN_OFF.md`).

### Dependencies

- **M1 must be complete.** The exception hierarchy merge must be done before the API
  audit, because the audit includes confirming that the exception hierarchy is singular.
- **M2 should be in progress or complete.** The `load_config()` return type
  (`Settings`) and `run_from_config()` signature are part of the public API and must
  be present and correct before the audit freezes them.
- No dependency on M3. M4 and M3 can run in parallel.

### Estimated Effort

**6–8 hours.**

| Task | Hours |
|---|---|
| Write `VERSIONING.md` | 1.5 |
| Audit and correct all `__all__` lists | 2.0 |
| Remove cross-package `_private` imports | 1.0 |
| Remove `AIProdError` from `__all__`; remove `unregister_*` from `__all__` | 0.5 |
| Add `RESULT_SCHEMA_VERSION`; document frozen fields | 0.5 |
| TSC review pass + corrections | 1.5 |
| Verify SDK §13.4 import paths | 1.0 |

### Risks

**Risk M4-R1 (Medium).** The audit may discover `_private` cross-package imports in
test files or in the CLI layer that represent genuine coupling rather than accidents.
These require design decisions about whether to make the API public or restructure the
coupling.
*Mitigation:* Treat test files differently from production code. `tests/` may import
private names (for white-box testing). Production code in `src/` may not.

**Risk M4-R2 (Low).** Removing `AIProdError` from `__all__` may break any external
code that currently does `from econflow import AIProdError`. At v0.7, the project is
pre-release; no external code should depend on it. However, the `examples/` directory
may reference it.
*Mitigation:* `grep -r "AIProdError" examples/` and update any references to
`EconFlowError`.

### Exit Criteria

All seven acceptance criteria pass. The TSC review comment is recorded. The Plugin
SDK's §13.4 import paths pass a mechanical verification test. `pytest -q` → all tests
pass with count ≥ M1 baseline.

---

## M5 — Packaging & CI

### Goal

Make EconFlow a properly packaged, installable Python library that can be distributed
through PyPI and that passes tests automatically on every commit on all three major
platforms and all supported Python versions. After M5, the question "does this change
break anything?" is answered by CI, not by manual testing on the developer's machine.

This milestone closes Requirements 10.3, 12.1, 12.2, 12.3, 13.1, 14.1, and the CI
requirement in 15.2.

### Deliverables

**`pyproject.toml` corrections:**
- Add `requests>=2.28` and `openpyxl>=3.1` to `[project.dependencies]`.
- Update `version` to use dynamic versioning (`dynamic = ["version"]`) keyed to git
  tags, or set `version = "0.9.0"` as the pre-release series until v1.0 is tagged.
- Add `homepage`, `repository`, and `documentation` URLs to `[project.urls]`.
- Confirm `cli_scaffold/` is excluded from the wheel via `exclude = ["src/econflow/cli_scaffold"]`.
- Add `[project.entry-points."econflow.plugins"]` section (initially empty; documents
  the mechanism for third-party plugins).

**`requirements.txt` drift guard:**
- Add a CI step: `python tools/check_requirements_sync.py` that diffs the
  `requirements.txt` list against `pyproject.toml [project.dependencies]` and exits
  non-zero if they diverge. Script is < 20 lines.

**CI configuration (`.github/workflows/ci.yml`):**
- Trigger: push and pull request on `main`.
- Jobs:
  - `lint`: `ruff check src/ tests/`; `ruff format --check src/ tests/`.
  - `test`: matrix `[ubuntu-22.04, macos-14, windows-2022]` × `[3.10, 3.11, 3.12, 3.13]`.
    Each matrix cell: `pip install -e .[dev]`; `pytest --tb=short -q`.
  - `clean-install`: matrix `[ubuntu-22.04, macos-14, windows-2022]` × `[3.10, 3.13]`.
    Fresh venv; `pip install .` (no extras); `econflow doctor`; `econflow --version`.
  - `requirements-sync`: runs the drift guard on every push.
- All CI jobs are required status checks; merging is blocked if any fail.

**`econflow doctor` enhancements:**
- Add checks for: `requests` (required), `openpyxl` (required), `pdflatex` (optional),
  `git` (required for provenance).
- Missing required dependencies → non-zero exit code.
- Missing optional dependencies → exit code 0 with advisory message.

**License audit:**
- Run `pip-licenses --from=mixed --format=json > docs/maintenance/DEPENDENCY_LICENSES.json`.
- Confirm all licenses are MIT, BSD, Apache 2.0, or LGPL (all compatible with MIT).
- Document any borderline cases in `docs/maintenance/DEPENDENCY_LICENSES.json`.

### Acceptance Criteria

1. `pip install econflow` in a Python 3.13 clean venv; `import requests; import openpyxl` → no `ImportError`.
2. `find $(python -c "import econflow; print(econflow.__file__.rsplit('/', 2)[0])")/econflow -name "cli_scaffold" -type d` → zero results.
3. CI runs on every PR; green on `[ubuntu-22.04, macos-14, windows-2022]` × `[3.10, 3.11, 3.12, 3.13]` (12 cells).
4. `econflow doctor` without `requests` installed → exit code 1; output contains `"requests: MISSING (required)"`.
5. `cat docs/maintenance/DEPENDENCY_LICENSES.json` → all entries have `License` in `["MIT", "BSD", "BSD-3-Clause", "Apache 2.0", "Apache Software License", "PSF", "LGPL", "MPL-2.0"]`.
6. `python tools/check_requirements_sync.py` → exit code 0 when files are in sync; exit code 1 when they diverge (CI step verifies both cases).
7. `pip show econflow` → `Home-page` and `Project-URLs` fields are non-empty.

### Dependencies

- **M1 must be complete** (dead code deleted; `dist/` gitignored; `cli_scaffold/`
  excluded from wheel confirmed).
- M5 is largely independent of M2, M3, and M4 and can run in parallel with all three.
  The CI matrix must test against whatever the current codebase is; it does not need
  feature completeness to be useful.

### Estimated Effort

**6–8 hours.**

| Task | Hours |
|---|---|
| `pyproject.toml` corrections | 0.5 |
| CI workflow file | 2.0 |
| Clean-install verification (debug cross-platform issues) | 1.5 |
| `doctor` enhancement | 1.0 |
| `requirements.txt` drift guard script | 0.5 |
| License audit + `DEPENDENCY_LICENSES.json` | 1.0 |
| Debug any Windows-specific test failures | 1.5 |

### Risks

**Risk M5-R1 (High).** The NTFS truncation bug documented during Sprint 7 demonstrates
that Windows-specific issues can be severe and non-obvious. CI on Windows may reveal
path separator issues, case-sensitivity problems, or file locking conflicts in the
cache manager.
*Mitigation:* Fix Windows-specific failures immediately; do not mark tests as
`platform.skip("Windows")` unless the underlying capability is genuinely unavailable.

**Risk M5-R2 (Medium).** `openpyxl` is listed as a required dependency in the v1.0
release criteria, but there is no openpyxl-dependent code visible in the current
codebase. Adding it as a hard dependency without a clear use case adds install weight
for no benefit.
*Mitigation:* Audit whether `openpyxl` is actually required (it may be needed for
the Excel renderer if one is planned) or whether it should be an optional extra
(`[project.optional-dependencies].excel = ["openpyxl>=3.1"]`).

**Risk M5-R3 (Low).** `pdflatex` availability in CI (for the LaTeX compile test in
Requirement 6.3) requires installing TeX Live in the CI environment, which is slow
(~5 minutes download). This may conflict with CI speed requirements.
*Mitigation:* LaTeX compile test is non-blocking (Requirement 6.3). Run it in a
separate, slower CI job on a weekly schedule rather than on every PR.

### Exit Criteria

All seven acceptance criteria pass. CI is green on all 12 matrix cells for the latest
commit. The `clean-install` job passes on `ubuntu-22.04`, `macos-14`, and
`windows-2022`. License audit file is committed to `docs/maintenance/`.

---

## M6 — Reproducibility Closure

### Goal

Close the remaining gaps in the provenance, integrity, and reproducibility systems so
that the `ReproducibilityCertificate` and `DatasetManifest` together form a complete,
verifiable audit trail that meets the requirements of academic data editors.

This milestone closes Requirements 7.2, 8.2, and 8.3.

### Deliverables

**Provenance–manifest link (follow-up to M2):**
- Verify that M2's `manifest_path` implementation writes correctly in all code paths:
  runs with `econflow fetch`, runs with local CSV only (manifest_path: null), and
  runs where `econflow fetch` is called multiple times.
- Integration test for each path.

**Integrity results in the replication package (Requirement 7.2):**
- `econflow package` auto-generates `REPLICATION_README.md` containing a section
  "Integrity Check Results" listing each check's `check_id`, `status`, and `message`.
- If any check has `status == "fail"`, the section is titled "⚠ Integrity Warnings"
  and the top of the README contains a prominent callout box.
- The `certificate.json` inside the archive contains the full `check_results` list.
- Integration test: produce a package from a synthetic result with one `fail` check;
  assert README contains "Integrity Warnings"; assert certificate contains the fail.

**Certificate backward compatibility test (Requirement 8.3):**
- Commit a fixture file `tests/fixtures/certificates/v0.7_certificate.json` — a real
  certificate produced by the current codebase.
- Add `tests/regression/test_certificate_compat.py` with one test:
  `ReproducibilityCertificate.from_json(v0_7_fixture)` must succeed without exception.
  The test must still pass after v1.0 is released.

**Cache key stability (Requirement 5.4):**
- Document the cache key algorithm for all five connectors in
  `docs/architecture/CACHE_KEY_ALGORITHM.md`: the exact fields included in the
  SHA-256 payload, the sort order, the JSON serialization, and the exclusion of
  credential fields.
- Add `tests/regression/test_cache_key_stability.py`: for each connector, verify
  that the cache key produced by the current implementation equals a known hex string
  hardcoded in the test. This test failing signals a breaking change to the cache key.

### Acceptance Criteria

1. `econflow run` (with `econflow fetch` step): `run_metadata.json` has `"manifest_path": "<valid_path>"` pointing to an existing file.
2. `econflow run` (CSV-only, no fetch): `run_metadata.json` has `"manifest_path": null`.
3. `econflow package` output archive contains `REPLICATION_README.md` with an "Integrity Check Results" section listing all three registered checks.
4. Package from a run with a `fail` check: README title includes "Integrity Warnings"; appears in the first 30 lines.
5. `pytest tests/regression/test_certificate_compat.py -v` → passes.
6. `pytest tests/regression/test_cache_key_stability.py -v` → passes for all five connector types.
7. `cat docs/architecture/CACHE_KEY_ALGORITHM.md` → documents all five connectors' key construction.

### Dependencies

- **M2 must be complete** (provenance–manifest link must be implemented before it can
  be verified and closed here).
- **M1 must be complete** (no dead ingestion modules that could confuse the manifest).
- M6 can run in parallel with M3, M4, M5.

### Estimated Effort

**5–7 hours.**

| Task | Hours |
|---|---|
| Verify and test provenance–manifest link (all three paths) | 1.5 |
| `econflow package` README generation with integrity section | 2.0 |
| Certificate backward compatibility fixture + test | 1.0 |
| Cache key documentation | 1.0 |
| Cache key stability regression tests | 1.0 |

### Risks

**Risk M6-R1 (Medium).** The auto-generated `REPLICATION_README.md` must look
professional enough to be included alongside a submitted paper. Template quality is a
design risk; a poorly formatted README reflects on the research.
*Mitigation:* Write the template to Markdown conventions; include the EconFlow version,
run timestamp, and a brief explanation of what each integrity check tests.

**Risk M6-R2 (Low).** The `v0.7_certificate.json` fixture must be produced from a
real pipeline run, not constructed manually. If the fixture is manually constructed, it
may not match the schema exactly and the test will give false confidence.
*Mitigation:* Produce the fixture by running `econflow certify` on the `getting_started`
example and copying the output certificate.

### Exit Criteria

All seven acceptance criteria pass. The `getting_started` example run produces an
archive that a TSC reviewer can inspect and confirm is self-documenting. The
certificate and cache key stability tests are committed to `tests/regression/`.

---

## M7 — Documentation Completeness

### Goal

Bring all user-facing documentation to the level required for v1.0: accurate, complete,
and verifiable by someone who has not read the source code.

This milestone closes Requirements 9.1, 9.2, 9.3, 13.3, 14.2, 14.3, and contributes
to 15.1, 15.3.

### Deliverables

**`README.md` — full rewrite:**
- Accurate test count (updated from 100 to the actual count at time of rewrite).
- All twelve CLI commands documented with one-line description.
- Five plugin types listed with a link to `docs/sdk/PLUGIN_SDK.md`.
- Reproducibility and integrity features summarized.
- "Quick Start" section: `pip install econflow` → `econflow init my_project` →
  `econflow run` → `econflow package`. Every command must work when copy-pasted.
- Badge for CI status, PyPI version, and Python version compatibility.

**CLI `--help` text:**
- Every command and sub-command: add `epilog` with one real example invocation.
- Every option: add `help=` text that is not the Typer auto-generated default.
- Every command: add explicit `[Returns]` text stating the exit code semantics
  (0 = success; 1 = validation failure; 2 = pipeline error).

**`CONTRIBUTING.md` — rewrite plugin sections:**
- Add "Adding a New Estimator" section referencing `docs/sdk/PLUGIN_SDK.md` §2.
- Add "Adding a New Connector" section referencing §3.
- Add "Adding a New Diagnostic" section referencing §4.
- Add "Adding a New Integrity Check" section referencing §5.
- State minimum test requirements per plugin type.
- State lint requirements (`ruff check`, `mypy --strict`).
- State process for proposing a new plugin type (open an issue with a design doc).

**`docs/architecture/` — update stale documents:**
- `ARCHITECTURE.md` (root): rewrite as a 1-page index linking to `docs/architecture/`
  with a high-level capability summary accurate for v0.9.
- Review `ESTIMATION_FRAMEWORK.md`, `REPORTING_ENGINE.md`, `WORKSPACE.md` for
  accuracy. Update or annotate any "planned" sections.

**`SECURITY.md` — update for cache and API key features:**
- Add section: "Cache Security" — cache key excludes credentials by design; documents
  which fields are excluded for each connector.
- Add section: "API Key Handling" — credentials are read from environment variables;
  never included in logs, provenance records, or cache keys.
- Add: "Which versions receive security patches" (all 1.x releases).

**`docs/development/RELEASE.md` (new):**
- Full release process: run release criteria checklist; tag the release; build the
  wheel (`python -m build`); upload to PyPI (`twine upload`); update CHANGELOG;
  update README test count badge.

**`examples/ai_productivity_paper/README.md`:**
- Update to use current CLI commands (`econflow run`, not `python run_pipeline.py`).
- Add: prerequisites, expected runtime, reference output verification step.

**Issue templates (`.github/ISSUE_TEMPLATE/`):**
- `bug_report.yml`: EconFlow version, Python version, OS, YAML config, full error.
- `feature_request.yml`: motivation, proposed API, workaround if any.
- `plugin_submission.yml`: plugin type, package name, example usage.

### Acceptance Criteria

1. A reviewer unfamiliar with EconFlow reads only `README.md` and successfully runs
   `econflow init my_test` → `econflow run --config examples/getting_started/config/config.yaml` → `econflow package`. Zero discrepancies between README and actual behavior.
2. `econflow <cmd> --help` for all 15 command/sub-command combinations produces output with at least one example invocation.
3. `grep "Adding a New Estimator" CONTRIBUTING.md` → non-empty.
4. `cat docs/development/RELEASE.md` → contains sections on tagging, building, and uploading.
5. `cat SECURITY.md` → contains "Cache Security" section.
6. `ls .github/ISSUE_TEMPLATE/*.yml` → at least three files.
7. `grep -i "1,0\|1\.0\|v1" README.md` → the README does not claim v1.0 has been released before it has.

### Dependencies

- **M2 should be complete.** The CLI's actual behavior (particularly `econflow run` with
  registry dispatch and `econflow fetch` with the manifest) must be final before the
  README is written, or it will need immediate revision.
- **M3 should be complete.** The list of implemented CLI commands depends on whether
  `report` can produce figures.
- **M4 must be complete.** `CONTRIBUTING.md` references the public API surface; the
  surface must be frozen before the contribution guide is final.
- M7 can begin in parallel with M3, M5, M6 (for the non-CLI-dependent parts:
  `SECURITY.md`, issue templates, `RELEASE.md`, architecture doc review).

### Estimated Effort

**8–10 hours.**

| Task | Hours |
|---|---|
| README rewrite | 2.5 |
| CLI `--help` text for all 15 commands | 2.0 |
| CONTRIBUTING.md plugin sections | 1.5 |
| Architecture doc review and updates | 1.0 |
| SECURITY.md update | 0.5 |
| RELEASE.md | 1.0 |
| Example README update | 0.5 |
| Issue templates | 0.5 |

### Risks

**Risk M7-R1 (Medium).** Documentation written before M2 is complete will describe
the pipeline dispatch correctly in theory but incorrectly in practice. Verifying
Acceptance Criterion 1 requires a functioning `econflow run` with registry dispatch.
*Mitigation:* Write the README's "Quick Start" section last, after M2 is verified.
Write the other sections in parallel.

**Risk M7-R2 (Low).** The `RELEASE.md` process document is only as good as the actual
release process. If the first real release (v1.0) reveals steps not covered by the
document, the document must be updated before the release completes.
*Mitigation:* Treat the first release as a test of the RELEASE.md; update it in real
time during the release.

### Exit Criteria

All seven acceptance criteria pass. The TSC reviews the README by attempting the
Quick Start workflow in a clean environment. Zero commands fail or behave differently
from the README description.

---

## M8 — RC1 Gate

### Goal

Tag the v1.0 Release Candidate. Conduct the TSC's formal interface freeze review.
Run the full test matrix on the RC tag. Confirm that every blocking requirement in
`V1_RELEASE_CRITERIA.md` is either Complete or has a documented waiver. No new
features are merged after RC1; only fixes to blocking issues.

### Deliverables

**Pre-RC checklist (gating on tagging RC1):**
All of M1–M7 exit criteria must be verified true. Specifically:
- All 26 blocking requirements in `V1_RELEASE_CRITERIA.md` are Complete or have a
  TSC-documented waiver.
- `pytest -q` on all 12 CI matrix cells: zero failures.
- `ruff check src/` → zero errors.
- `econflow --version` → `econflow 1.0.0rc1`.
- `pip install econflow==1.0.0rc1` from the test PyPI index succeeds on all platforms.

**TSC interface freeze review:**
- TSC formally reviews abstract method signatures of all five plugin base classes.
  Review documented in `docs/architecture/RC1_INTERFACE_SIGN_OFF.md`.
- TSC formally reviews `EstimationResult`, `DiagnosticResult`, `IntegrityCheckResult`,
  `ReportTable`, `ReportFigure`, `DatasetMetadata`, `DataValidationReport` field lists.
  Any field not listed in `PLUGIN_SDK.md` §13.3 is removed from `__init__.py`
  (or added to §13.3 and thus frozen).
- TSC formally reviews CLI command names and required arguments. Documented in the
  same sign-off file.

**RC1 plugin smoke test:**
- Write a minimal test plugin for each of the five plugin types using only the
  `docs/sdk/PLUGIN_SDK.md` documentation (no reading of source code).
  These five plugins are committed to `tests/fixtures/smoke_plugins/`.
- Each plugin runs successfully against `econflow==1.0.0rc1`.
- The same five plugins must run against `econflow==1.0.0` without modification
  (verified at M9).

**Performance benchmarks:**
- `tests/performance/test_benchmarks.py`:
  - Full pipeline with 6 estimators × 100 countries × 30 years: ≤ 60 seconds.
  - `econflow certify`: ≤ 5 seconds.
  - `econflow package`: ≤ 10 seconds.
  - Cache retrieve O(1) test: time ratio between 1000 and 1 entries < 2.
- Non-blocking if benchmarks fail; TSC may document a waiver with a planned fix in
  v1.0.1.

**`CHANGELOG.md` — `[1.0.0]` section drafted:**
- Drafted (not final) with all changes since v0.7, referencing this document.
- Finalized at M9.

### Acceptance Criteria

1. `git tag v1.0.0rc1` succeeds; `pip install econflow==1.0.0rc1` from test PyPI succeeds.
2. `pytest -q` on all 12 CI matrix cells: zero failures.
3. `docs/architecture/RC1_INTERFACE_SIGN_OFF.md` exists and is signed by the TSC.
4. All five smoke plugins in `tests/fixtures/smoke_plugins/` run against rc1 without modification.
5. Every blocking requirement in `V1_RELEASE_CRITERIA.md` is marked Complete or has a TSC waiver documented in `RC1_INTERFACE_SIGN_OFF.md`.
6. `econflow --version` on the installed rc1 package → `econflow 1.0.0rc1`.
7. Performance benchmarks: ≤ 60s full pipeline, ≤ 5s certify, ≤ 10s package (or TSC waiver if not met).

### Dependencies

- **M1–M7 must all be complete.** RC1 is the integration point for all preceding
  milestones. No milestone can be "mostly done" at RC1; all exit criteria must be
  verified.
- M8 has no parallel work possible: it is strictly sequential after M1–M7.

### Estimated Effort

**4–6 hours** (assuming M1–M7 are genuinely complete — RC1 should not be where bugs
from earlier milestones surface).

| Task | Hours |
|---|---|
| Pre-RC checklist verification | 1.0 |
| TSC interface review + sign-off document | 2.0 |
| RC1 smoke plugins (5 × ~30 minutes) | 2.5 |
| Performance benchmark implementation | 1.5 |
| CHANGELOG draft | 0.5 |
| Tag + test PyPI upload | 0.5 |

### Risks

**Risk M8-R1 (High).** RC1 typically reveals integration issues that were not visible
in individual milestone testing. If a blocking issue is discovered at RC1, it delays
the release and may require re-work in an earlier milestone. The RC1 period should be
treated as a fixed-duration (1–2 week) bug-fixing window.
*Mitigation:* Schedule RC1 with buffer before v1.0. Issues discovered at RC1 that
are genuine bugs are fixed. Issues that are design decisions are handled by TSC waiver
with documented rationale.

**Risk M8-R2 (Medium).** The smoke plugin test (writing plugins from documentation
only) may reveal gaps in the Plugin SDK documentation that were not visible during
document review. These gaps require SDK corrections before the interface can be called
"frozen."
*Mitigation:* Budget extra time for SDK corrections in the RC1 period. Any change to
an abstract method signature discovered during this process resets the freeze clock.

**Risk M8-R3 (Low).** Performance benchmarks may reveal that the full pipeline with
6 estimators on a 100×30 panel exceeds 60 seconds on reference hardware. The
benchmarks are non-blocking, but a poor result is a quality signal.
*Mitigation:* Profile and identify the bottleneck. If it is in linearmodels, it is
a known external factor and the benchmark bound should be documented accordingly.

### Exit Criteria

All seven acceptance criteria pass. RC1 is tagged and visible in the repository.
`pip install econflow==1.0.0rc1` completes without errors in a clean environment.
The TSC sign-off document is committed to `docs/architecture/`. No new feature PRs
are merged after RC1; only bug fixes. A 1–2 week RC1 stabilization period begins.

---

## M9 — v1.0 Release

### Goal

Issue the v1.0 release. Make the public commitment to API stability. Announce to the
research community. This milestone is complete when `pip install econflow==1.0.0`
succeeds, CI is green, and the CHANGELOG is published.

### Deliverables

**Release artifacts:**
- `git tag v1.0.0` on a commit that differs from RC1 only in the version string
  and CHANGELOG.
- Wheel uploaded to PyPI: `pip install econflow==1.0.0`.
- GitHub Release page with CHANGELOG section and links to `docs/sdk/PLUGIN_SDK.md`
  and `VERSIONING.md`.

**Verification that RC1 smoke plugins still work:**
- The five smoke plugins in `tests/fixtures/smoke_plugins/` are run against the v1.0
  wheel without modification. All five must pass. This verifies that no breaking
  change was introduced between RC1 and v1.0.

**`CHANGELOG.md` finalized:**
- `## [1.0.0] — 2026-xx-xx` section complete with:
  - Summary of what v1.0 delivers
  - Reference to `V1_RELEASE_CRITERIA.md` as the governing document
  - List of all blocking requirements and their resolution
  - Breaking changes from v0.7 (including `register` rename, exception hierarchy merge)
  - Deprecations in effect (with planned removal versions)

**Post-release communication:**
- Update `README.md` badge from `rc1` to `1.0.0`.
- Announce on relevant academic mailing lists and/or preprint servers.

### Acceptance Criteria

1. `pip install econflow==1.0.0` succeeds in a clean Python 3.10, 3.11, 3.12, and 3.13 environment.
2. All five RC1 smoke plugins run against `econflow==1.0.0` without modification.
3. `econflow --version` → `econflow 1.0.0`.
4. CI is green on the v1.0 tag on all 12 matrix cells.
5. `grep "## \[1.0.0\]" CHANGELOG.md` → non-empty.
6. PyPI page for `econflow` shows version `1.0.0` with correct metadata.
7. `pip show econflow` → `Requires: pandas, numpy, statsmodels, linearmodels, matplotlib, scipy, typer, rich, pyyaml, requests, openpyxl`.

### Dependencies

- **M8 (RC1 Gate) must be complete.** v1.0 is issued from the RC1 branch after
  a stabilization period with no regressions.

### Estimated Effort

**2–3 hours** (build, tag, upload, verify, communicate).

### Risks

**Risk M9-R1 (Low).** PyPI upload requires correct credentials and a working `twine`
configuration. The first real upload to PyPI will reveal whether the test PyPI
experience generalizes.
*Mitigation:* Follow `docs/development/RELEASE.md` exactly. Have a second team member
verify the upload before announcing.

**Risk M9-R2 (Low).** The smoke plugin compatibility test may fail if any subtle
behavior difference was introduced between RC1 and v1.0 (e.g., an exception message
that a smoke plugin inadvertently tested).
*Mitigation:* The smoke plugins must be written against interfaces, not error messages.
Error message text is explicitly excluded from the backward compatibility guarantee.

### Exit Criteria

All seven acceptance criteria pass. The CHANGELOG is complete. The v1.0 GitHub Release
page is live. The research community has been informed through at least one announcement
channel. This roadmap document's status is updated to "Complete" and archived in
`docs/development/`.

---

## Dependency Graph

The following graph shows how every milestone leads to v1.0. Arrows indicate "must
complete before." Critical path is shown by double lines. Parallel tracks are shown
side by side.

```
v0.7 BASELINE
     │
     ▼
╔══════════════════════════════════════════════════════╗
║  M1 — Foundation Cleanup                            ║  ← CRITICAL PATH START
║  Delete dead code, merge exceptions, rename pipeline ║
╚══════════════════════════════════════════════════════╝
     │
     │  ┌──────────────────────────────────────────────────────────┐
     │  │                    PARALLEL TRACK                        │
     ├──┼──────────────────────────────────────────────┐           │
     │  │                                              │           │
     ▼  ▼                                              ▼           ▼
╔══════════════╗   ╔══════════════════╗   ╔═══════════════╗   ╔═════════════╗
║  M2          ║   ║  M3              ║   ║  M5           ║   ║  M6         ║
║  Pipeline–   ║   ║  Feature         ║   ║  Packaging    ║   ║  Repro-     ║
║  Registry    ║   ║  Completeness    ║   ║  & CI         ║   ║  ducibility ║
║  Wiring      ║   ║                  ║   ║               ║   ║  Closure    ║
╚══════════════╝   ║  (fig builders,  ║   ╚═══════════════╝   ╚═════════════╝
     │             ║  GMM, quantile,  ║         │                   │
     │             ║  diagnostics)    ║         │                   │
     │             ╚══════════════════╝         │                   │
     │                    │                     │                   │
     │             ┌──────┘                     │                   │
     ▼             │                            │                   │
╔══════════════════╗                            │                   │
║  M4              ║                            │                   │
║  API             ║ ◄──────── M2 required      │                   │
║  Stabilization   ║ ◄──────── M3 preferred     │                   │
╚══════════════════╝                            │                   │
     │                                          │                   │
     │                                          │                   │
     └──────────────────┐                       │                   │
                        │                       │                   │
                        ▼                       │                   │
               ╔═════════════════╗              │                   │
               ║  M7             ║ ◄────────────┘                   │
               ║  Documentation  ║ ◄────── M4 required              │
               ║  Completeness   ║                                  │
               ╚═════════════════╝                                  │
                        │                                           │
                        └──────────────────┬────────────────────────┘
                                           │
                                           ▼
                              ╔═══════════════════════╗
                              ║  M8 — RC1 Gate        ║  ← CRITICAL PATH
                              ║                       ║
                              ║  Requires M1–M7 all   ║
                              ║  complete. TSC review. ║
                              ║  Interface freeze.     ║
                              ╚═══════════════════════╝
                                           │
                                           ▼
                              ╔═══════════════════════╗
                              ║  M9 — v1.0 Release    ║
                              ║                       ║
                              ║  pip install          ║
                              ║  econflow==1.0.0      ║
                              ╚═══════════════════════╝
```

### Dependency Table (formal)

| Milestone | Hard dependencies (must be complete) | Soft dependencies (should be complete) |
|---|---|---|
| M1 | None | None |
| M2 | M1 | — |
| M3 | M1 | M2 (for integration testing) |
| M4 | M1, M2 | M3 |
| M5 | M1 | — |
| M6 | M1, M2 | — |
| M7 | M4 | M2, M3, M5, M6 |
| M8 | M1, M2, M3, M4, M5, M6, M7 | — |
| M9 | M8 | — |

### Estimated Total Effort

| Milestone | Low estimate | High estimate |
|---|---|---|
| M1 Foundation Cleanup | 6 h | 8 h |
| M2 Pipeline–Registry Wiring | 8 h | 10 h |
| M3 Feature Completeness | 12 h | 16 h |
| M4 API Stabilization | 6 h | 8 h |
| M5 Packaging & CI | 6 h | 8 h |
| M6 Reproducibility Closure | 5 h | 7 h |
| M7 Documentation Completeness | 8 h | 10 h |
| M8 RC1 Gate | 4 h | 6 h |
| M9 v1.0 Release | 2 h | 3 h |
| **Total** | **57 h** | **76 h** |

At one 4-hour session per day, the critical path (M1 → M2 → M4 → M7 → M8 → M9)
requires approximately 10 sessions. The full roadmap (all milestones, some in parallel)
requires approximately 15–19 sessions.

---

## Sprint Allocation (Suggested)

| Sprint | Primary milestone | Secondary milestone | Total effort |
|---|---|---|---|
| 10 | M1 (Foundation Cleanup) | M5 setup (CI skeleton) | ~8 h |
| 11 | M2 (Pipeline–Registry) | M3 (Figure builders) | ~12 h |
| 12 | M3 (Estimators) + M4 (API) | M5 (cross-platform CI) | ~12 h |
| 13 | M6 (Repro Closure) + M7 (Docs) | M5 finalize | ~14 h |
| 14 | M8 (RC1 Gate) | Stabilization fixes | ~6 h |
| 15 | M9 (v1.0 Release) | — | ~3 h |

---

## What Is Explicitly Out of Scope for v1.0

The following items appear in the `ROADMAP.md` strategic roadmap but are not required
for v1.0 and must not delay it:

- **Stage 7 (AI Research Assistant):** Opt-in AI-assisted tools. Not a v1.0 commitment.
- **Cloud execution or distributed computation:** Long-term directions.
- **Journal integration:** Requires external coordination; not achievable in the v1.0 window.
- **Full Blundell-Bond System GMM:** The v1.0 GMM estimator is a functional approximation.
  Full implementation is v1.1.
- **LaTeX compile CI test (Req 6.3):** Non-blocking. TeX Live in CI is slow; defer to
  a weekly scheduled job.
- **Certificate backward compatibility test against a pre-v0.7 fixture:** The oldest
  available certificate is v0.7. The test in M6 covers v0.7 → v1.0.
- **Community-developed plugins:** The Plugin SDK enables them; their existence is not
  a v1.0 gate.
- **Three external research groups using EconFlow:** The ROADMAP.md Stage 9 criterion.
  This is a public beta criterion, not a v1.0 technical criterion.
- **Performance benchmarks passing:** Non-blocking per `V1_RELEASE_CRITERIA.md`.
  Benchmarks are instrumented in M8 and may be waived by TSC.

---

*EconFlow Technical Steering Committee — 2026-06-28*  
*This document is the governing roadmap from v0.7 to v1.0. It supersedes the
sprint-by-sprint recommendations in `docs/roadmap/V1_RELEASE_CRITERIA.md`
and all prior sprint planning documents. Amendments require TSC review and must
be documented with the date of amendment and the rationale for change.*
