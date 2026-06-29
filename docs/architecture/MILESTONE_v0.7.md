# EconFlow v0.7 — Architectural Milestone Review

**Document type:** Technical Steering Committee Review  
**Date:** 2026-06-28  
**Scope:** Full repository following completion of Sprint 8 (Data Ecosystem) and Sprint 7 (Research Integrity & Reproducibility Framework)  
**Status:** Permanent design record

---

> This document is intended to be read years from now. It describes not only what EconFlow has
> become at v0.7, but why it was built this way and what must remain true as development
> continues. Future contributors should treat it as a primary source on the project's
> philosophy and architecture.

---

## Preamble

EconFlow began as a single-paper replication package — a bespoke collection of scripts,
hardcoded paths, and paper-specific column names attached to the *AI Adoption and Total
Factor Productivity* study. By the time of this review, it has been systematically
refactored across eight development sprints into a generic, extensible research platform.
The transformation is substantial enough to warrant a formal assessment before development
continues.

The present repository contains 878 tests passing against a codebase spanning seven major
sub-packages, twelve CLI commands, and five independent plugin registries. The version
string in `pyproject.toml` reads `0.1.0`, which understates the functional maturity
meaningfully. For the purposes of this review, we designate the post-Sprint-8 state as
**v0.7** — the designation reflects milestone achievement rather than release semver.

---

## Question 1: What Capabilities Does EconFlow Now Provide?

### 1.1 Research Workspace

**What it does.** `econflow init` scaffolds a new project directory with a canonical
structure: `config/`, `data/`, `outputs/`, `paper/`, `scripts/`, `notebooks/`, `docs/`.
`econflow doctor` audits the runtime environment against a checklist of required and
optional dependencies, external tools, and platform constraints. `econflow validate`
parses the three YAML configuration files and reports schema conformance without executing
any pipeline code.

**Why it exists.** Reproducibility begins before the first line of analysis. A researcher
who uses an ad-hoc directory structure, or who runs analysis in an environment that is
never documented, has already compromised the ability to replicate the work. The workspace
commands enforce a convention that downstream tooling — provenance recording, certificate
generation, replication packaging — can rely on. Convention is not enforced rigidly; the
YAML files remain fully configurable. But the scaffold makes the right structure the path
of least resistance.

**Integration.** The `config/config.yaml` produced by `init` is consumed by every
subsequent command: `run`, `certify`, `validate`, and `report`. The directory structure
matches the paths used by `ReplicationPackage.build()`. `doctor` runs as a prerequisite
check before pipeline execution in CI workflows.

**Maturity.** Mature. The three YAML schema, the directory scaffold, and the
doctor checks are stable and tested. The one gap is that `load_config()` in
`core/config.py` still raises `NotImplementedError` — meaning the generic pipeline reads
YAML directly rather than through the typed `Settings` model. This is the single most
important structural gap in the workspace layer.

**Problems it solves.** Eliminates the most common reproducibility failure mode among
academic researchers: the undocumented, irreproducible research environment. It also
provides a natural on-ramp for new contributors who do not need to understand the full
platform before beginning productive work.

---

### 1.2 Data Management

**What it does.** `econflow.ingestion` provides a plugin-based data acquisition layer
with five connectors: `csv` (local files), `world_bank` (World Bank API v2), `oecd`
(OECD SDMX-JSON), `pwt` (Penn World Tables via Harvard Dataverse), and `fred` (St. Louis
Fed FRED API). Every connector exposes `connect()`, `download()`, `validate()`,
`metadata()`, `cache_key()`, `citation()`, and `version()`. The `CacheManager` stores
downloaded datasets under a deterministic SHA-256–keyed directory structure, with hash
verification on every retrieval. `DataValidationReport` provides structural checks on
panel CSVs. `DatasetManifest` records all datasets acquired during a run as a
JSON-serializable artifact.

**Why it exists.** Empirical research lives or dies by data provenance. When a dataset
can be silently updated at its source, or when a researcher uses a file whose origin is
no longer traceable, the analysis cannot be replicated. EconFlow's data layer treats every
download as an event to be recorded, verified, and reproduced. The cache is not merely a
performance optimization; it is a reproducibility guarantee. A pipeline that ran on a
cached dataset six months ago will produce the same result from the same cache key today,
regardless of what has changed upstream.

**Integration.** `DatasetMetadata` feeds directly into `ProvenanceRecorder` and
`ReproducibilityCertificate`. The `DatasetManifest` is designed to be included in
`ReplicationPackage` archives. `DataFingerprint` in the integrity layer reads the same
SHA-256 hash that `CacheManager` stores. The connector `citation()` method populates the
reference list in replication package READMEs.

**Maturity.** Mostly mature. `csv` and `world_bank` are production-quality. `fred`,
`oecd`, and `pwt` are implemented but not yet battle-tested against the full range of
their respective APIs' edge cases. The OECD SDMX-JSON parser, in particular, makes
assumptions about dimension ordering that may not hold for all public dataflows. There are
also vestigial root-level stub files (`ingestion/oecd.py`, `ingestion/pwt.py`,
`ingestion/world_bank.py`) from Sprint 4 that have not been deleted, creating a confusing
presence alongside the canonical `connectors/` subdirectory.

**Problems it solves.** Replaces ad-hoc download scripts that are not version-controlled,
not cached, and not verifiable with a uniform, auditable acquisition layer. Gives
researchers a single place to declare their data sources and a single mechanism for
verifying that those sources have not changed since the analysis was run.

---

### 1.3 Generic Pipeline

**What it does.** `pipeline_generic.py` implements `run_from_config()`, which reads
three YAML files — `config.yaml`, `models.yaml`, `outputs.yaml` — and executes a
complete analysis: load data, validate the panel structure, run all specified estimators,
build comparison tables, write CSV and LaTeX outputs, record provenance. The pipeline
takes no paper-specific assumptions. The dependent variable, regressors, entity column,
time column, clustering, and estimator type are all declared in YAML.

**Why it exists.** The original motivation was extracting EconFlow from a single paper.
The deeper motivation is that researchers should not need to write orchestration code.
Once the estimators, renderers, and connectors are registered, the pipeline should be a
configuration problem, not a programming problem. Separating the description of an
analysis from its execution makes studies easier to replicate, review, and modify.

**Integration.** The pipeline calls into `estimation.registry`, `outputs.tables`,
`outputs.renderers`, and `provenance`. It is the primary consumer of the plugin
registries for estimation and rendering. The `econflow run` CLI command delegates
entirely to `run_from_config()`. Legacy single-paper support is retained in the parallel
`pipeline.py` but is explicitly marked for eventual removal.

**Maturity.** Functional but not fully integrated with Sprint 5–8 subsystems.
`pipeline_generic.py` does not yet call into `econflow.estimation.registry` (it imports
`linearmodels` directly), does not produce `EstimationResult` objects, does not run
`BaseEstimator` subclasses, and does not invoke `CacheManager` or `DatasetManifest`.
There is a significant integration gap between the generic pipeline and the new
subsystem architecture. The pipeline works correctly, but it bypasses the very registries
and abstractions that Sprints 5–8 built. Closing this gap is the single highest-priority
architectural work item outstanding at v0.7.

