# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs) for the EconFlow
project. ADRs are permanent records of significant architectural decisions: why each
decision was made, what alternatives were considered, and what consequences it carries.

ADRs are not changelogs. They do not describe what changed in a sprint. They describe
decisions that shape the project's structure and constrain future development. Once
accepted, an ADR is superseded only by a new ADR that explicitly replaces it — it is
never silently amended or deleted.

## Status Definitions

| Status | Meaning |
|---|---|
| **Proposed** | Under discussion; not yet binding |
| **Accepted** | Binding on all contributors |
| **Deprecated** | Superseded by a newer ADR; kept for historical reference |
| **Superseded** | Replaced by the ADR identified in the Superseded by field |

## Index

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-001](ADR-001-plugin-registry.md) | Plugin Registry as the Primary Extension Mechanism | Accepted | 2026-06-28 |
| [ADR-002](ADR-002-configuration-first-design.md) | Configuration-First Design | Accepted | 2026-06-28 |
| [ADR-003](ADR-003-provenance-first-architecture.md) | Provenance-First Architecture | Accepted | 2026-06-28 |
| [ADR-004](ADR-004-connector-framework.md) | Connector Framework | Accepted | 2026-06-28 |
| [ADR-005](ADR-005-reporting-engine.md) | Reporting Engine | Accepted | 2026-06-28 |
| [ADR-006](ADR-006-research-integrity-framework.md) | Research Integrity Framework | Accepted | 2026-06-28 |
| [ADR-007](ADR-007-generic-variable-mapping.md) | Generic Variable Mapping | Accepted | 2026-06-28 |
| [ADR-008](ADR-008-public-api-philosophy.md) | Public API Philosophy | Accepted | 2026-06-28 |

## How to Write a New ADR

1. Copy the template below into a new file named `ADR-NNN-short-title.md`.
2. Fill in all sections. Do not leave sections empty.
3. Open a pull request. The ADR status is **Proposed** until the TSC merges it.
4. After merge, the status changes to **Accepted** and the decision is binding.

### Template

```markdown
# ADR-NNN: Title

**Status:** Proposed | Accepted | Deprecated | Superseded  
**Date:** YYYY-MM-DD  
**Deciders:** Technical Steering Committee  
**Supersedes:** ADR-NNN (if applicable)  
**Superseded by:** ADR-NNN (if applicable)

---

## Context

[What situation, problem, or constraint prompted this decision?]

## Decision

[What was decided? State it precisely.]

## Alternatives Considered

[For each alternative: what it is and why it was not chosen.]

## Trade-offs

[Accepted costs and realized benefits of the decision.]

## Consequences

[Immediate consequences and architectural constraints imposed.]

## Future Implications

[How this decision shapes future options.]

## Cross References

[Related ADRs, source files, and documentation.]
```

## Relationship to Other Documents

- **MILESTONE_v0.7.md** — Formal assessment of what EconFlow is at v0.7, including
  stable architectural decisions (Q2) that are formalized in these ADRs.
- **V1_RELEASE_CRITERIA.md** — What must be true before v1.0. Several ADRs describe
  decisions that have blocking release criteria derived from them.
- **VERSIONING.md** — Backward compatibility policy. ADR-008 defines the philosophy;
  VERSIONING.md provides the operational rules.
- **docs/plugin_sdk/PLUGIN_SDK.md** — The external contract for plugin authors.
  ADR-001, ADR-004, ADR-005, ADR-006, and ADR-008 together define what goes in it.
