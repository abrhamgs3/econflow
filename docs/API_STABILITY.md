# EconFlow Public API Stability Reference

**Version:** 1.0-beta  
**Date:** 2026-07-06  
**Maintainer:** EconFlow Core Team

This document classifies every symbol that EconFlow exports as one of four tiers:

| Tier | Meaning |
|------|---------|
| **Stable** | Will not break between v1.x minor releases. Breaking changes require a v2.0 major release and a deprecation cycle of at least one minor version. |
| **Experimental** | Implemented and usable, but the interface may change in a minor release. Breaking changes carry a `DeprecationWarning` for one minor version before removal. |
| **Internal** | Not part of the public contract. May change or be removed in any release. Do not import from paths prefixed with `_`. |
| **Deprecated** | Still works but will be removed in the stated future version. A `DeprecationWarning` is raised on use. |

---

## Exception Hierarchy

All public exceptions inherit from `EconFlowError`. A single `except EconFlowError`
clause catches every exception that EconFlow can raise.

```
Exception
└── EconFlowError                       (econflow.exceptions)
    ├── DataValidationError
    ├── MergeError
    ├── ModelSpecificationError
    ├── PipelineError                   (pipeline-layer)
    └── EconFlowCoreError               (econflow.core.exceptions)
        ├── ConfigurationError
        │   └── MissingConfigKeyError
        ├── RegistryError
        │   └── ProjectNotFoundError
        ├── PipelineError               (core-layer, different class)
        │   └── StageExecutionError
        ├── IngestionError
        │   ├── DownloadError
        │   └── CacheError
        ├── ProcessingError
        │   ├── HarmonisationError
        │   └── TransformationError
        ├── EstimationError
        │   └── ConvergenceError
        ├── DiagnosticsError
        ├── OutputError
        └── IntegrityError
            └── CertificateError
```

> **Note on PipelineError name collision:** `econflow.exceptions.PipelineError` and
> `econflow.core.exceptions.PipelineError` are distinct classes covering different
> semantic layers. Both are caught by `except EconFlowError`. Prefer the qualified
> import path to disambiguate.

---

## Stable API

### `econflow` (top level)

| Symbol | Type | Notes |
|--------|------|-------|
| `__version__` | `str` | Package version string |
| `EconFlowError` | exception | Root exception — catches all EconFlow errors |
| `EconFlowCoreError` | exception | Root for scaffold/core exceptions; subclass of `EconFlowError` |
| `DataValidationError` | exception | Raised when panel data fails schema checks |
| `MergeError` | exception | Raised when a data merge cannot be completed |
| `ModelSpecificationError` | exception | Raised for invalid econometric specifications |
| `PipelineError` | exception | Raised for pipeline orchestration failures (pipeline layer) |

### `econflow.estimation`

| Symbol | Type | Notes |
|--------|------|-------|
| `BaseEstimator` | abstract class | Extend to implement an estimator plugin |
| `EstimatorProtocol` | Protocol | Structural protocol for type checking |
| `EstimationResult` | dataclass | Returned by every `fit()` call |
| `DiagnosticResult` | dataclass | Returned by every `diagnostics()` call |
| `EstimatorError` | exception | Raised by estimator implementations |
| `register_estimator` | decorator | Register an estimator plugin |
| `get_estimator` | function | Retrieve an estimator class by ID |
| `list_estimators` | function | List all registered estimators with metadata |
| `list_by_backend` | function | Filter registered estimators by backend |
| `unregister_estimator` | function | Remove an estimator (testing only) |
| `PooledOLS` | estimator | Pooled OLS via `linearmodels` |
| `EntityFE` | estimator | Entity fixed effects via `linearmodels` |
| `TwoWayFE` | estimator | Two-way fixed effects via `linearmodels` |
| `RandomEffects` | estimator | Random effects (Swamy-Arora GLS) via `linearmodels` |
| `FirstDifference` | estimator | First-difference estimator via `linearmodels` |
| `IV2SLS` | estimator | Two-stage least squares via `linearmodels` |
| `BackendCapabilities` | dataclass | Describes what a backend supports |
| `BACKEND_LINEARMODELS` | `str` constant | `"linearmodels"` |
| `BACKEND_STATSMODELS` | `str` constant | `"statsmodels"` |
| `BACKEND_PYFIXEST` | `str` constant | `"pyfixest"` |
| `BACKEND_DOUBLEML` | `str` constant | `"doubleml"` |
| `BACKEND_PYMC` | `str` constant | `"pymc"` |
| `BACKEND_CUSTOM` | `str` constant | `"custom"` |
| `KNOWN_BACKENDS` | `frozenset` | All recognised backend identifiers |