**Problems it solves.** Makes it possible for a researcher unfamiliar with Python to
replicate a study by running a single command against a set of YAML files.

---

### 1.4 Econometric Estimation

**What it does.** `econflow.estimation` provides a uniform interface to eight estimators:
Pooled OLS (`ols`), Fixed Effects (`fe`), Two-Way Fixed Effects (`twfe`), Random Effects
GLS (`re`), First Difference (`fd`), IV/2SLS (`iv`), System GMM (`gmm`, stub), and
Panel Quantile Regression (`quantile`, stub). All implemented estimators return a
standardized `EstimationResult` containing `params`, `std_err`, `pvalues`, `nobs`, `rsq`,
`estimator_id`, and an attached list of `DiagnosticResult` objects. `BaseEstimator`
defines a three-method contract: `validate()`, `fit()`, `diagnostics()`. Estimators
register themselves via `@register(estimator_id)`.

**Why it exists.** Panel econometrics requires not just running a regression but
selecting the right estimator, running appropriate post-estimation diagnostics,
communicating results in a consistent format, and being able to swap estimators without
changing downstream reporting code. The `EstimationResult` contract means that a table
builder, a renderer, and a diagnostic check can all operate identically regardless of
which estimator produced the result. The alternative — ad-hoc model objects from six
different libraries — would require bespoke handling at every downstream step.

**Integration.** `EstimationResult` is the central data structure of EconFlow. It is
consumed by every diagnostic, every table builder, and every integrity check.
`ProvenanceRecorder.record_dataset()` and `ReproducibilityCertificate.build()` both
accept estimation results. The integrity checks in Sprint 7 operate on `EstimationResult`
objects. The pipeline is the primary caller of `BaseEstimator.run()`.

**Maturity.** Mature for the six implemented estimators. The two stubs — GMM and Panel
Quantile — expose the correct interface but raise `NotImplementedError` on `fit()`.
The `BaseEstimator._provenance_stamp()` method correctly records estimator identity for
downstream use. The main gap is that the generic pipeline does not yet instantiate
`BaseEstimator` subclasses via the registry.

**Problems it solves.** Normalizes the heterogeneous output objects of `statsmodels`,
`linearmodels`, and `scipy` into a single result type. Makes it possible to write code
that handles OLS and IV results identically without knowing which was used.

---

### 1.5 Diagnostics

**What it does.** `econflow.diagnostics` provides six post-estimation tests: Hausman
specification test (`hausman`), Breusch-Pagan test for heteroscedasticity
(`breusch_pagan`), Pesaran cross-sectional dependence test (`pesaran_cd`), Variance
Inflation Factor (`vif`), Wooldridge autocorrelation test (`wooldridge`, stub), and
serial correlation test (`serial_correlation`, stub). Each diagnostic is a
`BaseDiagnostic` subclass that implements `run(result: EstimationResult)` and returns a
`DiagnosticResult`. The registry exposes `@register_diagnostic()` for third-party
additions. `BaseDiagnostic.supports(estimator_id)` allows diagnostics to declare which
estimators they are applicable to, enabling the pipeline to automatically skip
inapplicable tests.

**Why it exists.** Post-estimation diagnostics are not optional in published empirical
work. A paper that reports IV estimates without reporting first-stage F-statistics, or
reports panel models without testing for cross-sectional dependence, is producing
unreliable results. Making diagnostics automatic — registered, self-describing, and
running as part of every estimation — removes the temptation to skip inconvenient tests.

**Integration.** `DiagnosticResult.estimator_id` is stamped by `run_with_context()` to
allow grouping by estimator in the `build_diagnostics_report()` output. The `integrity`
layer's `pvalue_distribution` check operates on diagnostic p-values. The reporting engine
renders diagnostics as a separate section in the publication bundle.

**Maturity.** Structurally mature; partially implemented. The four working diagnostics
cover the most common tests for panel data. The two stubs correctly advertise their
`status="stub"` in the registry.

**Problems it solves.** Converts post-estimation testing from a manual, often-omitted
step into an automatic, registered, and auditable part of every pipeline run.

---

### 1.6 Reporting

**What it does.** `econflow.outputs` provides a layered reporting engine. `ReportTable`
and `ReportFigure` are content-presentation-separated data structures: cells contain
pre-formatted strings; renderers handle structure. Five renderers are registered: `csv`,
`latex` (booktabs-formatted), `markdown`, `html`, and `json`. Eight table builders
construct publication-standard tables: regression comparison, summary statistics, balance,
correlation, robustness, sensitivity, falsification, and heterogeneity. Seven figure
builders are defined: `CoefficientPlot`, `CIPlot`, and five stubs. `PublicationBundle`
orchestrates writing all tables and figures to a directory. `DiagnosticsReportBuilder`
produces a formatted diagnostics section.

**Why it exists.** The bridge between estimation and publication is where reproducibility
most commonly fails. When a researcher manually copies coefficients into a LaTeX table,
discrepancies between the code output and the published table are invisible. EconFlow's
reporting engine generates the LaTeX table directly from the `EstimationResult` objects,
leaving no room for transcription error. The content-presentation separation means that
the same `ReportTable` can produce CSV for replication, LaTeX for submission, and
Markdown for a notebook without the table builder knowing which renderer is active.

**Integration.** Renderers register via `@register_renderer()`. The `PublicationBundle`
validates renderer IDs at construction time and raises `RegistryError` on an unknown ID.
The `econflow report` CLI command builds a bundle from the last pipeline run. Renderer
IDs are declared in `outputs.yaml` and passed through the pipeline.

**Maturity.** The renderer registry, table model, LaTeX and CSV renderers, and the
regression table builder are production-quality. The figure builders are structurally
correct but `CoefficientPlot` and `CIPlot` are the only two with working implementations;
the remaining five raise `NotImplementedError`.

**Problems it solves.** Eliminates the most common source of errors between analysis and
publication: manual transcription of results from terminal output into formatted tables.

---

### 1.7 Research Integrity

**What it does.** `econflow.integrity` provides three integrity checks on estimation
results: coefficient stability (detects extreme or non-finite coefficients),
sample size adequacy (checks n against configurable thresholds), and p-value distribution
health (flags distributions consistent with p-hacking — all significant, all identical,
or suspiciously right-skewed). Each check is a `BaseIntegrityCheck` subclass registered
via `@register_integrity_check()`. Checks return `IntegrityCheckResult` with status
`pass`, `warn`, `fail`, or `skip`.

**Why it exists.** The replication crisis in social science is partly a data fabrication
problem and partly a researcher-degrees-of-freedom problem. Automated integrity checks
do not solve the former, but they address a specific, detectable class of the latter:
results that have the statistical signatures of selective reporting. A pipeline that
automatically flags "all fifteen p-values are below 0.001 with identical values" is
imposing a minimum standard of statistical plausibility that no ad-hoc analysis workflow
provides. The intent is not accusation but early warning — a signal to the researcher to
inspect the results before submission.

**Integration.** Integrity checks are invoked by `econflow certify` and their results are
embedded in `ReproducibilityCertificate.check_results`. The certificate's
`overall_status` aggregates across all check results. The `econflow package` command
includes the certificate in the replication archive.

