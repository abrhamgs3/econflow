# Data Ecosystem & Connector Framework

**EconFlow Sprint 8 — Architecture Document**

---

## Overview

The data ecosystem layer provides a generic, plugin-based data acquisition pipeline for
EconFlow.  It replaces ad-hoc download scripts with a uniform interface that handles
caching, provenance, validation, citation, and versioning automatically.

---

## Core Components

### 1. `AbstractConnector` (base.py)

Every data source is represented as a concrete subclass of `AbstractConnector`.  The
interface requires six methods:

| Method | Purpose |
|---|---|
| `connect()` | Verify the source is reachable (lightweight ping) |
| `download(force=False)` | Fetch data and return path to a local CSV |
| `validate(path)` | Run structural checks; return `DataValidationReport` |
| `metadata()` | Return `DatasetMetadata` after download |
| `cache_key()` | Return a deterministic, collision-resistant cache key |
| `citation()` | Return academic citation string for the data source |
| `version()` | Return dataset version identifier |

`citation()` and `version()` are concrete methods backed by class-level `_CITATION` and
`_VERSION` attributes.  Subclasses either set these attributes or override the methods for
dynamic behavior.

The `fetch()` convenience method runs steps 1–4 in sequence and returns `(path, metadata)`.

### 2. ConnectorRegistry (registry.py)

Connectors self-register via the `@register(connector_id, label=…)` class decorator.
Registration happens at import time.  The `connectors/__init__.py` imports all built-in
modules, so `import econflow.ingestion` is sufficient to populate the registry.

```python
from econflow.ingestion.registry import get_connector, list_connectors

ConnClass = get_connector("world_bank")
all_connectors = list_connectors()   # sorted list of metadata dicts
```

Third-party connectors register themselves with the same decorator — no changes to
EconFlow core are required.

### 3. CacheManager (cache.py)

`CacheManager` provides a filesystem-backed key/value store for downloaded datasets.
Each cache slot is a directory `<cache_dir>/<key>/` containing:

- `data.csv` — the downloaded dataset (UTF-8, header row)
- `meta.json` — serialized `DatasetMetadata`

SHA-256 verification runs on every `retrieve()` call.  A mismatch raises
`CacheCorruptionError` so the caller can force a re-download rather than silently using
corrupt data.

Cache keys are deterministic hex digests of the connector ID and sorted parameters.
Identical queries always map to the same cache slot.

### 4. DatasetMetadata (metadata.py)

`DatasetMetadata` is a dataclass recording full provenance for one downloaded dataset:

```python
@dataclass
class DatasetMetadata:
    connector_id: str
    source: str
    download_date: str          # ISO-8601 UTC
    url: str
    version: str
    citation: str
    sha256_hash: str
    row_count: int
    col_count: int
    columns: list[str]
    params: dict[str, Any]
```

`DatasetMetadata.now(...)` is the factory for new records.  Full JSON round-trip via
`to_json()` / `from_json()`.

### 5. DatasetManifest (manifest.py)

`DatasetManifest` is a project-level registry of every dataset a pipeline run acquired.
It records connector ID, cache key, parameters, metadata, validation outcome, citation,
and dataset version for each entry.

```python
manifest = DatasetManifest(project="growth_study")
manifest.add_entry(
    connector_id="world_bank",
    cache_key=connector.cache_key(),
    params=connector.params,
    metadata=meta,
    validation_passed=True,
    citation=connector.citation(),
    dataset_version=connector.version(),
)
manifest.save(Path("outputs/manifest.json"))
```

Manifests are written atomically (write to `.tmp`, `fsync`, `rename`) to prevent partial
writes.  `ManifestEntry.to_dict()` is JSON-serializable.

### 6. DataValidator (validation.py)

`DataValidator` runs configurable checks on panel CSVs:

| Check | Code | Default |
|---|---|---|
| Required columns present | V-01 | on (columns list = `[]`) |
| No duplicate (entity, time) keys | V-02 | on |
| No null identifiers | V-03 | on |
| Expected years present | V-05 | off |
| Missing-value % under threshold | V-06 | off (threshold=1.0) |

Returns a `DataValidationReport` with `.has_errors`, `.n_errors`, `.n_warnings`, and
`.issues` list.

---

## Built-in Connectors

### `csv` — LocalCSVConnector

Reads any UTF-8 panel CSV from the local filesystem.  No network access.  The simplest
connector for starting a new project or testing pipeline code offline.

**Required params:** `path` (path to source CSV)
**Optional params:** `encoding`, `citation`, `required_columns`, `entity_col`, `time_col`

### `world_bank` — WorldBankConnector

Fetches indicator time series from the World Bank Open Data API v2.  No API key required.
Downloads all pages automatically and writes a tidy long-format CSV with columns
`[country, year, indicator, value]`.

**Required params:** `indicators` (list of WB indicator codes)
**Optional params:** `countries`, `year_start`, `year_end`, `entity_col`, `time_col`

### `oecd` — OECDConnector

Fetches data from the OECD SDMX-JSON API.  No API key required for public dataflows.
Parses the SDMX-JSON envelope (series dimension keys, observation time indices) and
writes long-format CSV.

**Required params:** `dataflow` (OECD dataflow ID)
**Optional params:** `filter`, `start_period`, `end_period`, `entity_col`, `time_col`

### `pwt` — PennWorldTablesConnector

Downloads the Penn World Tables Excel workbook from Harvard Dataverse and converts to
a wide-format CSV.  Optionally subsets to the requested variable codes.

**Required params:** none (defaults to version `"10.01"`)
**Optional params:** `version`, `variables`, `entity_col`, `time_col`
**Dependencies:** `requests`, `openpyxl`

### `fred` — FREDConnector

