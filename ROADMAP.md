# Roadmap

**EconFlow — Foundational Document**

*This document describes the strategic evolution of EconFlow across its
development stages. It is not a task list or a sprint backlog. It describes
goals, capabilities, and the reasoning behind sequencing decisions. Specific
features, file names, and implementation details belong in sprint planning
documents, not here.*

*Release designations are approximate. They indicate strategic inflection
points rather than calendar commitments. The completion criteria for each
stage should be met before the next stage begins.*

---

## Principles Guiding the Roadmap

The roadmap is sequenced to honour three constraints.

**Foundation before features.** Architectural decisions made early propagate
through the entire codebase. The provenance model, the configuration format,
the registry pattern, and the public API surface must be established before
the framework is used by researchers who will depend on their stability.

**Scientific utility before engineering elegance.** A stage is complete when
it enables researchers to do something they could not do before, not when
the implementation reaches a theoretical ideal. Engineering refinements are
ongoing and do not gate progress.

**Backward compatibility accumulates.** As the public API grows, the cost of
breaking changes increases. Later stages must be designed to fit within the
constraints established by earlier ones.

---

## Completed Stages

### Stage 0 — Foundation

**Goal.** Establish the package structure, core abstractions, and development
infrastructure on which all subsequent work depends.

**Major capability.** EconFlow becomes an installable Python package with a
command-line interface, a configuration loader, a provenance recorder, a
domain exception hierarchy, and a continuous integration setup.

**Why this stage matters.** No feature built on a weak foundation is
trustworthy. The choices made here — the configuration format, the
provenance schema, the exception hierarchy, the test infrastructure — will
constrain or enable everything that follows. Rushing this stage to reach
features faster creates compounding technical debt.

**Completion criteria.** The package installs cleanly from source. The CLI
provides at minimum a health check command. The provenance recorder produces
a machine-readable record of a pipeline run. The test suite covers core
components with greater than 95% statement coverage. CI passes on all
supported Python versions.

---

### Stage 1 — Generic Pipeline

**Goal.** Replace paper-specific pipeline scripts with a configurable,
data-agnostic pipeline that any panel econometrics project can use.

**Major capability.** A researcher can configure a complete empirical workflow
— from data loading through estimation to output — using YAML configuration
files, without modifying framework source code. The pipeline produces
identical outputs given identical inputs.

**Why this stage matters.** The original motivation for EconFlow was a
single research paper's pipeline. For the framework to be useful beyond
that paper, it must generalise. This stage draws the line between
project-specific configuration and general-purpose infrastructure.

**Completion criteria.** The AI and Productivity replication package runs
unmodified through the generic pipeline. At least one additional example
project demonstrates that the pipeline is not specific to that paper. The
configuration schema is documented. Regression tests protect scientific
outputs.

---

### Stage 2 — Research Workspace

**Goal.** Provide project management tooling — initialisation, validation,
health checks, and inspection — that makes EconFlow projects self-describing
and portable.

**Major capability.** The `econflow init`, `validate`, `doctor`, and `info`
commands allow a researcher to set up a new project, verify its configuration,
and inspect its current state from the command line. A project directory
contains everything needed to understand, run, and reproduce the analysis.

**Why this stage matters.** A framework that requires detailed knowledge of
its internals to use is not accessible. Tooling that makes the project
structure explicit — what files exist, what they do, whether the configuration
is valid — reduces the barrier to adoption and makes projects more portable.

**Completion criteria.** A new user can initialise a project, configure it,
and validate the configuration without consulting source code. The info
command accurately reflects the current state of the project. All four
commands have full test coverage.

---

### Stage 3 — Data Ecosystem

**Goal.** Provide a unified interface for acquiring, validating, caching,
and documenting datasets, with provenance integrated from the point of
ingestion.

**Major capability.** Data connectors with a common interface register
themselves through a plugin mechanism. Downloaded data is cached with
integrity verification. Dataset metadata — source, version, download
date, checksum — flows into the provenance record automatically.

**Why this stage matters.** Reproducibility fails most often at data
acquisition. If the data source changes, the version is undocumented,
or the download step is manual and unrepeatable, no amount of
configuration rigour downstream will recover it. This stage makes data
provenance as systematic as estimation provenance.

**Completion criteria.** At least two data connectors are fully
implemented (not stubs). The cache manager correctly detects and rejects
corrupted cached data. Dataset metadata is recorded in the provenance
record. The public API is stable and documented.

---

### Stage 4 — Estimation Framework

**Goal.** Transform the collection of estimation functions into a plugin-
based framework where every estimator is a first-class object with a
stable interface, consistent output structure, and integrated diagnostics.

**Major capability.** Estimators register themselves through `@register()`.
Every estimator exposes `validate()`, `fit()`, and `diagnostics()`. The
`run()` method executes these in sequence and returns an `EstimationResult`
with full provenance. Diagnostic tests are also plugins, registered
independently of estimators.

