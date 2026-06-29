# ADR-004: Connector Framework

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** —  
**Superseded by:** —

---

## Context

Empirical economics research uses data from a large and heterogeneous set of sources:
national statistical offices, international organizations (World Bank, OECD, IMF),
academic data repositories (Harvard Dataverse, ICPSR), central banks (FRED), and
institutional or proprietary databases. Each source has a different access mechanism:
REST APIs with different authentication requirements, bulk download files in different
formats (CSV, Excel, SDMX-JSON, Parquet), and different update frequencies and
versioning policies.

The original EconFlow codebase handled data acquisition with hardcoded scripts specific
to the AI & Productivity paper. Extracting EconFlow into a general platform required
replacing these scripts with a uniform, extensible data acquisition layer that:

1. Abstracts over different access mechanisms so that pipeline code is data-source agnostic.
2. Provides deterministic caching so that a pipeline run on cached data is byte-identical
   to the same run on freshly downloaded data.
3. Records provenance (citation, version, download date, parameter hash) for every
   dataset used in any pipeline run.
4. Validates the structure of downloaded data before it enters the pipeline.
5. Allows third-party connectors to be added without modifying EconFlow core.

The design was further constrained by the research context: researchers frequently work
offline, on institutional networks that restrict outbound connections, or with data
sources that require authentication credentials that must not be logged or stored in
plain text. The connector framework had to support offline operation (cache-only mode),
authentication via environment variables rather than configuration files, and
a clear separation between connection (which requires network access) and retrieval
(which may be satisfied from cache).

---

## Decision

We adopt the **`AbstractConnector` interface** as the uniform contract for all data
sources in EconFlow, implemented via the plugin registry pattern (ADR-001).

`AbstractConnector` defines nine methods, of which six are abstract (must be implemented
by every connector) and three are concrete (implemented by the base class, may be
overridden):

**Abstract methods:**
- `connect() -> None` — verify that the data source is reachable (network ping,
  credential check). Must raise `ConnectorError` if the source is unreachable or
  credentials are invalid. Must not download data.
- `download(force: bool = False) -> Path` — acquire the dataset and return the path
  to the local cached CSV file. If the cache key is already present and `force=False`,
  must return the cached path without a network request.
- `validate(path: Path) -> DataValidationReport` — run structural checks on a local
  CSV file and return a report with `passed`, `errors`, and `warnings` fields.
- `metadata() -> DatasetMetadata` — return a `DatasetMetadata` object describing the
  dataset (row count, column names, time range, entity count, download date).
- `cache_key() -> str` — return a stable, deterministic string that uniquely identifies
  this dataset at this set of parameters. Must be consistent: same connector, same
  parameters → same cache key on any machine, at any time.

**Concrete methods (may be overridden):**
- `citation() -> str` — return the human-readable citation for this data source.
  Default implementation returns `self._CITATION`.
- `version() -> str` — return the version string for this data source.
  Default implementation returns `self._VERSION`.
- `fetch() -> tuple[Path, DatasetMetadata, DataValidationReport]` — high-level
  convenience method that calls `connect()`, `download()`, `validate()`, and
  `metadata()` in sequence. Default implementation is provided; override only if
  the sequence must differ.

**Class-level attributes:**
- `_CITATION: str = ""` — module-level citation string, used by `citation()`.
- `_VERSION: str = "unknown"` — version string, used by `version()`.

The `cache_key()` contract has one additional security requirement: any parameter that
is a credential (API key, password, token) must be excluded from the SHA-256 payload.
This ensures that the same query with different API keys maps to the same cache slot
(same data), and that API keys are never persisted in cache metadata. The FRED connector
is the reference implementation of this requirement.

The `CacheManager` stores downloaded datasets under a directory structure keyed by the
connector's `cache_key()` return value. Hash verification runs on every cache retrieve:
the stored SHA-256 of the CSV file is compared against the actual hash. A mismatch
raises `CacheCorruptionError` immediately; the corrupt file is never returned to the
caller.

