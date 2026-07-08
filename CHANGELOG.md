# Changelog

## [Unreleased] — Sprint 11D: End-to-End Acceptance Test

### Added
- `econflow doctor` now checks whether `~/.local/bin` is on `PATH` (EXT-07) and
  prints the exact `export PATH=...` fix for Linux/macOS users after pip install.
- `econflow validate --data` now prints a data summary line after the data stage
  passes: `Data loaded: N rows · E entities · T time periods`.
- `econflow certify` auto-detects data paths and config from
  `outputs/provenance/run_metadata.json` when `--data` / `--config` are omitted.
- `econflow package` auto-detects `outputs/certificate.json` and all `config/*.yaml`
  files when the corresponding flags are omitted.
- `econflow init` scaffold now includes `markdown` in the default output formats
  (was `["csv", "latex"]`; now `["csv", "latex", "markdown"]`).
- Replication package `README.md` now includes the `econflow run` step in its
  "How to Replicate" section.
- `docs/release/USER_JOURNEY_VALIDATION.md` — full acceptance-test report.

### Changed
- `econflow init` config scaffold: placeholder column names now have `# ACTION REQUIRED`
  comments with concrete examples; `models.yaml` dependent/regressors annotated with
  `# ← replace with …`; next-steps message updated to name the placeholders explicitly.

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Documentation Audit (2026-07-07)

#### Fixed
- `CONTRIBUTING.md`: stale test count `371` → `931+`.
- `pyproject.toml`: added `per-file-ignores` for `tests/**` suppressing
  `E501`, `F401`, and `I001`; `ruff check src/ tests/` now exits 0.
- `src/econflow/outputs/__init__.py`: exported `BaseRenderer` and
  `FigureBuilder` so Plugin SDK import examples work.
- `docs/sdk/PLUGIN_SDK.md` §7: renamed non-existent `BaseFigureBuilder` →
  `FigureBuilder`; removed non-existent `register_figure_builder`,
  `get_figure_builder`, `list_figure_builders` from import blocks and
  backward-compatibility table.

#### Added
- `docs/release/DOCUMENTATION_VALIDATION.md` — full audit report: 13 files,
  168 code blocks verified, 12 release blockers found and resolved.

---

### Automatic Configuration Documentation (2026-07-07)

#### Added
- `src/econflow/config/docs.py` — `generate_config_reference(format)` and
  `write_config_reference(path, format)`: runtime documentation generator that
  reads Pydantic `model_fields`, `Field(description=...)`, `Field(examples=...)`,
  and type metadata (Literal args, Ge/Le/MinLen/Pattern constraints) to produce
  a 5-column table (Field, Type, Default, Allowed, Description) for every
  configuration option. `DEFAULT_OUTPUT_PATH = "docs/reference/configuration.md"`.
- `docs/reference/configuration.md` — auto-generated reference covering all
  three YAML files (`config.yaml`, `models.yaml`, `outputs.yaml`) including
  `se_type` Literal allowed values (`'robust' | 'clustered' | 'classical'`).
- `econflow docs config` CLI command — regenerates the reference doc on demand;
  supports `--stdout`, `--text`, and `--output <path>` flags.
- `tests/unit/test_config_docs.py` (31 tests): coverage for
  `generate_config_reference`, `_allowed_values_str`, `write_config_reference`,
  the `docs` CLI command, and validate→doc-hint integration.

#### Changed
- `src/econflow/commands/validate.py` — error and warning summaries now include
  a `Reference: docs/reference/configuration.md` doc hint and prompt
  `econflow docs config` for regeneration.
- `src/econflow/cli.py` — `docs` command added; `_output_summary` helper
  restored with complete body.

### Configuration Correctness Boundary (2026-07-06)

#### Added
- `src/econflow/config/validator.py` (740 lines): `ConfigValidator` — single source
  of truth for all 4 validation stages: YAML syntax, Pydantic schema, semantic, and
  cross-file. Returns `ValidationResult` (never raises). `validate_strict()` raises
  `ConfigValidationError` on any error and returns parsed config objects.
  - `ValidationIssue` dataclass: `stage`, `severity`, `source`, `location`, `message`,
    `fix`, `code` fields.
  - `ValidationResult` dataclass: `ok`, `errors`, `warnings`, `infos`, `by_stage()`,
    `by_source()` helpers.
- `src/econflow/core/exceptions.py` — `ConfigValidationError(ConfigurationError)`:
  carries full issue list; `error_count`, `errors`, `warnings` properties; renders
  first 10 errors in `str()`.