**Maturity.** The three implemented checks are production-quality. The plugin
architecture matches the pattern established in diagnostics and renderers and is ready
for additional checks without modification to core code.

**Problems it solves.** Provides the first automated barrier between an analysis run and
a submission — a layer that no existing econometrics library provides.

---

### 1.8 Reproducibility

**What it does.** `ReproducibilityCertificate` is a JSON-serializable snapshot of a
complete pipeline run: git commit hash, dirty-tree status, Python version, all package
versions, SHA-256 of every input dataset, row counts, SHA-256 of the configuration file,
and the results of all integrity checks. `detect_drift()` compares two certificates and
reports which of eight axes have changed (git, packages, data hash, data row count, data
file presence, config hash) with per-axis severity (`none`, `warn`, `fail`). The
`econflow verify` command captures the live environment and compares it to a stored
certificate. Schema version `1.0.0` is written to every certificate and is checked on
load.

**Why it exists.** A study is reproducible if and only if someone else can obtain the
same results from the same inputs on a different machine. The certificate does not
guarantee reproducibility — it provides the information needed to diagnose failures. If
a result changes, `detect_drift()` tells you whether the git commit changed, whether a
package was updated, or whether the dataset changed upstream. Without this record,
debugging a replication failure requires starting from zero.

**Integration.** The certificate is built from `EnvironmentFingerprint.capture()`, which
delegates to `provenance.py`'s `_git_info()`, `_python_info()`, `_platform_info()`,
and `_package_versions()` — there is no duplication. `DataFingerprint.from_path()`
handles CSV and Parquet natively. The certificate feeds the `ReplicationPackage`.

**Maturity.** Mature. Atomic writes, schema versioning, and eight-axis drift detection
are all implemented and tested. The one integration gap is that the generic pipeline does
not automatically call `certify` at the end of a run — it remains a separate explicit
step.

**Problems it solves.** Makes it possible to determine, after the fact, whether a
replication failure is a code problem, an environment problem, or a data problem.

---

### 1.9 Provenance

**What it does.** `ProvenanceRecorder` is a context manager that records a
`run_metadata.json` file for every pipeline execution. It captures timestamps, git state,
Python version, package versions, all input SHA-256 hashes, and all output directory
contents. The JSON Schema in `outputs/provenance/schema.json` specifies the record
format with a `schema_version` field. `DatasetManifest` (Sprint 8) extends this to
data-acquisition events, recording connector identity, cache key, parameters, validation
outcome, citation, and dataset version for each downloaded dataset.

**Why it exists.** Provenance is the continuous record of the chain of custody for
scientific data and analysis. It differs from reproducibility in that it records what
happened, not how to repeat it. A provenance record answers: who ran this pipeline, when,
on which version of the code, against which version of the data, and producing which
outputs. This record is required by journals and funding agencies as part of the
transparency infrastructure of modern empirical research.

**Integration.** `ProvenanceRecorder` is called by `pipeline_generic.py`. Its output is
consumed by `IntegrityFramework.from_provenance()`. The `run_metadata.json` and
`manifest.json` are both included by `ReplicationPackage`.

**Maturity.** The core `ProvenanceRecorder` is mature and has been in place since early
sprints. The `DatasetManifest` is newly added in Sprint 8 and follows the same JSON
serialization conventions. The two records are not yet linked — a manifest reference is
not embedded in `run_metadata.json`.

**Problems it solves.** Provides an audit trail that satisfies journal reproducibility
requirements and enables post-publication investigation of result discrepancies.

---

### 1.10 Plugin Architecture

**What it does.** Five independent plugin registries exist: estimators
(`@register(estimator_id)`), diagnostics (`@register_diagnostic(id)`), renderers
(`@register_renderer(id)`), connectors (`@register(connector_id)`), and integrity checks
(`@register_integrity_check(id)`). Every registry follows the same pattern: a
module-level `dict`, a class decorator that writes to the dict at import time, and
`get_<type>(id)`, `list_<type>()`, `unregister_<type>(id)` functions. Third-party
extensions need only import `register` and decorate a subclass of the appropriate base
class; no modification to EconFlow core is required.

**Why it exists.** Panel econometrics is not a closed domain. A researcher may need a
Driscoll-Kraay standard-error estimator, a custom heteroscedasticity test, or a
connector to a proprietary database. If these require forking EconFlow, the project
fails at its mission of being reusable. Plugin registries extend the platform without
modification to its core and without introducing coupling between subsystems.

**Integration.** All five registries are populated at import time by the respective
`plugins/__init__.py` modules or `connectors/__init__.py`. The generic pipeline queries
the estimator and renderer registries at runtime, making the set of available estimators
and renderers an open, not closed, set.

**Maturity.** The pattern is consistent, tested, and complete. The missing element is a
formal Plugin SDK: a documented, stable API surface that third-party authors can target
with confidence that it will not change. The registries exist; the contract around them
is not yet formally published.

---

### 1.11 Testing Infrastructure

**What it does.** 878 tests across three tiers: unit tests in `tests/unit/` covering
each sub-package in isolation; integration tests in `tests/integration/` covering
end-to-end workflows; and regression tests in `tests/regression/` tracking reference
outputs from the original AI & Productivity paper. pytest with `--import-mode=importlib`
prevents import-time cross-contamination. All network calls in connector tests are mocked
via `unittest.mock.patch`. The test suite runs in under 30 seconds.

**Why it exists.** At this scale of plugin architecture, the absence of tests means that
adding a new estimator or changing a renderer could silently break ten other things.
The three-tier structure reflects the different failure modes: unit tests catch API
contract violations within a module; integration tests catch interface mismatches between
modules; regression tests catch semantic changes to the results that users depend on.

**Maturity.** Good overall. The unit and integration tiers are well-populated. The
regression tier is present but covers only the original paper's outputs, not the generic
pipeline. Coverage configuration in `pyproject.toml` excludes large portions of the
production codebase from coverage requirements — this is a documented concession to the
stub ecosystem, not a quality failure, but it means that coverage numbers are not a
reliable quality signal at this stage.

**Problems it solves.** Makes refactoring safe. Without the test suite, the consistent
plugin pattern across five registries could not be maintained across eight sprints of
parallel development.

---

### 1.12 CLI

**What it does.** Twelve commands are accessible via the `econflow` entry point:
`init`, `doctor`, `validate`, `info`, `run`, `report`, `certify`, `verify`, `package`,
`fetch`, `datasets`, and `cache` (with four sub-commands: `list`, `inspect`, `clear`,
`purge`). All commands print Rich-formatted output to the terminal. All commands return
non-zero exit codes on failure, making them composable in shell scripts and CI pipelines.

**Why it exists.** A research platform that requires Python scripting to use is a
platform for Python programmers, not for empirical researchers. The CLI is the
commitment to making EconFlow useful to researchers who want to run a reproducible
analysis without writing pipeline code. The twelve commands cover the complete research
workflow: environment setup, data acquisition, analysis execution, result rendering, and
replication packaging.

