# Design Principles

**EconFlow — Foundational Document**

*This document records the principles that guide EconFlow's design and
implementation. Every significant design decision should be traceable to one
or more of these principles. When principles conflict, the order of listing
does not determine priority — the conflict should be resolved explicitly in
the relevant design discussion or pull request.*

---

## Principles

### 1. Configuration over hardcoding

Scientific parameters — which variables to use, which entities to include,
which estimator to run, which time period to study — belong in configuration
files, not in source code. When parameters live in code, changing them
requires a code change, a code review, and a commit. When they live in
configuration, they can be versioned, shared, compared across projects, and
audited without touching the framework.

**Practical implication.** EconFlow configuration files (YAML) are the
primary interface for project-specific decisions. The framework code should
not contain literals such as country names, variable names, file paths, or
model specifications. A configuration file is a scientific document. It
should be readable by an economist who does not know Python.

**Example.** Adding a new regressor to a model means editing a YAML file.
It does not mean finding the right place in a Python script.

---

### 2. Explicit over implicit

A researcher reading a configuration file or a provenance record should be
able to determine exactly what the framework did. Implicit behaviour —
default assumptions that activate silently, automatic transformations that
are not recorded, options that change depending on context — undermines
auditability and reproducibility.

**Practical implication.** Default values should be documented and
conservative. When the framework makes a choice on behalf of the researcher,
it should record that choice in the provenance record. Features that require
the researcher to know what is happening "behind the scenes" to use correctly
are design problems.

**Example.** If the framework drops missing observations, it records how
many, from which dataset, and at what stage. The researcher is not expected
to notice this by examining output shapes.

---

### 3. Single source of truth

Each piece of information in the system should have one authoritative
location. Estimator registrations, connector registrations, configuration
schemas, and output specifications should not be duplicated. When duplication
is necessary for backward compatibility, the duplication is explicit and
documented, with a clear path to its eventual elimination.

**Practical implication.** No hard-coded lists of estimator names, connector
names, or supported options that must be manually kept in sync with the
registry. `list_estimators()` is the truth. The YAML configuration schema
is the truth. If a value appears in two places and they can diverge, one of
those places is wrong.

**Example.** Adding a new estimator requires one registration call
(`@register()`). It does not require updating a list in `info.py`, a list
in `validate.py`, and documentation separately.

---

### 4. Deterministic outputs

Given the same configuration and input data, EconFlow should produce
identical outputs. This is not merely a goal; it is a design constraint.
Any component that introduces non-determinism — random number generation
without fixed seeds, ordering that depends on dictionary iteration, parallel
execution without deterministic merge — is a reproducibility defect.

**Practical implication.** Default random seeds are set explicitly.
Collections are sorted before use wherever iteration order affects output.
Output hashes are verified against provenance records. Components that
cannot be made deterministic are documented as such, and their use is opt-in.

**Example.** Running the same pipeline on Monday and Friday on the same
machine should produce byte-identical CSV output files.

---

### 5. Reproducibility by default

Provenance recording is not a feature that must be enabled. It activates
whenever the framework executes a workflow. Researchers who do not think
about provenance still produce a complete provenance record. Researchers
who do think about it can inspect, extend, and publish it.

**Practical implication.** The `ProvenanceRecorder` is part of the default
execution path, not an optional wrapper. Dataset metadata is recorded when
data is ingested. Estimation parameters are recorded when models are fit.
Software versions are recorded at run time. Output hashes are computed before
files are written.

**Example.** A researcher who runs the pipeline without reading the
provenance documentation still produces a `run_metadata.json` file that
could, in principle, support independent replication.

---

### 6. Scientific transparency

EconFlow does not make scientific decisions automatically. Estimation
specifications, sample selection rules, variable transformations, and
diagnostic thresholds are stated explicitly by the researcher in
configuration. The framework executes them faithfully and reports what
it did. It does not attempt to select the best model, optimise
specification, or choose variables on the researcher's behalf.

**Practical implication.** There are no automatic model selection routines,
no stepwise regression, no regularisation defaults that activate silently,
and no recommendations that the framework cannot explain by pointing to
a configuration value. When the framework encounters an ambiguous
situation, it raises an error rather than making a choice.

**Example.** If a variable specified in configuration is absent from the
dataset, the framework fails loudly rather than silently dropping the
variable and proceeding.

---

### 7. Modularity

