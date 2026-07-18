# EconFlow 1.0 API Freeze Audit Report

**Date:** 2026-07-13
**Auditor role:** Principal Release Engineer / Principal Econometrician
**Scope:** All public Python symbols, CLI commands, YAML config schema, and plugin interfaces
**Source files audited:** 11 `__init__.py` files covering all 8 subpackages + top-level
**Verdict:** ❌ NOT READY TO FREEZE — 3 critical issues must be resolved

---

## Executive Summary

EconFlow's public API is broad, well-structured, and largely internally consistent across its eight subpackages. The registry pattern is uniform. The plugin SDK surface is clearly delineated. The exception hierarchy is almost correct. The serialization contract (`to_dict` / `from_dict`) is consistent at the core data layer.

However, three issues make a 1.0 freeze indefensible in the current state:

1. **Dual `ModelSpecificationError`** — two unrelated classes share the same name across `econflow.exceptions` and `econflow.estimation.base`. They have different MROs. `isinstance()` checks across import paths will silently fail in user code.
2. **`AIProdError` in `__all__`** — a name marked for removal in v0.3.0 is formally committed to by inclusion in `__all__`. The planned removal would constitute a breaking change against the frozen API.
3. **`ValidationIssue` name collision** — both `econflow.config` and `econflow.ingestion` export a class named `ValidationIssue`. There is no disambiguation for users who import from both.

Five additional decisions are required before the freeze is architecturally sound (R-1 through R-5). These are not bugs but unresolved design choices that will constrain the project's ability to evolve after 1.0.

**Estimated effort to reach "Ready to Freeze":** 3–5 targeted edits to `exceptions.py`, `estimation/base.py`, `config/__init__.py`, `ingestion/__init__.py`, and the top-level `__init__.py`. No estimator mathematics, no pipeline changes, no test infrastructure changes are required.

---

## 1. Complete API Inventory and Stability Classification

Stability classifications:
- **Stable** — committed for the life of the 1.0.x series; changes require a major version bump
- **Experimental** — interface may change in minor versions; users should pin to a minor version
- **Internal** — not part of the public API; may change without notice
- **DEPRECATED** — kept for backward compat but excluded from `__all__` before freeze
- **DEFECTIVE** — present but broken; must be fixed before freeze

### 1.1 Top-level `econflow`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `__version__` | str | **Stable** | Semver-versioned |
| `EconFlowError` | Exception | **Stable** | Root exception; all library exceptions should inherit from this |
| `EconFlowCoreError` | Exception | **Experimental** | Subclass of `EconFlowError` post-C12; internal scaffold origin, role unclear to end users |
| `AIProdError` | Exception alias | **DEFECTIVE** | Must be removed from `__all__` before freeze; planned removal in v0.3.0 conflicts with 1.0 freeze |
| `DataValidationError` | Exception | **Stable** | |
| `MergeError` | Exception | **Stable** | |
| `ModelSpecificationError` | Exception | **DEFECTIVE** | Imports `exceptions.py` version (EconFlowError subclass), but `estimation.base` defines a second class with the same name and a different MRO — see Critical Issue C-1 |
| `PipelineError` | Exception | **Stable** | |
| `BaseEstimator` | ABC | **Stable** | Core plugin SDK surface |
| `EstimationResult` | Dataclass | **Stable** | Core data contract; `to_dict` / `from_dict` / `to_json` committed |
| `DiagnosticResult` | Dataclass | **Stable** | Core data contract |
| `PooledOLS` | Class | **Stable** | |
| `EntityFE` | Class | **Stable** | |
| `TwoWayFE` | Class | **Stable** | |
| `register_estimator` | Function | **Stable** | Canonical registry decorator |
| `list_estimators` | Function | **Stable** | |

**Missing from top-level:** `RandomEffects`, `FirstDifference`, `IV2SLS`, `SystemGMM`, `PanelQuantile` are not re-exported here; they require `from econflow.estimation import ...`. This asymmetry is addressed in R-4.

