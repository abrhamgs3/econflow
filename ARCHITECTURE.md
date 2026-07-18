# Architecture Overview

**EconFlow Platform** — v0.1.0

This document describes the current architecture of the `econflow` package
located at `src/econflow/`. Keep it in sync with the code.

---

## Design Goals

**Reproducibility** — every result traces to a specific data file, code commit,
and pipeline run.  **Modularity** — each subsystem can be tested independently.
**Generality** — any cross-country panel project can be configured without
touching platform code.

---

## Package Layout

```
src/econflow/
├── __init__.py          version string, top-level re-exports
├── cli.py               Active Typer CLI — doctor and run commands
├── pipeline.py          Sequential pipeline orchestrator
├── provenance.py        ProvenanceRecorder — run metadata to JSON
├── exceptions.py        Domain exception hierarchy (EconFlowError)
├── logging.py           Structured logging configuration
├── core/                Cross-cutting platform infrastructure
│   ├── config.py        Pydantic configuration loader
│   ├── exceptions.py    Scaffold exception hierarchy (EconFlowCoreError tree)
│   ├── pipeline.py      DAG-based pipeline orchestrator (Sprint 3+)
│   ├── provenance.py    run_metadata snapshot (stub)
│   └── registry.py      Project registry
├── ingestion/           Data connectors (Sprint 4)
│   ├── __init__.py      Public API re-exports
│   ├── base.py          AbstractConnector + ConnectorError
│   ├── registry.py      @register() decorator, get_connector(), list_connectors()
│   ├── metadata.py      DatasetMetadata — immutable provenance record
│   ├── cache.py         CacheManager — slot-based filesystem cache + SHA-256 verification
│   ├── validation.py    DataValidator, DataValidationConfig, DataValidationReport
│   └── connectors/
│       ├── __init__.py  Imports all built-in connectors (triggers @register())
│       ├── csv_connector.py  LocalCSVConnector [implemented]
│       ├── world_bank.py     WorldBankConnector [implemented]
│       ├── oecd.py           OECDConnector [stub]
│       └── pwt.py            PennWorldTablesConnector [stub]
├── processing/          Data transformation pipeline
│   ├── harmonise.py     CountryHarmoniser — ISO-3 crosswalk
│   ├── merge.py         DatasetMerger
│   ├── transform.py     Log transforms, variable construction
│   ├── ai_index.py      AIProxyIndexBuilder (PCA / equal-weight)
│   ├── tfp.py           TFPProcessor — PWT extraction + Solow residual
│   └── quality.py       QualityReporter, validate_data
├── estimation/          Plugin-based estimation framework (Sprint 5)
│   ├── __init__.py      Public API; imports all built-ins (triggers @register())
│   ├── registry.py      @register() decorator, get_estimator(), list_estimators()
│   ├── base.py          BaseEstimator ABC, EstimatorError (re-exports result types)
│   ├── result.py        EstimationResult, DiagnosticResult dataclasses
│   ├── ols.py           PooledOLS [implemented]
│   ├── fixed_effects.py EntityFE, TwoWayFE [implemented]
│   ├── random_effects.py RandomEffects [implemented]
│   ├── first_difference.py FirstDifference [implemented]
│   ├── iv.py            IV2SLS [implemented]
│   ├── gmm.py           SystemGMM [stub]
│   └── quantile.py      PanelQuantile [stub]
├── diagnostics/         Post-estimation diagnostic plugin framework (Sprint 5)
│   ├── __init__.py      Public API; imports all plugins (triggers @register_diagnostic())
│   ├── registry.py      @register_diagnostic(), get_diagnostic(), list_diagnostics()
│   ├── base.py          BaseDiagnostic ABC, DiagnosticError
│   └── plugins/
│       ├── __init__.py  Imports all 6 plugins to trigger registration
│       ├── hausman.py         Hausman endogeneity test [implemented]
│       ├── breusch_pagan.py   Breusch-Pagan LM test [implemented]
│       ├── pesaran_cd.py      Pesaran CD test [implemented]
│       ├── vif.py             VIF check [implemented]
│       ├── wooldridge.py      Wooldridge test [stub]
│       └── serial_correlation.py  Serial correlation test [stub]
├── sensitivity/         Robustness analysis
│   ├── runner.py        SensitivityRunner.from_models_yaml()
│   └── comparison.py    ResultsComparison — side-by-side table
├── data/                Active data loading/validation layer
│   ├── loaders.py       load_panel(), drop_aggregate_entities()
│   ├── validators.py    validate_data(), report_has_blockers()
│   └── cleaning.py      sample_selection_summary()
├── econometrics/        Active panel econometrics suites
│   └── panel.py         run_robustness/sensitivity/falsification/heterogeneity_suite
├── features/            Active variable engineering
│   └── engineering.py   log transforms, sub-index construction
├── visualization/       Publication figures
│   ├── figures.py       scatter, trend, coefficient comparison, missingness
│   └── style.py         Matplotlib style configuration
├── reporting/           LaTeX narrative generation
│   └── narrative.py     write_results(), write_falsification_results()
├── outputs/             Output renderers (Sprint 4+)
│   ├── base.py          Abstract BaseRenderer
│   ├── tables.py        TableRenderer
│   ├── figures.py       FigureRenderer
│   └── reports.py       PDFReportCompiler
├── commands/            Sprint 3B+ CLI command implementations
│   ├── _shared.py       Shared utilities: STATUS_ICONS, deep_get, load_yaml_safe
│   ├── init.py          econflow init — project scaffold
│   ├── doctor.py        econflow doctor — environment health check
│   ├── validate.py      econflow validate — config/data validation
│   └── info.py          econflow info — project summary + estimator registry
├── cli_scaffold/        Future multi-command CLI (Sprint 6)
│   ├── main.py          Typer app root
│   └── commands/        run, validate, reproduce, project
├── ml/                  Reserved
└── utils/               Reserved

tests/
├── conftest.py               Shared fixtures (generic sample_panel)
├── test_exceptions.py        Exception hierarchy tests
├── test_provenance.py        ProvenanceRecorder unit tests
├── regression/
│   ├── helpers.py            Six comparison utilities
│   ├── conftest.py           Reference-set loading fixtures
│   └── test_helpers.py       Unit tests for helpers
├── fixtures/
│   ├── synthetic/
│   │   └── sample_panel.csv  Generic 150-row synthetic panel
│   └── reference_outputs/    Moved → examples/ai_productivity_paper/reference_outputs/
├── unit/                     Unit tests for command modules + shared utilities
│   ├── test_shared.py        STATUS_ICONS, deep_get, load_yaml_safe (Sprint 3B.1)
│   ├── test_cmd_init.py      econflow init command
│   ├── test_cmd_doctor.py    econflow doctor command
│   ├── test_cmd_validate.py  econflow validate command
│   └── test_cmd_info.py      econflow info command
└── integration/              End-to-end workflow tests
    ├── test_workspace_lifecycle.py   init → validate → info roundtrip
    ├── test_pipeline_e2e.py         Full pipeline on getting_started example
    ├── test_csv_connector.py        LocalCSVConnector end-to-end (fetch + cache)
    ├── test_estimator_run.py        OLS/FE/TWFE/RE/FD/IV on synthetic panel (Sprint 5)
    └── test_diagnostic_run.py       Hausman/BP/CD/VIF diagnostic plugins (Sprint 5)
```