- `src/econflow/config/linter.py` — three new lint rules:
  - L-11: IV estimator with no instruments → error (prevents silent empty-IV runs)
  - L-12: TWFE with neither entity_effects nor time_effects set → warning
  - L-13: unknown renderer format ID (not in csv/latex/markdown/html/json) → warning
- `tests/unit/test_config_validation.py` (67 tests across 8 classes): full
  regression coverage for all 4 stages, `ConfigValidationError`, and programmatic
  API.
- `docs/architecture/CONFIG_VALIDATION.md` (280 lines): validation flow diagram,
  all rules table, programmatic API examples, CLI usage, migration notes.
- Test fixtures (7 directories): `iv_no_instruments/`, `twfe_no_effects/`,
  `bad_format/`, `x01_missing_model_ref/`, `x02_extra_regressors/`,
  `yaml_syntax_error/`, `wrong_nesting/`.

#### Changed
- `src/econflow/cli.py` — `econflow run` pre-flight replaced with
  `ConfigValidator.validate_strict(check_data=True)`; aborts with structured error
  list before touching any output files (load → validate → execute → report).
- `src/econflow/commands/validate.py` — fully delegates to `ConfigValidator`;
  renders issues grouped by stage and source via Rich; exits 1 on any error.
- `src/econflow/config/__init__.py` — exports `ConfigValidator`, `ValidationResult`,
  `ValidationIssue` in public API.
- `src/econflow/config/linter.py` — L-03 guarded against non-integer
  `sample_start`/`sample_end` (no crash on schema-invalid configs); `_ESTIMATOR_ALIASES`
  includes lowercase stub IDs; spec dict includes `entity_effects`, `time_effects`,
  `instruments` from typed model objects.
- Data stage D-01 (file not found) severity upgraded from `warning` → `error`
  (missing data file is a hard blocker, not advisory).

### Architecture Stabilization: Public API Hardening (2026-07-06)

#### Added
- `docs/API_STABILITY.md` (317 lines): Complete API stability tier classification
  for all 7 packages (estimation, ingestion, outputs, diagnostics, integrity,
  config, datasets). Documents Stable/Experimental/Internal/Deprecated tiers,
  versioning policy, and plugin entry-point documentation.
- `docs/release/BETA_READINESS_RESPONSE.md` (470 lines): External audit response
  document with confirmed/partially-confirmed/not-reproducible status for all
  16 issues, exact file:line citations, breaking-change assessments, and
  smallest safe fixes.
- `src/econflow/estimation/registry.py` — `register_estimator` / `unregister_estimator`
  stable API aliases; `_load_entry_point_plugins()` — entry-point auto-loading
  via `[project.entry-points."econflow.plugins"]` (S-2 fix).
- `src/econflow/ingestion/registry.py` — `register_connector` / `unregister_connector`
  stable API aliases.
- `src/econflow/integrity/checks/registry.py` — `unregister_integrity_check`
  stable alias (consistent with `register_integrity_check`).
- `src/econflow/config/__init__.py` — upgraded from stub to real public API
  exposing `ProjectConfig`, `ModelsConfig`, `OutputsConfig`, `ModelSpec`,
  `ConfigLinter`, `LintIssue`, `generate_config_reference`, `write_config_reference`.
- `src/econflow/config/linter.py` — lint rule L-04b: stub estimator detection;
  raises error when `gmm` or `quantile` used (registered but `NotImplementedError`).

#### Changed
- `src/econflow/core/exceptions.py` — `EconFlowCoreError` now inherits from
  `EconFlowError`; `except EconFlowError` now catches both pipeline-layer and
  core-layer exceptions (S-1 / task 213 fix).
- `src/econflow/__init__.py` — fixed module docstring (accurate "Available in v1.0"
  and "Not yet available" sections); added `EconFlowCoreError` to public API and
  `__all__`.
- `src/econflow/estimation/__init__.py` — `register_estimator`, `unregister_estimator`
  added to `__all__`; `register`/`unregister` marked deprecated.
- `src/econflow/ingestion/__init__.py` — `register_connector`, `unregister_connector`
  added to `__all__`; `register`/`unregister` marked deprecated.
- `src/econflow/integrity/__init__.py` and `integrity/checks/__init__.py` —
  `unregister_integrity_check` added to exports; `unregister_check` deprecated.
- `src/econflow/commands/validate.py` — removed GMM/quantile from fix hint
  (`Use one of: ols, fe, twfe, re, fd, iv`).