### 1.2 `econflow.estimation`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `EstimationResult` | Dataclass | **Stable** | |
| `DiagnosticResult` | Dataclass | **Stable** | |
| `BaseEstimator` | ABC | **Stable** | |
| `EstimatorError` | Exception | **Stable** | Does not inherit from `EconFlowError` — see Section 5.1 |
| `EstimatorProtocol` | Protocol | **Stable** | `runtime_checkable`; plugin compliance check |
| `BackendCapabilities` | Dataclass | **Stable** | |
| `BACKEND_LINEARMODELS` | str | **Stable** | |
| `BACKEND_STATSMODELS` | str | **Stable** | |
| `BACKEND_PYFIXEST` | str | **Stable** | |
| `BACKEND_DOUBLEML` | str | **Stable** | |
| `BACKEND_PYMC` | str | **Stable** | |
| `BACKEND_CUSTOM` | str | **Stable** | |
| `KNOWN_BACKENDS` | frozenset | **Stable** | |
| `LinearmodelsMixin` | Mixin | **Experimental** | Plugin SDK; concrete helpers may evolve — see R-2 |
| `StatsmodelsMixin` | Mixin | **Experimental** | Same |
| `PyfixestMixin` | Mixin | **Experimental** | Same |
| `DoubleMLMixin` | Mixin | **Experimental** | Same |
| `PyMCMixin` | Mixin | **Experimental** | Same |
| `register_estimator` | Function | **Stable** | Canonical name |
| `get_estimator` | Function | **Stable** | |
| `list_estimators` | Function | **Stable** | |
| `list_by_backend` | Function | **Stable** | |
| `unregister_estimator` | Function | **Stable** | |
| `register` | Function | **DEPRECATED** | Alias for `register_estimator`; remove from `__all__` before freeze — see R-1 |
| `unregister` | Function | **DEPRECATED** | Alias for `unregister_estimator`; same |
| `PooledOLS` | Class | **Stable** | |
| `EntityFE` | Class | **Stable** | |
| `TwoWayFE` | Class | **Stable** | |
| `RandomEffects` | Class | **Stable** | |
| `FirstDifference` | Class | **Stable** | |
| `IV2SLS` | Class | **Stable** | Sprint S2: pooled warning + first-stage / Wu-Hausman / Sargan diagnostics |
| `SystemGMM` | Class | **Experimental** | GMM implementation may need revision for unbalanced panels |
| `PanelQuantile` | Class | **Experimental** | Panel quantile estimation is less mature than the OLS/FE estimators |
| `PipelineContext` | Dataclass | **Experimental** | Architecture Freeze internal; see R-3 |
| `EstimationDispatcher` | Class | **Experimental** | Architecture Freeze internal; see R-3 |

### 1.3 `econflow.diagnostics`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `BaseDiagnostic` | ABC | **Stable** | Plugin SDK surface |
| `DiagnosticError` | Exception | **Stable** | |
| `register_diagnostic` | Function | **Stable** | |
| `get_diagnostic` | Function | **Stable** | |
| `list_diagnostics` | Function | **Stable** | |
| `unregister_diagnostic` | Function | **Stable** | |

### 1.4 `econflow.outputs`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `ReportTable` | Dataclass | **Stable** | |
| `ReportFigure` | Dataclass | **Stable** | |
| `TableRow` | Dataclass | **Stable** | |
| `BaseRenderer` | ABC | **Stable** | Plugin SDK surface |
| `FigureBuilder` | ABC | **Stable** | Plugin SDK surface |
| `RendererError` | Exception | **Stable** | |
| `get_renderer` | Function | **Stable** | |
| `list_renderers` | Function | **Stable** | |
| `register_renderer` | Function | **Stable** | |
| `unregister_renderer` | Function | **Stable** | |
| `build_regression_table` | Function | **Stable** | |
| `build_diagnostics_table` | Function | **Stable** | |
| `build_summary_stats_table` | Function | **Stable** | |
| `build_correlation_table` | Function | **Stable** | |
| `build_hausman_table` | Function | **Stable** | |
| `build_fe_table` | Function | **Stable** | |
| `build_iv_table` | Function | **Stable** | |
| `build_robustness_table` | Function | **Stable** | |
| `CoefficientPlot` | Class | **Stable** | |
| `CIPlot` | Class | **Stable** | |
| `build_diagnostics_report` | Function | **Stable** | |
| `PublicationBundle` | Class | **Stable** | |