Downloads time-series observations from the St. Louis Fed FRED API.  Supports multiple
series in one call.  Missing values (`"."`) are converted to empty strings.

**Required params:** `series_ids` (list of FRED series IDs)
**Optional params:** `api_key` (or `FRED_API_KEY` env var), `start_date`, `end_date`,
`frequency`, `aggregation_method`

API key available at: https://fred.stlouisfed.org/docs/api/api_key.html

---

## CLI Commands

### `econflow fetch <connector_id>`

Download a dataset using a registered connector.

```bash
# World Bank internet penetration
econflow fetch world_bank \
    --param indicators=IT.NET.USER.ZS \
    --param year_start=2000 \
    --param year_end=2022

# FRED annual GDP per capita
econflow fetch fred \
    --param series_ids=GDPPC,UNRATE \
    --param frequency=a \
    --param start_date=2000-01-01

# Local CSV (no network)
econflow fetch csv --param path=data/raw/panel.csv

# Force re-download; record manifest
econflow fetch world_bank \
    --param indicators=NY.GDP.MKTP.CD \
    --force \
    --manifest outputs/manifest.json
```

`--param` values are auto-parsed: comma-separated strings become lists; integers,
floats, and booleans are coerced to their native types.

### `econflow cache`

Inspect and manage the local dataset cache.

```bash
econflow cache list               # list all cached datasets
econflow cache inspect <key>      # show metadata + hash status
econflow cache clear --yes        # delete everything
econflow cache purge <key>        # delete one slot
```

### `econflow datasets`

List all registered connectors.

```bash
econflow datasets                 # list all
econflow datasets --filter world  # filter by ID substring
```

---

## Integration with Provenance & Integrity Frameworks

The data ecosystem integrates with Sprint 7's integrity framework:

1. **DatasetManifest → ReproducibilityCertificate**: `DatasetMetadata.sha256_hash` can
   be recorded in a `DataFingerprint` and included in the certificate.

2. **Citation chain**: `manifest.citations()` returns all dataset citation strings for
   inclusion in a replication package README.

3. **Drift detection**: `detect_drift()` compares SHA-256 hashes and row counts between
   two certificate runs.  The manifest records the connector parameters so the exact
   download can be reproduced.

```python
from econflow.integrity.certificate import ReproducibilityCertificate
from econflow.integrity.fingerprint import DataFingerprint

cert = ReproducibilityCertificate.build(
    project_name="My Study",
    data_fingerprints=[DataFingerprint.from_path(path)],
)
```

---

## Extension: Writing a New Connector

1. Create `src/econflow/ingestion/connectors/my_source.py`
2. Subclass `AbstractConnector`
3. Set `_CITATION` and `_VERSION` class attributes
4. Implement all six abstract methods
5. Decorate with `@register("my_source", label="…")`
6. Add the import to `connectors/__init__.py`

```python
from econflow.ingestion.base import AbstractConnector, ConnectorError
from econflow.ingestion.registry import register

@register("my_source", label="My Data Source", status="implemented")
class MySourceConnector(AbstractConnector):
    _CITATION = "Author (2024). My Dataset. https://example.com"
    _VERSION = "2024-Q1"

    def connect(self) -> None: ...
    def download(self, *, force=False): ...
    def validate(self, path): ...
    def metadata(self): ...
    def cache_key(self): return self._make_cache_key()
```

---

## Technical Debt

| Item | Severity | Notes |
|---|---|---|
| OECD connector uses generic SDMX-JSON parser | Medium | The dimension key parsing assumes specific ordering; some dataflows use different dimension arrangements |
| PWT downloads full Excel workbook | Low | ~40 MB download; no streaming; could use `pandas` for faster parse |
| FRED no offline fallback hint | Low | `connect()` requires live key validation; could support offline mode with `--offline` flag |
| `validate_dataframe()` type hint uses `pd.DataFrame` without import | Low | Type annotation uses string forward reference; actual pandas import only in method body |
| Root-level stubs `oecd.py`, `pwt.py`, `world_bank.py` | Medium | Old Sprint 4 stubs still exist alongside connectors/; should be removed |
| No streaming download for large datasets | Medium | WorldBank and FRED fetch entire response into memory |

---

## Sprint 9 Recommendations

1. **Remove root-level stubs**: Delete `src/econflow/ingestion/oecd.py`,
   `pwt.py`, `world_bank.py` (Sprint 4 artifacts now superseded by `connectors/`).

2. **Add `econflow fetch --offline` mode**: Check cache without attempting network,
   raise `ConnectorError` with clear message if not cached.

3. **Dataset schema discovery**: Add `schema()` method to `AbstractConnector` that
   returns the expected output columns and dtypes, enabling downstream validation.

4. **OECD full implementation**: Test against live OECD SDMX-JSON API across several
   public dataflows; harden dimension-key parsing for non-standard structures.

5. **PWT streaming**: Replace full-workbook load with sheet-level streaming via
   `openpyxl` `read_only=True` (already used) but add chunk-based row iteration.

6. **API key management**: Integrate with system keyring (via `keyring` library) so
   FRED API keys are not stored in plain-text config files.

7. **`econflow fetch --dry-run`**: Preview what would be downloaded (cache key, URL,
   estimated size) without executing the download.

8. **Panel-aware validation**: Add V-07 check that detects balanced vs unbalanced panels
   and reports the fraction of missing (entity, year) cells.

9. **Citation export**: Add `econflow package --include-manifest` to embed the dataset
   manifest and a formatted references section in the replication package README.

10. **Async downloads**: For multi-indicator World Bank fetches, parallelize across
    indicators using `asyncio` + `aiohttp` or `concurrent.futures.ThreadPoolExecutor`.
