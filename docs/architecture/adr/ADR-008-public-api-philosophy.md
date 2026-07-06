# ADR-008: Public API Philosophy

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** —  
**Superseded by:** —

---

## Context

EconFlow is approaching v1.0, the release that carries an implicit backward-compatibility
promise: code written against v1.0 must continue to work on v1.1, v1.2, and all future
minor releases. Breaking this promise damages researcher trust, invalidates existing
analysis pipelines, and makes EconFlow unsuitable for use in published research — where
code must produce identical results months or years after it was written.

Before v1.0 is released, the project must answer three questions:

1. **What is the public API?** Not everything importable from `econflow` is public.
   Helper functions, internal data structures, and intermediate abstractions that may
   change during development should be explicitly private. The public API is the
   set of names that EconFlow commits to maintaining.

2. **What does backward compatibility mean for EconFlow?** Standard semver backward
   compatibility covers function signatures and class interfaces. EconFlow has
   additional compatibility concerns: YAML configuration schema, JSON artifact schema,
   CLI command signatures, and plugin base class interfaces. All of these must be
   included in the backward compatibility commitment.

3. **How does EconFlow communicate API stability to users?** A `DeprecationWarning`
   is the Python standard mechanism for signaling that a name will be removed. But
   when does a deprecation warning become a removal? The project needs a policy, not
   a convention.

A further consideration is the plugin author perspective. Plugin authors write code
against EconFlow's base classes. They cannot be reached by a mailing list or a GitHub
notification when EconFlow changes a base class method signature. Their code will
break silently at the next EconFlow upgrade unless the base class interfaces are frozen
and any changes go through a formal deprecation process with a guaranteed support window.

---

## Decision

We adopt a **multi-surface public API** with explicit stability levels, governed by
the following principles.

### Principle 1: `__all__` as the API Boundary

Every sub-package's `__init__.py` defines `__all__`. Only names in `__all__` are part
of the public API. Names not in `__all__` are internal and may change without notice.

This is not merely a documentation convention. It is enforced by the review process:
any addition to a sub-package's `__all__` must be reviewed by the TSC, because it
is a public API commitment. Removals from `__all__` are breaking changes and require
a deprecation cycle.

The five public API surfaces, each with its own `__all__`, are:
- `econflow.estimation` — `BaseEstimator`, `EstimationResult`, `DiagnosticResult`,
  `get_estimator`, `list_estimators`, `register`
- `econflow.diagnostics` — `BaseDiagnostic`, `DiagnosticResult`, `get_diagnostic`,
  `list_diagnostics`, `register_diagnostic`
- `econflow.outputs` — `BaseRenderer`, `ReportTable`, `ReportFigure`,
  `PublicationBundle`, `get_renderer`, `list_renderers`, `register_renderer`,
  all table builder functions
- `econflow.ingestion` — `AbstractConnector`, `CacheManager`, `DatasetManifest`,
  `DatasetMetadata`, `DataValidationReport`, `get_connector`, `list_connectors`,
  `register`
- `econflow.integrity` — `BaseIntegrityCheck`, `IntegrityCheckResult`,
  `ReproducibilityCertificate`, `DataFingerprint`, `EnvironmentFingerprint`,
  `get_integrity_check`, `list_integrity_checks`, `register_integrity_check`

### Principle 2: Four API Surfaces, Four Compatibility Commitments

EconFlow has four distinct API surfaces with different stability requirements:

**Python API** — the importable classes, functions, and their signatures.
Governed by standard semver: no breaking changes in minor releases, breaking changes
only in major releases after a one-minor-version deprecation cycle.

**Configuration schema** — the YAML structure of `config.yaml`, `models.yaml`, and
`outputs.yaml`. Adding optional fields with defaults is not a breaking change.
Adding required fields, removing fields, or changing field types is a breaking change.
Schema changes are versioned by a `schema_version` field in the configuration file.

**CLI command interface** — the names and required arguments of all twelve CLI commands.
Adding optional flags is not a breaking change. Removing commands, renaming commands,
or removing required arguments is a breaking change. The `--help` output of every
command is part of its public interface.

**JSON artifact schema** — the structure of `run_metadata.json`, `certificate.json`,
and `manifest.json`. Adding fields is not a breaking change. Removing or renaming
fields is a breaking change, and requires a `schema_version` bump in the affected
artifact. EconFlow must be able to read any v1.x artifact produced by any v1.y
version, for all x, y.

