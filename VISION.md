# Vision

**EconFlow — Foundational Document**

*This document describes why EconFlow exists, who it is for, and what it aims
to contribute to empirical economic research. It is a long-term statement of
intent, not a marketing document. It should be revised only when the
fundamental direction of the project changes.*

---

## The Problem

Empirical economics produces knowledge through a sequence of steps: data
acquisition, cleaning, transformation, estimation, diagnostics, and reporting.
In most research workflows today, these steps are executed through a collection
of independent scripts, notebooks, and manual operations held together by
institutional memory and researcher habit.

This arrangement produces several persistent problems.

**Fragmented workflows.** A typical project might acquire data from three
sources using different scripts, clean it in a notebook, estimate models in
another script, and assemble tables manually. There is no central record of
how these pieces connect. Changing one step requires tracing its effects
through the rest by hand.

**Weak provenance.** The computational path from raw data to published
coefficient is rarely documented with enough precision to be reconstructed
by a different person, on a different machine, in a different year. Dataset
versions, software versions, random seeds, and filtering decisions are often
implicit in the code and undiscoverable without running it.

**Poor reproducibility.** Independent replication of published findings
requires not only the original data but the original workflow in its
original computational environment. In practice, replication packages are
frequently incomplete, dependent on undocumented file paths, or reliant on
software that is no longer available.

**Inconsistent documentation.** Assumptions embedded in estimation code —
which entities are excluded, which time periods are used, how missing values
are handled — are rarely documented at the point of the decision. They appear
in footnotes if at all. A reader cannot verify what was done without reading
the full codebase.

**Manual reporting.** Moving results from estimation to published tables
involves manual transcription or one-off scripts that are discarded after the
paper is submitted. This introduces transcription errors and makes the
estimation-to-report path unrepeatable.

**Disconnected tools.** The tools that economists use for data acquisition,
estimation, and reporting were not designed to work together. Combining them
requires glue code that is bespoke to each project and not reused.

None of these problems are new. They are structural features of a research
practice that evolved before reproducibility was treated as a first-class
requirement. The academic incentive structure rewards novel findings more than
reproducible process. The software ecosystem provides powerful tools for
individual steps but not for the workflow as a whole.

---

## Why EconFlow Exists

EconFlow is a Python framework for configurable, reproducible empirical
economic research. It exists because the problems described above are
tractable. They do not require changing academic incentives or research
culture. They require better workflow infrastructure.

EconFlow's contribution is to provide:

**A common workflow structure.** A project in EconFlow is defined by
configuration files that specify data sources, variable definitions, model
specifications, and output targets. The configuration is version-controlled,
human-readable, and independent of the code that executes it.

**Provenance by default.** Every run records its computational context —
software versions, dataset identifiers, configuration state, output hashes —
without requiring the researcher to take any additional action. Provenance is
not an afterthought; it is embedded in the execution path.

**Auditable assumptions.** Variable transformations, sample selections,
estimation specifications, and diagnostic thresholds are declared in
configuration, not hidden in scripts. A reader can verify what was done
without running the code.

**A plugin architecture for estimators and diagnostics.** Econometric
methods are registered components with stable interfaces. Adding an estimator
does not require modifying the framework core. Removing one does not break
other components.

**Reproducible outputs.** The path from configuration to published table
is executed by the framework, not assembled by hand. The same configuration
produces the same outputs in the same order on any compatible system.

EconFlow does not claim to solve the reproducibility problem in empirical
economics. Reproducibility depends on practices, culture, and incentives
that extend far beyond any software tool. What EconFlow does is make
reproducible practice significantly easier than the alternative, so that
researchers who want to practice it do not have to build the infrastructure
themselves.

---

## Long-term Vision

### Five years

Within five years, EconFlow should be a credible tool for research groups
conducting applied panel econometrics. A researcher starting a new project
should be able to adopt EconFlow's workflow without significant friction.
The framework should have a stable, well-documented public API. Its core
abstractions — the project configuration, the estimator interface, the
provenance record, the output pipeline — should have demonstrated stability
across at least two major releases without breaking changes.

The community should be large enough to sustain itself: external contributors
should have added connectors, estimators, and diagnostic plugins without
assistance from the core team. There should be at least one published
research paper that uses EconFlow and makes its replication package publicly
available through the framework.

### Ten years

Within ten years, EconFlow should be part of a broader ecosystem of
open science tools for economics. Replication packages produced with EconFlow
should be self-describing: a reader should be able to reconstruct the full
computational environment and reproduce all results from a single archive.