---

## Shared CLI Utilities (`commands/_shared.py`)

All four command modules share common building blocks extracted into
`econflow.commands._shared` (Sprint 3B.1).  Import from here rather than
duplicating:

| Symbol | Type | Used by |
|--------|------|---------|
| `STATUS_ICONS` | `dict[str, str]` | doctor, validate, init |
| `deep_get(data, *keys)` | function | validate, info |
| `load_yaml_safe(path)` | function | validate, info |

**Registry-driven validation**: `validate.py` derives `_SUPPORTED_ESTIMATORS`
from `list_estimators()` (Sprint 5 live registry).  Adding a new `@register()`ed
estimator automatically makes it accepted by `econflow validate` and visible in
`econflow info` — no manual list updates needed.

---

## Active vs. Scaffold Modules

The package currently has two implementation layers:

Two namespace overlaps are intentional and will be resolved during the scaffold migration:

- `econometrics/` (active suites) and `estimation/` (scaffold estimator classes) serve different abstraction levels. Import from `econflow.econometrics` for running model suites; `econflow.estimation` will expose low-level estimators once populated.
- `visualization/` (active figures) and `outputs/figures.py` (scaffold renderer) will be merged into `outputs/` in Sprint 4. Use `econflow.visualization` until then.

**Active** (`data/`, `econometrics/`, `features/`, `visualization/`, `reporting/`,
`pipeline.py`, `provenance.py`, `cli.py`) — production code used by
`run_pipe