- `src/econflow/cli.py` — pre-flight `run_validate()` call before `run_from_config()`
  so `econflow run` aborts on invalid config (C-2 fix).
- `src/econflow/config/linter.py` — removed `gmm`/`quantile` from
  `_CANONICAL_ESTIMATORS`; stub estimators only trigger L-04b.
- `src/econflow/datasets/panel.py` — removed duplicate `__repr__` (F811); kept
  the `panel_balance`-based implementation.
- `pyproject.toml` — added `pydantic>=2.0` to `[project.dependencies]` (CF-1 fix).
- `docs/sdk/PLUGIN_SDK.md` — updated to reflect `register_estimator` as canonical
  name and entry-point loading as fully implemented.

#### Internal fixes (ruff)
- `src/econflow/estimation/base.py` — `TYPE_CHECKING` guard for `BackendCapabilities`.
- `src/econflow/data/cleaning.py` — `TYPE_CHECKING` guard for `SelectionSummary`;
  wrapped long line (E501).
- `src/econflow/data/loaders.py` — `TYPE_CHECKING` guard for `PanelDataset`.
- `src/econflow/commands/validate.py` — removed unused `results_cfg` (F841).
- `src/econflow/config/linter.py` — removed unused `all_estimators` block (F841).

### Architecture Stabilization Milestone 4 — User-Facing Configuration UX (2026-07-06)

#### Added
- `src/econflow/config/models.py` (517 lines): Pydantic v2 strict models for
  all three YAML configuration files:
  - `ProjectConfig` — `project`, `data`, `sample` (with year-order validator),
    `variables` (with non-empty-regressors validator); `extra="forbid"`.
  - `ModelsConfig` — `list[ModelSpec]` with `min_length=1`, duplicate-ID
    validator, `^[A-Za-z][A-Za-z0-9_-]*$` ID pattern; `ModelSpec` has
    `extra="allow"` for estimator-specific keys.
  - `OutputsConfig` — `outputs` block with `base_dir`, nested `tables`
    (including `ComparisonTableModel`) and `figures`; `extra="forbid"`.
  - Every `Field` carries `description=` and `examples=`.
- `src/econflow/config/linter.py` (529 lines): `ConfigLinter` class with
  10 semantic lint rules (L-01 through L-10):
  - L-01: dependent in regressors → error
  - L-02: duplicate regressors → error
  - L-03: start_year ≥ end_year → error
  - L-04: unknown estimator with fuzzy-match suggestion → warning
  - L-05: model regressor not in config.variables.regressors → warning
  - L-06: absolute outputs.base_dir → warning
  - L-07: unsupported data file extension → warning
  - L-08: project.version not valid semver → warning
  - L-09: model dependent ≠ config dependent → info
  - L-10: model has no label → info
  - Issues sorted errors → warnings → info; every error has `fix` text.
- `src/econflow/config/docs.py` (344 lines): `generate_config_reference()`
  reads Pydantic `model_fields` at runtime to generate a Markdown or plain-text
  configuration reference that is always in sync with the schema.
  `write_config_reference(path)` writes to file.
- `docs/architecture/CONFIG_REFERENCE.md`: auto-generated from live Pydantic
  models via `generate_config_reference()`.
- `tests/fixtures/config/` — fixture YAML files:
  - `valid/` — passing config, models, and outputs fixtures.
  - `invalid/` — 7 named fixtures for specific lint rules (dep_in_regressors,
    dup_regressors, year_order, extra_key, unknown_estimator, dup_model_ids,
    abs_base_dir).
- `tests/unit/test_config_milestone4.py` (661 lines, 54 tests):
  `TestProjectConfig` (11), `TestModelsConfig` (7), `TestOutputsConfig` (5),
  `TestConfigLinterRules` (17), `TestConfigDocsGenerator` (5),
  `TestValidateCommand` (7), `TestValidateDirectoryArg` (3).

#### Changed
- `src/econflow/commands/validate.py` — complete rewrite with three-phase output:
  - Phase 1: Schema validation via Pydantic (per-file pass/fail with actionable
    error messages and `Fix:` hints).
  - Phase 2: Semantic validation via `ConfigLinter` (L-01 through L-10).
  - Phase 3: Cross-file consistency (output model IDs exist in models.yaml,
    model regressors subset of config regressors).
  - Phase 4 (opt-in `--data`): data file existence, column presence, duplicate
    panel keys.
  - `_SUPPORTED_ESTIMATORS` preserved as module-level alias for backward
    compatibility with existing tests.
