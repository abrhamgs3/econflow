# ADR-003: Provenance-First Architecture

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** —  
**Superseded by:** —

---

## Context

Reproducibility failures in empirical research fall into three distinct categories:

1. **Code failures** — the analysis code has a bug or was changed after the results
   were produced.
2. **Environment failures** — the software environment (package versions, Python
   version, OS) has changed, producing different numerical results from identical code.
3. **Data failures** — the input data has changed since the analysis was run, either
   because the source was updated, the file was modified, or a different version was
   accidentally used.

Traditional replication packages address only category 1: they provide the code and
hope that the environment and data are still available and unchanged. They do not record
what the environment was, they do not verify that the data has not changed, and they
provide no mechanism for a replicator to diagnose which category of failure they are
experiencing.

The provenance question in EconFlow is: given that a study was run at time T and a
replicator is attempting to reproduce it at time T+N, what information is needed to
determine whether any reproduction failure is due to code change, environment change,
or data change? The answer is a complete record of the state of the world at time T.

The design question is when and how to capture this record. There were two options:
capture provenance as an optional post-hoc step (the researcher runs the pipeline and
then optionally generates a provenance record), or make provenance capture unconditional
and integral to every pipeline execution. The latter is the provenance-first principle.

An additional consideration was the scope of provenance. "Provenance" in data management
traditionally means the lineage of a dataset — where it came from and what
transformations were applied. In EconFlow, provenance is broader: it covers the origin
of the data, the software environment, the analysis configuration, the code state
(git commit), and the outputs produced. This broader scope is necessary because
environment and code changes are the dominant sources of replication failure in
empirical economics, not data lineage.

---

## Decision

We adopt **unconditional, integral provenance recording** as a foundational architectural
principle. Provenance is not a feature that runs when requested; it is a property of
every pipeline execution.

The decision has four concrete expressions:

**1. `ProvenanceRecorder` as a mandatory context manager.**
Every pipeline execution is wrapped in a `ProvenanceRecorder` context manager.
The recorder initializes at pipeline start and writes `run_metadata.json` at pipeline
completion. There is no configuration option to disable provenance recording. The
`run_metadata.json` file is written atomically (to a `.tmp` file, then renamed) to
prevent partial writes from producing corrupt records.

**2. SHA-256 hashing of all inputs and outputs.**
Every input file (the configuration files, the data source) and every output file
(tables, figures, the certificate) is hashed with SHA-256 and the hash is recorded
in `run_metadata.json`. This is not optional. The hash is computed regardless of
file size. The cost is I/O time proportional to file size; this is accepted.

**3. Full environment fingerprinting.**
`EnvironmentFingerprint.capture()` records at minimum: the git commit hash, whether
the working tree is dirty (uncommitted changes), the Python version and implementation,
the operating system and platform, and the versions of all installed packages in the
environment. This record is the answer to environment-category failures: a replicator
who sees different results can compare their `EnvironmentFingerprint` against the
stored one and immediately identify which package version changed.

**4. `DatasetManifest` for data acquisition provenance.**
Every `AbstractConnector.download()` call produces a `ManifestEntry` that records the
connector ID, the parameters used, the cache key, the downloaded file hash, the
validation outcome, the citation, and the dataset version. The `DatasetManifest`
aggregates all entries across a pipeline run. This answers data-category failures:
a replicator can compare manifests to determine whether the same connector parameters
produced the same cache key, which verifies that the same data version was used.

These four components form a **complete provenance chain**: configuration → data
acquisition → environment → execution → outputs. Given the full chain, any
reproduction failure can be diagnosed to one of the three categories without examining
the pipeline code.

The provenance record format is defined by a JSON Schema at
`outputs/provenance/schema.json`. The `schema_version` field in every record allows
future format changes to be detected and handled by migration utilities.

---

## Alternatives Considered

### Alternative 1: Opt-in Provenance

Provenance recording is available as a command (`econflow certify`) but is not run
automatically during `econflow run`. Researchers who want provenance records must
explicitly request them.

**Why not chosen:** The runs most likely to have reproducibility problems are the runs
done under time pressure — late-night revision runs, submission-deadline runs. These
are precisely the runs for which a researcher is most likely to skip an optional step.
If provenance is opt-in, the record will be absent for the runs where it is most needed.
An opt-in model is appropriate for a convenience feature; it is inappropriate for a
reproducibility guarantee.

### Alternative 2: Git-Only Provenance

The git commit hash is the complete provenance record. A pinned commit hash plus the
repository URL fully specifies the code state, and the code contains the data source
references.

**Why not chosen:** Git-only provenance is insufficient for three reasons. First, it
does not handle the common case of a dirty working tree (uncommitted changes are not
captured by the commit hash). Second, it does not record the environment, and
environment failures are a major source of replication failure. Third, it does not
record the data: a git commit specifies the code that fetches data, not the data itself.
Two runs from the same commit against a source that has been updated will produce
different results. Git-only provenance cannot distinguish this from a code bug.

### Alternative 3: DVC (Data Version Control)

Use an external tool such as DVC to manage data versioning and provenance. EconFlow
generates DVC metadata files alongside its outputs.

**Why not chosen:** DVC is an external dependency with its own storage backend (S3,
GCS, Azure), its own CLI, and its own configuration. Requiring DVC would add
significant onboarding friction for researchers who are not infrastructure engineers.
The subset of DVC's functionality that EconFlow needs — file hashing, version recording,
and artifact linkage — is simple enough to implement directly. DVC integration could be
added as an optional export format in a future sprint, but it cannot be a dependency.

