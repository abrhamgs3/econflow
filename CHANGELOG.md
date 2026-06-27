# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
  appends a dataset provenance record to `metadata["datasets"]` in the run JSON.
- `tests/unit/test_ingestion_metadata.py`: 25 tests covering `DatasetMetadata`.
- `tests/unit/test_ingestion_cache.py`: 25 tests covering `CacheManager`.
- `tests/unit/test_ingestion_validation.py`: 25 tests covering `DataValidator`
  (all six checks + report serialization + config defaults).
- `tests/unit/test_ingestion_registry.py`: 26 tests covering registry
  decorator, get/list/unregister, and built-in connector registration.
- `tests/integration/test_csv_connector.py`: 20 end-to-end tests for
  `LocalCSVConnector` (connect, download, validate, metadata, fetch, cache).
- `docs/architecture/DATA_ECOSYSTEM.md`: Architecture document covering design
  goals, module responsibilities, data flow diagram, cache key design,
  provenance integration, extension guide, and testing instructions.

---

### Sprint 3B.1 — Architecture Cleanup (2026-06-27)

#### Added
- `src/econflow/commands/_shared.py`: shared CLI utilities module with
  `STATUS_ICONS` (all five check statuses), `deep_get()`, and `load_yaml_safe()`.
  Eliminates duplicate implementations previously copied across command modules.
- `tests/unit/test_shared.py`: 22 unit tests covering `STATUS_ICONS`, `deep_get`,
  and `load_yaml_safe`.
- Tests directory scaffold in `econflow init`: `tests/__init__.py` and
  `tests/test_pipeline.py` (smoke tests) are now written by `econflow init`.
- Unit tests for `tests/` scaffold creation added to `test_cmd_init.py`.
- Unit tests for registry-driven estimator validation added to `test_cmd_validate.py`.

#### Changed
- `validate.py`: `_STATUS_ICON`, `_deep_get`, `_load_yaml_safe` removed; now
  imported from `._shared`. `_SUPPORTED_ESTIMATORS` is now a `frozenset` derived
  from `ESTIMATOR_REGISTRY` — adding an implemented estimator to the registry
  automatically makes `econflow validate` accept it.
- `doctor.py`: local `_STATUS_ICON` removed; now uses `STATUS_ICONS` from
  `._shared`. `EXT-04`/`EXT-05` (uv/pip) now display version in the **detail**
  column (consistent with `EXT-01`..`EXT-03`), not embedded in the label.
- `info.py`: local `_deep_get` and `_load_yaml` removed; now delegates to
  `deep_get` and `load_yaml_safe` from `._shared`.
- `init.py`: fixed rendering regression in `_write_file()` — success icon was
  `v` (plain text), now correctly `✔` (Rich markup `[green]✔[/green]`);
  skip icon was `-`, now `–` (en-dash, consistent with doctor/validate).
- `ARCHITECTURE.md`: updated package layout, added Shared CLI Utilities section,
  documented registry-driven validation design.

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