- `src/econflow/cli.py` — `validate` command gains:
  - `config_dir: Optional[Path]` positional argument: `econflow validate config/`
    resolves all three files from the directory.
  - `--verbose / -v` flag: show passing checks as well as failures.
  - `--config`, `--models`, `--outputs` now override the positional directory
    for per-file overrides.

### Architecture Stabilization Milestone 3 — Library-Agnostic EstimatorProtocol (2026-07-06)

#### Added
- `src/econflow/estimation/protocol.py`: new module defining `EstimatorProtocol`
  (`@runtime_checkable Protocol`), `BackendCapabilities` dataclass, and six
  `BACKEND_*` string constants (`linearmodels`, `statsmodels`, `pyfixest`,
  `doubleml`, `pymc`, `custom`) plus `KNOWN_BACKENDS` frozenset.
- `src/econflow/estimation/backends/` — new package of library-specific mixin
  classes:
  - `LinearmodelsMixin` [implemented]: `_to_panel()` (MultiIndex builder for
    linearmodels), `_check_linearmodels()`, `_backend_capabilities()` returning
    `BackendCapabilities(supports_panel=True, supports_iv=True, supports_gmm=True)`.
  - `StatsmodelsMixin` [stub — Milestone 4]: `_to_formula()` raises
    `NotImplementedError`; `_check_statsmodels()` returns installed version.
  - `PyfixestMixin` [stub — Milestone 4]: `_to_fixest_formula()` raises
    `NotImplementedError`; `_check_pyfixest()` returns installed version.
  - `DoubleMLMixin` [stub — Milestone 5]: `_to_doubleml_data()` raises
    `NotImplementedError`; `_check_doubleml()` returns installed version.
  - `PyMCMixin` [stub — Milestone 6]: `_build_pymc_model()` and
    `_extract_posterior_summary()` raise `NotImplementedError`;
    `_check_pymc()` returns installed version.
- `BaseEstimator.backend: str = "unknown"` — new class attribute; all 8
  concrete estimators now declare `backend = "linearmodels"`.
- `BaseEstimator._backend_capabilities()` — new concrete method returning a
  `BackendCapabilities` instance; falls back to `backend="custom"` for
  unrecognised backend strings.
- `list_by_backend(backend: str)` in `estimation/registry.py` — filters the
  registry by backend identifier and returns sorted metadata dicts.
- `tests/unit/test_estimator_protocol.py`: 51 protocol conformance and
  migration tests covering: `isinstance(est, EstimatorProtocol)` for all 8
  registered estimators, duck-typed custom class satisfies protocol without
  ABC inheritance, incomplete class does NOT satisfy protocol, all
  `BackendCapabilities` flags, `list_by_backend()`, `LinearmodelsMixin._to_panel()`,
  stub mixin `NotImplementedError`, `_backend_capabilities()` fallback, and all
  public `__init__` exports.

#### Changed
- `estimation/registry.py`: `@register()` decorator gains optional `backend=`
  keyword; reads `cls.backend` as fallback. `_REGISTRY_META` entries now include
  `"backend"` key. `list_estimators()` returns dicts with `"backend"` key.
- `estimation/base.py`: `validate(data)`, `fit(data)`, and `run(data)` type
  hints updated to `pd.DataFrame | Any` to formally document Dataset acceptance.
  `_to_panel()` retains a deprecation note pointing to `LinearmodelsMixin`.
- `estimation/{ols,fixed_effects,random_effects,first_difference,iv,gmm,quantile}.py`:
  each class now declares `backend = "linearmodels"`.
- `estimation/__init__.py`: exports `EstimatorProtocol`, `BackendCapabilities`,
  all `BACKEND_*` constants, `KNOWN_BACKENDS`, all 5 backend mixins, and
  `list_by_backend`.
- `docs/architecture/ESTIMATION_FRAMEWORK.md`: added Milestone 3 section
  documenting `EstimatorProtocol` design, backend mixin table, `BackendCapabilities`
  usage, migration path for third-party estimators, and updated module map.

#### Architecture Notes
- **No breaking changes**: all existing estimators, registry calls, and imports
  work without modification. `BaseEstimator._to_panel()` kept in base for
  backward compat (formally deprecated, owned by `LinearmodelsMixin`).
- **Structural typing**: `EstimatorProtocol` is a `typing.Protocol` — any class
  implementing `fit/validate/diagnostics/run` + `estimator_id/name/backend`
  satisfies it without inheriting `BaseEstimator`. Enables third-party backends.
