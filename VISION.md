# Vision

**EconFlow — Foundational Document**

*This document is the long-term philosophical statement of the project.
It is not a feature list, a marketing document, or a product roadmap.
It should be revised only when the project's fundamental beliefs change.
When architectural decisions are contested, this document is consulted first.*

*Written by the founders. Intended to remain relevant in ten years.*

---

## The Problem We Were Handed

Empirical economics has a methodology problem it does not acknowledge as one.

Economists hold statistical inference to exacting standards. Identification
strategies are scrutinised. Standard errors are clustered with care.
Specification choices are justified in footnotes that span pages. The
intellectual apparatus of causal inference — potential outcomes, exclusion
restrictions, parallel trends — is applied with rigour developed over decades.

And then the results are moved into a table by hand.

The computational path from raw data to published coefficient is, in most
published work, opaque. Not fraudulently opaque — the opacity is structural.
It is the accumulated consequence of workflows that evolved before
reproducibility was considered a first-class scientific requirement.
Scripts are the unit of research. Notebooks are assembled ad hoc.
Data transformations live in memory and are never recorded. Statistical
assumptions are encoded in configuration variables whose names appear only
in the code that reads them.

A reader of a published paper can evaluate the statistical theory.
She cannot, in general, verify the computation. She cannot know whether the
"balanced panel of 43 countries, 1990–2018" was assembled by the code
she is reading or by a prior cleanup script that was discarded. She cannot
know whether the standard errors would change if she ran the same code
on a machine with a different version of the estimation library. She cannot
know, without contacting the authors, whether the replication package is
complete.

This is the problem EconFlow exists to address. Not to solve — software
alone cannot solve a problem whose roots are cultural and incentive-driven.
But to make reproducible practice easier than its absence, so that
researchers who want to practice it do not have to build the infrastructure
themselves.

---

## What We Believe

**Reproducibility is not a feature. It is a property of the execution model.**

A framework that treats provenance recording as an optional module has
misunderstood the problem. Provenance must be embedded in the execution
path — produced automatically, every time, whether or not the researcher
thinks about it. A researcher who never reads the provenance documentation
should still produce a complete provenance record.

**The computational path is part of the methodology.**

When a paper reports its identification strategy, it reports its methodology.
When it omits the computational path from raw data to published result,
it omits part of its methodology. EconFlow is built on the belief that this
omission is correctable — not through culture change, but through workflow
infrastructure that records the path automatically.

**Configuration is a scientific document.**

A YAML file that specifies which variables enter a model, which entities are
excluded, and which time periods are analysed is a statement of methodology.
It should be version-controlled, peer-reviewable, and human-readable by an
economist who does not know Python. Code that embeds these decisions as
literals is a methodology that can only be audited by reading the code.

**The framework does not make scientific decisions.**

What to estimate. Which results to report. Whether to reject a null
hypothesis. These are decisions made by the researcher. EconFlow executes
them faithfully and records what it did. It does not select models, optimise
specifications, or suggest interpretations. Scientific authority belongs to
the researcher, not to the framework or to anything the framework might embed.

**An open ecosystem is a scientific requirement, not an engineering preference.**

Commercial software creates access inequality. A graduate student at a
well-funded institution uses the same tools as a researcher at a university
with no site licence. An open-source, openly documented framework is not just
a technical choice — it is a commitment to the principle that the ability to
do credible empirical work should not depend on institutional wealth.

**Simple, explicit, and correct. In that order.**

A framework that is sophisticated but opaque does not serve empirical economics.
A framework that is fast but non-deterministic does not serve empirical economics.
A framework that is ergonomic but makes hidden assumptions does not serve
empirical economics. When these values conflict, simplicity and correctness
outrank sophistication and ergonomics. An economist who can understand what the
framework did is better served than one who can do it faster but cannot explain
how.

**Failures should be loud and precise.**

A workflow that completes silently despite a misconfiguration has done the
researcher a disservice. She will discover the error when she reads the output
or when a reviewer asks. EconFlow fails immediately, with an error that names
the specific value that caused the failure, the expected value, and where it
was set. Warnings are for conditions that do not affect correctness. Everything
else is an exception.

**Stability is a feature with scientific stakes.**

A replication package written today should run without modification five years
from now. This is not merely an engineering standard — it is a scientific
requirement. Replication across time is as important as replication across
machines. When EconFlow breaks backward compatibility, it breaks replication
packages, and the researchers who cannot replicate their own published results
are not the ones who will report this. Stability is maintained conservatively,
with deprecation periods, migration guides, and explicit version commitments.

---

## What Distinguishes EconFlow

The landscape of econometric software is rich. EconFlow exists within it, not
instead of it. Understanding what it does differently requires understanding
what the existing tools do — and what they do not.

### statsmodels and linearmodels