**Maturity.** The command surface is complete and consistent. The implementation quality
varies: `init`, `doctor`, `validate`, and the integrity commands are clean and
well-tested; `run` and `report` still connect to the legacy pipeline and the non-registry
generic pipeline respectively. The CLI scaffold in `cli_scaffold/` is a dead artifact
that should be deleted.

---

### 1.13 Developer Experience

**What it does.** `pyproject.toml` configures Hatchling as the build backend, Ruff for
linting with `E`, `F`, `I`, `UP` rule sets at line length 100, and pytest with
`--import-mode=importlib`. `CHANGELOG.md` is maintained per sprint. Five architecture
documents in `docs/architecture/` describe the design of each major subsystem. The
`examples/ai_productivity_paper/` directory contains a complete reference study with
YAML configuration and reference outputs.

**Why it exists.** A platform that is hard to contribute to will not be contributed to.
The linting configuration, consistent plugin pattern, and architecture documentation
lower the barrier for new contributors. The reference example shows the intended usage
pattern end-to-end.

**Maturity.** The tooling is appropriate for the project's stage. The documentation
coverage is uneven: the five architecture docs are thorough; the README is stale (it
reports "100-test suite" against a current count of 878, and does not mention the
integrity or data ecosystem layers). The CONTRIBUTING.md, CODE_OF_CONDUCT.md, and
SECURITY.md exist but have not been updated to reflect the plugin architecture.

---

## Question 2: Which Architectural Decisions Are Now Stable?

### 2.1 Plugin Registries as the Primary Extension Mechanism

**Status: Core**

**Adopted because:** EconFlow needs to be extended without forking. A researcher adding
a custom estimator should not need to modify `estimation/__init__.py`. The import-time
decorator pattern (`@register()`) is borrowed from Flask, pytest, and Sphinx — mature
projects that have validated it at scale. The five registries in EconFlow are not
independent inventions; they are a consistent application of a single idiom.

**Why it must remain stable:** The plugin pattern is what separates EconFlow from a
fixed-function script collection. If registries were replaced with explicit imports,
third-party extensions would require EconFlow core modifications and would conflict on
update. If a different extension mechanism were adopted (e.g., entry points, class
inheritance scanning), every existing plugin would break and every architecture document
would be obsolete.

**Risks of change:** Any change to the decorator signature or the `_REGISTRY` dict
structure would break every registered plugin silently at import time. Changes to
`get_<type>(id)` raising conventions would break every CLI command that calls it.

---

### 2.2 `EstimationResult` as the Central Data Carrier

**Status: Core**

**Adopted because:** The alternative — passing raw model objects from `linearmodels` or
`statsmodels` between pipeline stages — would require every downstream component
(diagnostics, table builders, integrity checks) to know which library produced the
result and handle its idiosyncratic API. `EstimationResult` normalizes all of this into
a single, library-agnostic data structure with known fields: `params`, `std_err`,
`pvalues`, `nobs`, `rsq`, `estimator_id`, and `diagnostic_results`.

**Why it must remain stable:** The `EstimationResult` schema is the API contract between
estimation and everything downstream. It is referenced in diagnostics, integrity checks,
table builders, and the reporting engine. A breaking change to its field names would
cascade across every subsystem. New fields can be added safely; removing or renaming
existing fields requires a versioned migration path.

**Risks of change:** Removing `pvalues` or changing `params` from a pandas `Series`
to a dict would break every diagnostic plugin, every integrity check, and every table
builder simultaneously.

---

### 2.3 Configuration-First Architecture

**Status: Core**

**Adopted because:** The original paper-specific pipeline had analysis decisions embedded
in Python code. Every research question that differed from the original paper required
code changes. YAML configuration separates the declaration of an analysis (what to
estimate, with what variables, over which sample) from its execution.

**Why it must remain stable:** If EconFlow began requiring code changes to run a
different study, it would cease to be a platform and become a set of examples.
Configuration-first means that a researcher can replicate a published study by inspecting
and modifying three YAML files, without reading any Python.

**Risks of change:** If pipeline configuration were migrated to a Python DSL or a
programmatic API, the barrier to non-programmer researchers would rise sharply. The
connection to the integrity and provenance layers (which fingerprint the config file)
would break.

---

### 2.4 Schema-Versioned JSON Artifacts

**Status: Core**

**Adopted because:** Certificates, manifests, and provenance records are intended to
persist across platform versions. A certificate written by EconFlow 0.7 may need to be
read by EconFlow 1.2 for long-term replication studies. Without `schema_version`,
there is no mechanism to detect or handle format incompatibilities.

**Why it must remain stable:** The value of a reproducibility certificate is that it
can be read years after it was written. If schema versioning were abandoned, the entire
reproducibility layer would degrade on every platform update. The `1.0.0` versions on
`ReproducibilityCertificate` and `DatasetManifest` are commitments, not labels.

**Risks of change:** Any breaking change to the JSON schema without a version bump
would make stored certificates unreadable. Any change to `CERTIFICATE_SCHEMA_VERSION`
without a documented migration path would invalidate existing archives.

---

### 2.5 Content-Presentation Separation in Outputs

**Status: Strongly Stable**

**Adopted because:** A table builder that produces LaTeX directly cannot also produce
CSV or Markdown. Separating `ReportTable.cells` (pre-formatted strings) from the
renderer (which provides structure) allows any table to be rendered to any format
without the table builder knowing which renderer is active.

**Why it must remain stable:** The renderer registry is the architectural location for
adding new output formats. A future Quarto renderer, a Word renderer, or an HTML
dashboard renderer should require adding one registered class, not modifying eight table
builders.

**Risks of change:** If table builders were rewritten to produce format-specific output,
the `renderers/` plugin system would be obsolete and every new output format would
require modifying every table builder.

---

### 2.6 Provenance-First Design

**Status: Core**

**Adopted because:** Provenance was designed in from Sprint 2, not retrofitted later.
The `ProvenanceRecorder` context manager wraps the entire pipeline execution.
SHA-256 hashing of inputs is not optional configuration; it runs unconditionally.
This reflects a foundational commitment: every pipeline run is a scientific event that
must be recorded.

**Why it must remain stable:** If provenance recording became optional or conditional,
researchers would disable it when it was inconvenient — precisely the runs where it is
most needed. The value of a provenance record is that it covers all runs, not some runs.

**Risks of change:** Making provenance opt-in would undermine the reproducibility
guarantees that differentiate EconFlow from running a script manually.

---

### 2.7 No Paper-Specific Assumptions

**Status: Core**

**Adopted because:** EconFlow was extracted from a single paper. The extraction was only
worthwhile if the result could run a different study without code changes. Every commit
that re-introduced a paper-specific assumption would narrow the user base back toward
one.

**Why it must remain stable:** This is the constraint that defines EconFlow's identity.
A tool that can run only one paper's analysis is a replication package, not a platform.

**Risks of change:** Allowing paper-specific configuration under any name — "study
defaults," "built-in templates," "preset configurations" — would be the beginning of
re-specialization.

---

### 2.8 Fail Loudly

**Status: Strongly Stable**