- **Runtime checkable**: `isinstance(est, EstimatorProtocol)` works at runtime,
  enabling runner-level backend capability routing.

---

### Architecture Stabilization Milestone 2 — Dataset Abstraction (2026-07-06)

#### Added
- `src/econflow/datasets/` — new package implementing a typed Dataset abstraction
  layer that replaces raw `pd.DataFrame` passing throughout EconFlow.
- `src/econflow/datasets/types.py`: shared value types — `DatasetMetadata`,
  `ProvenanceRecord`, `ColumnInfo`, `VariableRegistry`, `MissingnessSummary`,
  `PanelBalance`, `ValidationStatus`, `SelectionSummary`, `VALID_ROLES`.
- `src/econflow/datasets/base.py`: abstract `Dataset` base class with defensive
  DataFrame storage, `functools.cached_property` lazy diagnostics, and pandas
  pass-through operators (`__getitem__`, `__contains__`, `groupby`, `reset_index`).
- `src/econflow/datasets/panel.py`: `PanelDataset` — primary Dataset type for
  EconFlow. Methods: `to_dataframe()` (P0-safe flat copy), `to_multiindex_dataframe()`
  (equivalent to legacy `_to_panel()`), `rename_entity_col()` (resolves
  country/iso3 bifurcation), `copy()`.
- `src/econflow/datasets/cross_section.py`: `CrossSectionDataset` — one row per
  entity; validates no duplicate entities.
- `src/econflow/datasets/time_series.py`: `TimeSeriesDataset` — one observation
  per time period; validates no duplicate periods.
- `src/econflow/datasets/spatial.py`: `SpatialDataset` — stub with lat/lon
  columns; all spatial methods raise `NotImplementedError` (Milestone 3).
- `src/econflow/datasets/migration.py`: compatibility layer — `from_dataframe()`,
  `to_dataframe()`, `rename_entity_col()`, `@accepts_dataset` decorator.
- `src/econflow/datasets/__init__.py`: exports all public Dataset classes,
  types, and migration utilities.
- `BaseEstimator._resolve_dataframe()` in `estimation/base.py`: single
  Dataset-to-DataFrame conversion point in the estimation layer. Returns
  `to_dataframe()` for `PanelDataset`, `.dataframe` for other `Dataset`
  subclasses, and passes `pd.DataFrame` through unchanged.
- `_resolve_df()` module-level shim in `econometrics/panel.py`: same logic
  applied at the boundary of the legacy estimation functions.
- `load_panel_dataset()` in `data/loaders.py`: new loader that wraps `load_panel()`
  and returns a `PanelDataset`.
- `sample_selection_summary_typed()` in `data/cleaning.py`: returns
  `tuple[pd.DataFrame, SelectionSummary]` — typed alternative to the
  `.attrs`-based legacy function.
- `_get_sel()` helper in `reporting/narrative.py`: extracts sample counts from
  either a legacy `.attrs`-bearing `pd.DataFrame` or a typed `SelectionSummary`.
- `tests/unit/test_datasets.py`: 75 new unit tests covering all Dataset classes,
  value types, migration utilities, `_resolve_dataframe`, and data layer additions.
- `docs/architecture/DATASET_ABSTRACTION.md`: full architecture reference
  including type hierarchy, contract, safety properties, and file manifest.

#### Changed
- `estimation/{ols,fixed_effects,random_effects,first_difference,iv,gmm,quantile}.py`:
  each concrete `fit()` method now calls `data = self._resolve_dataframe(data)` as
  its first statement, enabling `PanelDataset | pd.DataFrame` at all call sites.
- `econometrics/panel.py`: all six public estimation functions now call
  `df = _resolve_df(df)` at entry, accepting `PanelDataset | pd.DataFrame`.
- `reporting/narrative.py`: `write_falsification_results()` now accepts either
  a legacy `pd.DataFrame` (with `.attrs`) or a `SelectionSummary` object.

#### Architecture Notes
- **P0 safety preserved**: `to_dataframe()` returns a byte-for-byte flat copy of
  the original input. The `dropna()` call inside each estimator's `fit()` sees
  exactly the same rows. Econometric results are unchanged.
- **No breaking changes**: all existing callers that pass `pd.DataFrame` continue
  to work without modification.
- **`.attrs` fragility resolved**: `SelectionSummary` carries sample counts in
  typed dataclass fields that survive all pandas operations.


### Sprint 10 — Replication Engine (2026-06-29)

#### Added
- `src/econflow/replication/` — new package implementing a three-command
  automatic replication engine: `inspect` → `reproduce` → `compare`.