### Principle 3: The Plugin Base Class Interface Is the Most Important Stability Commitment

The abstract method signatures of the five plugin base classes are the API that
third-party plugin authors write against. They receive no notification when these
signatures change. They cannot run EconFlow's test suite against a pre-release.

Therefore: **the abstract method signatures of `BaseEstimator`, `BaseDiagnostic`,
`BaseRenderer`, `AbstractConnector`, and `BaseIntegrityCheck` must not change between
any two v1.x releases.** New optional parameters with defaults may be added in minor
releases. Existing parameters may not be removed or renamed. Return types may not
change. Exceptions that the base class declares may be raised but their names may not
change.

If a plugin interface must change for correctness reasons, the old method is deprecated
by making it call the new method with a compatibility shim. The deprecated form is
supported for at least one full minor release cycle. The deprecation is announced in the
CHANGELOG with a migration guide.

### Principle 4: Deprecation Policy

The deprecation lifecycle for any public API element is:

1. **Proposal.** A TSC member proposes removal in a GitHub issue with justification.
2. **Deprecation release.** In the next minor release, the element emits
   `DeprecationWarning` when accessed. The `CHANGELOG.md` and `VERSIONING.md` note the
   deprecation and the planned removal version.
3. **Support window.** The element is supported for at least two minor releases
   after the deprecation release. Users receive at least two opportunities to update
   their code before removal.
4. **Removal.** In the planned major release, the element is removed. The CHANGELOG
   entry references the deprecation issue and the migration guide.

This policy applies to all four API surfaces. A configuration field that is deprecated
must remain valid in `load_config()` for at least two minor releases, with a
`UserWarning` emitted when it is used.

### Principle 5: Private by Default

Any name that begins with `_` is private. Any name in a module that is not in the
module's `__all__` is private even if it does not begin with `_`. Any name in a
sub-package that is accessible via an import path containing a module not listed in the
parent's `__all__` is private.

Private names may change, be renamed, or be removed in any release — including patch
releases — without notice. Plugin authors who import private names do so at their own
risk and will not receive deprecation warnings before those names are changed.

The one exception is test infrastructure. `tests/conftest.py` fixtures and
`tests/helpers/` utilities are stable within a major version even though they are not
in any `__all__`. This is a convention, not a guarantee, and applies only to code
in the `tests/` directory.

---

## Alternatives Considered

### Alternative 1: Everything Is Public Until Explicitly Marked Private

The inverse of the chosen approach: all importable names are public by default, and
only names beginning with `_` are private.

**Why not chosen:** This maximizes the backward compatibility surface to include every
helper function, every intermediate data structure, and every implementation detail
that happens to be importable. Maintaining backward compatibility for names that were
never intended to be public would prohibit routine refactoring. Python's standard
convention of using `__all__` to declare the public API is well-established and the
chosen approach.

### Alternative 2: Versioned Modules (`econflow.v1`, `econflow.v2`)

When a breaking change is made, the new API is published under a new module namespace
(`econflow.v2.estimation`). The old namespace is maintained indefinitely.

**Why not chosen:** This is the approach used by some large libraries (e.g., `protobuf`,
Azure SDK) where breaking changes are frequent and the user base is large. For EconFlow
at v1.0, versioned namespaces add complexity without proportional benefit. The semver
deprecation policy provides adequate protection for a project of EconFlow's current
scale. Versioned namespaces may be reconsidered if major breaking changes become
necessary after v1.0.

### Alternative 3: No Stability Guarantee for Plugin Interfaces

Plugin base class interfaces are internal and may change in any release. Plugin authors
are expected to track EconFlow development and update their plugins accordingly.

**Why not chosen:** This makes EconFlow unsuitable as a platform. If third-party plugin
authors cannot rely on a stable interface, they will not write plugins. The entire
value proposition of the plugin architecture depends on plugin authors having confidence
that their code will continue to work across EconFlow updates.

### Alternative 4: Calver (Calendar Versioning)

Use date-based version strings (e.g., `2026.06`) rather than semver. Each release is
a snapshot; there is no formal backward compatibility commitment.

**Why not chosen:** Calver is appropriate for tools where each release is self-contained
and users always update to the latest (e.g., Ubuntu, Python itself). EconFlow is used
in published research where analysis code may be run years after it was written. A
researcher who publishes a replication package in 2026 that requires `econflow==2026.06`
must be able to install that version in 2030 and have it work. Calver provides no
signal about backward compatibility; semver does.