### 1.5 `econflow.integrity`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `CERTIFICATE_SCHEMA_VERSION` | str | **Internal** | Schema version string; no user-facing use case — see Rec-1 |
| `ReproducibilityCertificate` | Dataclass | **Stable** | |
| `BaseIntegrityCheck` | ABC | **Stable** | Plugin SDK surface |
| `IntegrityCheckResult` | Dataclass | **Stable** | |
| `get_check` | Function | **Stable** | |
| `list_checks` | Function | **Stable** | |
| `register_integrity_check` | Function | **Stable** | |
| `unregister_integrity_check` | Function | **Stable** | |
| `unregister_check` | Function | **DEPRECATED** | Alias; remove from `__all__` before freeze — see R-1 |
| `DriftItem` | Dataclass | **Stable** | |
| `DriftReport` | Dataclass | **Stable** | |
| `detect_drift` | Function | **Stable** | |
| `ConfigFingerprint` | Class | **Stable** | |
| `DataFingerprint` | Class | **Stable** | |
| `EnvironmentFingerprint` | Class | **Stable** | |
| `ReplicationPackage` | Class | **Stable** | |

### 1.6 `econflow.ingestion`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `AbstractConnector` | ABC | **Stable** | Plugin SDK surface |
| `ConnectorError` | Exception | **Stable** | |
| `CacheManager` | Class | **Stable** | |
| `CacheCorruptionError` | Exception | **Stable** | |
| `DatasetMetadata` | Dataclass | **Stable** | |
| `DatasetManifest` | Dataclass | **Stable** | |
| `ManifestEntry` | Dataclass | **Stable** | |
| `register_connector` | Function | **Stable** | |
| `get_connector` | Function | **Stable** | |
| `list_connectors` | Function | **Stable** | |
| `unregister_connector` | Function | **Stable** | |
| `register` | Function | **DEPRECATED** | Alias; remove from `__all__` before freeze — see R-1 |
| `unregister` | Function | **DEPRECATED** | Alias; same |
| `DataValidator` | Class | **Stable** | |
| `DataValidationConfig` | Dataclass | **Stable** | |
| `DataValidationReport` | Dataclass | **Stable** | |
| `ValidationIssue` | Dataclass | **DEFECTIVE** | Name collision with `econflow.config.ValidationIssue` — see Critical Issue C-3 |

### 1.7 `econflow.config`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `ProjectConfig` | Pydantic v2 model | **Stable** | |
| `ModelsConfig` | Pydantic v2 model | **Stable** | |
| `OutputsConfig` | Pydantic v2 model | **Stable** | |
| `ModelSpec` | Pydantic v2 model | **Stable** | |
| `ConfigLinter` | Class | **Stable** | |
| `LintIssue` | Dataclass | **Stable** | |
| `generate_config_reference` | Function | **Stable** | |
| `write_config_reference` | Function | **Stable** | |
| `ConfigValidator` | Class | **Stable** | |
| `ValidationResult` | Dataclass | **Stable** | |
| `ValidationIssue` | Dataclass | **DEFECTIVE** | Name collision with `econflow.ingestion.ValidationIssue` — see Critical Issue C-3 |

### 1.8 `econflow.replication`