Both are excellent libraries for statistical and panel econometric estimation.
Neither treats the research workflow as its concern. They accept a DataFrame
and return results. How the DataFrame was assembled, which entities were
excluded, what version of the source data was used, and where the results go
afterward are explicitly out of scope.

This is not a flaw. It is a design decision appropriate to general-purpose
libraries. But it means that reproducibility — the gap between "running code"
and "reproducible science" — is left for the researcher to bridge. Most do
not bridge it, not because they do not care, but because building the bridge
on each project is expensive and not rewarded.

EconFlow is built around `linearmodels` and `statsmodels`. It uses them for
what they are excellent at and adds the workflow layer they deliberately omit.

### pyfixest

`pyfixest` is fast, elegant, and increasingly the tool of choice for
high-dimensional fixed-effects estimation in Python. It is designed for
exploratory analysis at the REPL. The researcher imports it, passes a formula
and a DataFrame, and has results in milliseconds.

EconFlow is not designed for exploratory analysis. It is designed for the
transition from exploration to the reproducible pipeline — the point where
"I found something interesting" becomes "I need to be able to replicate this
result in two years." These are different problems. Both deserve good tools.

### Stata

Stata do-files are reproducible pipelines. In this sense, Stata understands
the problem better than most of its Python counterparts. A do-file specifies
the full sequence of operations; running it reproduces the results.

EconFlow admires this. It does not admire the closed ecosystem, the commercial
licence, the platform-specific binary format for datasets, or the limited
interoperability with the broader scientific Python stack. And Stata's
reproducibility is reproducibility within Stata's world — it does not extend
to the data acquisition layer, does not produce machine-readable provenance,
and does not compose with version control in a way that makes the full
computational path auditable.

### R

The R ecosystem — `fixest`, `plm`, `lme4`, the tidyverse — represents the
closest intellectual ancestor to what EconFlow is trying to do. `fixest` in
particular is faster and richer in estimation methods than anything currently
in EconFlow's estimator registry. The tidyverse pipeline (`|>`) is a genuine
contribution to the idea that data transformations should be composable and
auditable.

EconFlow's distinction from R is not superiority of estimation. It is the
addition of a structured configuration layer, a provenance record, a plugin
architecture that allows the framework to be extended without forking, and an
integrity certification step that makes reproducibility a verifiable property
of a run rather than an aspiration.

EconFlow also operates in Python, which is where the data ecosystem — pandas,
xarray, dask, the scientific stack — increasingly lives. This is not a
statement that Python is better than R. It is a statement that researchers
who already work in Python should not have to leave it to get workflow
infrastructure.

---

## What EconFlow Will Never Become

These boundaries are deliberate. They are not limitations to be overcome
in a future version. They are properties that define the project's identity.
Crossing them would require a new project, not a new version.

**EconFlow will never make scientific decisions.**

The framework will not select the best model, choose among specification
alternatives, or recommend whether to report a result. These are scientific
judgments that belong to the researcher. Tools that automate scientific
judgment create the appearance of rigour without its substance. We do not
build those tools.

**EconFlow will never be a general statistical computing environment.**

It is not statsmodels. It is not R. It is not a competitor to scipy. It is
a workflow framework for applied empirical economics, and the moment it
tries to be everything, it becomes nothing. Features that expand scope
beyond this boundary require explicit consensus and a documented reason.

**EconFlow will never be a machine learning framework.**

Cross-validation, hyperparameter search, prediction pipelines, neural
networks, and ensemble methods serve different purposes than causal inference
from observational panel data. They can live alongside EconFlow. They do
not live inside it.

**EconFlow will never be a Jupyter notebook.**

Notebooks are excellent for exploration. They are poor units of reproducible
research. A notebook's execution is ordered by the researcher's history, not
by a declared dependency graph. EconFlow's configuration-driven pipeline is
a deliberate alternative. We will build good notebook integrations. We will
not absorb the notebook as our primary interface.

**EconFlow will never prioritise performance over correctness or clarity.**

If there is a trade-off between a fast implementation that requires careful
use and a slower implementation that always does the right thing, we choose
the slower one. Estimation is not a hot path. The time a researcher spends
waiting for results is small compared to the time spent interpreting them.
Correct and clear results delivered slowly are more valuable than fast results
delivered with hidden caveats.

**EconFlow will never make reproducibility optional.**

Provenance recording is not a flag. Integrity checking is not a feature to
be enabled. The moment reproducibility becomes a configuration choice,
researchers will configure it away under deadline pressure. The framework
protects the researcher from herself by making the reproducible path the
only path.

---

## How We Think About AI

Artificial intelligence is already part of research practice. It will become
more so. EconFlow must have a considered position.

Our position: AI assists. The researcher decides.

Concretely, this means several things.

AI tools integrated into EconFlow may flag potential specification problems,
suggest additional diagnostic tests, identify unusual data patterns, or
summarise estimation output. These are accelerants. They reduce the cost of
good practice. They do not substitute for it.

