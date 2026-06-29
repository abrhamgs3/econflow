# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
  all model objects, registry functions, table builders, figure builders,
  diagnostics builder, and `PublicationBundle`.
- `src/econflow/commands/report.py`: `run_report()` backing function for the
  `econflow report` CLI command.
- `src/econflow/cli.py`: `econflow report` command registered via
  `@app.command()`.
- `docs/architecture/REPORTING_ENGINE.md`: full architecture documentation for
  Sprint 6 (454 lines).
- **158 new tests** across 5 new test modules:
  `tests/unit/test_report_model.py`,
  `tests/unit/test_renderer_registry.py`,
  `tests/unit/test_renderers.py`,
  `tests/unit/test_table_builders.py`,
  `tests/unit/test_figure_builders.py`,
  `tests/integration/test_outputs_pipeline.py`.

#### Fixed
- `src/econflow/outputs/diagnostics_report.py`: `_conclusion()` uses
  `DiagnosticResult.level` (not the non-existent `passed`/`message` fields);
  estimator grouping uses `extra["estimator_id"]` instead of missing
  `estimator_id` attribute.


### Sprint 5 — Estimation Framework (2026-06-28)

#### Added
- `src/econflow/estimation/result.py`: `EstimationResult` immutable dataclass with
  full provenance, `tvalues` property, `summary_frame()`, `to_dict()`, `to_json()`.
  `DiagnosticResult` dataclass with `to_dict()`, `to_json()`, `from_dict()`.
- `src/econflow/estimation/registry.py`: `@register()` decorator and
  `get_estimator()` / `list_estimators()` / `unregister()`.  Estimators
  self-register at import time.  Raises `RegistryError` (not `ValueError`) on
  duplicate or unknown id.
- `src/econflow/estimation/base.py` (rewrite): `BaseEstimator` abstract class with
  `validate()`, `fit()`, `diagnostics()`, concrete `run()` chain, and helper
  methods `_require_params()`, `_require_columns()`, `_to_panel()`,
  `_provenance_stamp()`.  `EstimatorError` for typed failure reporting.
  Re-exports `EstimationResult` and `DiagnosticResult` for backward compatibility.
- `src/econflow/estimation/ols.py`: `PooledOLS` — `linearmodels.PooledOLS`.
  Registers as `"ols"`.
- `src/econflow/estimation/fixed_effects.py`: `EntityFE` (`"fe"`) and `TwoWayFE`
  (`"twfe"`) via `linearmodels.PanelOLS`.
- `src/econflow/estimation/random_effects.py`: `RandomEffects` (`"re"`) via
  `linearmodels.RandomEffects`.
- `src/econflow/estimation/first_difference.py`: `FirstDifference` (`"fd"`) via
  `linearmodels.FirstDifferenceOLS`.
- `src/econflow/estimation/iv.py`: `IV2SLS` (`"iv"`) via `linearmodels.iv.IV2SLS`.
  Enforces order condition; correctly splits exogenous and endogenous regressors.
- `src/econflow/estimation/gmm.py`: `SystemGMM` (`"gmm"`) — stub.
- `src/econflow/estimation/quantile.py`: `PanelQuantile` (`"quantile"`) — stub.
- `src/econflow/estimation/__init__.py` (rewrite): full public API; imports all
  built-in estimators to trigger `@register()` calls.
- `src/econflow/diagnostics/base.py`: `BaseDiagnostic` ABC with `run()`,
  `supports()`, `_not_applicable()`.  `DiagnosticError` exception.
- `src/econflow/diagnostics/registry.py`: `@register_diagnostic()`,
  `get_diagnostic()`, `list_diagnostics()`, `unregister_diagnostic()`.
  Raises `RegistryError` on duplicate/unknown id.
- `src/econflow/diagnostics/__init__.py` (rewrite): full public API; imports all
  built-in plugins.
- `src/econflow/diagnostics/plugins/hausman.py`: Hausman endogeneity test.
  Regularises near-singular covariance difference matrix.  Registers as
  `"hausman"`.
- `src/econflow/diagnostics/plugins/breusch_pagan.py`: Breusch-Pagan LM
  heteroskedasticity test via `statsmodels`.  Registers as `"breusch_pagan"`.
- `src/econflow/diagnostics/plugins/pesaran_cd.py`: Pesaran (2004) cross-sectional
  dependence CD test.  Registers as `"pesaran_cd"`.
- `src/econflow/diagnostics/plugins/vif.py`: Variance Inflation Factor check via
  `statsmodels` with numpy fallback.  Registers as `"vif"`.
- `src/econflow/diagnostics/plugins/wooldridge.py`: stub — registers as
  `"wooldridge"`.
- `src/econflow/diagnostics/plugins/serial_correlation.py`: stub — registers as
  `"serial_correlation"`.
- `tests/unit/test_estimation_result.py`: 27 tests covering `EstimationResult`
  and `DiagnosticResult` construction, serialisation, and mutability.
- `tests/unit/test_estimation_registry.py`: 21 tests covering `@register()`,
  `get_estimator()`, `list_estimators()`, `unregister()`, and all 8 built-in
  estimator registrations.