| Symbol | Type | Stability | Notes |
|--------|------|-----------|-------|
| `inspect_project` | Function | **Stable** | |
| `InspectionReport` | Dataclass | **Stable** | |
| `ProjectCheck` | Dataclass | **Stable** | |
| `build_plan` | Function | **Stable** | |
| `ExecutionPlan` | Dataclass | **Stable** | |
| `ExecutionStep` | Dataclass | **Stable** | |
| `execute_plan` | Function | **Stable** | |
| `ReplicationResult` | Dataclass | **Stable** | |
| `StepResult` | Dataclass | **Stable** | |
| `compare_outputs` | Function | **Stable** | |
| `ComparisonReport` | Dataclass | **Stable** | |
| `OutputComparison` | Dataclass | **Stable** | |
| `DEFAULT_TOLERANCE` | float | **Stable** | Document the value and rationale — see Rec-3 |
| `ReproducibilityReport` | Class | **Stable** | |

### 1.9 CLI Commands

| Command | Stability | Notes |
|---------|-----------|-------|
| `econflow --version` | **Stable** | |
| `econflow init [DIRECTORY]` | **Stable** | |
| `econflow doctor` | **Stable** | |
| `econflow validate` | **Stable** | |
| `econflow info` | **Stable** | |
| `econflow run` | **Stable** | |
| `econflow report` | **Stable** | |
| `econflow certify` | **Stable** | |
| `econflow verify` | **Stable** | |
| `econflow package` | **Stable** | |
| `econflow fetch` | **Stable** | |
| `econflow cache` | **Stable** | |
| `econflow datasets` | **Stable** | |
| `econflow release-check` | **Internal** | Developer / CI quality gate; should not be listed alongside user-facing commands — see Rec-5 |
| `econflow inspect` | **UNVERIFIED** | In `replication` module docstring but absent from `cli.py` docstring; see R-5 |
| `econflow reproduce` | **UNVERIFIED** | Same |
| `econflow compare` | **UNVERIFIED** | Same |

### 1.10 Plugin / Extension Points

| Interface | Stability | Notes |
|-----------|-----------|-------|
| `econflow.plugins` entry point group | **Stable** | Auto-loaded by all registries; stable extension point — needs documentation — see Rec-4 |
| `BaseEstimator` subclassing + `validate`/`fit`/`diagnostics` ABC | **Stable** | |
| `@register_estimator(id)` decorator | **Stable** | |
| `EstimatorProtocol` conformance check | **Stable** | |
| `BaseDiagnostic` subclassing + `@register_diagnostic` | **Stable** | |
| `AbstractConnector` subclassing + `@register_connector` | **Stable** | |
| `BaseRenderer` subclassing + `@register_renderer` | **Stable** | |
| `BaseIntegrityCheck` subclassing + `@register_integrity_check` | **Stable** | |

### 1.11 YAML Configuration Schema

| Key / File | Stability | Notes |
|------------|-----------|-------|
| `config/config.yaml` (ProjectConfig) | **Stable** | All fields validated by Pydantic v2 |
| `config/models.yaml` (ModelsConfig + ModelSpec) | **Stable** | `estimator_id` validated against live registry |
| `config/outputs.yaml` (OutputsConfig) | **Stable** | |
| `KNOWN_ESTIMATORS` list in models.yaml | **DEPRECATED** | Replaced by registry-driven validation; fallback should be removed before freeze |

---

## 2. Critical Issues (Blocking — Must Fix Before Freeze)

### C-1: Dual `ModelSpecificationError` — Two Classes, Same Name, Different MROs

**Severity: CRITICAL**

`econflow.exceptions.ModelSpecificationError` inherits from `EconFlowError`. `econflow.estimation.base.ModelSpecificationError` inherits from `EstimatorError`. They share a name but are completely unrelated in the class hierarchy.

```python
from econflow import ModelSpecificationError as A
from econflow.estimation.base import ModelSpecificationError as B
assert A is B   # AssertionError — they are different objects
assert issubclass(B, A)  # False — different MROs
```