AI tools integrated into EconFlow do not modify configuration, alter
provenance records, or change what the framework reports without explicit
researcher instruction. A suggestion that is acted upon becomes a decision —
and decisions are made by researchers.

When AI is used in a workflow, the provenance record says so. It records
which tool was consulted, what it suggested, and what the researcher did
with the suggestion. AI-assisted and manual workflows produce equivalent
provenance records with an additional AI provenance field.

We are sceptical of "AI-first" research workflows in which the researcher
is a supervisor rather than a practitioner. Not because the outputs are
necessarily wrong, but because the accountability is obscured. When a
model fails to replicate, or a coefficient is questioned, the researcher
who understands every step of her own workflow can defend it. The researcher
who delegated to an AI cannot.

Over the long term, AI will likely become better at econometric inference
than individual researchers are. This does not change our position. The
question is not whether AI can produce correct estimates — it may well —
but whether the research enterprise as a whole benefits from workflows in
which scientific judgment is atomised and distributed across opaque models
that cannot be interrogated. We believe it does not.

EconFlow's AI stance in one sentence: use AI to make researchers faster at
doing their job, not to change whose job it is.

---

## Reproducibility as Architecture

The deepest design commitment in EconFlow is that reproducibility is not
a module. It is a property of the execution model.

This distinction matters. A module can be skipped. A property of the
execution model cannot be skipped without changing the execution model.

**In practice this means:**

Every public function that transforms data records what it did. Not in a
log that can be disabled — in a data structure that is returned alongside
the result and becomes part of the provenance record automatically.

Configuration is the authoritative source of all scientific parameters.
Code that contains literals representing country names, variable definitions,
model specifications, or sample selection criteria is a bug. These belong
in the configuration file, where they can be versioned, compared, and
audited without reading code.

Output files are not the product of a run. Verified, hash-confirmed output
files accompanied by a complete provenance record are the product of a run.
An output file without a provenance record is unverifiable. We do not produce
unverifiable outputs by default.

The integrity check is not an audit step that runs after the research is
done. It runs as part of the pipeline. A result that has not been integrity-
checked is a result that has not been completed.

Non-determinism is a reproducibility defect. Any component that produces
different outputs given identical inputs — due to random seeds, iteration
order over hash maps, floating-point accumulation order in parallel execution
— is treated as a bug, not a feature. Where non-determinism cannot be
eliminated, it is documented as a known deviation and its effect on outputs
is bounded.

**The architectural implication:**

When a new feature is proposed, the first question is not "does this make
the framework more powerful?" It is "does this make results more or less
reproducible?" Features that add capability at the cost of reproducibility
are not additions — they are regressions.

---

## The Decade Ahead

In five years, EconFlow should be a credible infrastructure choice for
research groups conducting applied empirical work. Its plugin architecture
should be populated by estimators and connectors written by researchers
who are not its core developers. Its provenance records should be accepted
by journals and data repositories as sufficient documentation of computational
methodology. A paper with an EconFlow replication package should be
meaningfully easier to replicate than one without.

In ten years, the goal is more ambitious and less certain.

We believe that the way empirical research is documented will change. Not
because journals will mandate it, though some may, but because the tools
to do it correctly will have become the path of least resistance. EconFlow
wants to be part of that infrastructure — the layer between the researcher's
scientific judgment and the published record that ensures the connection
between them is complete, auditable, and reproducible.

We do not expect EconFlow to be the only such framework. We expect it to
be one of several, each optimised for different research communities. We
hope the ideas it embeds — configuration-first workflows, automatic provenance,
plugin-based extensibility, integrity certification — become common enough
that they need not be explained to newcomers.

We will consider the project successful when a graduate student starting a
new panel econometrics project reaches for a workflow framework as naturally
as she reaches for an estimator library — when the infrastructure of
reproducibility is assumed, not heroically constructed.

We will consider the project finished when that infrastructure is so embedded
in research practice that EconFlow can be replaced by its successors without
loss. Tools should outlive their implementations.

---

## What This Document Is Not

This is not a roadmap. Specific milestones, release criteria, and sprints
are documented elsewhere.

This is not a design specification. Technical choices are documented in
Architecture Decision Records, which are binding on the code but temporary.
This document is not.

This is not a promise. It is a statement of intent, as clear and honest as
we can make it about what we are building and why. We may be wrong about
some of it. Where we are wrong, we will say so and revise.

This is not a contribution guide. CONTRIBUTING.md documents how to
participate in the project.

This is the answer to the question: *If you had to explain why EconFlow exists
to a skeptical colleague who already uses Stata and sees no reason to change,
what would you say?*

We would say: EconFlow exists because the methodology of empirical economics
is incomplete without a reproducible record of its computation, and no existing
tool makes producing that record as easy as not producing it. We are trying
to close that gap.

---

*This document supersedes the previous VISION.md dated prior to 2026-06-29.
The founding intent has not changed; this version states it with more
precision.*