- `src/econflow/replication/models.py`: shared dataclasses — `ProjectCheck`,
  `InspectionReport`, `ExecutionStep`, `ExecutionPlan`, `StepResult`,
  `ReplicationResult`, `OutputComparison`, `ComparisonReport`.
- `src/econflow/replication/inspector.py`: `inspect_project()` — 8-point
  pre-flight check (Python version, config files, data file, SHA-256 checksum,
  estimator registry, dependencies).  Resolves data paths relative to the
  config file's directory (CWD-independent).
- `src/econflow/replication/planner.py`: `build_plan()` — deterministic
  `ExecutionPlan` of validate + run steps.
- `src/econflow/replication/executor.py`: `execute_plan()` — subprocess
  isolation; captures stdout/stderr per step; times each step.
- `src/econflow/replication/comparator.py`: `compare_outputs()` — toleranced
  file-type-aware comparison (CSV numeric, LaTeX structural, JSON deep).
  New `baseline_only` parameter: when `True`, extra replica files are silently
  ignored (used by `reproduce` to avoid spurious warnings from intermediate
  files).
- `src/econflow/replication/reporter.py`: `ReproducibilityReport` — bundles
  inspection + execution + comparison into Markdown + JSON outputs.
- `src/econflow/commands/inspect.py`: `run_inspect()` — `econflow inspect`.
- `src/econflow/commands/reproduce.py`: `run_reproduce()` — `econflow
  reproduce`; 4-step workflow (inspect → plan → execute → compare); cleans
  replica tables before each run for idempotent comparison; compares
  `original_outputs/tables/` against `outputs/tables/`.
- `src/econflow/commands/compare.py`: `run_compare()` — `econflow compare`.
- `src/econflow/cli.py`: three new commands — `inspect`, `reproduce`, `compare`.
- `examples/blind_replication/` — self-contained blind replication example:
  6 firms × 15 years synthetic investment panel (DGP: invest = 1.8×market_value
  + 0.6×capital_stock + firm FE + ε, seed=7); three estimators (pooled OLS,
  entity FE, two-way FE); reference outputs; `econflow reproduce` returns PASS.
- `docs/architecture/REPLICATION_ENGINE.md` — 313-line architecture document.
- `tests/replication/` — 93 unit/integration tests + 15 CLI tests covering all
  replication modules (971 total tests).

#### Fixed
- `src/econflow/pipeline_generic.py`: resolved `data.path` and `outputs.base_dir`
  relative to their respective config files' directories rather than CWD.
  This makes `econflow run` reproducible from any working directory.
- `src/econflow/pipeline_generic.py`: fixed double-extension bug where
  `comparison_table.csv.csv` was written instead of `comparison_table.csv`
  when the filename in `outputs.yaml` already included the `.csv` extension.
- `src/econflow/commands/validate.py`: estimator IDs now compared
  case-insensitively (registry uses lowercase; YAML may use uppercase `OLS`,
  `FE`).  Data path resolved relative to config file directory.
- `src/econflow/replication/inspector.py`: data path resolved relative to
  config file directory (same convention as pipeline_generic).
- `examples/getting_started/config/config.yaml`: data path changed from
  repo-root-relative `examples/getting_started/data/grunfeld.csv` to
  config-dir-relative `../data/grunfeld.csv`.
- `examples/getting_started/config/outputs.yaml`: `base_dir` changed from
  `examples/getting_started/outputs` to `../outputs`.
- `examples/blind_replication/config/config.yaml`: data path changed to
  `../data/investment_panel.csv` (config-dir-relative).
- `examples/blind_replication/config/outputs.yaml`: `base_dir` changed to
  `../outputs`.
- `tests/replication/test_planner.py`: updated `test_run_command_contains_output_dir`
  → `test_run_command_contains_config_paths` to reflect that `econflow run`
  does not accept `--output-dir`.

### Sprint 8 — Data Ecosystem & Connector Framework (2026-06-28)

#### Added
- `src/econflow/ingestion/connectors/fred.py`: `FREDConnector` — new connector
  for the St. Louis Fed FRED API.  Supports multiple series IDs, date ranges,
  frequency aggregation, and missing-value normalisation (`"."` → `""`).
  API key via `params["api_key"]` or `FRED_API_KEY` environment variable.
  Registered as `"fred"` with `status="implemented"`.