**Impact:** A user who writes `except ModelSpecificationError` after `from econflow import ModelSpecificationError` will NOT catch exceptions raised by estimators that use `raise ModelSpecificationError(...)` from `econflow.estimation.base`. The exception propagates uncaught. This is a silent production bug.

The Sprint S1 docstring for `econflow.estimation.base.ModelSpecificationError` says it was "Added to support detection of time-invariant regressors." This strongly suggests the intention was to add a new error type, not to shadow the root hierarchy.

**Required fix:** Unify into one class. Recommended path:
1. Keep `econflow.exceptions.ModelSpecificationError` (subclass of `EconFlowError`).
2. In `econflow.estimation.base`, import and re-export it rather than defining a second class: `from econflow.exceptions import ModelSpecificationError`.
3. Make the unified class inherit from both `EstimatorError` and `EconFlowError` so that `except EstimatorError` and `except EconFlowError` both catch it.
4. Update the Sprint S1 docstring to reflect the unified class.

---

### C-2: `AIProdError` in `__all__` Conflicts with 1.0 Freeze

**Severity: CRITICAL**

`AIProdError` is documented in `econflow/__init__.py` as "deprecated alias — kept for backward compat until v0.3.0." It is included in `__all__`.

A 1.0 API freeze commits to all items in `__all__` until the next major version (2.0). Removing `AIProdError` in v0.3.0 or v1.x after a 1.0 freeze would violate semantic versioning.

**Required fix:** Remove `AIProdError` from `__all__` before freezing. Retain the alias in the module body with a `DeprecationWarning` triggered on attribute access (or via `__getattr__` at the module level), so existing code continues to work but users are warned. The name will be gone from the committed public API without being a runtime removal.

---

### C-3: `ValidationIssue` Name Collision Between `econflow.config` and `econflow.ingestion`

**Severity: CRITICAL**

Both subpackages export a class named `ValidationIssue` representing completely different concepts:
- `econflow.config.ValidationIssue` — a YAML configuration lint issue
- `econflow.ingestion.ValidationIssue` — a data quality / schema validation issue

```python
from econflow.config import ValidationIssue    # config issue
from econflow.ingestion import ValidationIssue  # data issue — silently shadows the first import
```

Type checkers cannot infer intent. IDE autocomplete gives the wrong class. Any code that imports from both subpackages in the same module must alias one, which users will discover only after hitting confusing type errors or silent mis-catches.

**Required fix:** Rename before freeze. Options:
- Rename `econflow.config.ValidationIssue` → `ConfigValidationIssue` (or `LintViolation`)
- Rename `econflow.ingestion.ValidationIssue` → `DataValidationIssue`
- Both renames are preferable to clearly distinguish the two error domains.

---

## 3. Required Decisions (Must Resolve Before Freeze)

### R-1: Deprecated Aliases in `__all__`

The following deprecated names are currently in public `__all__` and will be frozen by a 1.0 release:

| Symbol | Module | Canonical name |
|--------|--------|---------------|
| `register` | `econflow.estimation` | `register_estimator` |
| `unregister` | `econflow.estimation` | `unregister_estimator` |
| `register` | `econflow.ingestion` | `register_connector` |
| `unregister` | `econflow.ingestion` | `unregister_connector` |
| `unregister_check` | `econflow.integrity` | `unregister_integrity_check` |

**Decision:** Remove all five from `__all__` before freeze. Retain in the module body so existing code does not break at runtime, but issue `DeprecationWarning` on use. They are not committed to under the 1.0 API contract.

---

### R-2: Backend Mixin Classification

`LinearmodelsMixin`, `StatsmodelsMixin`, `PyfixestMixin`, `DoubleMLMixin`, `PyMCMixin` are exported from `econflow.estimation.__all__`. They are scaffold for plugin authors, but their helper method signatures are not formally documented or tested as API contracts.

If they are frozen as Stable, any change to a mixin method (adding a parameter, changing a return type) is a breaking change that affects all plugin authors who inherited from the mixin.

