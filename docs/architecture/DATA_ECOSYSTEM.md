# Data Ecosystem Architecture

**EconFlow Sprint 4**

This document describes the data acquisition, caching, validation, and
provenance subsystem introduced in Sprint 4.  It covers the design goals,
module responsibilities, data flow, and extension points.

---

## Goals

1. **Unified interface** — every data source, regardless of transport or format,
   exposes the same five-method API so pipeline code never knows whether it is
   talking to a local CSV, the World Bank API, or the OECD SDMX endpoint.

2. **Deterministic caching** — a dataset is keyed by a SHA-256 of the connector
   ID and download parameters.  The same parameters always resolve to the same
   cache slot; changing any parameter automatically invalidates and re-fetches.

3. **Automatic provenance** — every download is recorded with source URL,
   download timestamp, dataset version, citation string, file hash, and row/col
   counts.  The record is written alongside the cached CSV and can be injected
   into `ProvenanceRecorder` with a single call.

4. **Configurable validation** — six structural checks run on every downloaded
   CSV.  Checks are configurable per connector and produce a structured report
   rather than raising exceptions, so callers decide how to handle warnings
   vs. errors.

5. **Extensibility** — third-party connectors register with a one-line decorator.
   No modification to existing EconFlow code is required.

---

## Package Layout

```
src/econflow/ingestion/
├── __init__.py          Public API re-exports (CacheManager, DatasetMetadata,
│                        AbstractConnector, DataValidator, register, …)
├── base.py              AbstractConnector + ConnectorError
├── registry.py          @register() decorator + get_connector() / list_connectors()
├── metadata.py          DatasetMetadata dataclass + JSON serialization
├── cache.py             CacheManager — slot-based filesystem cache
├── validation.py        DataValidator + DataValidationConfig + DataValidationReport
└── connectors/
    ├── __init__.py      Imports all built-in connectors (triggers @register())
    ├── csv_connector.py LocalCSVConnector  [status: implemented]
    ├── world_bank.py    WorldBankConnector [status: implemented]
    ├── oecd.py          OECDConnector      [status: stub]
    └── pwt.py           PennWorldTablesConnector [status: stub]
```

---

## Module Responsibilities

### `base.py` — `AbstractConnector`

Defines the contract every connector must implement:

| Method | Responsibility |
|--------|----------------|
| `connect()` | Verify the data source is reachable (e.g. HTTP ping, file exists check). |
| `download(*, force)` | Fetch the raw data and write it to the cache slot (or return the source path directly). |
| `validate(path)` | Run structural checks on the downloaded file; return a `DataValidationReport`. |
| `metadata()` | Return the `DatasetMetadata` record for the last download. |
| `cache_key()` | Return the deterministic cache slot key (a 64-char SHA-256 hex string). |

The concrete `fetch()` method chains these five methods in order and returns
`(path, metadata)`.  Pipeline code calls `fetch()` rather than the individual
methods unless it needs fine-grained control.

`_make_cache_key(extra=None)` is a protected helper that computes a SHA-256
of `{"connector_id": ..., "params": {sorted params}}` plus any `extra` dict.
Subclasses call this from `cache_key()`.

### `registry.py` — Connector Registry

```python
_REGISTRY: dict[str, type[AbstractConnector]]
_REGISTRY_META: dict[str, dict[str, str]]
```

`@register(connector_id, *, label, status, notes)` is a class decorator that
populates both dicts at import time and stamps `cls.connector_id`.

`get_connector(id)` raises `KeyError` with the list of available IDs if the
connector is not registered.

`list_connectors()` returns a sorted list of dicts (id, label, status, notes)
suitable for `econflow info`.

`unregister(id)` is provided for testing; not intended for production use.

### `metadata.py` — `DatasetMetadata`

An immutable dataclass capturing the full provenance of a download:

| Field | Type | Description |
|-------|------|-------------|
| `connector_id` | `str` | Registry ID of the producing connector |
| `source` | `str` | Human-readable source name |
| `download_date` | `str` | ISO-8601 UTC timestamp |
| `url` | `str` | Canonical source URL or file path |
| `version` | `str` | Dataset version from the source API |
| `citation` | `str` | Academic citation string |
| `sha256_hash` | `str` | SHA-256 of the cached CSV (64 hex chars) |
| `row_count` | `int` | Data rows (excluding header) |
| `col_count` | `int` | Column count |
| `columns` | `list[str]` | Ordered column names |
| `params` | `dict` | Connector parameters used for this download |

`DatasetMetadata.now(*, connector_id, source, url, ...)` is the primary factory;
it stamps `download_date` with the current UTC time.

Full JSON round-trip: `to_json()` / `from_json()` / `to_dict()` / `from_dict()`.

### `cache.py` — `CacheManager`

Slot-based filesystem cache.  Layout:

```
<cache_dir>/
└── <64-char-key>/
    ├── data.csv
    └── meta.json
```

| Method | Description |
|--------|-------------|
| `store(key, source_path, metadata)` | Copy `source_path` into the slot, compute SHA-256, populate row/col counts, write `meta.json`. Returns the cached `data.csv` path. |
| `retrieve(key)` | Verify SHA-256 (raises `CacheCorruptionError` on mismatch); return `(data_path, DatasetMetadata)`. |
| `is_cached(key)` | True iff `data.csv` and `meta.json` both exist in the slot. |
| `list_cached()` | Return all slot keys present on disk. |
| `invalidate(key)` | Delete the slot; return `True` if it existed. |
| `clear()` | Delete all slots; return count. |
| `compute_hash(path)` | Static method; return SHA-256 hex of a file. |