### `econflow.diagnostics`

| Symbol | Type | Notes |
|--------|------|-------|
| `BaseDiagnostic` | abstract class | Extend to implement a diagnostic plugin |
| `DiagnosticError` | exception | Raised when a diagnostic test cannot be computed |
| `register_diagnostic` | decorator | Register a diagnostic plugin |
| `get_diagnostic` | function | Retrieve a diagnostic class by ID |
| `list_diagnostics` | function | List all registered diagnostics with metadata |
| `unregister_diagnostic` | function | Remove a diagnostic (testing only) |

### `econflow.outputs`

| Symbol | Type | Notes |
|--------|------|-------|
| `ReportTable` | dataclass | Content container for a publication table |
| `ReportFigure` | dataclass | Content container for a publication figure |
| `TableRow` | dataclass | A single row in a `ReportTable` |
| `RendererError` | exception | Raised when a renderer fails to produce its artifact |
| `register_renderer` | decorator | Register a renderer plugin |
| `get_renderer` | function | Retrieve a renderer class by ID |
| `list_renderers` | function | List all registered renderers with metadata |
| `unregister_renderer` | function | Remove a renderer (testing only) |
| `build_regression_table` | function | Build a standard regression results table |
| `build_summary_stats_table` | function | Build a summary statistics table |
| `build_balance_table` | function | Build a balance/comparison table |
| `build_correlation_table` | function | Build a correlation matrix table |
| `build_robustness_table` | function | Build a robustness checks table |
| `build_sensitivity_table` | function | Build a sensitivity analysis table |
| `build_falsification_table` | function | Build a falsification/placebo table |
| `build_heterogeneity_table` | function | Build a heterogeneity analysis table |
| `CoefficientPlot` | figure builder | Coefficient plot with confidence intervals |
| `CIPlot` | figure builder | Confidence interval comparison plot |
| `build_diagnostics_report` | function | Build a diagnostic results table |
| `PublicationBundle` | class | Chainable API for assembling a full publication output set |

### `econflow.integrity`

| Symbol | Type | Notes |
|--------|------|-------|
| `ReproducibilityCertificate` | class | Serialisable record of a full pipeline run |
| `CERTIFICATE_SCHEMA_VERSION` | `str` | Current certificate schema version |
| `BaseIntegrityCheck` | abstract class | Extend to implement an integrity check plugin |
| `IntegrityCheckResult` | dataclass | Result of a single integrity check |
| `register_integrity_check` | decorator | Register an integrity check plugin |
| `get_check` | function | Retrieve an integrity check class by ID |
| `list_checks` | function | List all registered integrity checks |
| `unregister_integrity_check` | function | Remove an integrity check (testing only) |
| `DriftReport` | dataclass | Result of comparing two certificates |
| `DriftItem` | dataclass | A single changed item in a `DriftReport` |
| `detect_drift` | function | Compare two certificates and return a `DriftReport` |
| `ConfigFingerprint` | dataclass | SHA-256 snapshot of the configuration files |
| `DataFingerprint` | dataclass | SHA-256 snapshot of data files |
| `EnvironmentFingerprint` | dataclass | Snapshot of the Python environment |
| `ReplicationPackage` | class | Build journal-ready archival bundles |

### `econflow.ingestion`