**Adopted because:** Silent failures in empirical pipelines are dangerous. A validator
that warns but continues, a diagnostic that returns `None` on failure, a cache that
silently returns corrupt data — any of these would produce incorrect results that look
correct.

**Why it must remain stable:** `ConnectorError`, `EstimatorError`, `CacheCorruptionError`,
`RegistryError` — these exist precisely to ensure that anomalies surface as immediate,
traceable failures rather than downstream corruptions.

**Risks of change:** Adding "best-effort" modes, try/except-and-continue patterns, or
silent fallbacks anywhere in the execution path would erode the reliability guarantees
that make EconFlow appropriate for published research.

---

### 2.9 Single CLI Entry Point

**Status: Evolving**

**Adopted because:** A consistent `econflow <command>` interface makes the platform
discoverable. Every capability is reachable from a single executable.

**Why it should remain stable:** Splitting the CLI into multiple entry points would
fragment the user experience and create version skew risks between components.

**Current risk:** The `cli_scaffold/` artifact and the inconsistency between the legacy
`pipeline.py` path and the generic `pipeline_generic.py` path mean that the CLI's
internal routing is more complex than it should be. This is evolving, not stable.

---

## Question 3: What Technical Debt Is Intentionally Deferred?

### 3.1 `load_config()` Returning `Settings` — *Near-term*

**What it is.** `core/config.py` defines `Settings`, `ProjectMeta`, `DataConfig`,
`VariablesConfig`, and all nested Pydantic models, but `load_config()` raises
`NotImplementedError`. The generic pipeline reads YAML via `_load_yaml()` instead,
bypassing type validation.

**Why deferred.** The YAML schema was designed before all its consumers were known.
Implementing `load_config()` before the pipeline, connector, and integrity layers were
finalized risked repeated rewrites as new fields were discovered. Now that the full
surface is visible, implementing it is straightforward and safe.

**When to revisit.** Immediately after this milestone review. This is blocking task
rather than acceptable debt — every CLI command that accepts a `--config` flag is
potentially silently ignoring invalid YAML. Sprint 9 must implement this.

---

### 3.2 Two Estimator Stubs — *Near-term*

**What it is.** System GMM and Panel Quantile Regression are registered with
`status="stub"` and raise `NotImplementedError` on `fit()`.

**Why deferred.** GMM requires implementing two-step weighting matrix estimation and
Windmeijer-corrected standard errors — a non-trivial implementation that was deprioritized
relative to the architectural work of establishing the registry pattern. Quantile
regression for panels has multiple competing methods (Canay 2011, Machado-Santos Silva
2019); committing to one before the user base provides signal is premature.

**When to revisit.** GMM is used by most IV robustness checks in applied macro work;
it should be implemented in Sprint 9 or 10. Quantile can follow demand.

---

### 3.3 Two Diagnostic Stubs — *Near-term*

**What it is.** Wooldridge autocorrelation test and serial correlation test are
`status="stub"`.

**Why deferred.** The Wooldridge test requires auxiliary regression on first differences,
which was not prioritized while the diagnostic registry architecture was being established.

**When to revisit.** Sprint 9. Both tests are referenced in empirical practice for
panel data; their absence is a gap in the diagnostics layer's completeness.

---

### 3.4 Five Figure Builder Stubs — *Medium-term*

**What it is.** `distribution.py`, `event_study.py`, `residual_plot.py`,
`heteroscedasticity_plot.py`, and `panel_trends.py` expose the correct interface but
raise `NotImplementedError`.

**Why deferred.** Figures require more design decisions than tables: output format,
resolution, theming, color accessibility. These decisions should be made with user
feedback rather than in isolation. The two implemented builders (`CoefficientPlot`,
`CIPlot`) provide a reference implementation.

**When to revisit.** Medium-term. Event study plots are the most requested by
researchers using difference-in-differences designs; that should come first.

---

### 3.5 Generic Pipeline Not Using Estimator Registry — *Near-term*

**What it is.** `pipeline_generic.py` calls `linearmodels` directly rather than
dispatching through `estimation.registry`. This means that adding a new estimator to the
registry does not make it available in the pipeline.

**Why deferred.** The registry was built in Sprint 5; the generic pipeline predates it
and was not refactored in the same sprint to keep scope manageable.

**When to revisit.** Sprint 9. This is the most important single integration gap in the
system. Until it is closed, the plugin architecture for estimation is not reachable from
the primary user-facing workflow.

---

### 3.6 Plugin SDK Documentation — *Medium-term*

**What it is.** No formal, versioned API documentation describes the stable interface
that a third-party plugin author should implement. The architecture documents describe
the internal design; a Plugin SDK would describe the external contract.

**Why deferred.** Publishing an API contract before the API is stable creates a migration
burden when the contract changes. The plugin pattern is consistent but not yet committed
to backward compatibility.

**When to revisit.** Before v1.0. A plugin SDK is a prerequisite for the project being
genuinely extensible by authors who are not familiar with the internals.

---

### 3.7 Stale Root-Level Ingestion Stubs — *Near-term*

**What it is.** `ingestion/oecd.py`, `ingestion/pwt.py`, `ingestion/world_bank.py` at
the package root are Sprint 4 artifacts that have been superseded by the `connectors/`
subdirectory implementations.

**Why deferred.** Deletion was deprioritized during Sprint 8 to avoid the risk of
breaking existing import paths.

**When to revisit.** Immediately. These files are not imported by anything (they were
stubs, not functional), but their presence creates confusion for anyone reading the
directory structure.

---

### 3.8 Cloud Execution and Distributed Computation — *Long-term*

**What it is.** EconFlow runs on a single machine. Large panel datasets with thousands
of units and decades of observations may exceed available RAM or require parallel
estimation.

**Why deferred.** The current user base runs studies on personal computers and research
servers. Cloud execution would require authentication, credential management, cost
awareness, and job monitoring — a substantial surface that is not yet justified by demand.

**When to revisit.** When there is evidence that users are RAM-constrained or that
estimation runtimes are prohibitive. Long-term.

---

### 3.9 Bayesian Estimation — *Long-term*

**What it is.** None of the eight registered estimators use Bayesian inference. MCMC
estimation, prior specification, and posterior summary tables are all absent.

**Why deferred.** Bayesian panel econometrics requires different concepts of uncertainty,
different diagnostics (chain convergence, posterior predictive checks), and different
output formats. This is not an extension of the existing architecture; it is a parallel
track. It should not be attempted until the frequentist track is complete.

**When to revisit.** After v1.0.

---

### 3.10 Journal API Integrations — *Long-term*

**What it is.** No mechanism exists to submit a replication package directly to a
journal's data repository (ICPSR, Harvard Dataverse, Zenodo).

**Why deferred.** Submission APIs are unstable, authentication is complex, and the
submission process varies by journal. The `ReplicationPackage` builder produces a
directory that can be uploaded manually — this is adequate for the current use case.

**When to revisit.** Long-term, and only if the user community clearly identifies this
as a friction point. The manual step is not a serious burden.

---

## Question 4: Which Principles Must Never Be Violated?

### Principle 1: Scientific Correctness Over Convenience

**Purpose.** Every implementation decision that trades accuracy for ease of use must be
refused.