The framework should integrate with scientific repositories, preprint servers,
and data archives at the level of metadata and provenance, not just file
formats. A graduate student learning empirical methods should encounter
reproducible workflow practice as a standard part of their training, not a
specialised skill.

EconFlow should remain a tool for serious empirical work. It is not a
goal to become the most-used econometrics package in Python, to compete with
Stata or R as a general statistical environment, or to be adopted by
practitioners outside applied economic research. Depth within a defined scope
is preferable to breadth across a wide field.

---

## Who EconFlow Is For

EconFlow is designed for:

**Empirical economists** conducting applied research with panel data, cross-
sectional data, or time series. The primary use case is research that produces
published findings: working papers, journal articles, policy reports.

**Applied researchers** in adjacent fields — political science, sociology,
public health — who use the econometric methods EconFlow supports and who
face the same workflow problems.

**Research groups** that produce multiple papers from related datasets and
benefit from a shared, consistent workflow infrastructure.

**Graduate students** learning empirical methods. EconFlow provides a
structured environment in which good practice — configuration management,
reproducibility, provenance — is the path of least resistance.

**Policy analysts** who need to document their analytical process for audit
or replication by external reviewers.

EconFlow is **not** designed for:

**Statisticians** working with methods outside panel econometrics. EconFlow
is not a general statistical computing environment.

**Machine learning practitioners.** The framework has no machinery for
cross-validation, hyperparameter search, neural networks, or prediction
pipelines. These are different problems requiring different tools.

**Data engineers** building production data pipelines. EconFlow is designed
for research workflows, not operational systems.

**Researchers who do not need reproducibility.** If a project is genuinely
exploratory, one-off, and not intended for publication or replication,
EconFlow's structure may be more overhead than benefit. Simple scripts are
sometimes the right tool.

---

## Scope

### What belongs in EconFlow

- Panel data acquisition, caching, and validation through a unified connector
  interface
- Data harmonisation, transformation, and sample selection with auditable
  configuration
- Panel econometric estimation through a plugin-based estimator registry
- Post-estimation diagnostics as registered plugins
- Sensitivity and robustness analysis
- Provenance recording: dataset versions, software state, output checksums
- Tabular and graphical output generation driven by configuration
- A command-line interface for project management and workflow execution
- A project configuration format that is version-controllable and human-readable
- Documentation, testing infrastructure, and contribution tooling

### What does not belong in EconFlow

- Manuscript writing, word processing, or reference management
- Literature search or bibliographic analysis
- Structural economic modelling (DSGE, CGE, agent-based models)
- Bayesian computation as a primary workflow
- Natural language processing or text analysis as core functionality
- General-purpose AI assistants or chatbots
- Data visualisation for communication rather than diagnosis
- Statistical theory or econometric pedagogy
- Operational data pipelines for production systems
- Any component that requires an active internet connection to function
  correctly (data connectors are optional and fail gracefully offline)

This boundary is not fixed permanently. As the framework matures, the
community will identify adjacent capabilities that belong inside EconFlow.
Changes to scope should be deliberate, documented, and reversible.

---

## Success Criteria

EconFlow's success cannot be measured by software metrics alone. The following
criteria reflect the scientific purpose of the project.

**Scientific replication.** A researcher using only an EconFlow replication
package — the configuration, the data, and the framework — should be able to
reproduce every result in a published paper without contacting the original
authors. When this is possible, the framework has contributed to scientific
reproducibility in practice, not just in principle.

**Workflow adoption.** Research groups conducting applied empirical work should
adopt EconFlow's configuration and provenance conventions because they find
them useful, not because they are required to. Adoption driven by utility is
more durable than adoption driven by mandate.

**Graduate training.** Graduate students in applied economics programs should
encounter EconFlow or workflows modelled on it as part of their training.
Good practice should be taught as a normal part of empirical work, not as an
advanced specialisation.

**Community contributions.** External contributors — researchers, not core
developers — should add estimators, connectors, and diagnostic plugins that
the core team did not design. This demonstrates that the plugin architecture
is accessible and that the project serves needs beyond those of its authors.

**Credible replication packages.** Papers with EconFlow replication packages
should be noticeably easier to replicate than papers with ad hoc replication
packages. This should be verifiable by anyone who attempts it.

**Longevity.** The framework should be maintainable by a small team over a
long period. Code written for EconFlow v0.1 should continue to work without
modification through v1.x releases. A researcher returning to a project
after several years should not find the framework has changed out from under
their work.

EconFlow will be considered successful when researchers choose it not because
it is new or fashionable, but because it makes their work more reliable,
more reproducible, and easier to share.
