# EconFlow — Repository-Wide Public API Review

**Document type:** Technical Steering Committee Review  
**Date:** 2026-06-28  
**Scope:** Every importable name across `src/econflow/`, all CLI commands, all configuration
schemas, all JSON artifact schemas  
**Method:** Static analysis of all `__init__.py` `__all__` lists, all base class
definitions, all registry exports, and all CLI command signatures  
**Status:** Authoritative pre-v1.0 record

---

## Executive Summary

EconFlow currently exposes **three distinct API layers** that differ radically in
maturity:

1. **The platform API** — `estimation`, `diagnostics`, `ingestion`, `outputs`,
   `integrity`. Built in Sprints 4–8 with clear plugin contracts, consistent patterns,
   and `__all__` declarations. This is the API that should become the v1.0 public
   surface.

2. **The legacy paper API** — `data`, `econometrics`, `visualization`, `features`,
   `reporting`, `processing`, `sensitivity`. Built in Sprint 1–2 for the AI &
   Productivity paper. Contains paper-specific function names (`ai_tfp_scatter`,
   `run_tfp_model`), paper-specific configuration fields (`ai_proxy`, `ai_index_method`),
   and implicit column assumptions. These packages are currently importable from
   `econflow.*` and appear in `__all__`. They must not enter the v1.0 public API.

3. **Structural debt** — two exception hierarchies with unresolved roots (`EconFlowError`
   vs `EconFlowCoreError`), duplicate provenance modules (`provenance.py` vs
   `core/provenance.py`), three stale root-level connector stubs, and three stale
   `outputs/` flat files alongside the new sub-directory implementations.

**Finding:** Of the 195 names currently importable from `econflow.*` sub-packages,
approximately 70 are Stable, 45 are Experimental, 52 are Internal, and 28 are
Deprecated or must be deprecated before v1.0.

**Recommendation:** Adopt the two-phase package structure described in Section 7.
Phase 1 (before v1.0 RC) removes all paper-specific names from the public API without
touching their implementations. Phase 2 (before v2.0) removes the legacy implementations
entirely.

---

## Methodology

The following sources were analyzed:

- All `__init__.py` files: `__all__` lists extracted via AST
- All five base classes: abstract method signatures
- All five plugin registries: public functions
- `cli.py`: all `@app.command()` and `@*_app.command()` decorated functions
- `core/config.py`: all Pydantic model fields
- `exceptions.py` and `core/exceptions.py`: full exception hierarchies
- `provenance.py` and `core/provenance.py`: duplicate module analysis
- `pipeline.py`, `pipeline_generic.py`, `core/pipeline.py`: pipeline module analysis
- Directory tree: identification of stale flat files alongside new sub-directories

**Classification definitions used in this review:**

| Label | Meaning |
|---|---|
| **Stable** | Committed to backward compatibility. May be included in v1.0 `__all__`. |
| **Experimental** | Implemented but not yet proven across diverse use cases. Permitted in v1.0 `__all__` only with an explicit `Experimental` note in the Plugin SDK. |
| **Internal** | Implementation detail. Must not appear in any public `__all__`. Name begins with `_` or should. |
| **Deprecated** | Currently in `__all__` but must be removed before v1.0 is released. A deprecation cycle is required if any external code depends on it. |

---

## Section 1: Top-Level Package (`econflow`)

**File:** `src/econflow/__init__.py`

| Name | Type | Classification | Notes |
|---|---|---|---|
| `__version__` | str | **Stable** | Standard convention; must be maintained. |
| `EconFlowError` | exception class | **Stable** | Canonical root exception; see §6 for hierarchy conflict. |
| `AIProdError` | exception alias | **Deprecated** | Paper-specific name. `CHANGELOG.md` promises removal at v0.3.0. Must be removed before v1.0. |
| `DataValidationError` | exception class | **Stable** | Generic; useful to callers who catch validation failures. |
| `MergeError` | exception class | **Stable** | Generic; useful to callers who perform data merges. |
| `PipelineError` | exception class | **Stable** | Generic, but see §6 — there are two classes with this name. |
| `ModelSpecificationError` | exception class | **Stable** | Generic; useful to plugin authors who validate estimator params. |

**Issues:**
- `AIProdError` is still in `__all__`. It must be removed.
- The top-level docstring still describes the package in terms of its original
  AI & Productivity scope: `"ingestion: World Bank, OECD, PWT"` and references
  `sensitivity`, `reporting`, and `visualization` as core sub-packages. The docstring
  must be rewritten to reflect the platform API.
- `EconFlowError` is the canonical root here, but `core/exceptions.py` defines a
  separate `EconFlowCoreError` root. Both trees contain a class named `PipelineError`
  that are not the same class. See §6.

---

## Section 2: Estimation (`econflow.estimation`)

**File:** `src/econflow/estimation/__init__.py`

This sub-package is the most mature in the codebase. All names are well-defined
and consistent. This is the reference for what a well-designed EconFlow sub-package
looks like.

| Name | Type | Classification | Notes |
|---|---|---|---|
| `EstimationResult` | dataclass | **Stable** | Central data carrier. Fields are frozen per ADR-008 intent. |
| `DiagnosticResult` | dataclass | **Stable** | Produced by diagnostics, attached to `EstimationResult`. |
| `BaseEstimator` | abstract class | **Stable** | Plugin interface. Methods `validate`, `fit`, `diagnostics` are frozen. |
| `EstimatorError` | exception | **Stable** | Raised by estimators on failure. |
| `register` | function | **Stable** | `@register("id")` decorator for estimator plugins. |
| `get_estimator` | function | **Stable** | Primary registry access function. |
| `list_estimators` | function | **Stable** | Returns sorted list of registered IDs. |
| `unregister` | function | **Internal** | For tests only. Must not be used in production code. Should be `_unregister` or move to a `testing` sub-module. |
| `PooledOLS` | class | **Stable** | Implemented, tested. |
| `EntityFE` | class | **Stable** | Implemented, tested. |
| `TwoWayFE` | class | **Stable** | Implemented, tested. |
| `RandomEffects` | class | **Stable** | Implemented, tested. |
| `FirstDifference` | class | **Stable** | Implemented, tested. |
| `IV2SLS` | class | **Stable** | Implemented, tested. |
| `SystemGMM` | class | **Experimental** | Stub — `fit()` raises `NotImplementedError`. Must be implemented or removed before v1.0. |
| `PanelQuantile` | class | **Experimental** | Stub — `fit()` raises `NotImplementedError`. Must be implemented or removed before v1.0. |