### `validation.py` — `DataValidator`

Runs up to six checks on a CSV file or pandas DataFrame:

| Code | Check | Level | Trigger |
|------|-------|-------|---------|
| V-00 | File exists | error | File not found at path |
| V-01 | Required columns | error | Any `required_columns` missing from header |
| V-02 | Duplicate rows | warning | (`entity_col`, `time_col`) pair appears more than once |
| V-03 | Missing identifiers | warning | Blank or null `entity_col` or `time_col` |
| V-05 | Missing years | warning | `check_missing_years=True` and a year in `expected_years` is absent for any entity |
| V-06 | Missing value % | warning | Any column has `>max_missing_pct` fraction of blank cells |

`DataValidationConfig` controls which checks run and with what thresholds.
`DataValidationReport` accumulates `ValidationIssue` objects; callers inspect
`report.has_errors` to decide whether to abort.

---

## Data Flow

```
researcher code
     │
     ▼
connector.fetch(force=False)
     │
     ├─► connect()          ── verify source reachable
     ├─► download(force)    ── check CacheManager.is_cached(key)
     │       │                    hit:  CacheManager.retrieve(key) → path, meta
     │       │                    miss: fetch raw data → CacheManager.store(key, ...) → path
     ├─► validate(path)     ── DataValidator.validate_path(path) → DataValidationReport
     └─► metadata()         ── return DatasetMetadata
          │
          ▼
     (path, DatasetMetadata)
          │
          ├─► ProvenanceRecorder.record_dataset(metadata)
          │        └── appended to metadata["datasets"] in run_metadata.json
          └─► pipeline code uses path
```

---

## Cache Key Design

The cache key is the SHA-256 hex of:

```json
{
  "connector_id": "<id>",
  "params": { "<sorted param keys>": "<values>" }
}
```

Computed deterministically so the same download parameters always map to the
same slot across machines and sessions.  Connectors may pass an `extra` dict
to `_make_cache_key()` to include additional dimensions (e.g. `LocalCSVConnector`
includes the resolved absolute source path so that two files at different
absolute paths never collide even if they have the same base name).

---

## Provenance Integration

`ProvenanceRecorder.record_dataset(metadata: DatasetMetadata)` appends a
`DatasetMetadata.to_dict()` snapshot to `metadata["datasets"]` in the
run provenance JSON.  The JSON schema is additive: the new `datasets` key is
an array of dataset provenance records, each matching the `DatasetMetadata`
field set.

Example provenance output:

```json
{
  "schema_version": "1.0.0",
  "run_id": "f47ac10b-...",
  "datasets": [
    {
      "connector_id": "world_bank",
      "source": "World Bank Open Data",
      "download_date": "2026-06-27T12:00:00+00:00",
      "url": "https://api.worldbank.org/v2",
      "version": "2024-Q2",
      "citation": "World Bank (2024). World Development Indicators.",
      "sha256_hash": "a3f5...",
      "row_count": 4320,
      "col_count": 4,
      "columns": ["country", "year", "indicator", "value"],
      "params": {"indicators": ["IT.NET.USER.ZS"], "year_start": 2000}
    }
  ],
  ...
}
```

---

## Writing a New Connector

1. Create `src/econflow/ingestion/connectors/my_source.py`.
2. Implement all five abstract methods and `cache_key()`.
3. Decorate the class with `@register("my_source", label="My Source")`.
4. Add the import to `src/econflow/ingestion/connectors/__init__.py`.
5. Write tests in `tests/unit/test_ingestion_my_source.py` and
   `tests/integration/test_my_source_connector.py`.

No other code changes are required.  The connector will appear automatically
in `econflow info` and be available via `get_connector("my_source")`.

---

## Testing

```bash
# Unit tests (no network required)
pytest tests/unit/test_ingestion_metadata.py
pytest tests/unit/test_ingestion_cache.py
pytest tests/unit/test_ingestion_validation.py
pytest tests/unit/test_ingestion_registry.py

# Integration tests (local files only — no network)
pytest tests/integration/test_csv_connector.py

# All ingestion tests
pytest tests/unit/test_ingestion_*.py tests/integration/test_csv_connector.py -v
```

World Bank, OECD, and PWT connector integration tests are not included in the
default suite because they require live network access.  They will be added
under `tests/integration/` and marked with `@pytest.mark.network` when the
stub implementations are completed.

---

## Known Limitations and Future Work

- **OECD connector** (`status: stub`) — interface complete; download and parsing
  logic not yet implemented.  See module docstring for the implementation plan.
- **PWT connector** (`status: stub`) — interface complete; Excel download and
  reshaping not yet implemented.  Requires `openpyxl` or `pandas[excel]`.
- **Streaming large files** — `CacheManager.store()` currently reads the source
  file into memory to count rows/cols.  A future version should stream the file
  to disk and parse the header separately.
- **Cache size limits** — no eviction policy is implemented.  For large
  datasets, callers should call `cache.invalidate(key)` or `cache.clear()`
  manually.
