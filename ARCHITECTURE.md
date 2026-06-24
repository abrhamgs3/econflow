# Architecture Overview

**EconFlow Platform** — v0.2.0

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
├── exceptions.py        Domain exception hierarchy (AIProdError)
├── logging.py           Structured logging configuration
├── core/                Cross-cutting platform infrastructure
│   ├── config.py        Pydantic configuration loader
│   ├── exceptions.py    Extended exception hierarchy (APRPError tree)
│   ├── pipeline.py      DAG-based pipeline orchestrator (Sprint 3+)
│   ├── provenance.py    run_metadata snapshot (stub)
│   └── registry.py      Project registry
├── ingestion/           Data connectors
│   ├── base.py          Abstract BaseConnector
│   ├── cache.py         DownloadCache filesystem key-value store
│   ├── world_bank.py    World Bank API v2 connector
│   ├── oecd.py          OECD SDMX-JSON connector
│   └── pwt.py           Penn World Tables connector
├── processing/          Data transformation pipeline
│   ├── harmonise.py     CountryHarmoniser — ISO-3 crosswalk
│   ├── merge.py         DatasetMerger
│   ├── transform.py     Log transforms, variable construction
│   ├── ai_index.py      AIProxyIndexBuilder (PCA / equal-weight)
│   ├── tfp.py           TFPProcessor — PWT extraction + Solow residual
│   └── quality.py       QualityReporter, validate_data
├── estimation/          Panel estimators
│   ├── base.py          Abstract BaseEstimator, EstimationResult
│   ├── ols.py           PooledOLS
│   ├── fixed_effects.py TwoWayFE (linearmodels.PanelOLS wrapper)
│   ├── random_effects.py RandomEffectsGLS
│   ├── iv.py            IVEstimator (2SLS)
│   ├── gmm.py           GMMEstimator (Arellano-Bond / Blundell-Bond)
│   └── quantile.py      PanelQuantile
├── diagnostics/         Post-estimation diagnostic tests
│   ├── specification.py Hausman test
│   ├── overid.py        Sargan-Hansen J-test
│   ├── dependence.py    Pesaran cross-sectional dependence CD test
│   ├── serial.py        Arellano-Bond AR(1)/AR(2) test
│   └── reporter.py      DiagnosticReport — unified diagnostics summary
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
├── cli_scaffold/        Future multi-command CLI (Sprint 6)
│   ├── main.py          Typer app root
│   └── commands/        run, validate, reproduce, project
├── ml/                  Reserved
└── utils/               Reserved

tests/
├── conftest.py               Shared fixtures (generic sample_panel)
├── test_exceptions.py        Exception hierarchy tests
├── test_provenance.py        ProvenanceRecorder unit tests (35 tests)
├── regression/
│   ├── helpers.py            Six comparison utilities
│   ├── conftest.py           Reference-set loading fixtures
│   └── test_helpers.py       Unit tests for helpers (49 tests)
├── fixtures/
│   ├── synthetic/
│   │   └── sample_panel.csv  Generic 150-row synthetic panel
│   └── reference_outputs/    Moved → examples/ai_productivity_paper/reference_outputs/
├── unit/                     Reserved — Sprint 3+
└── integration/              Reserved — Sprint 3+
```

---

## Active vs. Scaffold Modules

The package currently has two implementation layers:

**Active** (`data/`, `econometrics/`, `features/`, `visualization/`, `reporting/`,
`pipeline.py`, `provenance.py`, `cli.py`) — production code used by
`run_pipeline.py` in the paper repo. All 109 tests cover this layer.

**Scaffold** (`core/`, `ingestion/`, `processing/`, `estimation/`, `diagnostics/`,
`sensitivity/`, `outputs/`, `cli_scaffold/`) — target architecture stubs.
These will be populated in Sprints 3–8 as the migration progresses. The scaffold
is imported by `projects/` configs but does not execute real logic yet.

The migration roadmap is in `docs/SPRINT_MIGRATION_ROADMAP.md`.

---

## Pipeline (Active)

`econflow.pipeline.run()` executes five subsystems in order:

```
validate_data → load_panel → econometrics suites → figures → narratives
```

---

## Exception Hierarchy (Active)

```
AIProdError
├── DataValidationError
├── MergeError
├── PipelineError
└── ModelSpecificationError
```

Extended hierarchy (scaffold, `core/exceptions.py`):

```
APRPError
├── ConfigurationError  └── MissingConfigKeyError
├── RegistryError       └── ProjectNotFoundError
├── PipelineError       └── StageExecutionError
├── IngestionError      ├── DownloadError, CacheError
├── ProcessingError     ├── HarmonisationError, TransformationError
├── EstimationError     └── ConvergenceError
├── DiagnosticsError
└── OutputError
```

---

## Testing

```bash
pytest                          # all tests
pytest tests/regression/        # regression helper tests (49)
pytest tests/test_provenance.py # ProvenanceRecorder (35)
```

Known baseline issue: `ai_index_levels_fe` reference output (n=1,144) was
produced from an intermediate dataset. Current platform produces n=2,053.
Root cause documented in the paper repo's `outputs/FORENSIC_REPORT_ai_index_levels_fe.md`.