- `tests/unit/test_estimation_base.py`: 29 tests covering `EstimatorError`,
  `BaseEstimator` abstract enforcement, `run()` chain, helpers, and backward-compat
  re-exports.
- `tests/unit/test_diagnostic_registry.py`: 23 tests covering
  `@register_diagnostic()`, `BaseDiagnostic`, `DiagnosticError`, and all 6 built-in
  plugin registrations.
- `tests/integration/test_estimator_run.py`: 21 end-to-end tests — each implemented
  estimator run on a 200-row synthetic panel; stubs verified to raise
  `NotImplementedError`.
- `tests/integration/test_diagnostic_run.py`: 24 end-to-end tests — Hausman,
  Breusch-Pagan, Pesaran CD, and VIF on real `EstimationResult` objects; stubs
  verified; registry round-trip tested.
- `docs/architecture/ESTIMATION_FRAMEWORK.md`: full architecture document.

#### Changed
- `src/econflow/commands/info.py`: removed hard-coded `ESTIMATOR_REGISTRY` and
  `DATA_CONNECTOR_REGISTRY` lists (H1 tech debt).  Both tables now driven by
  `list_estimators()` and `list_connectors()` from the live registries.
  `ESTIMATOR_REGISTRY` is retained as a module-level alias (calls live registry)
  for backward compatibility.
- `src/econflow/commands/validate.py`: `_SUPPORTED_ESTIMATORS` now derived from
  `list_estimators()` instead of the hand-coded list in `info.py`.
- `src/econflow/estimation/registry.py`: raises `RegistryError` (not `ValueError`
  / `KeyError`) for duplicate registration and unknown id lookups. `unregister()`
  now raises `RegistryError` on unknown id (was silent).
- `src/econflow/diagnostics/registry.py`: same `RegistryError` upgrade.
  `unregister_diagnostic()` now raises on unknown id.
- `src/econflow/estimation/base.py`: `_provenance_stamp()` now includes
  `econflow_version` field.
- `src/econflow/diagnostics/base.py`: `_not_applicable()` now returns
  `level="skip"` (was `"info"`).
- `tests/unit/test_cmd_info.py`: updated to use `_load_connector_registry()` and
  lowercase estimator IDs (`"ols"`, `"fe"`).
- `tests/unit/test_cmd_validate.py`: updated to use lowercase estimator IDs.

---

### Sprint 4 — Data Ecosystem (2026-06-27)

#### Added
- `src/econflow/ingestion/metadata.py`: `DatasetMetadata` immutable dataclass
  with full JSON round-trip serialization and a `DatasetMetadata.now()` factory.
- `src/econflow/ingestion/registry.py`: `@register()` decorator and
  `get_connector()` / `list_connectors()` / `unregister()` functions.
  Connectors self-register at import time; no manual registration steps needed.
- `src/econflow/ingestion/base.py` (rewritten): `AbstractConnector` with five
  abstract methods (`connect`, `download`, `validate`, `metadata`, `cache_key`)
  and a `fetch()` convenience wrapper.  `ConnectorError` for typed failure reporting.
- `src/econflow/ingestion/cache.py` (rewritten): `CacheManager` — slot-based
  filesystem cache at `<cache_dir>/<key>/data.csv` + `meta.json`.
  SHA-256 verification on retrieval, `CacheCorruptionError` on hash mismatch.
- `src/econflow/ingestion/validation.py`: `DataValidator` with six configurable
  checks (V-00 through V-06).  `DataValidationConfig`, `DataValidationReport`,
  and `ValidationIssue` provide structured, serializable results.
- `src/econflow/ingestion/connectors/csv_connector.py`: `LocalCSVConnector` —
  full implementation.  Reads any UTF-8 CSV; integrates with `CacheManager`;
  registers as `"csv"`.
- `src/econflow/ingestion/connectors/world_bank.py`: `WorldBankConnector` —
  full implementation.  Downloads indicator time series from the World Bank
  API v2 (no API key required), paginates, writes tidy long-format CSV.
  Registers as `"world_bank"`.
- `src/econflow/ingestion/connectors/oecd.py`: `OECDConnector` — complete
  interface with detailed stub.  Full implementation plan documented in module
  docstring.  Registers as `"oecd"` with `status="stub"`.
- `src/econflow/ingestion/connectors/pwt.py`: `PennWorldTablesConnector` —
  complete interface with detailed stub.  Full implementation plan documented.
  Registers as `"pwt"` with `status="stub"`.
- `src/econflow/ingestion/__init__.py` (rewritten): exposes full public API —
  `AbstractConnector`, `ConnectorError`, `CacheManager`, `CacheCorruptionError`,
  `DatasetMetadata`, `register`, `get_connector`, `list_connectors`,
  `DataValidator`, `DataValidationConfig`, `DataValidationReport`, `ValidationIssue`.
- `src/econflow/provenance.py`: `ProvenanceRecorder.record_dataset(metadata)`
  appends a dataset provenan