**Decision options:**
- Classify as **Experimental** (document that signatures may change in minor versions) and keep in `__all__`.
- Move to `econflow.estimation._backends` (Internal) and exclude from `__all__`.

The second option is lower risk. Plugin authors who need backend helpers can still import from the private path; only the public commitment is removed.

---

### R-3: `PipelineContext` and `EstimationDispatcher` Classification

These two classes are Architecture Freeze invariants. They are in `econflow.estimation.__all__`.

`PipelineContext` is the internal parameter bundle; `EstimationDispatcher` is the sole production dispatch path. Exposing them as formally public means any future pipeline refactoring (e.g., async dispatch, multi-model dispatch) creates a user-visible breaking change.

The Architecture Freeze was an internal engineering constraint that prevented changes during Sprint development. It is separate from a public API commitment.

**Decision:** Move both to `Experimental` in the short term (minor versions may change them). Before 1.0, formally document their interface contracts if they are to be Stable, or move them to `econflow.estimation._pipeline` and exclude from `__all__`.

---

### R-4: Top-level Estimator Export Asymmetry

`PooledOLS`, `EntityFE`, `TwoWayFE` are re-exported from the top-level `econflow` namespace. `RandomEffects`, `FirstDifference`, `IV2SLS`, `SystemGMM`, `PanelQuantile` are not.

This creates asymmetric discoverability: the three most commonly used estimators are importable as `from econflow import EntityFE`, but a user looking for `IV2SLS` must know to use `from econflow.estimation import IV2SLS`.

**Decision:** Either add all 8 estimators to `econflow.__all__` (preferred for consistency), or explicitly document in the module docstring that the top-level namespace exports only the three core OLS/FE estimators as convenience imports.

---

### R-5: Replication CLI Commands — Verify Wiring

The `econflow.replication` module docstring explicitly documents three CLI commands:
- `econflow inspect <project_dir>`
- `econflow reproduce <project_dir>`
- `econflow compare <baseline_dir> <replica_dir>`

The `cli.py` module docstring lists 14 commands and does not include any of these three. Either:
- They are wired in `cli.py` but missing from the docstring (documentation bug), or
- They were never wired into the CLI entry point (implementation bug).

**Action required:** Verify `cli.py` against `econflow.replication` module docstring and reconcile before freeze.

---

## 4. Recommended Changes (Improve Before Freeze)

### Rec-1: Remove `CERTIFICATE_SCHEMA_VERSION` from `integrity.__all__`

This is an internal schema version string for the reproducibility certificate JSON format. No user-facing code should inspect or depend on it directly. Including it in `__all__` commits to the name for the life of 1.0. Move to `_CERTIFICATE_SCHEMA_VERSION` (private) or at minimum remove from `__all__`.

### Rec-2: Document `EconFlowCoreError` Role Explicitly

After the C12 unification, `EconFlowCoreError` is a subclass of `EconFlowError` and is exported at the top level. Its origin as an internal scaffold exception means its semantics relative to `EconFlowError` are unclear to end users. Document when to raise it versus the other exception types, or move it to `Internal` classification.

### Rec-3: Document `DEFAULT_TOLERANCE` Value and Rationale

`DEFAULT_TOLERANCE` is a float constant in `econflow.replication.__all__`. Its value and the rationale for that value (e.g., relative tolerance for floating-point output comparison) should be documented in the class/function docstring of `compare_outputs`. Users writing blind replication tests need to know when to override it.

### Rec-4: Document `econflow.plugins` Entry Point Group

The estimator, connector, diagnostic, and renderer registries all call `_load_entry_point_plugins()` on initialization, which loads any package registered under the `econflow.plugins` entry point group. This is a genuine public extension point for third-party packages, but it is not documented in the Plugin SDK. Add a section to `docs/sdk/PLUGIN_SDK.md` describing the expected `pyproject.toml` configuration and what `__init__.py` must expose.

### Rec-5: Classify `econflow release-check` as a Developer Command