**Rationale.** EconFlow produces results that researchers publish. A published result
is permanent. An incorrect result — caused by a silent approximation, a default that
seemed convenient, or a numerical shortcut — cannot be unpublished. The harm from a
convenience-driven error in a research platform is categorically different from the harm
of a bug in business software.

**Examples.** The Hausman test uses `np.linalg.pinv` rather than direct inversion
because the variance difference matrix may be near-singular. The cache hash verification
runs on every retrieve, not just the first. Diagnostic p-values are never imputed or
defaulted. `CacheCorruptionError` is raised rather than returning the corrupt file with
a warning.

**Consequences of violation.** If `linearmodels` errors were silently caught and
replaced with OLS results, or if missing panel identifiers were silently imputed rather
than flagged, researchers would produce and publish incorrect results with no indication
that anything had gone wrong. This is the failure mode that destroyed careers during the
replication crisis, and it is the failure mode that EconFlow exists to prevent.

---

### Principle 2: Reproducibility by Default

**Purpose.** Every pipeline run produces a reproducibility record. There is no
configuration option to disable it.

**Rationale.** Reproducibility is only a guarantee if it is unconditional. A researcher
who knows they can turn off provenance recording will turn it off when the run takes
longer than expected, when the output directory is full, or when debugging. The value
of the record is its completeness across all runs.

**Examples.** `ProvenanceRecorder` wraps the entire pipeline execution as a context
manager, not an optional post-processing step. `CacheManager.verify_hash()` runs on
every retrieve, not on demand. `ReproducibilityCertificate` is written atomically with
`os.fsync()` + `Path.replace()` to prevent partial writes that would corrupt the record.

**Consequences of violation.** Making provenance optional would mean that the runs most
likely to contain errors — rushed debugging runs, late-night revision runs — would be
the runs without records. These are precisely the runs that need audit trails.

---

### Principle 3: Transparency Before Automation

**Purpose.** EconFlow may automate the execution of analysis, but it must never automate
the interpretation of results.

**Rationale.** Automated pipelines that select estimators, drop observations, or
interpret significance levels without researcher review transfer scientific judgment to
software. Software cannot exercise scientific judgment. If EconFlow were to automatically
select FE over RE based on the Hausman test result, it would be removing a decision that
belongs to the researcher. The platform reports the Hausman test result; the researcher
decides what to do with it.

**Examples.** Integrity checks produce `pass`, `warn`, `fail`, and `skip` — they do not
modify the analysis. Diagnostic results are attached to `EstimationResult` but do not
change the coefficients. The pipeline runs all estimators specified in YAML; it does not
select among them.

**Consequences of violation.** An automated estimator-selection feature would mean that
the YAML configuration no longer fully describes the analysis. The same YAML file run on
different data would produce different estimator choices. This is precisely the
researcher-degrees-of-freedom problem that EconFlow is designed to expose, not replicate.

---

### Principle 4: Explicit Configuration, Never Magic Defaults

**Purpose.** Every analysis parameter that affects results must be explicitly declared in
a configuration file. No silent defaults.

**Rationale.** In an ad-hoc script, a researcher may forget to set the number of
bootstrap iterations or the clustering variable, and a default will be used. That default
may produce incorrect standard errors. If the default is not documented in the script,
the analysis is not reproducible. EconFlow's configuration-first architecture requires
explicit declaration of all parameters; no parameter may be silently inferred.

**Examples.** `DataValidationConfig` defaults `max_missing_pct=1.0` (effectively
disabled) rather than silently dropping observations. The `year_start` and `year_end`
parameters of `WorldBankConnector` default to `None` (no bound) rather than a
decade-specific default. `@register()` raises `RegistryError` on duplicate IDs rather
than silently overwriting.

**Consequences of violation.** Any "smart default" that changes behavior based on the
data being analyzed — automatic outlier removal, automatic frequency detection, automatic
lag selection — would make the analysis non-reproducible from its configuration file
alone.

---

### Principle 5: Generic Before Special-Case

**Purpose.** No module, function, or configuration option in the published EconFlow
package may be specific to any particular study.

**Rationale.** EconFlow was extracted from a single paper. Its entire value proposition
is that it can run any study, not just one. Every special case admitted into the core
platform narrows its applicability and increases the maintenance burden. If a feature
cannot be designed generically, it belongs in an example, not in the platform.

**Examples.** `WorldBankConnector` accepts any list of indicator codes; it does not know
what they measure. `build_regression_table()` accepts any `EstimationResult`; it does
not know what the regressors represent. The `config.yaml` schema accepts any column
names for `entity_col`, `time_col`, `outcome`, and `controls`.

**Consequences of violation.** Adding a built-in "AI adoption index" connector, or a
`build_tfp_table()` function, or a `run_ai_productivity_pipeline()` shortcut, would be
re-specialization. It would signal to potential users that EconFlow is for AI and
productivity research, not for their study.

---

### Principle 6: Backward Compatibility as a Commitment

**Purpose.** Any change to the public API that breaks existing code must go through a
deprecation cycle, not a breaking release.

**Rationale.** Research pipelines are often run months or years after they were written.
A researcher who ran a study in 2025 and returns to replicate it in 2027 must be able to
run the same YAML files against the same version of EconFlow and obtain the same results.
If API changes routinely break old configurations, EconFlow undermines the reproducibility
it is designed to provide.

**Examples.** The `APRPError → EconFlowCoreError` rename in Sprint 1 was implemented with
a deprecated alias, not a breaking change. `CERTIFICATE_SCHEMA_VERSION = "1.0.0"` is
checked on load, and the load function is expected to maintain backward compatibility
with older certificates.

**Consequences of violation.** A breaking change to `EstimationResult` fields, YAML
schema required keys, or CLI command signatures would invalidate existing research
pipelines. This is not merely inconvenient — it is a reproducibility failure.

---

### Principle 7: Provenance Everywhere

**Purpose.** Every artifact produced by EconFlow — a CSV table, a LaTeX file, a
certificate, a manifest — must be traceable to the inputs and configuration that produced
it.

**Rationale.** Research outputs are not standalone files. They are the end of a chain
that begins with data acquisition and passes through cleaning, estimation, and rendering.
If any link in that chain is not recorded, the chain is broken. "Provenance everywhere"
means that the chain is unbroken — not that every file contains a complete provenance
record, but that a complete record exists and is findable.

**Examples.** `run_metadata.json` records input and output SHA-256 hashes.
`ReproducibilityCertificate` records the git commit that produced it.
`DatasetManifest` records the connector, parameters, and cache key for every downloaded
dataset. `DatasetMetadata.download_date` is stored in UTC ISO-8601.

**Consequences of violation.** Any pipeline path that produces outputs without recording
provenance — a shortcut command that skips provenance for speed, a "quick run" mode that
skips hashing — would be an exit from the reproducibility guarantee.

---

### Principle 8: The Plugin Contract Is a Public Contract

**Purpose.** Once a plugin interface is documented, it must remain stable. Plugin authors
are external to the project and cannot be notified of breaking changes.