**Why this stage matters.** The estimation step is the scientific core of
the framework. Its output — the `EstimationResult` — is what researchers
will inspect, report, and defend. Making this output rich, consistent,
and provenance-bearing is the most direct contribution to research
reproducibility. The plugin architecture allows the community to add
estimators and diagnostics without modifying framework code.

**Completion criteria.** The six core estimators (Pooled OLS, Entity FE,
Two-Way FE, Random Effects, First Difference, IV/2SLS) are fully implemented.
The four core diagnostics (Hausman, Breusch-Pagan, Pesaran CD, VIF) are
fully implemented. The `EstimationResult` includes complete provenance. The
public API is stable. The test suite verifies numerical correctness on
synthetic data with known parameters.

---

## Current Development

EconFlow is between Stage 4 (complete) and Stage 5 (next). The estimation
framework is implemented and tested. The reporting engine has not yet been
built.

---

## Upcoming Stages

### Stage 5 — Reporting Engine

**Goal.** Provide a configurable, reproducible pipeline for producing
publication-ready tables and figures from `EstimationResult` objects.

**Major capability.** Tables (LaTeX, CSV, plain text) and figures are
generated from configuration, not assembled by hand. The same configuration
that specifies the estimation also specifies the output format. A change
to an estimation specification automatically propagates to the corresponding
table without manual transcription.

**Why this stage matters.** The path from estimation result to published
table is the most common source of errors in empirical research. Numbers
are transcribed incorrectly, significance stars are applied inconsistently,
and tables are assembled from different model runs than those described in
the text. A reporting engine that reads directly from `EstimationResult`
objects eliminates this class of error.

**What belongs here.** Coefficient tables with standard errors and
significance indicators; comparison tables across multiple specifications;
diagnostic summary tables; coefficient plots; residual diagnostics figures;
LaTeX and plain-text output modes.

**What does not belong here.** Manuscript writing, narrative generation,
or any output that requires human judgement about what to say. The
reporting engine produces formatted data; the researcher interprets it.

**Completion criteria.** A complete paper-style coefficient table is
generated from a list of `EstimationResult` objects with a single
configuration block. Output is identical across runs. LaTeX, CSV, and
plain-text formats are all tested.

---

### Stage 6 — Reproducibility Framework

**Goal.** Provide a complete, verifiable audit trail for the full
computational path from raw data through published output, suitable for
submission as a replication package.

**Major capability.** A completed pipeline run produces a
self-contained archive that records: the configuration, the software
environment, the dataset identifiers and checksums, the estimation
specifications, the output files and their checksums, and the provenance
record linking each output to its inputs. An independent researcher
can use this archive to verify or reproduce the results.

**Why this stage matters.** Stages 0–5 build the components of a
reproducible workflow. Stage 6 integrates them into a product that
can be submitted alongside a published paper. This is the point at
which EconFlow's stated commitment to reproducibility becomes
verifiable by people outside the original research group.

**What belongs here.** Deterministic environment capture (lockfiles,
container specifications); output manifest with checksums; provenance
graph linking raw data to each published output; archive export
functionality; a verification tool that checks an archive against its
manifest.

**Completion criteria.** An EconFlow replication archive can be
independently verified by a researcher who did not run the original
pipeline, using only the archive and the EconFlow framework. At
least one published paper uses this capability.

---

### Stage 7 — AI Research Assistant

**Goal.** Provide opt-in AI-assisted tools that accelerate research tasks
without making scientific decisions. All AI-generated content is labelled,
auditable, and excluded from provenance records by default.

**Major capability.** Integrated tools that can: flag potential
specification concerns (e.g., low instrument relevance in IV, near-
multicollinearity in VIF results), suggest relevant diagnostic tests based
on the estimator used, summarise estimation output in plain language, and
compare results across specifications. All suggestions are advisory; none
alter configuration or results without explicit researcher action.

**Why this stage matters.** AI tools can accelerate the diagnostic and
interpretation phase of empirical research without compromising the
researcher's intellectual ownership of the findings. This stage realises
the principle that AI assists but never decides. It also provides a model
for responsible AI integration in scientific software.

**Design constraints.** AI suggestions must be distinguishable from
framework output. The framework must be fully functional without any AI
integration. AI tools must not require external API access for the
core workflow to succeed. Every AI-assisted action must be logged with
enough detail to be reviewed and, if necessary, overridden.

**Completion criteria.** At least two AI-assisted diagnostic tools are
implemented as optional plugins. Their output is clearly labelled and
does not appear in provenance records unless explicitly included. The
framework's test suite passes without any AI dependency.

---

### Stage 8 — Plugin SDK and Ecosystem

**Goal.** Provide a stable, documented SDK for third-party estimators,
connectors, and diagnostic plugins, along with tooling that makes building
and distributing plugins straightforward.

**Major capability.** An external developer can build an EconFlow plugin
— an estimator, connector, or diagnostic — as a standalone Python package,
distribute it through PyPI, and have it integrate seamlessly with the
framework's CLI, provenance system, and test infrastructure. The core
framework team does not need to review or merge community plugins.