| Symbol | Type | Notes |
|--------|------|-------|
| `AbstractConnector` | abstract class | Extend to implement a data connector plugin |
| `ConnectorError` | exception | Raised by connector implementations |
| `CacheManager` | class | Deterministic SHA-256-keyed download cache |
| `CacheCorruptionError` | exception | Raised when cached data fails hash verification |
| `DatasetMetadata` | dataclass | Provenance record for a downloaded dataset |
| `DatasetManifest` | class | JSON-serialisable record of all datasets in a run |
| `ManifestEntry` | dataclass | A single entry in a `DatasetManifest` |
| `register_connector` | decorator | Register a data connector plugin |
| `get_connector` | function | Retrieve a connector class by ID |
| `list_connectors` | function | List all registered connectors with metadata |
| `unregister_connector` | function | Remove a connector (testing only) |
| `DataValidator` | class | Structural validation for panel CSVs |
| `DataValidationConfig` | dataclass | Configuration for `DataValidator` |
| `DataValidationReport` | dataclass | Structured report from `DataValidator` |
| `ValidationIssue` | dataclass | A single issue found during validation |

### `econflow.replication`

| Symbol | Type | Notes |
|--------|------|-------|
| `inspect_project` | function | Run pre-flight checks on a project directory |
| `InspectionReport` | dataclass | Structured result of `inspect_project` |
| `ProjectCheck` | dataclass | A single check in an `InspectionReport` |
| `build_plan` | function | Build an `ExecutionPlan` from an `InspectionReport` |
| `ExecutionPlan` | dataclass | Ordered list of steps for a replication run |
| `ExecutionStep` | dataclass | A single step in an `ExecutionPlan` |
| `execute_plan` | function | Execute an `ExecutionPlan` and return a `ReplicationResult` |
| `ReplicationResult` | dataclass | Outcome of executing a replication plan |
| `StepResult` | dataclass | Outcome of a single `ExecutionStep` |
| `compare_outputs` | function | Compare output directories between two runs |
| `ComparisonReport` | dataclass | Structured result of `compare_outputs` |
| `OutputComparison` | dataclass | Comparison of a single output file |
| `DEFAULT_TOLERANCE` | `float` | Default numeric tolerance for output comparison |
| `ReproducibilityReport` | class | Bundled report (inspection + execution + comparison) |

### `econflow.config`

| Symbol | Type | Notes |
|--------|------|-------|
| `ProjectConfig` | Pydantic model | Validated `config.yaml` schema |
| `ModelsConfig` | Pydantic model | Validated `models.yaml` schema |
| `OutputsConfig` | Pydantic model | Validated `outputs.yaml` schema |
| `ModelSpec` | Pydantic model | A single model specification within `ModelsConfig` |
| `ConfigLinter` | class | 10-rule configuration linter |
| `LintIssue` | dataclass | A single linting issue with severity, message, and fix hint |
| `generate_config_reference` | function | Render Markdown/text config docs from the live schema |
| `write_config_reference` | function | Write config reference to a file |

---

## Experimental API

These symbols are implemented and recommended for use, but their signatures or
behaviour may change in a v1.x minor release. Changes will carry a
`DeprecationWarning` for one minor version before removal.

### `econflow.estimation`

| Symbol | Status | Notes |
|--------|--------|-------|
| `LinearmodelsMixin` | Experimental | Backend mixin; interface may be revised in v1.1 |
| `StatsmodelsMixin` | Experimental | Backend mixin; interface may be revised in v1.1 |
| `PyfixestMixin` | Experimental | Backend mixin; interface may be revised in v1.1 |
| `DoubleMLMixin` | Experimental | Backend mixin; interface may be revised in v1.1 |
| `PyMCMixin` | Experimental | Backend mixin; interface may be revised in v1.1 |
| `SystemGMM` | Experimental — stub | Raises `NotImplementedError`; use is blocked by `econflow validate` |
| `PanelQuantile` | Experimental — stub | Raises `NotImplementedError`; use is blocked by `econflow validate` |

### `econflow.outputs`