**Rationale.** The plugin architecture is the mechanism by which EconFlow becomes more
capable over time without central coordination. If a researcher writes a
`@register("my_estimator")` plugin today and it breaks when EconFlow updates the
`BaseEstimator` interface, that researcher has been harmed by the update. Plugin
interfaces are public APIs, not implementation details.

**Examples.** `BaseEstimator.validate()`, `fit()`, and `diagnostics()` must not change
signatures. `BaseDiagnostic.run()` must continue to return `DiagnosticResult`. The
`@register_renderer()` decorator must remain importable from `econflow.outputs`.

**Consequences of violation.** Breaking a plugin interface silently breaks every
third-party plugin without any diagnostic signal. Researchers whose workflows depend on
those plugins would experience mysterious import errors or incorrect behavior.

---

### Principle 9: AI Assists; It Does Not Replace Scientific Judgment

**Purpose.** EconFlow may use automated checks to flag anomalies, but it must not
automate decisions that require domain expertise.

**Rationale.** The integrity check system can flag a suspicious p-value distribution. It
cannot determine whether that distribution reflects p-hacking, a genuine discovery, or
unusual data characteristics. That determination requires a researcher. A platform that
claims to detect scientific misconduct, or that automatically corrects for suspected
selection effects, is making a scientific claim that the software is not equipped to make.

**Examples.** `PvalueDistributionCheck` returns `warn` or `fail`; it does not modify
the estimation or suppress the results. `CoefficientStabilityCheck` flags large
coefficients; it does not re-scale them. All integrity checks are advisory, not
corrective.

**Consequences of violation.** Automated correction or suppression of results based on
integrity checks would mean that the published output is not the output of the analysis
as declared in the configuration — it is the output of a post-hoc correction algorithm.
This is precisely the hidden researcher-degrees-of-freedom problem.

---

## Repository Health Assessment

### Architecture Maturity — Good

The seven-subsystem structure (workspace, ingestion, estimation, diagnostics, outputs,
integrity, provenance) is coherent and defensible. The plugin registry pattern is
consistent across all five registries. The content-presentation separation in outputs,
the `EstimationResult` carrier, and the schema-versioned JSON artifacts reflect genuine
architectural thought. The main gap is the integration failure between `pipeline_generic.py`
and the new subsystem registries, which leaves the central user-facing workflow
disconnected from five sprints of infrastructure work.

### Code Organization — Good

The `src/` layout, `pyproject.toml`-based build, and `tests/` separation are
standard and appropriate. Within sub-packages, the pattern `base.py`, `registry.py`,
`plugins/` is consistent and readable. The two organization problems are the
`cli_scaffold/` artifact (dead code that creates confusion) and the root-level ingestion
stubs that coexist with `connectors/`.

### API Consistency — Good

Every plugin registry exposes `get_<type>()`, `list_<type>()`, `register_<type>()`,
`unregister_<type>()`. Every base class provides `_make_cache_key()` or equivalent
shared helpers. Every serializable artifact provides `to_dict()`, `to_json()`,
`from_dict()`, `from_json()`. The consistency is genuine and makes the codebase
readable across subsystems.

### Documentation Quality — Needs Improvement

The five architecture documents in `docs/architecture/` are thorough and well-written.
The README is materially stale: it reports 100 tests against 878, does not mention the
integrity layer, the data ecosystem, or nine of the twelve CLI commands, and still
describes the project as primarily a replication package rather than a platform. This
is the documentation gap most visible to new users and potential contributors.

### Testing Maturity — Good

878 tests across three tiers, with network calls mocked, running in under 30 seconds,
is a strong position for a platform at this stage. The coverage exclusion list in
`pyproject.toml` is extensive and reflects the stub ecosystem honestly, but it means
that coverage metrics cannot be used as a quality gate. The regression tier covers only
the original paper; generic pipeline regression tests do not yet exist.

### Extensibility — Good

The five plugin registries, the formal `BaseEstimator`, `BaseDiagnostic`,
`BaseIntegrityCheck`, and `AbstractConnector` contracts, and the `BaseRenderer`
interface collectively make EconFlow genuinely extensible. Adding a new connector,
estimator, diagnostic, renderer, or integrity check requires touching exactly one file
(the new plugin module) and one import in the corresponding `plugins/__init__.py`. No
modifications to core code are required. The one missing piece is a documented,
versioned Plugin SDK.

### Maintainability — Good

The consistent plugin pattern, the architecture documents, the per-sprint CHANGELOG
entries, and the three-tier test suite collectively make the codebase maintainable for a
new contributor. The primary maintainability risk is the growing divergence between
`pipeline_generic.py` (which bypasses the registry) and the plugin architecture (which
is the intended mechanism). Every sprint that passes without integrating these makes the
integration more expensive.

### Scientific Reproducibility — Excellent

This is the strongest aspect of the platform. The combination of deterministic
cache keys, SHA-256 hash verification on retrieve, schema-versioned certificates, eight-
axis drift detection, atomic file writes, and the provenance-everywhere principle
represents the most complete reproducibility infrastructure of any Python econometrics
tool the committee is aware of. The foundation is sound and the principles are clear.

### Open-Source Readiness — Needs Improvement

The CONTRIBUTING.md, CODE_OF_CONDUCT.md, and SECURITY.md exist but have not been
updated to reflect the plugin architecture. The README is stale. The `examples/`
directory contains the original paper's outputs, which is appropriate, but there is no
"getting started" example for a new study. The `requests` and `openpyxl` dependencies
required by the network connectors are not listed in `pyproject.toml`. A new contributor
who installs from PyPI and attempts to fetch Penn World Tables data would receive an
unhelpful `ImportError` rather than a clear dependency error.

---

## Risk Assessment

### Risk 1: The Integration Gap Between Pipeline and Registries

**Likelihood:** Certain if unaddressed.  
**Impact:** High. As long as `pipeline_generic.py` imports `linearmodels` directly,
adding a new estimator to the registry has no effect on the primary user-facing workflow.
The plugin architecture for estimation becomes documentation fiction.  
**Mitigation:** Sprint 9 must refactor `run_from_config()` to dispatch through
`estimation.registry`. This is not technically complex; it is a prioritization problem.

---

### Risk 2: README-Induced Abandonment

**Likelihood:** High for any new contributor or evaluating researcher.  
**Impact:** Medium. A README that reports 100 tests against 878 and does not mention
the integrity layer signals that the project is unmaintained or that its documentation
cannot be trusted. First impressions are disproportionately influential for open-source
adoption.  
**Mitigation:** Update the README before the next public announcement. This takes hours,
not sprints.

---

### Risk 3: `load_config()` Remaining Unimplemented

**Likelihood:** High if not explicitly prioritized in Sprint 9.  
**Impact:** Medium-High. The typed `Settings` model exists and is correct, but is never
used. YAML configuration validation is purely structural (does the YAML parse?) rather
than semantic (are the values within valid ranges?). A researcher who uses an invalid
`year_start` value will receive a runtime error deep in the pipeline rather than an
early, clear configuration error.  
**Mitigation:** Implement `load_config()` in Sprint 9. The Pydantic models are already
written.

---

### Risk 4: Connector API Surface Instability Before Plugin SDK Publication