---

## Trade-offs

**Accepted costs:**

- Maintaining `__all__` lists requires discipline: every new public symbol must be
  added to `__all__` explicitly, and every removal requires a deprecation cycle.
  This is an ongoing maintenance cost that grows with the API surface.

- The four-surface compatibility commitment (Python API, configuration schema, CLI,
  JSON artifacts) is broader than standard library semver. Some changes that would
  be non-breaking under standard semver (e.g., adding a new required field to the
  YAML schema) are breaking under EconFlow's policy. This restricts development
  flexibility.

- The two-minor-release deprecation window means that unwanted API elements remain
  in the codebase for at least one full minor release cycle after they are deprecated.
  This accumulates technical debt that must be actively managed.

**Realized benefits:**

- A researcher who pins `econflow>=1.0,<2.0` in their replication package can be
  confident that the package will install and run correctly on any v1.x release, for
  any x. This is the foundation of long-term reproducibility.

- Plugin authors can target specific minor versions of EconFlow and know that their
  plugins will continue to work until a major release, with at least two minor release
  versions of notice before any breaking change.

- The `schema_version` field in JSON artifacts allows future migration utilities to
  read and convert artifacts from any v1.x version. Reviewers who open a replication
  package five years after submission can read the certificate regardless of which
  v1.x version produced it.

---

## Consequences

**Immediate consequences:**

1. Every sub-package's `__init__.py` must define `__all__` before v1.0 is released.
   This is a blocking v1.0 requirement (see V1_RELEASE_CRITERIA §2.1).

2. `VERSIONING.md` must be written before v1.0 and must define breaking changes
   across all four API surfaces (see V1_RELEASE_CRITERIA §2.3).

3. The TSC must conduct a formal review of all five `__all__` lists before the v1.0
   RC is tagged. Any name that cannot be committed to backward compatibility must be
   removed from `__all__` before RC1.

4. The Plugin SDK document (ADR-001 and V1_RELEASE_CRITERIA §3.1) must describe the
   public API surface for plugin authors, distinguishing the stable plugin interfaces
   from the broader Python API.

**Architectural constraints imposed:**

- Any merge that adds a new name to a sub-package's `__all__` requires explicit
  approval from the TSC. This is enforced by a code review policy, not by automation,
  but the policy is binding.

- Any name that is currently importable but not in `__all__` is considered internal
  and may be moved, renamed, or removed in any release. The transition period between
  v0.7 and v1.0 RC is the opportunity to move any accidentally-public names into
  properly scoped private locations.

---

## Future Implications

**ADR-008-F1 (Planned):** API linting. A CI check that verifies no cross-package
import of private names (`from econflow.estimation._helpers import _coerce_params`)
will be added before v1.0. The check will run on every PR and fail if any private
import is detected (see V1_RELEASE_CRITERIA §2.2).

**ADR-008-F2 (Under consideration):** Public API changelog. A separate
`CHANGELOG_API.md` that lists only API-surface changes (additions to and removals
from `__all__`, base class signature changes, schema changes, CLI changes) would give
plugin authors and researchers a focused view of what affects their code, without
requiring them to read the full CHANGELOG.

**ADR-008-F3 (Contingent):** API stability score. If EconFlow acquires a substantial
third-party plugin ecosystem, an API stability score — calculated from the rate of
public API changes per minor release — would provide ecosystem participants with a
quantitative signal of the stability of the platform.

---

## Cross References

- `VERSIONING.md` — semver and backward compatibility policy (to be written before v1.0)
- `src/econflow/*/\_\_init\_\_.py` — `__all__` declarations in each sub-package
- `docs/plugin_sdk/PLUGIN_SDK.md` — Plugin SDK (external API contract for plugin authors)
- `docs/architecture/MILESTONE_v0.7.md` §Q2 — stable architectural decisions
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §2, §3 — public API and plugin SDK release criteria
- ADR-001 — Plugin Registry (plugin base class interfaces as public API)
- ADR-002 — Configuration-First Design (configuration schema as public API)
- ADR-003 — Provenance-First Architecture (JSON artifact schema as public API)
- ADR-004 — Connector Framework (`AbstractConnector` interface stability)
- ADR-005 — Reporting Engine (`BaseRenderer` interface stability)
- ADR-006 — Research Integrity Framework (`BaseIntegrityCheck` interface stability)