- `src/econflow/ingestion/manifest.py`: `DatasetManifest` + `ManifestEntry` —
  project-level registry of all datasets acquired during a pipeline run.
  Records connector ID, cache key, parameters, metadata, validation outcome,
  citation string, and dataset version for each entry.  Atomic JSON writes.
  Schema version `"1.0.0"`.
- `AbstractConnector.citation()` and `AbstractConnector.version()` — new
  concrete methods on the base class backed by class-level `_CITATION` and
  `_VERSION` attributes.  All built-in connectors now expose these.
- `src/econflow/commands/fetch_cmd.py`: `run_fetch()` — `econflow fetch`
  command logic.  Connects, downloads, validates, prints metadata summary,
  optionally writes manifest entry.
- `src/econflow/commands/cache_cmd.py`: `run_cache_list()`,
  `run_cache_inspect()`, `run_cache_clear()`, `run_cache_purge()` — full cache
  management CLI backend.
- `src/econflow/commands/datasets_cmd.py`: `run_datasets()` — lists all
  registered connectors with status and notes.
- `src/econflow/cli.py` — three new top-level commands: `econflow fetch`,
  `econflow datasets`; one new sub-app: `econflow cache {list,inspect,clear,purge}`.
- `docs/architecture/DATA_ECOSYSTEM.md` — 332-line architecture document
  covering connector interface, registry, cache, manifest, validation, citation
  system, technical debt, and Sprint 9 recommendations.
- `tests/unit/test_ingestion_connectors.py` — 40+ unit tests covering all five
  connectors, `AbstractConnector` citation/version interface, registry
  integration, and `DatasetManifest`.
- `tests/integration/test_ingestion_pipeline.py` — 20+ integration tests:
  offline cache cycle, checksum verification, corruption detection, manifest
  building, CLI fetch integration, regression (cache key stability).

#### Changed
- `src/econflow/ingestion/connectors/oecd.py`: replaced `NotImplementedError`
  stub with full SDMX-JSON implementation.  Parses dimension metadata to decode
  country/time/measure keys from series key strings.
- `src/econflow/ingestion/connectors/pwt.py`: replaced `NotImplementedError`
  stub with full Excel-download implementation.  Streams `.xlsx` from Harvard
  Dataverse, parses `data` sheet via `openpyxl`, writes wide-format CSV,
  optionally subsets to requested variable codes.
- `src/econflow/ingestion/connectors/__init__.py`: added `FREDConnector` import.
- `src/econflow/ingestion/__init__.py`: added `DatasetManifest`, `ManifestEntry`
  to public API and `__all__`.



### Sprint 7 — Research Integrity & Reproducibility Framework (2026-06-28)

#### Added
- `src/econflow/integrity/` — new sub-package providing the full Research
  Integrity & Reproducibility Framework.
- `src/econflow/integrity/fingerprint.py`: `EnvironmentFingerprint` (git,
  Python, platform, package versions), `DataFingerprint` (SHA-256, row/column
  counts for CSV/Parquet), `ConfigFingerprint` (SHA-256 + preview).
  Re-uses existing helpers from `provenance.py` — no duplication.
- `src/econflow/integrity/certificate.py`: `ReproducibilityCertificate`
  dataclass — bundles all fingerprints and integrity check results into a
  JSON-serialisable record.  `overall_status` is aggregated from check results
  (`"pass"` / `"warn"` / `"fail"`).  Schema version `"1.0.0"`.  Atomic writes
  via `os.fsync()` + `Path.replace()`.  `CertificateError` on I/O failure.
- `src/econflow/integrity/drift.py`: `DriftItem`, `DriftReport`,
  `detect_drift()`.  Compares two certificate dicts (or JSON paths) on 8 axes:
  git commit, dirty flag, package versions, data SHA-256, data row count, data
  file presence, and config SHA-256.  Severity: `"none"` / `"warn"` / `"fail"`.
- `src/econflow/integrity/package.py`: `ReplicationPackage` — chainable builder
  that writes a journal-ready directory (`certificate.json`,
  `environment.txt`, `config/`, `scripts/`, auto-generated `README.md`,
  `manifest.json`).
- `src/econflow/integrity/checks/base.py`: `BaseIntegrityCheck` ABC and
  `IntegrityCheckResult` dataclass.  Same pattern as `BaseDiagnostic`.
- `src/econflow/integrity/checks/registry.py`: `@register_integrity_check()`,
  `get_check()`, `list_checks()`, `unregister_check()`.  Raises `RegistryError`
  on duplicate or unknown id.