Each subsystem — ingestion, estimation, diagnostics, outputs, provenance —
should be usable without the others. A researcher who only wants the
estimator registry should be able to import `econflow.estimation` without
importing the data ecosystem. A researcher who only wants the validator
should be able to use it on a dataframe obtained from any source.

**Practical implication.** No circular imports between subsystems. Public
interfaces are stable across minor versions. Subsystems communicate through
shared data structures (`EstimationResult`, `DatasetMetadata`, etc.) rather
than through shared state. Each subsystem is testable in isolation.

**Example.** A user can install EconFlow and use only the estimation
framework with their own data loading code, never touching connectors,
cache, or CLI.

---

### 8. Composable architecture

EconFlow's components should work together through stable, documented
interfaces rather than through shared implementation. The data ecosystem
produces `DatasetMetadata`. The estimation framework consumes
`pd.DataFrame`. The provenance recorder accepts `DatasetMetadata` and
`EstimationResult`. These interfaces are contracts, not implementation
details.

**Practical implication.** Adding a new estimator does not require knowledge
of how connectors work. Adding a new connector does not require knowledge
of how estimators work. A researcher building a custom component should need
to understand only the interfaces relevant to that component.

**Example.** An external package can implement the `BaseEstimator` interface
and register with `@register()` without any other dependency on EconFlow's
internals.

---

### 9. Minimal hidden state

EconFlow components should not maintain mutable global state beyond what is
necessary for their function. The estimator registry and connector registry
are intentional exceptions: their purpose is to maintain a global map of
registered components. All other components should be stateless or carry
their state explicitly.

**Practical implication.** Functions that transform data take data as input
and return data as output. They do not store intermediate results in module-
level variables, modify their arguments, or depend on execution order beyond
what is specified by their call graph. Tests should not need to reset global
state between test cases, except for registry contents.

**Example.** Running two estimators in sequence should produce the same
results regardless of which order they ran, because neither modifies shared
state.

---

### 10. Fail loudly

When EconFlow encounters a condition it cannot handle — a missing column,
a misconfigured parameter, a violated statistical assumption, an unregistered
estimator — it raises a typed, informative exception immediately. It does not
attempt to recover silently, substitute a default, or issue a warning that
the researcher might not see.

**Practical implication.** Every public function validates its inputs before
proceeding. Error messages include the specific value that caused the failure,
the expected values or range, and a reference to the configuration key or
function parameter responsible. Warnings are used only for conditions that
do not prevent correct execution; everything else is an exception.

**Example.** Requesting an unregistered estimator raises
`RegistryError: No estimator registered as 'gls'. Available: ['fe', 'iv',
'ols', 're', 'twfe', ...]` — not a `KeyError` or a silent fallback to a
default estimator.

---

### 11. Backward compatibility

EconFlow's public API is a commitment. A configuration file or Python code
that works with EconFlow v0.5 should work without modification through
EconFlow v0.x releases. Breaking changes require a major version increment,
a migration guide, and a deprecation period. Internal implementation can
change freely; public interfaces cannot.

**Practical implication.** The public API is documented explicitly. Internal
functions are prefixed with `_` and carry no compatibility guarantee.
Deprecations are announced with a version number and a replacement, and the
deprecated path continues to work for at least one minor release cycle.
Re-exports exist to smooth transitions (e.g., `from econflow.estimation.base
import EstimationResult` continues to work even after the class moved).

**Example.** A replication package written against EconFlow v0.3 should
still run against EconFlow v0.9 without any changes to the configuration
files.

---

### 12. Documentation as code

Behaviour is documented at the point of implementation through type
annotations, docstrings, and tests. Architecture is documented in Markdown
files that are kept in version control alongside the code. Documentation
that lives elsewhere — in wikis, slides, or personal notes — will diverge
from the implementation. Documentation in the repository will not.

**Practical implication.** Every public function has a docstring with
parameters, return values, exceptions, and at least one example. Every
public module has a docstring explaining its purpose. Architecture documents
(such as this one) are updated as part of the pull request that changes the
architecture. Stale documentation is treated as a bug.

**Example.** The `ARCHITECTURE.md` file reflects the actual package
structure, not the intended structure from a year ago.

---

### 13. Tests protect science