**Likelihood:** Medium.  
**Impact:** Medium. If a third-party author writes a connector plugin against the
current `AbstractConnector` interface and the interface changes (e.g., `citation()` is
made abstract rather than concrete), the plugin breaks silently at import time.  
**Mitigation:** Formalize and freeze the `AbstractConnector` public interface before
advertising the plugin system. Mark the interface as stable in the architecture
documentation with a clear commitment to backward compatibility.

---

### Risk 5: Cumulative Stub Drift

**Likelihood:** Medium.  
**Impact:** Low-Medium. The project currently carries two estimator stubs, two diagnostic
stubs, five figure stubs, and `load_config()`. Each stub is a gap between what the
platform claims to support and what it actually delivers. Stubs are appropriate
temporarily; they become a liability when they accumulate over multiple release cycles.
If GMM and Wooldridge remain stubs through v1.0, they signal that EconFlow does not
complete what it starts.  
**Mitigation:** Establish a formal stub retirement policy: no new stubs may be added
without a committed target sprint for full implementation. Existing stubs must be
retired before v1.0.

---

## Strategic Recommendations

### Recommendation 1: Integrate the Generic Pipeline with the Estimator Registry

**Priority: Highest**

This is the single most important architectural work item outstanding at v0.7. Until
`run_from_config()` dispatches through `estimation.registry`, the platform has two
parallel paths: one that uses the full Sprint 5 architecture (the `BaseEstimator`
subclasses, `EstimationResult`, `DiagnosticResult`) and one that uses the old
linearmodels-direct path (`pipeline_generic.py`). The Sprint 7 integrity checks,
the Sprint 6 table builders, and the Sprint 8 manifest system are all wired to
`EstimationResult`. Until the generic pipeline produces `EstimationResult` objects,
those subsystems are never exercised in the primary workflow.

This is not a new feature. It is completing the integration between features already
built. It should be Sprint 9's first deliverable.

---

### Recommendation 2: Publish a Plugin SDK and Freeze Interfaces

**Priority: High**

EconFlow's differentiation depends on its extensibility. Extensibility only matters to
researchers who believe the plugin interface will remain stable. Until the project
publishes a formal Plugin SDK document — specifying which base classes are stable,
which decorator signatures are committed, and what the backward compatibility policy
is — potential plugin authors have no basis for confidence.

This is a documentation and policy task, not a coding task. It requires deciding what
is stable, writing it down, and committing to it. The answer should be: the six abstract
methods of `AbstractConnector`, the three abstract methods of `BaseEstimator`, the
`run()` method of `BaseDiagnostic`, the `render()` method of `BaseRenderer`, and the
`run()` method of `BaseIntegrityCheck`. These are the stable plugin contracts.

This should precede any public announcement of the plugin system.

---

### Recommendation 3: Implement `load_config()` and Retire the Highest-Priority Stubs

**Priority: High**

The typed `Settings` model in `core/config.py` is correct, complete, and unused.
Implementing `load_config()` — a 30-line function that calls `yaml.safe_load()` and
`Settings.model_validate()` — would make configuration validation semantic rather than
structural, provide meaningful error messages to researchers who supply invalid values,
and close the most visible gap between what the architecture documents describe and
what the code does.

Alongside this, the Wooldridge test and GMM estimator should be implemented in Sprint 9.
These are the stubs most commonly expected in applied panel econometrics; their absence
is the most frequently asked "does EconFlow support X?" question.

---

## Final Verdict

### What Kind of Software Has EconFlow Become?

EconFlow has become a research-infrastructure platform — a middle layer between raw data
sources and published scientific artifacts. It is not an econometrics library; it does
not compete with `linearmodels` or `statsmodels`, which it uses as computational
backends. It is not a statistical computing environment; it does not provide an
interactive interface for data exploration. It is a platform that takes the outputs of
those tools and places them in a reproducibility infrastructure that academic research
requires but almost never has.

The seven sprints of development have produced a system with a consistent plugin
architecture, a genuine provenance chain from data acquisition to replication packaging,
automated integrity checks on estimation results, and a CLI that covers the entire
research workflow. These capabilities, taken together, address a specific and
well-defined problem: the gap between "I have results" and "I can prove I have results
and that they are correct."

### What Differentiates EconFlow from Existing Econometrics Libraries?

The existing Python econometrics libraries — `linearmodels`, `statsmodels`, `pyfixest` —
are computation libraries. They accept data and return model objects. They do not know
where the data came from, what version it was, whether the analysis environment has
changed, or how to package the results for journal submission.

EconFlow's differentiator is not the estimators (which it borrows) but the
infrastructure around them: deterministic caching with SHA-256 verification, schema-
versioned reproducibility certificates, eight-axis drift detection, automated integrity
checks with `pass`/`warn`/`fail` semantics, and a replication packaging system that
produces a journal-ready archive. No existing Python econometrics tool provides any of
this. The closest analogs are workflow management tools (`snakemake`, `dvc`) that are
domain-agnostic; EconFlow makes the same infrastructure decisions in a domain-specific
form that requires no pipeline-authoring knowledge from the researcher.

### What Remains Before Version 1.0?

Three things must happen before a v1.0 designation is appropriate:

First, the generic pipeline must dispatch through the estimator registry, closing the
integration gap that currently makes the plugin architecture partially decorative.

Second, `load_config()` must be implemented, making configuration validation
semantic and making the typed `Settings` model the single authoritative representation
of a project's configuration.

Third, all stubs that represent capabilities advertised to users — GMM, Wooldridge,
the figure builders — must either be implemented or explicitly removed from the
registered set. A v1.0 release that advertises `gmm` in `econflow info` but raises
`NotImplementedError` when invoked is not a v1.0 release.

The documentation — the README, the Plugin SDK, the getting-started guide — must also
be updated to reflect the actual state of the platform, not the state it was in after
Sprint 2.

### What Should the Project Deliberately Avoid Becoming?

EconFlow must avoid becoming a general-purpose econometrics framework. The temptation,
as the plugin system matures and contributors arrive, will be to add Bayesian estimators,
time-series models, machine learning integrations, and interactive dashboards. Each of
these is a legitimate research need, but none of them is the need that EconFlow
addresses. EconFlow's value is its focus: reproducible panel econometrics from data
acquisition to publication. Scope expansion that dilutes this focus will dilute the
quality of the reproducibility infrastructure and make EconFlow compete against tools
that are better positioned in the expanded scope.

More specifically: EconFlow must not become a paper. If any module assumes a particular
research question, a particular dataset, or a particular result interpretation, the
project has returned to its origin. The AI & Productivity example in `examples/` is
the correct location for paper-specific code. The platform itself must remain agnostic
to what any particular study is about.

The advice to the project's founders is: EconFlow is doing something real and doing it
well. The architecture is coherent, the principles are sound, and the reproducibility
infrastructure is genuinely novel in this domain. The remaining work before v1.0 is
integration, not invention. Resist the temptation to add capabilities at the expense of
completing the integration of the capabilities already built. A platform that does eight
things fully is worth far more than a platform that does sixteen things partially.

---

*End of Architectural Milestone Review — EconFlow v0.7*  
*Technical Steering Committee*  
*2026-06-28*
