# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.2.0] — 2026-06-24  *(Release Candidate 1)*

### Changed — Breaking (public API)
- **Renamed base exception** `AIProdError` → `EconFlowError` in
  `src/econflow/exceptions.py`.  `AIProdError` is kept as a deprecated alias
  emitting `DeprecationWarning`; it will be removed in v0.3.0.
- **CLI entry point renamed** `ai-productivity` → `econflow`.  Update any
  scripts or CI commands that call `ai-productivity`.
- **Environment-variable prefix** changed from `APRP_` to `ECONFLOW_`.
  Users who configured `APRP_*` variables must rename them.
- **Scaffold root exception** `APRPError` renamed to `EconFlowCoreError` in
  `src/econflow/core/exceptions.py`.  `APRPError` kept as deprecated alias.

### Changed — Non-breaking
- `DEFAULT_REQUIRED_COLUMNS` replaces hard-coded `REQUIRED_COLUMNS` constant
  in `src/econflow/data/validators.py`.  `validate_data()` now accepts
  `required_columns`, `entity_col`, `time_col`, and `log_vars` parameters for
  full schema configurability.  `REQUIRED_COLUMNS` is kept as an alias.
- Provenance schema `$id` changed from `ai-productivity/provenance/run_metadata/v1`
  to `econflow/provenance/run_metadata/v1`.  Existing `run_metadata.json` files
  remain valid; the `$id` is informational only.
- `tests/conftest.py` `sample_panel` fixture now uses generic column names
  (`entity`, `time`, `outcome`, `treatment`, `covariate_1`, `covariate_2`).
- All module docstrings updated to reference EconFlow rather than the
  AI & Productivity paper.
- `app/streamlit_app.py` page title updated to "EconFlow Pipeline".

### Fixed
- Broken file-path reference in `src/econflow/processing/harmonise.py`
  (`ai_productivity/data/iso3_crosswalk.csv` → `econflow/data/iso3_crosswalk.csv`).

---

## [0.1.0] — 2026-06-18

### Added
- Professional `src/econflow/` package layout (extracted from AI & Productivity paper).
- `pyproject.toml` replacing `requirements.txt`; package installable via `uv pip install -e .`.
- CLI entry point `econflow` with `--version`, `doctor`, and `run` commands.
- Centralized structured logger (`econflow.logging`).
- Domain-specific exception hierarchy (`EconFlowError`, `DataValidationError`,
  `MergeError`, `PipelineError`, `ModelSpecificationError`).
- First automated test suite (`tests/test_exceptions.py`).
- `.gitignore` configured for Python research projects.
- GitHub Actions CI workflow (install → test → lint on every push).
- ProvenanceRecorder context manager with 35 unit tests.
- Regression testing framework with 6 comparison utilities (49 tests).
- Reference output fixtures with SHA-256 manifest.

### Existing (pre-extraction)
- Panel dataset: 25-column CSV, 193 countries × 2010–2024.
- Data sources: WDI, PWT, AI Index proxy, WGI, Barro-Lee.
- Econometric pipeline: baseline FE, two-way FE, trimmed FE, growth model,
  sensitivity suite, falsification suite, heterogeneity suite.
- Visualization: scatter, trend, coefficient comparison, missingness profile.
