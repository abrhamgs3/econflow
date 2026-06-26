# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] — 2026-06-24 — *First public release*

### Added
- Professional `src/econflow/` package layout extracted from the AI & Productivity paper.
- `pyproject.toml`: package installable via `pip install econflow` or `uv pip install -e .`.
- CLI entry point `econflow` with `--version`, `doctor`, and `run` commands.
- Centralised structured logger (`econflow.logging`).
- Domain-specific exception hierarchy: `EconFlowError`, `DataValidationError`,
  `MergeError`, `PipelineError`, `ModelSpecificationError`.
  `AIProdError` kept as a deprecated alias; will be removed in v0.3.0.
- `EconFlowCoreError` as scaffold root; `APRPError` kept as deprecated alias.
- Configurable `validate_data()`: accepts `required_columns`, `entity_col`,
  `time_col`, and `log_vars` parameters; `DEFAULT_REQUIRED_COLUMNS` constant.
- Provenance recorder (`ProvenanceRecorder`) with SHA-256 output hashing.
- Regression testing framework with 6 comparison utilities.
- Reference output fixtures (44 artefacts + SHA-256 manifest) in
  `examples/ai_productivity_paper/reference_outputs/`.
- Full automated test suite: 100 tests (49 regression, 16 exception, 35 provenance).
- GitHub Actions CI: pytest on Python 3.10/3.11/3.12 + ruff lint.
- MIT LICENSE.

### Domain-neutral rewrite (pre-release cleanup)
- Renamed base exception `AIProdError` → `EconFlowError`.
- Renamed CLI entry point `ai-productivity` → `econflow`.
- Renamed environment-variable prefix `APRP_` → `ECONFLOW_`.
- Renamed scaffold root exception `APRPError` → `EconFlowCoreError`.
- Provenance schema `$id` updated to `econflow/provenance/run_metadata/v1`.
- Fixed broken path in `src/econflow/processing/harmonise.py`.
- All module docstrings updated to reference EconFlow.
- AI & Productivity paper assets relocated to `examples/ai_productivity_paper/`
  (config, Streamlit dashboard, reference outputs).

### Existing (pre-extraction, unchanged)
- Panel dataset: 25-column CSV, 193 countries × 2010–2024.
- Data sources: WDI, PWT, AI Index proxy, WGI, Barro-Lee.
- Econometric pipeline: baseline FE, two-way FE, trimmed FE, growth model,
  sensitivity suite, falsification suite, heterogeneity suite.
- Visualization: scatter, trend, coefficient comparison, missingness profile.

---

[Unreleased]: https://github.com/abrhamgs3/econflow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/abrhamgs3/econflow/releases/tag/v0.1.0