Five connectors are included in the EconFlow distribution:
- `csv` — local CSV files (no network access; reference implementation of simplest case)
- `world_bank` — World Bank Open Data API v2
- `oecd` — OECD SDMX-JSON API
- `pwt` — Penn World Tables via Harvard Dataverse (streaming Excel download)
- `fred` — St. Louis Fed FRED API (requires API key)

---

## Alternatives Considered

### Alternative 1: Function-Based Connectors

Each data source is represented as a set of functions (`connect_world_bank()`,
`download_world_bank()`, etc.) rather than a class hierarchy.

**Why not chosen:** Functions cannot be registered by a plugin decorator, discovered by
`list_connectors()`, or instantiated with per-request parameters. A class with
`__init__(params: dict)` allows a single connector type to be instantiated with
different parameters for different datasets (e.g., two `WorldBankConnector` instances
for two different indicator codes, in the same pipeline run). Functions would require
either global state or parameter threading, both of which are problematic in concurrent
use.

### Alternative 2: pandas `read_csv()` / `read_excel()` Direct Use

The pipeline calls pandas I/O functions directly. Connectors are not abstracted.

**Why not chosen:** Direct pandas I/O provides no caching, no citation, no validation,
no provenance recording, and no extension point. Every new data source requires
modifying the pipeline. The connector framework's primary purpose is to place these
concerns in a single, reusable, extensible location.

### Alternative 3: Arrow Flight / ADBC

Use a standard database connectivity layer (Arrow Flight or ADBC) as the uniform
interface. All data sources are exposed as ADBC-compatible endpoints.

**Why not chosen:** ADBC is appropriate for tabular database sources. It does not model
the concept of "download a file", "verify that a source is reachable", or
"produce a citation". The economics data sources EconFlow targets (REST APIs, Excel
files, SDMX) do not have ADBC drivers. Building ADBC adapters for them would be
more complex than the `AbstractConnector` interface.

### Alternative 4: Singer (ETL protocol)

Use the Singer ETL protocol, in which sources ("taps") and destinations ("targets")
communicate via JSON-Lines streams. EconFlow acts as a Singer target.

**Why not chosen:** Singer taps are separate processes. The citation, cache key, and
validation information that EconFlow needs from a connector cannot be communicated
through Singer's data stream protocol without extending it. Singer is appropriate for
production ETL pipelines; it is overengineered for the research context where data
sources number in the tens, not thousands.

---

## Trade-offs

**Accepted costs:**

- The `AbstractConnector` interface requires implementing nine methods (six abstract).
  For simple sources, several of these methods are nearly trivial (the CSV connector's
  `connect()` simply checks that the file exists), but they must still be implemented.
  The verbosity is a feature: it forces every connector author to think about caching,
  citation, validation, and metadata even if the defaults are sufficient.

- The `cache_key()` contract requires that every connector deterministically identify
  its dataset parameters. For some data sources (e.g., a source with no versioning
  and a single global dataset), the cache key is arbitrary. This is accepted: even
  an arbitrary but stable cache key correctly implements the "same parameters → same
  cache slot" contract.

- OECD SDMX-JSON parsing is complex: the connector must decode dimension key strings
  (e.g., `"0:1:2"`) by indexing into arrays built from the `structures` field.
  This is specific to OECD's format and is documented in the connector's source.
  It is not abstracted further because OECD is the only SDMX-JSON source currently
  targeted; premature abstraction of SDMX parsing would add complexity without benefit.

**Realized benefits:**

- `econflow fetch --connector world_bank --dataset SP.POP.TOTL` and
  `econflow fetch --connector fred --dataset GDP` are syntactically identical from the
  CLI's perspective. The pipeline code is identical for both. The differences are
  entirely inside the connector.

- Adding a new connector — a hypothetical IMF connector or a proprietary institutional
  database connector — requires writing one class and one `@register()` decorator. The
  pipeline, the CLI, the caching layer, and the validation framework all work
  immediately with the new connector.