**Issues:**
- `unregister` is in `__all__`. It is a test utility and should be removed from the
  public API. Rename to `_unregister` or create a `econflow.testing` module.
- `SystemGMM` and `PanelQuantile` are in `__all__` and are stubs. A user who reads
  `list_estimators()`, selects `gmm`, and runs `econflow run` receives
  `NotImplementedError`. This must be resolved before v1.0.

**`EstimationResult` field inventory:**

| Field | Type | Classification |
|---|---|---|
| `params` | `pd.Series` | **Stable** |
| `std_err` | `pd.Series` | **Stable** |
| `pvalues` | `pd.Series` | **Stable** |
| `nobs` | `int` | **Stable** |
| `rsq` | `float \| None` | **Stable** |
| `estimator_id` | `str` | **Stable** |
| `f_statistic` | `float \| None` | **Stable** |
| `f_pvalue` | `float \| None` | **Stable** |
| `entity_col` | `str` | **Stable** |
| `time_col` | `str` | **Stable** |
| `entities` | `list[str]` | **Stable** |
| `time_periods` | `list` | **Stable** |
| `diagnostic_results` | `list[DiagnosticResult]` | **Stable** |
| `warnings` | `list[str]` | **Stable** |
| `provenance` | `dict` | **Experimental** — schema of this dict is undocumented. |
| `extra` | `dict` | **Experimental** — escape hatch; contents are undefined. |

---

## Section 3: Diagnostics (`econflow.diagnostics`)

**File:** `src/econflow/diagnostics/__init__.py`

| Name | Type | Classification | Notes |
|---|---|---|---|
| `BaseDiagnostic` | abstract class | **Stable** | Plugin interface. `run()` and `supports()` are frozen. |
| `DiagnosticError` | exception | **Stable** | Raised by diagnostics on failure. |
| `register_diagnostic` | function | **Stable** | Decorator for diagnostic plugins. |
| `get_diagnostic` | function | **Stable** | Primary registry access. |
| `list_diagnostics` | function | **Stable** | Returns sorted list of registered IDs. |
| `unregister_diagnostic` | function | **Internal** | Test utility. Must not be in `__all__`. |

**From `diagnostics/plugins/__init__.py`:**

| Name | Type | Classification | Notes |
|---|---|---|---|
| `HausmanTest` | class | **Stable** | Implemented and tested. |
| `BreuschPagan` | class | **Stable** | Implemented and tested. |
| `PesaranCD` | class | **Stable** | Implemented and tested. |
| `VIFCheck` | class | **Stable** | Implemented and tested. |
| `WooldridgeTest` | class | **Experimental** | Stub — raises `NotImplementedError`. |
| `SerialCorrelationTest` | class | **Experimental** | Stub — raises `NotImplementedError`. |

**Issues:**
- `unregister_diagnostic` should not be in `__all__`.
- `diagnostics/plugins/__init__.py` exports `WooldridgeTest` and
  `SerialCorrelationTest` which are stubs. These are in `__all__`. Same issue as
  GMM/Quantile in estimation.
- `diagnostics/dependence.py`, `diagnostics/serial.py`, `diagnostics/specification.py`,
  `diagnostics/overid.py`, and `diagnostics/reporter.py` are in the source tree but
  have no `__all__` and are not imported from the package `__init__`. It is unclear
  whether these are internal helpers or superseded stubs. They require classification
  and either formal export or deletion.

---

## Section 4: Ingestion (`econflow.ingestion`)

**File:** `src/econflow/ingestion/__init__.py`

| Name | Type | Classification | Notes |
|---|---|---|---|
| `AbstractConnector` | abstract class | **Stable** | Plugin interface. Nine methods; six abstract. |
| `ConnectorError` | exception | **Stable** | Raised by connectors on failure. |
| `CacheManager` | class | **Stable** | Cache operations with hash verification. |
| `CacheCorruptionError` | exception | **Stable** | Raised on hash mismatch. |
| `DatasetMetadata` | dataclass | **Stable** | Metadata record for every downloaded dataset. |
| `DatasetManifest` | dataclass | **Stable** | Project-level record of all acquisitions. |
| `ManifestEntry` | dataclass | **Stable** | Per-dataset entry within `DatasetManifest`. |
| `register` | function | **Stable** | Decorator for connector plugins. **Name conflict** — see Issues. |
| `get_connector` | function | **Stable** | Primary registry access. |
| `list_connectors` | function | **Stable** | Returns list of registered connector dicts. |
| `DataValidator` | class | **Stable** | Structural validation for panel CSVs. |
| `DataValidationConfig` | dataclass | **Stable** | Configuration for `DataValidator`. |
| `DataValidationReport` | dataclass | **Stable** | Structured validation output. |
| `ValidationIssue` | dataclass | **Stable** | Individual validation finding within a report. |

**From `ingestion/connectors/__init__.py`:**

| Name | Type | Classification | Notes |
|---|---|---|---|
| `LocalCSVConnector` | class | **Stable** | Fully implemented. Reference for simplest connector. |
| `WorldBankConnector` | class | **Stable** | Fully implemented. |
| `OECDConnector` | class | **Experimental** | Implemented but SDMX-JSON parsing makes hard assumptions about dimension structure. |
| `PennWorldTablesConnector` | class | **Experimental** | Implemented but only tested against PWT 10.01 Excel structure. |
| `FREDConnector` | class | **Stable** | Fully implemented; security-aware cache key design. |

**Issues — Critical:**
- `ingestion` exports `register` and `estimation` exports `register`. Both names are
  in their respective `__all__` lists. A researcher who writes
  `from econflow.ingestion import register; from econflow.estimation import register`
  will silently overwrite one with the other. The connector registry decorator must
  be renamed to `register_connector` to match the naming convention of the other four
  registries (`register_diagnostic`, `register_renderer`, `register_integrity_check`).
  This is the single most dangerous naming inconsistency in the current API.

- Three stale root-level files remain at `ingestion/oecd.py`, `ingestion/pwt.py`,
  `ingestion/world_bank.py`. These are Sprint 4 stubs superseded by the
  `connectors/` subdirectory. They are not imported from `ingestion/__init__.py` and
  are not in `__all__`, but they are importable as `from econflow.ingestion.oecd import ...`.
  Any code that imports from these paths will break when the files are deleted. They
  must be deleted; their existence is misleading.

- `unregister` (connector registry) is not in `ingestion/__all__` — correct. But
  the function exists in `ingestion/registry.py` and is importable. Confirm it is
  documented as internal only.