- `src/econflow/integrity/checks/plugins/coefficient_stability.py`:
  `CoefficientStabilityCheck` — flags extreme (`> fail_threshold`) or non-finite
  coefficient values.
- `src/econflow/integrity/checks/plugins/sample_size.py`:
  `SampleSizeCheck` — verifies `nobs` meets minimum thresholds.
- `src/econflow/integrity/checks/plugins/pvalue_distribution.py`:
  `PvalueDistributionCheck` — flags identical p-values, all < 0.001,
  all > 0.99, or suspiciously high fraction significant.
- `src/econflow/commands/certify.py`: `run_certify()` — builds and saves a
  certificate, optionally running all integrity checks.
- `src/econflow/commands/verify.py`: `run_verify()` — loads baseline certificate
  and compares against current certificate or live environment.
- `src/econflow/commands/package_cmd.py`: `run_package()` — builds a replication
  package directory.
- `src/econflow/cli.py`: three new commands — `econflow certify`,
  `econflow verify`, `econflow package`.
- `src/econflow/core/exceptions.py`: `IntegrityError` and `CertificateError`
  added to the exception hierarchy under `EconFlowCoreError`.
- **90 new tests** across 5 new test modules:
  `tests/unit/test_integrity_fingerprint.py` (25 tests),
  `tests/unit/test_integrity_certificate.py` (18 tests),
  `tests/unit/test_integrity_drift.py` (15 tests),
  `tests/unit/test_integrity_checks.py` (22 tests),
  `tests/integration/test_integrity_pipeline.py` (10 tests).
- `docs/architecture/INTEGRITY_FRAMEWORK.md`: architecture documentation
  for Sprint 7 (296 lines).

### Sprint 6 — Reporting & Publication Engine (2026-06-28)

#### Added
- `src/econflow/outputs/model.py`: `ReportTable` and `ReportFigure` dataclasses
  with full serialisation (`to_dict` / `to_json` / `from_dict`).  `TableRow`
  carries pre-formatted strings — renderers handle structure, not content.
- `src/econflow/outputs/registry.py`: `@register_renderer()` decorator,
  `get_renderer()`, `list_renderers()`, `unregister_renderer()`.  Raises
  `RegistryError` on duplicate or unknown id.
- `src/econflow/outputs/base.py`: `BaseRenderer` ABC with abstract `render()`
  and concrete `render_to_file()`.  `RendererError` for typed failure reporting.
- `src/econflow/outputs/renderers/`: 5 built-in renderers — `CSVRenderer`,
  `JSONRenderer`, `MarkdownRenderer` (GFM), `HTMLRenderer`, `LaTeXRenderer`
  (booktabs).  All self-register at import via `@register_renderer()`.
- `src/econflow/outputs/tables/regression.py`: `build_regression_table()` —
  full implementation.  Coefficient rows with SE sub-rows, significance stars
  (configurable thresholds), footer stats (N, R², estimator, FE indicators),
  column labels, variable ordering and display labels.
- `src/econflow/outputs/tables/summary_stats.py`: `build_summary_stats_table()`
  — full implementation.  N, Mean, Std Dev, Min, configurable percentiles, Max.
  Excludes non-numeric columns automatically.
- `src/econflow/outputs/tables/`: 6 complete-interface stubs — `balance.py`,
  `correlation.py`, `robustness.py`, `sensitivity.py`, `falsification.py`,
  `heterogeneity.py`.  Each module documents the full intended interface.
- `src/econflow/outputs/figures/base.py`: `FigureBuilder` ABC.
- `src/econflow/outputs/figures/coefficient_plot.py`: `CoefficientPlot` — full
  implementation.  Forest-style coefficient plot data with CI bounds from
  configurable z-score, sort options, variable subset and label mapping.
- `src/econflow/outputs/figures/ci_plot.py`: `CIPlot` — full implementation.
  Focal-variable CI comparison across specifications.
- `src/econflow/outputs/figures/`: 4 stubs — `ResidualFigure`,
  `DistributionFigure`, `EventStudyFigure`, `RobustnessComparisonFigure`.
- `src/econflow/outputs/diagnostics_report.py`: `build_diagnostics_report()` —
  converts `list[DiagnosticResult]` to a `ReportTable` with Pass/Fail/N/A
  conclusions, optional grouping by estimator.
- `src/econflow/outputs/bundle.py`: `PublicationBundle` — chainable API for
  collecting tables and figures and writing them to a structured output
  directory with `manifest.json`.
- `src/econflow/outputs/__init__.py` (rewrite): complete public API re-exporting
  all model objects, registry functions, table builders, fig