- The `ManifestEntry` produced by each connector's `fetch()` call becomes part of the
  `DatasetManifest`, which is the data acquisition provenance record. This integration
  is automatic: every connector produces a manifest entry; the manifest collects them.

---

## Consequences

**Immediate consequences:**

1. Every new data source must be implemented as an `AbstractConnector` subclass
   decorated with `@register(connector_id)`. No data source may be accessed by the
   pipeline directly (e.g., by calling `pd.read_csv()` on a URL).

2. The `cache_key()` method must exclude credentials from its SHA-256 payload. This
   is enforced by code review, not by the framework. Any connector that includes
   an API key in the cache key hash is incorrect and must be fixed before release.

3. The `CacheManager` is the single point of truth for whether a dataset has been
   downloaded. The pipeline may not read a dataset file directly; it must go through
   `CacheManager.retrieve()`, which performs hash verification.

4. Every connector must handle the case where `connect()` fails (source unreachable)
   and the case where the cache is available (`force=False`). These are the two modes
   of offline operation, and both must work without raising an unhandled exception.

**Architectural constraints imposed:**

- Connector parameters are `dict[str, Any]`. The connector is responsible for
  validating its own parameters in `__init__()` and raising `ConnectorError` with
  a descriptive message for any invalid parameter. The pipeline passes parameters
  through without inspection.

- Output format is always a CSV file. Connectors that receive data in other formats
  (Excel, SDMX-JSON, Parquet) must convert to CSV before writing to the cache.
  This is a deliberate uniformity requirement: the validation and pipeline layers
  assume CSV. Connectors that want to preserve the original format may do so
  alongside the CSV, but the CSV is always produced.

---

## Future Implications

**ADR-004-F1 (Planned):** `schema()` method. A future extension to `AbstractConnector`
will add an optional `schema()` method that returns a machine-readable description of
the dataset's columns, types, and expected ranges. This would enable type-safe
configuration validation (verifying that the column names in `config.yaml` exist in
the schema) and richer validation rules in `DataValidationReport`.

**ADR-004-F2 (Planned):** `--offline` mode. `econflow fetch --offline` will restrict
all connectors to cache-only operation: `connect()` is skipped; `download()` raises
`CacheError` if the cache key is not present rather than attempting a network request.
This enables researchers to run pipelines on air-gapped systems.

**ADR-004-F3 (Under consideration):** Async downloads. For pipelines that fetch many
indicators from the World Bank or FRED, sequential `download()` calls are slow.
An optional `download_batch(requests: list[ConnectorRequest]) -> list[Path]` method
on `CacheManager` would allow concurrent downloads. This requires careful handling of
rate limits and would be implemented as an opt-in connector capability.

**ADR-004-F4 (Planned):** OECD dimension structure hardening. The current OECD
SDMX-JSON parser makes assumptions about dimension ordering that hold for common
dataflows but fail on others. A more robust parser that handles arbitrary dimension
structures is required before v1.0 (see V1_RELEASE_CRITERIA §5.3).

---

## Cross References

- `src/econflow/ingestion/base.py` — `AbstractConnector` interface
- `src/econflow/ingestion/cache.py` — `CacheManager` implementation
- `src/econflow/ingestion/manifest.py` — `DatasetManifest`, `ManifestEntry`
- `src/econflow/ingestion/validation.py` — `DataValidator`, `DataValidationReport`
- `src/econflow/ingestion/connectors/` — five reference connector implementations
- `src/econflow/commands/fetch_cmd.py` — CLI implementation for `econflow fetch`
- `src/econflow/commands/cache_cmd.py` — CLI implementation for `econflow cache`
- `docs/architecture/DATA_ECOSYSTEM.md` — data ecosystem architecture document
- `docs/architecture/MILESTONE_v0.7.md` §1.2 — data management capability assessment
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §5 — connector framework release criteria
- ADR-001 — Plugin Registry (registration mechanism for connectors)
- ADR-003 — Provenance-First Architecture (`ManifestEntry` and provenance integration)
- ADR-008 — Public API Philosophy (`AbstractConnector` as a frozen public interface)