**`AbstractConnector` method classification:**

| Method | Abstract | Classification | Notes |
|---|---|---|---|
| `connect()` | Yes | **Stable** | |
| `download(force)` | Yes | **Stable** | |
| `validate(path)` | Yes | **Stable** | |
| `metadata()` | Yes | **Stable** | |
| `cache_key()` | Yes | **Stable** | |
| `citation()` | No | **Stable** | Reads `self._CITATION`; may be overridden. |
| `version()` | No | **Stable** | Reads `self._VERSION`; may be overridden. |
| `fetch(force)` | No | **Stable** | High-level convenience; calls the five above. |
| `_make_cache_key(extra)` | No | **Internal** | Helper for subclasses. Underscore-prefixed; correct. |

---

## Section 5: Outputs (`econflow.outputs`)

**File:** `src/econflow/outputs/__init__.py`

| Name | Type | Classification | Notes |
|---|---|---|---|
| `ReportTable` | dataclass | **Stable** | Central content-presentation contract. |
| `ReportFigure` | dataclass | **Stable** | Figure equivalent of `ReportTable`. |
| `TableRow` | dataclass | **Stable** | Cell within a `ReportTable`. |
| `RendererError` | exception | **Stable** | Raised by renderers and `PublicationBundle`. |
| `get_renderer` | function | **Stable** | Primary renderer registry access. |
| `list_renderers` | function | **Stable** | Returns sorted list of renderer IDs. |
| `register_renderer` | function | **Stable** | Decorator for renderer plugins. |
| `unregister_renderer` | function | **Internal** | Test utility. Must not be in `__all__`. |
| `build_regression_table` | function | **Stable** | |
| `build_summary_stats_table` | function | **Stable** | |
| `build_balance_table` | function | **Stable** | |
| `build_correlation_table` | function | **Stable** | |
| `build_robustness_table` | function | **Stable** | |
| `build_sensitivity_table` | function | **Stable** | |
| `build_falsification_table` | function | **Stable** | |
| `build_heterogeneity_table` | function | **Stable** | |
| `CoefficientPlot` | class | **Stable** | Implemented. |
| `CIPlot` | class | **Stable** | Implemented. |
| `build_diagnostics_report` | function | **Stable** | |
| `PublicationBundle` | class | **Stable** | Orchestrates full publication output. |

**From `outputs/figures/__init__.py`:**

| Name | Type | Classification | Notes |
|---|---|---|---|
| `CoefficientPlot` | class | **Stable** | Implemented. |
| `CIPlot` | class | **Stable** | Implemented. |
| `ResidualFigure` | class | **Experimental** | Stub. |
| `DistributionFigure` | class | **Experimental** | Stub. |
| `EventStudyFigure` | class | **Experimental** | Stub. |
| `RobustnessComparisonFigure` | class | **Experimental** | Stub. |