`econflow release-check` runs the 9-check Release Quality Gate. It is a CI/developer tool, not a user-facing data analysis command. Its presence among `--version`, `run`, `certify` etc. is confusing to first-time users. Options: move under `econflow dev release-check`, or add a `[Developer Tools]` section in the CLI help output.

---

## 5. Internal Consistency Check

### 5.1 Exception Hierarchy

The project intends `EconFlowError` to be the root of all library exceptions. The current state:

| Exception | Inherits from | Consistent? |
|-----------|--------------|-------------|
| `EconFlowError` | `Exception` | ✅ Root |
| `EconFlowCoreError` | `EconFlowError` (post-C12) | ✅ In hierarchy |
| `AIProdError` | alias for `EconFlowError` | ❌ Should be removed from `__all__` |
| `DataValidationError` | `EconFlowError` | ✅ |
| `MergeError` | `EconFlowError` | ✅ |
| `PipelineError` | `EconFlowError` | ✅ |
| `ModelSpecificationError` (exceptions.py) | `EconFlowError` | ❌ Duplicate class |
| `ModelSpecificationError` (estimation/base.py) | `EstimatorError` | ❌ Duplicate class |
| `EstimatorError` | `Exception` (not `EconFlowError`) | ⚠️ Intentional decoupling, but undocumented |

The `EstimatorError` / `EconFlowError` disconnect is a potential user-facing gap: `except EconFlowError` at the application level will miss all estimation errors unless C-1 is resolved and the unified `ModelSpecificationError` bridges the two hierarchies. This behavior should be explicitly documented if the decoupling is intentional.

### 5.2 Registry Pattern Consistency

All four registries (estimation, diagnostics, ingestion, integrity) are consistent:

| Operation | estimation | diagnostics | ingestion | integrity |
|-----------|-----------|-------------|-----------|-----------|
| Register | `register_estimator` | `register_diagnostic` | `register_connector` | `register_integrity_check` |
| Get | `get_estimator` | `get_diagnostic` | `get_connector` | `get_check` |
| List | `list_estimators` | `list_diagnostics` | `list_connectors` | `list_checks` |
| Unregister | `unregister_estimator` | `unregister_diagnostic` | `unregister_connector` | `unregister_integrity_check` |

The pattern is clean and uniform. The only exceptions are the deprecated short aliases (`register`/`unregister`) in estimation and ingestion, which are addressed in R-1. Once those are removed from `__all__`, the registry API is fully consistent across all four subsystems.

### 5.3 Serialization Contract

`EstimationResult` and `DiagnosticResult` implement `to_dict()`, `to_json()`, and `from_dict()`. This is a documented stable contract.

Notably, the higher-level result objects in `econflow.replication` (`InspectionReport`, `ExecutionPlan`, `ReplicationResult`, `ComparisonReport`) do not appear to implement this interface. Users who want to serialize these results for downstream analysis will have inconsistent experiences depending on which subpackage they use. This is not critical for 1.0 but should be noted in the roadmap.

### 5.4 YAML Config Schema vs. Registry Coupling

`ModelsConfig` now validates `estimator_id` values against the live registry (Phase 4 work). The `KNOWN_ESTIMATORS` fallback list in `models.py` is deprecated. Before freeze, the fallback should be fully removed so the registry is the sole source of truth for valid estimator identifiers. Retaining the fallback creates a second code path that can diverge from the registry.

### 5.5 Naming Convention Consistency

Across all subpackages, public function names follow `verb_noun` (e.g., `list_estimators`, `get_estimator`, `detect_drift`, `build_plan`, `inspect_project`). Class names follow `NounNoun` PascalCase. These conventions are consistent and should be enforced for any future additions.

One anomaly: `build_diagnostics_report` (in `outputs`) returns a `DiagnosticsReportBuilder` or similar, while `detect_drift` (in `integrity`) returns a `DriftReport` directly. The asymmetry in verb choice (`build_` vs. `detect_`) across different concepts is acceptable; the convention is domain-driven rather than uniform.