EconFlow's tests are not merely an engineering quality check. They verify
that the framework produces scientifically correct outputs. A test that checks
whether OLS produces unbiased coefficients on a simulated dataset with known
ground truth is protecting scientific validity. A test that checks whether
the Hausman statistic is computed correctly is protecting a research decision
that may affect published findings.

**Practical implication.** Tests are written at three levels: unit tests that
verify individual functions, integration tests that verify component
interactions, and regression tests that verify end-to-end scientific
outputs. The test suite includes synthetic data with known population
parameters so that numerical correctness can be verified. Tests of
econometric outputs are labelled and explained so that a future maintainer
understands what is being protected.

**Example.** An estimator is not considered implemented until it produces
correct coefficient estimates on a dataset where the true parameters are known.

---

### 14. Stable public APIs

The framework exposes a minimal, deliberately designed public API. Internal
helpers, temporary utilities, and implementation details are not part of the
public API and carry no compatibility guarantees. The public API is small
enough to be documented completely and large enough to cover legitimate use
cases without requiring users to reach into internals.

**Practical implication.** New functionality is added as an internal
implementation first. It becomes part of the public API only after its
interface has been reviewed, documented, and tested. Exposing internals
prematurely creates maintenance burden and user confusion. The `__all__`
lists in each module's `__init__.py` are authoritative.

**Example.** A user who imports only from `econflow.estimation` has access
to everything they need to run estimators. They do not need to know that
`_to_panel()` exists.

---

### 15. AI assists, never decides

EconFlow may incorporate AI-powered tools to accelerate or facilitate research
tasks — flagging potential specification issues, suggesting diagnostic tests,
summarising estimation output, identifying unusual data patterns. These tools
are advisory. Every scientific decision — what to estimate, which results to
report, how to interpret a diagnostic — is made by the researcher.

**Practical implication.** AI-generated suggestions are labelled as
suggestions and do not alter configuration, results, or provenance
automatically. The framework does not select models, choose variables, or
impute data using AI without explicit researcher instruction. An AI-assisted
workflow produces the same provenance record as a manual workflow, with
an additional note recording which AI tool was used and what it suggested.

**Example.** An AI assistant might flag that a Hausman test p-value of 0.04
is close to conventional thresholds and suggest consulting the random effects
result. It does not automatically switch the estimator.

---

## Decision Framework

Before adding a feature, changing an interface, or introducing a new
dependency, a developer should be able to answer the following questions
affirmatively:

**1. Does this improve scientific reproducibility or transparency?**
Features that make it harder to trace the path from data to result, or that
introduce implicit behaviour, are presumptively rejected regardless of
their engineering merit.

**2. Does this generalise beyond one research project?**
EconFlow is not a collection of paper-specific scripts. A feature that is
useful only for the project that motivated it belongs in a project-specific
extension, not in the framework.

**3. Does it increase long-term maintainability?**
Code that is complex, poorly documented, or tightly coupled to specific
library versions is a maintenance liability. Prefer simplicity over
cleverness.

**4. Does it introduce hidden assumptions?**
Features that work correctly only under assumptions that are not stated
explicitly — balanced panels, monotonic time indices, specific data types —
must document those assumptions or enforce them with clear errors.

**5. Can it be tested for correctness, not just for function?**
A feature that can be tested only for whether it runs, not for whether it
produces the right answer, is a scientific risk. Prefer features whose
correct output can be verified against a known standard.

**6. Can it be documented completely in a docstring?**
If the behaviour of a function cannot be described clearly in a docstring,
the function probably does too much or makes too many implicit assumptions.

**7. Would another applied economist understand it?**
The primary users of EconFlow are not software engineers. A feature that
requires deep knowledge of the framework's internals to use correctly has
failed this test. Configuration interfaces, error messages, and documentation
should be written for an economist, not a programmer.

**8. Does it respect the defined scope?**
Features that expand scope — into manuscript writing, machine learning,
general data science — require explicit scope review and consensus, not
just implementation.

**9. Does it break existing workflows?**
If a change breaks a configuration file that worked before, it is a breaking
change and must be handled accordingly: deprecation period, migration guide,
major version increment.

**10. Is the benefit proportional to the complexity?**
Small features with large implementation complexity should be questioned.
The framework should remain maintainable by a small team. Complexity that
cannot be justified by clear, documented benefit is debt.

---

*These principles are not a checklist to be completed. They are a frame for
reasoning. When a design decision is difficult, the question is which
principle is most relevant and what it implies — not whether all ten
questions have been answered.*