**Why this stage matters.** The long-term health of the framework depends
on a community that can extend it without modifying it. The plugin
architecture established in earlier stages is a necessary condition;
this stage provides the documentation, tooling, and conventions that make
external plugins practical.

**Completion criteria.** The plugin SDK is documented with a complete
example plugin. At least two community-developed plugins exist that were
built without involvement from the core team. A plugin validation tool
checks that a plugin correctly implements the required interface.

---

### Stage 9 — Public Beta

**Goal.** Invite broad use, collect structured feedback, and stabilise
the public API before committing to v1.0 guarantees.

**Major capability.** EconFlow is announced to the research community
through appropriate channels (academic mailing lists, preprint servers,
research group workshops). Feedback is collected systematically through
a structured process. The framework handles real-world use cases that
differ from the development scenarios.

**Why this stage matters.** No design survives contact with users
unmodified. The public beta is the opportunity to discover the
assumptions that were embedded in the design without being stated, the
use cases that were not anticipated, and the documentation gaps that
make the framework inaccessible. Changes during the beta are easier
than changes after v1.0 guarantees are in force.

**Completion criteria.** The public API has been stable for at least
two minor releases. Known breaking changes from the beta have been
resolved. The documentation is complete for all public API components.
At least three research groups outside the original development team
have used the framework for real research.

---

### Stage 10 — Stable v1.0

**Goal.** Commit to long-term stability and establish EconFlow as
reliable research infrastructure.

**Major capability.** The v1.0 release commits the public API to
compatibility guarantees: no breaking changes in 1.x releases without
a deprecation period, a migration guide, and a major version increment.
The framework is documented completely. The architecture is stable.
The community has a clear process for proposing changes.

**Why this stage matters.** Research infrastructure must be trustworthy
over years, not months. A researcher writing a replication package
against EconFlow v1.0 should be confident that it will still run
against EconFlow v1.9 without modification. This commitment is the
foundation on which long-term adoption is built.

**Completion criteria.** A public compatibility policy is documented
and enforced by the release process. The change log is complete from
v0.1.0. The framework has been used in at least one published paper
with a public replication package.

---

## Long-term Directions

*The following directions represent possibilities that the project may
explore after v1.0. They are not commitments. Each would require
significant design work, community input, and resources that are not
currently planned. They are listed to indicate the direction of the
project's ambitions without overstating them.*

**Cloud execution.** A configuration that runs correctly on a local
machine should be executable on a remote compute environment with
minimal changes. This requires a stable execution model, containerisation
support, and a way to manage remote data access that preserves provenance.

**Distributed computation.** Large panels, many specifications, and
intensive sensitivity analyses could benefit from parallel execution
across multiple cores or machines. This must be designed to preserve
determinism — the same results must be produced regardless of how the
computation is distributed.

**Collaborative research.** Research projects are often conducted by
teams. Tooling that helps teams manage configuration, share provenance
records, and merge contributions would make EconFlow more useful for
collaborative work. This is a social and design problem as much as a
technical one.

**Integration with scientific repositories.** EconFlow provenance records
contain structured metadata that could, in principle, be deposited
directly to data archives (e.g., Zenodo, the Inter-university Consortium
for Political and Social Research) and linked to preprints or
journal articles. This would require coordination with repository
operators and the development of appropriate metadata standards.

**Journal integration.** Some journals now require structured replication
packages as a condition of publication. EconFlow replication archives
could, in principle, be designed to meet these requirements automatically.
This requires dialogue with journal editors and data editors.

**Research object publication.** A self-contained research object — data,
configuration, provenance, and outputs in a single archive with machine-
readable metadata — is a more complete unit of scientific communication
than a paper plus a replication package. EconFlow archives could evolve
toward this standard.

**Open science interoperability.** Emerging standards for research
objects, computational notebooks, and linked scholarly communication
(e.g., Executable Research Articles, MyST, Pandoc scholarly formats)
may eventually intersect with EconFlow workflows in ways that are
currently unclear.

None of these directions will be pursued until v1.0 is stable and the
core framework has demonstrated its value to a real user community.
Premature extension into adjacent areas risks diluting the project's
focus before its core mission is complete.

---

## What the Roadmap Does Not Contain

**Dates.** Estimating research software development timelines accurately
is difficult. A roadmap that commits to specific dates creates pressure
to release prematurely or to defer necessary work to meet a schedule.
Stages are complete when their criteria are met, not when a calendar
event occurs.

**Feature lists.** Individual features, API designs, and implementation
approaches are decided in pull requests and design discussions, not in
this document. The roadmap describes what the framework should be capable
of and why, not how it should be built.

**Guarantees about external factors.** The availability of contributors,
the stability of upstream dependencies, changes in the research software
ecosystem, and shifts in community needs are beyond the project's control.
The roadmap is a plan, not a contract.

---

*This roadmap should be revised when a stage is completed, when the
project's strategic direction changes, or when accumulated experience
reveals that the sequencing was wrong. Revisions should be documented
in the git history with enough context to understand why the change was
made.*