---

## 6. Risks of Freezing the Current API

### Risk 1 — Silent `ModelSpecificationError` miss-catches (HIGH)

If C-1 is not resolved and the API is frozen, users who write `except ModelSpecificationError` after importing from `econflow` will silently miss exceptions raised from within estimators. The bug is invisible at the code-reading level and will surface only as uncaught exceptions in production.

### Risk 2 — `AIProdError` trapped by freeze (MEDIUM-HIGH)

If `AIProdError` is frozen in `__all__`, the planned v0.3.0 removal becomes a semantic versioning violation. Either the removal is cancelled (accumulating technical debt) or the project makes a major version bump for what is effectively a single alias removal.

### Risk 3 — Backend mixin signature binding (MEDIUM)

If `LinearmodelsMixin` et al. are frozen as Stable, refactoring any mixin helper method requires a major version bump. All 8 built-in estimators use these mixins. This constrains the project's ability to adopt new linearmodels API versions without a 2.0 release.

### Risk 4 — `PipelineContext` coupling for plugin authors (MEDIUM)

Plugin authors who import `PipelineContext` to test their estimators within the dispatch flow will be broken by any pipeline architecture change. Freezing `PipelineContext` as Stable binds the pipeline architecture for the life of 1.0.

### Risk 5 — Deprecated alias accumulation (LOW)

There are 5 deprecated names across `__all__` of three subpackages. If frozen, these names must be maintained until 2.0. They add noise to API documentation and IDE autocomplete. The maintenance cost is low but non-zero.

### Risk 6 — Missing replication CLI commands (LOW-MEDIUM)

If `econflow inspect`, `econflow reproduce`, and `econflow compare` are not wired into `cli.py`, the `replication` subpackage is only accessible via the Python API. This is a discoverability issue for researchers who primarily use the CLI workflow.

---

## 7. Final Recommendation

### ❌ NOT READY TO FREEZE

Three critical defects (C-1, C-2, C-3) must be resolved before a 1.0 API freeze is defensible. Five design decisions (R-1 through R-5) must be made explicitly, even if the answer is "freeze the current state intentionally."

### Freeze-Readiness Checklist

| Item | Status |
|------|--------|
| C-1: Resolve dual `ModelSpecificationError` | ❌ Open |
| C-2: Remove `AIProdError` from `__all__` | ❌ Open |
| C-3: Rename `ValidationIssue` name collision | ❌ Open |
| R-1: Remove deprecated aliases from `__all__` | ⚠️ Decision required |
| R-2: Classify backend mixins (Stable or Internal) | ⚠️ Decision required |
| R-3: Classify `PipelineContext`/`EstimationDispatcher` | ⚠️ Decision required |
| R-4: Reconcile top-level estimator exports | ⚠️ Decision required |
| R-5: Verify replication CLI commands are wired | ⚠️ Needs verification |
| Rec-1: Remove `CERTIFICATE_SCHEMA_VERSION` from `__all__` | ℹ️ Recommended |
| Rec-2: Document `EconFlowCoreError` role | ℹ️ Recommended |
| Rec-3: Document `DEFAULT_TOLERANCE` | ℹ️ Recommended |
| Rec-4: Document `econflow.plugins` entry point | ℹ️ Recommended |
| Rec-5: Move `release-check` to developer section | ℹ️ Recommended |

Once all three Critical items are resolved and all five Required decisions are made, the API is ready for freeze. The overall API design is sound: the registry pattern is consistent, the plugin SDK surface is clearly delineated, the serialization contract is uniform at the core layer, and the CLI covers the full researcher workflow. The issues identified are targeted and fixable without any architectural changes.

---

*Report generated 2026-07-13. Based on direct inspection of all 8 subpackage `__init__.py` files, the top-level `__init__.py`, `cli.py`, `estimation/base.py`, `estimation/result.py`, `estimation/registry.py`, `estimation/protocol.py`, and `exceptions.py`.*
