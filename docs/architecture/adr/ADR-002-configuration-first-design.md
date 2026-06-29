# ADR-002: Configuration-First Design

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** —  
**Superseded by:** —

---

## Context

In the original form of EconFlow, every analysis decision was embedded in Python code.
The dependent variable, the fixed effect specification, the set of control variables,
the sample period, the clustering level, and the set of estimators to run were all
hardcoded in a script that was effectively a one-time artifact. Replicating the study
meant running the original author's script; modifying the study — to add a control
variable, or restrict the sample to a different period, or run a robustness check with
a different specification — required editing Python.

This design is appropriate for a replication package. It is not appropriate for a
platform. EconFlow needed to serve at least three distinct user types:

1. **Economists without Python fluency** who need to configure and run a study but
   should not need to write pipeline code.
2. **Methodologists** who want to replicate a study and then modify the specification
   to test robustness, without touching the original author's code.
3. **Tool builders** who wrap EconFlow in larger workflows and need to generate
   analysis configurations programmatically.

All three user types share a common need: the description of an analysis must be
separable from its execution. The configuration file is the description; the pipeline
is the execution. This separation is the configuration-first principle.

A secondary motivation was reproducibility. If analysis decisions are in code, the
configuration is implicit — the code *is* the configuration, and changing the code to
run a robustness check creates a new, unnamed analysis that is not distinguishable from
the original by inspection. If analysis decisions are in a YAML file, the configuration
is explicit and versionable: the YAML file is a complete description of the study,
independent of the code that runs it. `git diff config.yaml` shows exactly what changed
between two analysis runs.

---

## Decision

We adopt **three-file YAML configuration** as the complete, authoritative description
of any EconFlow pipeline run. No analysis parameter may be specified anywhere other
than these three files. The pipeline reads only the configuration files; it may not
read command-line arguments other than the paths to those files and output directories.

The three files and their responsibilities are:

**`config/config.yaml`** — Project identity and data specification:
- Project name, description, and author metadata
- Data source path (local CSV or connector specification)
- Variable mapping: which columns are the entity identifier, time identifier,
  outcome variable, treatment variable, and control variables
- Sample restrictions: entity list, time period bounds
- Data validation parameters: maximum missing rate, required columns
- Output directory paths

**`config/models.yaml`** — Estimation specification:
- List of estimator IDs to run (drawn from the estimator registry)
- Per-estimator parameters: fixed effect specification, clustering variable,
  instrument specification for IV, robustness check variants
- Whether to run diagnostics after each estimator
- Comparison table configuration: which estimates to include, formatting options

**`config/outputs.yaml`** — Reporting specification:
- Which table types to produce for each estimator result
- Which renderer IDs to use for each table (drawn from the renderer registry)
- Figure specifications: which figure types to produce and with which parameters
- Publication bundle configuration: directory structure, file naming conventions

These three files together constitute a **complete specification** of the analysis.
Given these files, the EconFlow platform, and the referenced data, any person on any
machine must be able to reproduce the study's output exactly.

The YAML schemas are validated by Pydantic models in `core/config.py`. Every field has
an explicit type, and the validator rejects invalid values before any pipeline code
executes (`load_config()` is the single entry point for all configuration reading).
No configuration parameter may have a silent default that alters analysis results.
Defaults are permitted only for cosmetic or performance parameters (e.g., output
directory structure, verbosity level).

---

## Alternatives Considered

### Alternative 1: Python API Only (No Configuration Files)

The platform exposes a Python API, and researchers write Python scripts to configure
their analyses. Configuration files are optional and generated from code.