### Alternative 4: Logging-Based Provenance

Instrument every significant operation with structured log entries. Generate provenance
records from the log after the run completes.

**Why not chosen:** Log-based provenance is lossy (what to log must be decided at
instrumentation time, not at analysis time), fragile (log format changes break
retroactive analysis), and depends on the log being captured and retained (which is
not guaranteed in all execution environments). A structured `run_metadata.json`
written at the end of the run is simpler, more reliable, and easier to read than a
log parser.

---

## Trade-offs

**Accepted costs:**

- Every pipeline run produces files beyond the analysis outputs: `run_metadata.json`,
  `manifest.json`, and the `.tmp` files during atomic writes. For researchers who do
  not want provenance records, these files are unwanted clutter. This is accepted:
  reproducibility requires unconditional recording.

- SHA-256 hashing of large data files takes time proportional to file size. A 1 GB
  dataset takes approximately 2–5 seconds to hash on typical hardware. This is accepted
  as a fixed overhead per run. The hash is computed once per file per run, not on
  every read.

- The environment fingerprint captures every installed package version. In environments
  with hundreds of packages, this produces a large JSON field. This is accepted:
  package version information is critical for debugging environment failures, and
  storage cost is trivial.

- `ProvenanceRecorder` adds a dependency on `git` being available in the execution
  environment. When `git` is not available (e.g., on some HPC systems), the recorder
  records `"git_commit": null` rather than failing. This is the only case where a
  provenance field may be null; all other fields are mandatory.

**Realized benefits:**

- `ReproducibilityCertificate.detect_drift()` provides eight-axis comparison between
  two certificates. Without unconditional provenance recording, this comparison is
  impossible: there would be nothing to compare.

- The `DatasetManifest` allows a replicator to verify that they are using the same
  data version as the original author by comparing cache keys — without having access
  to the original data.

- The provenance record is the input to `IntegrityFramework.from_provenance()`, which
  re-runs integrity checks against a stored certificate. This integration is only
  possible because the provenance record exists unconditionally.

---

## Consequences

**Immediate consequences:**

1. Every pipeline execution path must be wrapped in `ProvenanceRecorder`. There is no
   "quick run" mode that skips provenance. CLI commands that invoke pipeline logic
   must either call `ProvenanceRecorder` directly or call `run_from_config()`, which
   calls it internally.

2. Every `AbstractConnector.download()` implementation must return a `ManifestEntry`.
   Connectors that do not produce manifest entries are incomplete implementations,
   not valid plugins.

3. The `run_metadata.json` schema is a public contract. Adding fields is backward
   compatible; removing or renaming fields requires a schema version bump and a
   migration utility.

4. `ProvenanceRecorder` must handle the case where the pipeline fails partway through.
   On failure, a partial provenance record is written with `status: "failed"` and
   the exception type and message recorded. Partial records are valid provenance and
   must be loadable by `ReproducibilityCertificate.from_json()`.

**Architectural constraints imposed:**

- No pipeline code may produce output files without the `ProvenanceRecorder` context
  being active. This is enforced by code review; in a future sprint, a runtime check
  may be added that raises `ProvenanceError` if output files are written outside a
  recorder context.

- The provenance record must be written before the pipeline exits in all cases,
  including uncaught exceptions. The `ProvenanceRecorder.__exit__` method must not
  itself raise an exception.

---

## Future Implications

**ADR-003-F1 (Planned):** Provenance-manifest linkage. The `run_metadata.json` must
contain a `manifest_path` field pointing to the `DatasetManifest` JSON produced during
the same run (see V1_RELEASE_CRITERIA §8.2). This is a missing requirement at v0.7 and
must be implemented before v1.0.

**ADR-003-F2 (Under consideration):** W3C PROV-O export. The W3C Provenance Ontology
(PROV-O) is a standardized RDF vocabulary for expressing provenance. An optional
export of `run_metadata.json` to PROV-O format would allow EconFlow provenance records
to be consumed by external provenance management systems and would satisfy the
provenance requirements of research data repositories such as Harvard Dataverse and
Zenodo without custom integration.

**ADR-003-F3 (Contingent):** Provenance graph visualization. A `econflow provenance`
command that renders the provenance chain as a directed acyclic graph (configuration
→ data → pipeline → outputs) would help researchers communicate their data lineage
to reviewers and collaborators. This is contingent on user demand.

---

## Cross References

- `src/econflow/provenance.py` — `ProvenanceRecorder` implementation
- `src/econflow/integrity/fingerprint.py` — `EnvironmentFingerprint`, `DataFingerprint`
- `src/econflow/integrity/certificate.py` — `ReproducibilityCertificate`, `detect_drift()`
- `src/econflow/ingestion/manifest.py` — `DatasetManifest`, `ManifestEntry`
- `src/econflow/outputs/provenance/schema.json` — provenance JSON Schema
- `docs/architecture/INTEGRITY_FRAMEWORK.md` — integrity and reproducibility architecture
- `docs/architecture/MILESTONE_v0.7.md` §1.8, §1.9 — reproducibility and provenance assessments
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §8 — reproducibility release criteria
- ADR-002 — Configuration-First Design (configuration fingerprinting)
- ADR-004 — Connector Framework (`ManifestEntry` from connectors)
- ADR-006 — Research Integrity Framework (consumes provenance records)