**Issues:**
- `unregister_renderer` is in `__all__`. Should be removed.
- Three flat legacy files coexist with the new directory structure:
  - `outputs/figures.py` — an old flat module now shadowed by `outputs/figures/`
  - `outputs/tables.py` — an old flat module now shadowed by `outputs/tables/`
  - `outputs/reports.py` — an old flat stub
  These three files are not imported from `outputs/__init__.py`. However, they are
  importable as `from econflow.outputs.figures import ...` (resolves to the flat file
  or the directory depending on Python's import resolution). This is a latent collision
  that could produce incorrect imports on some platforms. All three must be deleted.
- `BaseRenderer` is not in `outputs/__all__`. Plugin authors who want to subclass it
  must import from `econflow.outputs.base`, which is not a declared public path.
  `BaseRenderer` must be added to `outputs/__all__`.

**`ReportTable` field classification:**

| Field | Classification | Notes |
|---|---|---|
| `title` | **Stable** | |
| `table_type` | **Stable** | |
| `columns` | **Stable** | |
| `rows` | **Stable** | |
| `footer` | **Stable** | |
| `subtitle` | **Stable** | |
| `notes` | **Stable** | |
| `metadata` | **Experimental** | Contents undefined; renderer-specific use only. |

---

## Section 6: Integrity (`econflow.integrity`)

**File:** `src/econflow/integrity/__init__.py`

| Name | Type | Classification | Notes |
|---|---|---|---|
| `CERTIFICATE_SCHEMA_VERSION` | str constant | **Stable** | `"1.0.0"`. Versioning commitment. |
| `ReproducibilityCertificate` | dataclass | **Stable** | Primary reproducibility artifact. |
| `BaseIntegrityCheck` | abstract class | **Stable** | Plugin interface. `run()` is frozen. |
| `IntegrityCheckResult` | dataclass | **Stable** | Structured check output. |
| `get_check` | function | **Stable** | Primary registry access. |
| `list_checks` | function | **Stable** | Returns sorted list of check IDs. |
| `register_integrity_check` | function | **Stable** | Decorator for integrity check plugins. |
| `unregister_check` | function | **Internal** | Test utility. Must not be in `__all__`. |
| `DriftItem` | dataclass | **Stable** | Single axis comparison result. |
| `DriftReport` | dataclass | **Stable** | Aggregated drift comparison output. |
| `detect_drift` | function | **Stable** | Compare two certificates across eight axes. |
| `ConfigFingerprint` | dataclass | **Stable** | SHA-256 snapshot of a configuration file. |
| `DataFingerprint` | dataclass | **Stable** | SHA-256 + row/col snapshot of a data file. |
| `EnvironmentFingerprint` | dataclass | **Stable** | Python, OS, git, package version snapshot. |
| `ReplicationPackage` | class | **Stable** | Journal-ready archival bundle builder. |

**Issues:**
- `unregister_check` is in `__all__`. Should be removed.
- `integrity/checks/plugins/__init__.py` exports three module-level string constants
  (`coefficient_stability`, `pvalue_distribution`, `sample_size`) which appear to be
  the registered plugin IDs as strings, not the plugin classes themselves. These are
  not meaningful public exports and should not be in `__all__`. Removing them does not
  affect functionality; the plugins are registered on import by the `@register_integrity_check`
  decorator on their classes.
- `ReproducibilityCertificate` lacks a `detect_drift()` instance method. Drift
  detection is a free function (`detect_drift(a, b)`). For discoverability, consider
  adding `cert_a.drift_from(cert_b)` as a convenience method in a future release.

**`ReproducibilityCertificate` field classification:**

| Field | Classification | Notes |
|---|---|---|
| `project_name` | **Stable** | |
| `schema_version` | **Stable** | Must match `CERTIFICATE_SCHEMA_VERSION`. |
| `created_at` | **Stable** | |
| `environment` | **Stable** | Contains `EnvironmentFingerprint.to_dict()`. |
| `data_fingerprints` | **Stable** | List of `DataFingerprint.to_dict()`. |
| `config_fingerprint` | **Stable** | `ConfigFingerprint.to_dict()`. |
| `check_results` | **Stable** | List of `IntegrityCheckResult.to_dict()`. |
| `overall_status` | **Stable** | `"pass"`, `"warn"`, `"fail"`, or `"skip"`. |

---

## Section 7: CLI (`econflow` entry point)

**File:** `src/econflow/cli.py`

| Command | Status | Classification | Notes |
|---|---|---|---|
| `econflow init` | Implemented | **Stable** | Scaffolds project directory. |
| `econflow doctor` | Implemented | **Stable** | Environment audit. |
| `econflow validate` | Implemented | **Stable** | Configuration schema validation. |
| `econflow info` | Implemented | **Stable** | Registry and environment information. |
| `econflow run` | Implemented | **Experimental** | Calls `pipeline_generic.py` which bypasses the estimator registry. |
| `econflow report` | Implemented | **Experimental** | Depends on `econflow run` having been called first. |
| `econflow certify` | Implemented | **Stable** | Produces `ReproducibilityCertificate`. |
| `econflow verify` | Implemented | **Stable** | Compares environment against stored certificate. |
| `econflow package` | Implemented | **Stable** | Builds replication archive. |
| `econflow fetch` | Implemented | **Stable** | Downloads dataset via registered connector. |
| `econflow cache list` | Implemented | **Stable** | Lists cached datasets. |
| `econflow cache inspect` | Implemented | **Stable** | Shows metadata for a specific cache key. |
| `econflow cache clear` | Implemented | **Stable** | Removes a specific cache entry. |
| `econflow cache purge` | Implemented | **Stable** | Removes all cache entries (requires `--yes`). |
| `econflow datasets` | Implemented | **Stable** | Lists registered connectors. |

**Issues:**
- `econflow run` calls `pipeline_generic.py::run_from_config()` which imports
  `linearmodels` directly rather than dispatching through the estimator registry.
  Marking it Experimental is the honest classification; marking it Stable would be
  false while the registry bypass persists.
- The CLI entry point still contains a large amount of inline logic in `cli.py` for
  the `run` command (lines 336–500 in the file). This should be delegated to
  `commands/run.py` to match the pattern of every other command.

---

## Section 8: Configuration Schema (`econflow.core.config`)

**File:** `src/econflow/core/config.py`

| Model | Classification | Notes |
|---|---|---|
| `Settings` | **Experimental** | `load_config()` raises `NotImplementedError`. Not currently used by the pipeline. |
| `ProjectMeta` | **Experimental** | `name`, `version`, `description`, `authors`, `output_dir` are generic. |
| `DataConfig` | **Experimental** | Generic wrapper around `DataSourceConfig` and `SampleConfig`. |
| `DataSourceConfig` | **Experimental** | `base_url`, `indicators`, `extra` — somewhat generic. |
| `SampleConfig` | **Internal** | `countries` field encodes a geography assumption; not generic for non-country studies. |
| `VariablesConfig` | **Deprecated** | Contains `ai_proxy: list[str]` and `ai_index_method: Literal["pca", "equal_weight"]` — these are paper-specific fields that must not appear in the generic platform configuration schema. |
| `AuthorConfig` | **Stable** | Generic. |

**Critical finding:** `VariablesConfig.ai_proxy` and `VariablesConfig.ai_index_method`
are paper-specific fields in a module that is meant to be the generic configuration
schema for all EconFlow studies. A researcher running a labor economics study should not
encounter `ai_proxy` in their configuration schema. These fields must be removed and
replaced with the generic variable role mapping described in ADR-007: `entity_col`,
`time_col`, `dependent`, `treatment`, `controls`.

The `SampleConfig.countries` field similarly assumes geographic entities. It should be
renamed `entities` with documentation that it accepts any entity identifiers.

---

## Section 9: Legacy Paper API

These sub-packages contain names that were the original EconFlow public API for the
AI & Productivity paper. They are currently in `__all__` and importable from
`econflow.*`. None of them may appear in the v1.0 public API.

### 9.1 `econflow.data`

| Name | Classification | Notes |
|---|---|---|
| `load_panel` | **Deprecated** | Superseded by `AbstractConnector.download()` + `LocalCSVConnector`. |
| `drop_aggregate_entities` | **Deprecated** | Paper-specific. No generic equivalent needed. |
| `validate_data` | **Deprecated** | Superseded by `DataValidator.validate()`. |
| `report_has_blockers` | **Deprecated** | Superseded by `DataValidationReport.passed`. |
| `save_validation_report` | **Deprecated** | Superseded by `DataValidationReport.to_json()`. |
| `sample_selection_summary` | **Deprecated** | Paper-specific. |
| `REQUIRED_COLUMNS` | **Deprecated** | Paper-specific constant. |

**Disposition:** The entire `data/` sub-package is a paper-specific data loading layer.
Its functionality is superseded by `ingestion/`. The package should be removed from
`__all__` immediately and moved to `examples/ai_productivity_paper/` or deleted before v1.0.

### 9.2 `econflow.econometrics`

| Name | Classification | Notes |
|---|---|---|
| `run_tfp_model` | **Deprecated** | Paper-specific function name. |
| `run_growth_model` | **Deprecated** | Paper-specific function name. |
| `run_robustness_suite` | **Deprecated** | Paper-specific. |
| `run_sensitivity_suite` | **Deprecated** | Paper-specific. |
| `run_falsification_suite` | **Deprecated** | Paper-specific. |
| `run_heterogeneity_suite` | **Deprecated** | Paper-specific. |

**Disposition:** The entire `econometrics/` sub-package must be removed from `__all__`
and relocated to `examples/ai_productivity_paper/`. The functions in it call
`linearmodels` directly with hardcoded column names and are the origin of the
pipeline-registry bypass documented elsewhere.

### 9.3 `econflow.visualization`

| Name | Classification | Notes |
|---|---|---|
| `ai_tfp_scatter` | **Deprecated** | Paper-specific name in public API. |
| `ai_tfp_trend` | **Deprecated** | Paper-specific name in public API. |
| `ai_coefficient_comparison` | **Deprecated** | Paper-specific name in public API. |
| `missingness_profile` | **Deprecated** | Generic utility but accessible only through a paper-named module. |
| `apply_style` | **Deprecated** | Useful utility buried in paper-specific sub-package. |
| `COLORS` | **Deprecated** | Same. |
| `WIDTH_FULL` | **Deprecated** | Same. |

**Disposition:** `ai_tfp_scatter`, `ai_tfp_trend`, `ai_coefficient_comparison` are
names that cannot enter the v1.0 public API. `apply_style`, `COLORS`, and
`WIDTH_FULL` are worth retaining if moved to a generic `econflow.style` or
`econflow.outputs.style` namespace. `missingness_profile` could move to
`econflow.outputs.figures`.

### 9.4 `econflow.features`

| Name | Classification | Notes |
|---|---|---|
| `engineer_features` | **Deprecated** | Hardcodes AI index construction; paper-specific. |
| `add_log_transforms` | **Deprecated** | Generic utility but currently hardcodes column names. |
| `add_sub_indices` | **Deprecated** | Paper-specific sub-index construction. |

**Disposition:** `add_log_transforms` could be salvaged as a generic utility if
refactored to accept a column list parameter. In its current form, all three must be
removed from the public API.

### 9.5 `econflow.reporting`

| Name | Classification | Notes |
|---|---|---|
| `write_results` | **Deprecated** | Produces paper-specific narrative text. |
| `write_falsification_results` | **Deprecated** | Paper-specific. |

**Disposition:** The narrative text produced by these functions references TFP and AI
adoption by name. The entire `reporting/` sub-package is paper-specific.

### 9.6 `econflow.processing`

No `__all__` is defined; nothing is currently exported. However, the sub-package
contains eight modules with classes that are importable:

| Class | Classification | Notes |
|---|---|---|
| `AIProxyIndexBuilder` | **Deprecated** | Paper-specific name and implementation. |
| `CountryHarmoniser` | **Deprecated** | Name encodes geographic assumption. |
| `DatasetMerger` | **Internal** | Potentially useful generically but currently paper-specific. |
| `IndicatorQuality` / `QualityReporter` | **Internal** | Could be useful; no `__all__`, no imports from parent. |
| `TFPProcessor` | **Deprecated** | Paper-specific. |
| `TransformPipeline` | **Internal** | Generic concept but not part of any declared API. |

**Disposition:** `processing/` has no `__all__` and is not imported from the top-level
`econflow` package. It is effectively already internal. Formalize this by confirming
no external code imports from it, then leave it as internal until Sprint 9 decides
what to do with the paper-specific logic.

### 9.7 `econflow.sensitivity`

No `__all__` is defined. Contains `ResultsComparison` and `SensitivityRunner`. These
are potentially useful generic concepts that could be promoted to the platform API
after refactoring to remove paper-specific assumptions. Currently internal by omission.

---

## Section 10: Exception Hierarchy — Critical Conflict

The repository contains two exception hierarchies with incompatible roots:

**Hierarchy A** (`src/econflow/exceptions.py`):
```
EconFlowError (root)
├── AIProdError [alias — deprecated]
├── DataValidationError
├── MergeError
├── PipelineError          ← NAME CONFLICT (see below)
└── ModelSpecificationError
```
This hierarchy is the public API (exported from `econflow.__init__.__all__`).

**Hierarchy B** (`src/econflow/core/exceptions.py`):
```
EconFlowCoreError (root)
├── APRPError [alias — deprecated]
├── ConfigurationError
│   └── MissingConfigKeyError
├── RegistryError
│   └── ProjectNotFoundError
├── PipelineError          ← NAME CONFLICT with Hierarchy A
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
This hierarchy is NOT exported from any `__all__`. It is imported internally by
the commands and sub-packages that were built in Sprints 3–8.

**The conflict:** Two classes are both named `PipelineError`, are rooted at different
base classes (`EconFlowError` vs `EconFlowCoreError`), and are not the same object.
Code that catches `econflow.PipelineError` will not catch
`econflow.core.exceptions.PipelineError` and vice versa.

**Resolution required before v1.0:** These two hierarchies must be merged into one.
The recommended resolution is:

1. `EconFlowCoreError` is the root of the merged hierarchy, renamed to `EconFlowError`.
2. `AIProdError` and `APRPError` are both removed (they were promises to remove before
   v0.3.0 and before v1.0 respectively).
3. The rich Hierarchy B (which has `RegistryError`, `ConfigurationError`,
   `CacheError`, `CertificateError`, etc.) is adopted as the complete exception tree.
4. The simpler Hierarchy A exceptions (`DataValidationError`, `MergeError`,
   `ModelSpecificationError`) are added as leaves of the merged tree.
5. `exceptions.py` is removed; `core/exceptions.py` becomes the canonical location.
6. `econflow.__init__.__all__` is updated to re-export from `core.exceptions`.

This is a breaking change from the current Hierarchy A names, but acceptable before
v1.0 when the backward compatibility promise has not yet been made.

---

## Section 11: Duplicate and Orphaned Modules

The following modules exist in the source tree and require explicit disposition before v1.0:

| Module | Status | Required Action |
|---|---|---|
| `provenance.py` | Active (used by `pipeline_generic.py`) | Keep. This is the primary implementation. |
| `core/provenance.py` | Stub (never called) | Delete. Its functionality is not needed; the `integrity/` package supersedes the stub's intent. |
| `pipeline.py` | Active (used by examples) | Move to `examples/ai_productivity_paper/`. It is paper-specific. |
| `pipeline_generic.py` | Active (used by `econflow run`) | Keep. Primary pipeline. Needs registry integration. |
| `core/pipeline.py` | Stub (`Stage`, `Pipeline` classes, never used) | Delete or defer to Sprint 9 if needed. |
| `logging.py` | Exists; content unknown | Review. If paper-specific, delete. If generic, expose via `__all__`. |
| `outputs/figures.py` | Stale flat module | Delete. Superseded by `outputs/figures/`. |
| `outputs/tables.py` | Stale flat module | Delete. Superseded by `outputs/tables/`. |
| `outputs/reports.py` | Stale stub | Delete. |
| `ingestion/oecd.py` | Stale Sprint 4 stub | Delete. Superseded by `ingestion/connectors/oecd.py`. |
| `ingestion/pwt.py` | Stale Sprint 4 stub | Delete. Superseded by `ingestion/connectors/pwt.py`. |
| `ingestion/world_bank.py` | Stale Sprint 4 stub | Delete. Superseded by `ingestion/connectors/world_bank.py`. |
| `cli_scaffold/` | Dead artifact | Delete entire directory. |
| `ml/__init__.py` | Empty | Delete directory or document as reserved namespace. |
| `config/__init__.py` | Empty | Review; may be legacy from early sprint. |
| `data/__init__.py` | Active, paper-specific | Remove from `__all__`; relocate to examples. |

---

## Section 12: Registry API Naming Inconsistency

The five registries expose `register` functions with inconsistent naming:

| Registry | Decorator name | Access function | Unregister function |
|---|---|---|---|
| Estimators | `register` | `get_estimator` | `unregister` |
| Diagnostics | `register_diagnostic` | `get_diagnostic` | `unregister_diagnostic` |
| Renderers | `register_renderer` | `get_renderer` | `unregister_renderer` |
| Connectors | `register` | `get_connector` | `unregister` (not in `__all__`) |
| Integrity checks | `register_integrity_check` | `get_check` | `unregister_check` |

**Problems:**
1. Estimators and connectors both export a function named `register`. If imported
   into the same namespace, one overwrites the other.
2. `get_check` does not follow the `get_<type>` convention — it should be
   `get_integrity_check` to match `register_integrity_check`.
3. `unregister` (estimator and connector) does not follow the `unregister_<type>`
   convention.
4. Unregister functions appear in `estimation/__all__` but not in `ingestion/__all__`.
   The convention should be uniform: unregister is never in `__all__`.

**Required before v1.0:**
- `ingestion.register` → `ingestion.register_connector`
- `estimation.register` → `estimation.register_estimator`
- `integrity.get_check` → `integrity.get_integrity_check`
- All `unregister_*` functions removed from all `__all__` lists

---

## Section 13: Recommended Package Structure for v1.0

The following structure minimizes breaking changes to existing external code while
achieving a clean public API boundary before the v1.0 backward compatibility promise.

### Phase 1: Before v1.0 RC (no code changes, only `__all__` and relocation)

The key insight is that removing a sub-package from `__all__` does not break code
that imports from it directly (`from econflow.data import load_panel` still works).
The public API narrowing is immediate; the code removal can happen in Sprint 9.

**Step 1: Remove from all `__all__` lists**
- Remove all of `data`, `econometrics`, `visualization`, `features`, `reporting`
  from their own `__all__` (or empty the lists)
- Remove `AIProdError`, `APRPError` from their respective `__all__` lists
- Remove all `unregister_*` functions from all `__all__` lists
- Remove stub class instances from `integrity/checks/plugins/__init__.__all__`

**Step 2: Add missing items to `__all__` lists**
- Add `BaseRenderer` to `outputs/__all__`
- Add `BaseEstimator` to `estimation/__all__` (already there — confirm)
- Add `BaseDiagnostic` to `diagnostics/__all__` (already there — confirm)

**Step 3: Rename to resolve conflicts**
- `ingestion.register` → `register_connector` (with `register` as a deprecated alias
  emitting `DeprecationWarning`)
- `estimation.register` → `register_estimator` (with `register` as a deprecated alias)
- `integrity.get_check` → `get_integrity_check` (with `get_check` as deprecated alias)

### Phase 2: Sprint 9 (code relocation)

```
src/econflow/
├── __init__.py                    ← exports only platform API symbols
├── exceptions.py                  ← MERGED hierarchy (from core/exceptions.py)
├── cli.py
├── provenance.py                  ← keep; core/provenance.py deleted
├── pipeline_generic.py            ← keep; pipeline.py moved to examples/
│
├── core/
│   ├── config.py                  ← VariablesConfig paper fields removed
│   └── registry.py
│
├── commands/                      ← all CLI command implementations
├── estimation/                    ← STABLE; rename register → register_estimator
├── diagnostics/                   ← STABLE; rename unregister → _unregister
├── ingestion/                     ← STABLE; rename register → register_connector
│   └── connectors/
├── outputs/                       ← STABLE; add BaseRenderer to __all__
│   ├── figures/
│   ├── tables/
│   └── renderers/
├── integrity/                     ← STABLE; rename get_check → get_integrity_check
│
└── [DELETED or moved to examples/]
    ├── data/                      → examples/ai_productivity_paper/data_layer/
    ├── econometrics/              → examples/ai_productivity_paper/econometrics/
    ├── visualization/             → examples/ai_productivity_paper/visualization/
    ├── features/                  → examples/ai_productivity_paper/features/
    ├── reporting/                 → examples/ai_productivity_paper/reporting/
    ├── processing/                → examples/ai_productivity_paper/processing/
    ├── sensitivity/               → examples/ai_productivity_paper/sensitivity/
    ├── cli_scaffold/              → DELETE
    ├── ml/                        → DELETE (empty)
    ├── config/                    → DELETE (empty, superseded by core/config.py)
    ├── core/provenance.py         → DELETE
    ├── core/pipeline.py           → DELETE
    ├── pipeline.py                → examples/ai_productivity_paper/
    ├── outputs/figures.py         → DELETE
    ├── outputs/tables.py          → DELETE
    ├── outputs/reports.py         → DELETE
    ├── ingestion/oecd.py          → DELETE
    ├── ingestion/pwt.py           → DELETE
    └── ingestion/world_bank.py    → DELETE
```

### Projected v1.0 public API surface

After Phase 2, the complete `econflow.*` public API is:

```python
# econflow
econflow.EconFlowError               # root exception
econflow.ConfigurationError          # config failures
econflow.RegistryError               # unknown plugin ID
econflow.ConnectorError              # data acquisition failures
econflow.EstimatorError              # estimation failures
econflow.DiagnosticError             # diagnostic failures
econflow.RendererError               # rendering failures
econflow.IntegrityError              # integrity check infrastructure failures
econflow.CacheError                  # cache failures
econflow.__version__

# econflow.estimation
econflow.estimation.EstimationResult
econflow.estimation.DiagnosticResult
econflow.estimation.BaseEstimator
econflow.estimation.register_estimator
econflow.estimation.get_estimator
econflow.estimation.list_estimators
econflow.estimation.{PooledOLS, EntityFE, TwoWayFE, RandomEffects,
                     FirstDifference, IV2SLS, SystemGMM, PanelQuantile}

# econflow.diagnostics
econflow.diagnostics.BaseDiagnostic
econflow.diagnostics.DiagnosticError
econflow.diagnostics.register_diagnostic
econflow.diagnostics.get_diagnostic
econflow.diagnostics.list_diagnostics
econflow.diagnostics.{HausmanTest, BreuschPagan, PesaranCD, VIFCheck,
                      WooldridgeTest, SerialCorrelationTest}

# econflow.ingestion
econflow.ingestion.AbstractConnector
econflow.ingestion.ConnectorError
econflow.ingestion.CacheManager
econflow.ingestion.CacheCorruptionError
econflow.ingestion.DatasetMetadata
econflow.ingestion.DatasetManifest
econflow.ingestion.ManifestEntry
econflow.ingestion.DataValidator
econflow.ingestion.DataValidationConfig
econflow.ingestion.DataValidationReport
econflow.ingestion.ValidationIssue
econflow.ingestion.register_connector
econflow.ingestion.get_connector
econflow.ingestion.list_connectors
econflow.ingestion.connectors.{LocalCSVConnector, WorldBankConnector,
                                OECDConnector, PennWorldTablesConnector,
                                FREDConnector}

# econflow.outputs
econflow.outputs.BaseRenderer
econflow.outputs.ReportTable
econflow.outputs.ReportFigure
econflow.outputs.TableRow
econflow.outputs.RendererError
econflow.outputs.PublicationBundle
econflow.outputs.register_renderer
econflow.outputs.get_renderer
econflow.outputs.list_renderers
econflow.outputs.{build_regression_table, build_summary_stats_table,
                  build_balance_table, build_correlation_table,
                  build_robustness_table, build_sensitivity_table,
                  build_falsification_table, build_heterogeneity_table}
econflow.outputs.{CoefficientPlot, CIPlot, ResidualFigure, DistributionFigure,
                  EventStudyFigure, RobustnessComparisonFigure}
econflow.outputs.build_diagnostics_report

# econflow.integrity
econflow.integrity.CERTIFICATE_SCHEMA_VERSION
econflow.integrity.ReproducibilityCertificate
econflow.integrity.BaseIntegrityCheck
econflow.integrity.IntegrityCheckResult
econflow.integrity.register_integrity_check
econflow.integrity.get_integrity_check
econflow.integrity.list_checks
econflow.integrity.DriftItem
econflow.integrity.DriftReport
econflow.integrity.detect_drift
econflow.integrity.ConfigFingerprint
econflow.integrity.DataFingerprint
econflow.integrity.EnvironmentFingerprint
econflow.integrity.ReplicationPackage
```

This surface is approximately **95 names** — a reduction from the current ~195 importable
names. Every name in this list is generic, non-paper-specific, and committable to
backward compatibility at v1.0.

---

## Section 14: Priority Action List

Ordered by risk and dependency:

### Blocking — must complete before v1.0 RC

1. **Resolve the exception hierarchy conflict.** Two roots, one shared class name
   (`PipelineError`). Merge hierarchies with `EconFlowCoreError`/`EconFlowError` as
   root. Remove both `AIProdError` and `APRPError`.

2. **Rename `register` in estimation and ingestion.** Both registries export a public
   function named `register`. Rename to `register_estimator` and `register_connector`
   respectively. Add deprecated aliases. This is the highest-priority single name
   conflict in the API.

3. **Remove paper-specific sub-packages from `__all__`.** `data`, `econometrics`,
   `visualization`, `features`, `reporting` must not appear in any `__all__` list.
   Their code can remain; only their public API designation is removed.

4. **Remove `VariablesConfig.ai_proxy` and `ai_index_method`** from `core/config.py`.
   Replace with the generic variable role fields (`entity_col`, `time_col`, `dependent`,
   `treatment`, `controls`). Implement `load_config()`.

5. **Remove all `unregister_*` from `__all__` lists** across all five registries.

6. **Delete the twelve stale files** identified in §11. No code depends on them.

7. **Add `BaseRenderer` to `outputs/__all__`.**

8. **Rename `get_check` → `get_integrity_check`** in `integrity/__all__`.

### Non-blocking — before v1.0 final

9. Implement or remove `SystemGMM`, `PanelQuantile`, `WooldridgeTest`,
   `SerialCorrelationTest`. Stubs in `__all__` are not acceptable at v1.0.

10. Rewrite the top-level `econflow` docstring to describe the platform, not the paper.

11. Add `RegistryError`, `ConfigurationError`, `CacheError` to the public exception
    exports in `econflow.__init__.__all__`. These are the exceptions that plugin
    authors most commonly need to catch.

12. Move `pipeline.py` to `examples/ai_productivity_paper/`.

13. Resolve the `outputs/figures.py` vs `outputs/figures/` namespace collision.

---

## Appendix A: Complete Name Classification Table

| Import path | Name | Classification |
|---|---|---|
| `econflow` | `__version__` | Stable |
| `econflow` | `EconFlowError` | Stable |
| `econflow` | `AIProdError` | Deprecated |
| `econflow` | `DataValidationError` | Stable |
| `econflow` | `MergeError` | Stable |
| `econflow` | `PipelineError` | Stable (after hierarchy merge) |
| `econflow` | `ModelSpecificationError` | Stable |
| `econflow.estimation` | `EstimationResult` | Stable |
| `econflow.estimation` | `DiagnosticResult` | Stable |
| `econflow.estimation` | `BaseEstimator` | Stable |
| `econflow.estimation` | `EstimatorError` | Stable |
| `econflow.estimation` | `register` | Deprecated → rename to `register_estimator` |
| `econflow.estimation` | `get_estimator` | Stable |
| `econflow.estimation` | `list_estimators` | Stable |
| `econflow.estimation` | `unregister` | Internal |
| `econflow.estimation` | `PooledOLS` | Stable |
| `econflow.estimation` | `EntityFE` | Stable |
| `econflow.estimation` | `TwoWayFE` | Stable |
| `econflow.estimation` | `RandomEffects` | Stable |
| `econflow.estimation` | `FirstDifference` | Stable |
| `econflow.estimation` | `IV2SLS` | Stable |
| `econflow.estimation` | `SystemGMM` | Experimental (stub) |
| `econflow.estimation` | `PanelQuantile` | Experimental (stub) |
| `econflow.diagnostics` | `BaseDiagnostic` | Stable |
| `econflow.diagnostics` | `DiagnosticError` | Stable |
| `econflow.diagnostics` | `register_diagnostic` | Stable |
| `econflow.diagnostics` | `get_diagnostic` | Stable |
| `econflow.diagnostics` | `list_diagnostics` | Stable |
| `econflow.diagnostics` | `unregister_diagnostic` | Internal |
| `econflow.diagnostics` | `HausmanTest` | Stable |
| `econflow.diagnostics` | `BreuschPagan` | Stable |
| `econflow.diagnostics` | `PesaranCD` | Stable |
| `econflow.diagnostics` | `VIFCheck` | Stable |
| `econflow.diagnostics` | `WooldridgeTest` | Experimental (stub) |
| `econflow.diagnostics` | `SerialCorrelationTest` | Experimental (stub) |
| `econflow.ingestion` | `AbstractConnector` | Stable |
| `econflow.ingestion` | `ConnectorError` | Stable |
| `econflow.ingestion` | `CacheManager` | Stable |
| `econflow.ingestion` | `CacheCorruptionError` | Stable |
| `econflow.ingestion` | `DatasetMetadata` | Stable |
| `econflow.ingestion` | `DatasetManifest` | Stable |
| `econflow.ingestion` | `ManifestEntry` | Stable |
| `econflow.ingestion` | `register` | Deprecated → rename to `register_connector` |
| `econflow.ingestion` | `get_connector` | Stable |
| `econflow.ingestion` | `list_connectors` | Stable |
| `econflow.ingestion` | `DataValidator` | Stable |
| `econflow.ingestion` | `DataValidationConfig` | Stable |
| `econflow.ingestion` | `DataValidationReport` | Stable |
| `econflow.ingestion` | `ValidationIssue` | Stable |
| `econflow.ingestion.connectors` | `LocalCSVConnector` | Stable |
| `econflow.ingestion.connectors` | `WorldBankConnector` | Stable |
| `econflow.ingestion.connectors` | `OECDConnector` | Experimental |
| `econflow.ingestion.connectors` | `PennWorldTablesConnector` | Experimental |
| `econflow.ingestion.connectors` | `FREDConnector` | Stable |
| `econflow.outputs` | `ReportTable` | Stable |
| `econflow.outputs` | `ReportFigure` | Stable |
| `econflow.outputs` | `TableRow` | Stable |
| `econflow.outputs` | `RendererError` | Stable |
| `econflow.outputs` | `BaseRenderer` | Stable (missing from `__all__`) |
| `econflow.outputs` | `get_renderer` | Stable |
| `econflow.outputs` | `list_renderers` | Stable |
| `econflow.outputs` | `register_renderer` | Stable |
| `econflow.outputs` | `unregister_renderer` | Internal |
| `econflow.outputs` | `build_regression_table` | Stable |
| `econflow.outputs` | `build_summary_stats_table` | Stable |
| `econflow.outputs` | `build_balance_table` | Stable |
| `econflow.outputs` | `build_correlation_table` | Stable |
| `econflow.outputs` | `build_robustness_table` | Stable |
| `econflow.outputs` | `build_sensitivity_table` | Stable |
| `econflow.outputs` | `build_falsification_table` | Stable |
| `econflow.outputs` | `build_heterogeneity_table` | Stable |
| `econflow.outputs` | `CoefficientPlot` | Stable |
| `econflow.outputs` | `CIPlot` | Stable |
| `econflow.outputs` | `ResidualFigure` | Experimental (stub) |
| `econflow.outputs` | `DistributionFigure` | Experimental (stub) |
| `econflow.outputs` | `EventStudyFigure` | Experimental (stub) |
| `econflow.outputs` | `RobustnessComparisonFigure` | Experimental (stub) |
| `econflow.outputs` | `build_diagnostics_report` | Stable |
| `econflow.outputs` | `PublicationBundle` | Stable |
| `econflow.integrity` | `CERTIFICATE_SCHEMA_VERSION` | Stable |
| `econflow.integrity` | `ReproducibilityCertificate` | Stable |
| `econflow.integrity` | `BaseIntegrityCheck` | Stable |
| `econflow.integrity` | `IntegrityCheckResult` | Stable |
| `econflow.integrity` | `get_check` | Deprecated → rename to `get_integrity_check` |
| `econflow.integrity` | `list_checks` | Stable |
| `econflow.integrity` | `register_integrity_check` | Stable |
| `econflow.integrity` | `unregister_check` | Internal |
| `econflow.integrity` | `DriftItem` | Stable |
| `econflow.integrity` | `DriftReport` | Stable |
| `econflow.integrity` | `detect_drift` | Stable |
| `econflow.integrity` | `ConfigFingerprint` | Stable |
| `econflow.integrity` | `DataFingerprint` | Stable |
| `econflow.integrity` | `EnvironmentFingerprint` | Stable |
| `econflow.integrity` | `ReplicationPackage` | Stable |
| `econflow.data` | `load_panel` | Deprecated |
| `econflow.data` | `drop_aggregate_entities` | Deprecated |
| `econflow.data` | `validate_data` | Deprecated |
| `econflow.data` | `report_has_blockers` | Deprecated |
| `econflow.data` | `save_validation_report` | Deprecated |
| `econflow.data` | `sample_selection_summary` | Deprecated |
| `econflow.data` | `REQUIRED_COLUMNS` | Deprecated |
| `econflow.econometrics` | `run_tfp_model` | Deprecated |
| `econflow.econometrics` | `run_growth_model` | Deprecated |
| `econflow.econometrics` | `run_robustness_suite` | Deprecated |
| `econflow.econometrics` | `run_sensitivity_suite` | Deprecated |
| `econflow.econometrics` | `run_falsification_suite` | Deprecated |
| `econflow.econometrics` | `run_heterogeneity_suite` | Deprecated |
| `econflow.visualization` | `ai_tfp_scatter` | Deprecated |
| `econflow.visualization` | `ai_tfp_trend` | Deprecated |
| `econflow.visualization` | `ai_coefficient_comparison` | Deprecated |
| `econflow.visualization` | `missingness_profile` | Deprecated |
| `econflow.visualization` | `apply_style` | Deprecated (relocate to outputs.style) |
| `econflow.visualization` | `COLORS` | Deprecated (relocate) |
| `econflow.visualization` | `WIDTH_FULL` | Deprecated (relocate) |
| `econflow.features` | `engineer_features` | Deprecated |
| `econflow.features` | `add_log_transforms` | Deprecated |
| `econflow.features` | `add_sub_indices` | Deprecated |
| `econflow.reporting` | `write_results` | Deprecated |
| `econflow.reporting` | `write_falsification_results` | Deprecated |

**Summary counts:**

| Classification | Count |
|---|---|
| Stable | 72 |
| Experimental | 13 |
| Internal | 7 |
| Deprecated | 28 |
| **Total** | **120** |

---

*This document is a static analysis record. No code was modified in its preparation.
All findings are based on the repository state at v0.7 (2026-06-28).
Recommendations in §13 and §14 are the input to Sprint 9 planning.*

*EconFlow Technical Steering Committee — 2026-06-28*