| Symbol | Status | Notes |
|--------|--------|-------|
| `build_sensitivity_table` | Experimental | Signature may gain parameters in v1.1 |
| `build_falsification_table` | Experimental | Signature may gain parameters in v1.1 |
| `build_heterogeneity_table` | Experimental | Signature may gain parameters in v1.1 |

---

## Internal API

Do not import from the following paths. They are implementation details and may
change in any release without notice.

| Path | Reason |
|------|--------|
| `econflow.core.pipeline` | Abstract base raises `NotImplementedError`; not connected to any live code path |
| `econflow.core.config` | `load_config()` raises `NotImplementedError`; pipeline reads YAML directly |
| `econflow.core.registry` | Internal registry state; access via `econflow.estimation.get_estimator` etc. |
| `econflow.commands.*` | CLI command implementations; use the `econflow` CLI directly |
| `econflow.config.linter._*` | Private linting rule helpers |
| `econflow.estimation.backends.*` | Internal mixin implementations; import mixins via `econflow.estimation` |
| `econflow.diagnostics.plugins.*` | Plugin modules; import diagnostics via `econflow.diagnostics` |
| `econflow.integrity.checks.plugins.*` | Plugin modules; import checks via `econflow.integrity` |
| `econflow.ingestion.connectors.*` | Connector modules; import connectors via `econflow.ingestion` |
| `econflow.outputs.renderers.*` | Renderer modules; import renderers via `econflow.outputs` |
| `econflow.pipeline` | Legacy paper-specific pipeline; use `pipeline_generic.run_from_config` |
| `econflow.pipeline_generic` | Direct module use; prefer the `econflow run` CLI command |
| `econflow.cli_scaffold.*` | Development scaffold; not shipped in wheel |
| `econflow.processing.*` | Not yet implemented (all stubs) |
| `econflow.sensitivity.*` | Not yet implemented (all stubs) |
| `econflow.reporting.*` | Not yet implemented (all stubs) |

---

## Deprecated API

| Symbol | Deprecated in | Removed in | Replacement |
|--------|--------------|------------|-------------|
| `econflow.AIProdError` | v0.1.0 | v0.3.0 | `econflow.EconFlowError` |
| `econflow.core.exceptions.APRPError` | v0.1.0 | v0.3.0 | `econflow.core.exceptions.EconFlowCoreError` |
| `econflow.estimation.register` | v1.0 | v2.0 | `econflow.estimation.register_estimator` |
| `econflow.estimation.unregister` | v1.0 | v2.0 | `econflow.estimation.unregister_estimator` |
| `econflow.ingestion.register` | v1.0 | v2.0 | `econflow.ingestion.register_connector` |
| `econflow.ingestion.unregister` | v1.0 | v2.0 | `econflow.ingestion.unregister_connector` |
| `econflow.integrity.unregister_check` | v1.0 | v2.0 | `econflow.integrity.unregister_integrity_check` |

---

## Versioning Policy

EconFlow follows [Semantic Versioning](https://semver.org/).

- **v1.0 → v1.x:** No breaking changes to Stable API. Experimental API may change
  with one-version `DeprecationWarning`. New symbols may be added.
- **v1.x → v2.0:** Deprecated symbols removed. Experimental symbols may be promoted
  to Stable or removed. Internal paths may change without notice.
- **Pre-release (current):** The beta phase ends when all Experimental-stub items
  (`SystemGMM`, `PanelQuantile`) are either implemented or removed.

---

## Plugin Entry Points

Third-party packages may register plugins via setuptools entry points:

```toml
[project.entry-points."econflow.plugins"]
my_estimator = "my_package.my_module"
```

The module `my_package.my_module` is imported automatically when
`econflow.estimation` is first loaded. It should call `register_estimator` (or
another `register_*` decorator) at module level to register its plugin.

For estimators, connectors, diagnostics, integrity checks, renderers, and figure
builders, use the corresponding `register_*` function from the relevant package.
All `register_*` functions follow the same signature pattern:

```python
@register_estimator("my_id", label="Human Name", status="implemented")
class MyEstimator(BaseEstimator):
    ...
```

---

*Last reviewed: 2026-07-06. Update this document whenever __all__ lists change.*