**Why not chosen:** A Python API requires Python fluency. The configuration-first
approach allows economists without Python expertise to run complete analyses, which is
a primary design goal. A Python API also embeds analysis decisions in executable code,
which makes it harder to diff two analyses and understand what changed. The Python API
remains available (researchers can import EconFlow's sub-packages directly), but it
is not the primary interface.

### Alternative 2: Single Configuration File

All analysis parameters — data, models, and outputs — are combined in a single YAML
file.

**Why not chosen:** A single file would grow to hundreds of lines for a complex
multi-estimator study and would conflate concerns that change at different rates.
The data specification (`config.yaml`) changes rarely. The model specification
(`models.yaml`) changes frequently during analysis development. The output specification
(`outputs.yaml`) changes most frequently (researchers constantly adjust table formatting).
Separating the three files makes it possible to version-control them independently
and to understand at a glance what changed between two runs.

### Alternative 3: TOML or JSON Configuration

Use TOML (as in `pyproject.toml`) or JSON as the configuration format.

**Why not chosen:** YAML allows multi-line strings, inline comments, and anchors (for
reusing common configurations across multiple estimator definitions). TOML's inline
comment syntax is equivalent, but TOML lacks anchors, making the specification of
robustness check variants verbose. JSON allows neither comments nor anchors. YAML is
the established format for research configuration (used by Snakemake, Nextflow, and
Jupyter Book) and is the most familiar format among the target user base.

### Alternative 4: Domain-Specific Language

Define a custom DSL for specifying panel econometric analyses.

**Why not chosen:** A DSL requires a parser, error messages, and documentation that
are entirely owned by the EconFlow project. YAML configuration reuses the YAML tooling
ecosystem (syntax highlighting, validators, editors). The investment in a DSL is
justified only if the configuration language needs constructs that YAML cannot express;
this has not been demonstrated.

---

## Trade-offs

**Accepted costs:**

- Configuration files add ceremony for simple analyses. Running a single OLS regression
  requires three YAML files even if the researcher wants only the coefficients.
  The Python API is available for simple cases, but the CLI requires the full
  configuration structure. This is an intentional trade-off for reproducibility.

- YAML has well-known pitfalls (indentation sensitivity, Norway problem with `no`/`yes`
  boolean values, implicit type coercion). The Pydantic validation layer catches
  most of these at load time, but YAML errors can be opaque. Comprehensive error
  messages in `load_config()` are necessary to mitigate this.

- The three-file separation means that trivially related parameters are in different
  files. A researcher who wants to change both the sample restriction and the estimator
  list must edit two files. This is preferable to a single file that mixes concerns
  but may be surprising to researchers accustomed to script-based analysis.

**Realized benefits:**

- The configuration files are the study's machine-readable specification. They can be
  committed to version control, shared with collaborators, and diffed to understand what
  changed between analysis iterations.
- `ProvenanceRecorder` fingerprints `config.yaml` with SHA-256. Any change to the
  configuration is detectable in the provenance record, without reading the pipeline code.
- Programmatic generation of configuration files (for Monte Carlo studies or sensitivity
  analyses over many specifications) requires only standard YAML generation; no EconFlow
  Python API is needed.
- Non-Python users can understand, modify, and review an analysis by reading YAML.

---

## Consequences

**Immediate consequences:**

1. `core/config.py` is the single authoritative location for all configuration schemas.
   Any new configuration parameter must be added to the Pydantic models in this file
   before it can be used anywhere in the pipeline.

2. `load_config()` is the single entry point for all configuration reading. No pipeline
   module may call `yaml.safe_load()` directly. This is enforced by code review;
   a linting rule may be added in a future sprint.

3. Every CLI command that accepts `--config` must obtain its configuration through
   `load_config()` and must fail with a `ConfigurationError` before executing any
   pipeline logic if the configuration is invalid.

4. No analysis parameter may be hardcoded in pipeline code. If a parameter is currently
   hardcoded, it must be moved to the configuration schema before the code ships.

**Architectural constraints imposed:**

- The pipeline is a function of configuration. Given the same configuration files and
  the same data, the pipeline must produce identical output on any machine. Any
  parameter that makes the output non-deterministic (random seeds, timestamps) must be
  explicitly controlled by a configuration value or a provenance record.

- The configuration schema is a public API. Adding required fields to the schema is a
  breaking change (existing configuration files become invalid). Adding optional fields
  with defaults is not a breaking change. Removing or renaming fields is a breaking
  change. The semver policy in `VERSIONING.md` governs schema changes.

---

## Future Implications

**ADR-002-F1 (Planned):** Configuration inheritance. Robustness check analyses are
frequently small variations on a base specification. A future configuration feature
will allow `models.yaml` to define a `base` configuration and a set of `variants` that
override specific fields. This follows the pattern of `docker-compose.override.yml`
and Kubernetes kustomize. The base specification remains a complete, valid configuration;
variants are additive overlays.

**ADR-002-F2 (Under consideration):** Configuration profiles. A `profiles/` directory
alongside the three config files would allow researchers to define named environment
profiles (e.g., `local`, `hpc`, `ci`) that override resource and output settings without
modifying the analysis specification. This is analogous to Spring Boot's application
profiles and would support researchers who run the same analysis in different computing
environments.

**ADR-002-F3 (Contingent):** Schema migration. When the configuration schema changes
in a breaking way (required fields added, field types changed), a migration utility
`econflow config migrate --from 1.0 --to 2.0 config.yaml` will be provided. This
parallels Kubernetes API version migration and Django `makemigrations`. The utility
is not planned for v1.0 but must exist before the first breaking schema change.

---

## Cross References

- `src/econflow/core/config.py` — Pydantic models for all three configuration schemas
- `src/econflow/pipeline_generic.py` — primary consumer of the configuration
- `src/econflow/cli.py` — CLI entry points that call `load_config()`
- `src/econflow/provenance.py` — SHA-256 fingerprinting of `config.yaml`
- `docs/architecture/MILESTONE_v0.7.md` §1.1, §1.3 — workspace and pipeline assessments
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §1.4 — `load_config()` as a blocking v1.0 requirement
- ADR-003 — Provenance-First Architecture (configuration fingerprinting)
- ADR-007 — Generic Variable Mapping (how variable names are specified in configuration)
- ADR-008 — Public API Philosophy (configuration schema as public API)
