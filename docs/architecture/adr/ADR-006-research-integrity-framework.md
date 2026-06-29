# ADR-006: Research Integrity Framework

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** —  
**Superseded by:** —

---

## Context

The replication crisis in social science has two distinct root causes. The first is
inadequate documentation: studies that cannot be replicated because the code, data, or
environment is not recorded. EconFlow's provenance-first architecture (ADR-003) and
reproducibility certificate address this cause.

The second root cause is subtler: studies that are technically replicable but whose
results are misleading because of undisclosed researcher-degrees-of-freedom — the
researcher's ability to make many analysis decisions (which observations to exclude,
which controls to include, which estimator to use, when to stop collecting data) and
to report only the combination that produces statistically significant results. This
practice, variously called p-hacking, HARKing (Hypothesizing After Results are Known),
or selective reporting, can produce statistically significant findings from noise.

EconFlow cannot detect intentional misconduct. It can, however, detect specific,
observable statistical signatures that are consistent with selective reporting:
coefficient distributions that are numerically implausible, p-value distributions that
lack the expected characteristics of genuine discoveries, and sample sizes that are
inadequate for the claimed precision. These signatures are not proof of misconduct —
they can arise from legitimate data characteristics — but they are grounds for
heightened scrutiny.

The design question was how to integrate these checks into EconFlow without crossing
the line from "flagging statistical anomalies" to "making scientific judgments."
The checks must be advisory, not corrective. They must report their findings; they must
not modify the analysis. The researcher must remain the decision-maker.

A secondary design question was extensibility. The set of integrity checks that
are useful in panel econometrics will evolve as the research community's understanding
of best practices develops. The framework must allow new checks to be added without
modifying the existing infrastructure.

---

## Decision

We adopt the **`BaseIntegrityCheck` plugin pattern** as the mechanism for research
integrity checking in EconFlow. Integrity checks are registered plugins — `BaseIntegrityCheck`
subclasses decorated with `@register_integrity_check(id)` — that accept an
`EstimationResult` and return an `IntegrityCheckResult` with a status of `pass`,
`warn`, `fail`, or `skip`.

**The `IntegrityCheckResult` status semantics are strictly defined:**
- `pass` — the check ran and found no anomaly.
- `warn` — the check found a condition that merits attention but does not indicate
  a likely problem. The analysis should proceed; the researcher should note the warning.
- `fail` — the check found a condition that is statistically implausible under normal
  research conditions. The researcher must investigate before submission.
- `skip` — the check determined it is not applicable to this estimator or this result
  configuration. This is not a failure.

**Critically: no status causes the pipeline to stop.** `fail` status is recorded in the
`ReproducibilityCertificate` and reported to the researcher, but the pipeline continues.
The decision to act on a `fail` result belongs to the researcher, not to EconFlow.
This is the architectural expression of the principle "transparency before automation"
(Inviolable Principle 3 in MILESTONE_v0.7.md). Automated halting of an analysis based
on integrity check results would transfer scientific judgment to software.

**The three built-in integrity checks are:**

`coefficient_stability` — checks that all estimated coefficients are finite
(not `NaN`, `inf`, or `-inf`) and that no coefficient has an absolute value exceeding
a configurable threshold (default: 1000, which is implausibly large for normalized
economic variables). Rationale: extreme coefficients typically indicate collinearity,
data scaling problems, or numerical instability, not a genuine economic effect of
that magnitude.

`pvalue_distribution` — checks for three patterns in the distribution of p-values
across all estimated coefficients:
1. All p-values below 0.001 (statistical significance is implausibly uniform).
2. All p-values identical (numerical error or data fabrication).
3. Suspiciously right-skewed distribution with no p-values above 0.05 (consistent with
   filing-drawer effects or selective reporting of significant results).
Rationale: genuine discoveries typically produce a mix of significant and
non-significant results. A result set where every coefficient is significant at p<0.001
warrants scrutiny.

`sample_size` — checks that the number of observations meets minimum thresholds for
the claimed analysis: total observations, minimum observations per entity (for
fixed-effects estimators), and minimum time periods per entity. Rationale: claims of
precision from estimates with inadequate sample sizes are misleading, even when
technically computable.

Integrity checks are run automatically by `econflow certify` and their results are
embedded in the `ReproducibilityCertificate`. The `overall_status` of the certificate
is the most severe status across all checks: if any check returns `fail`, the overall
status is `fail`. The certificate is written in either case. A researcher who submits
a replication package with a `fail`-status certificate is not prevented from doing so;
they are providing evidence that the anomaly was detected and considered.

---

## Alternatives Considered

### Alternative 1: Hard Stop on Integrity Failure

A `fail` status causes the pipeline to halt, and the researcher must explicitly
override the halt (e.g., with `--force`) to continue.

**Why not chosen:** This transfers scientific judgment to software. There are legitimate
cases where all p-values are below 0.001 (a genuine discovery in a high-powered study),
where sample size is small (a specialized study of rare events), or where coefficients
are large (economic variables with unusual scales). Requiring researchers to override
an automated halt in these cases is paternalistic and potentially harmful. The correct
response to a suspicious result is investigation, not suppression.

### Alternative 2: Pre-submission Checklist (No Automation)

EconFlow provides a documented checklist of integrity concerns that researchers review
manually before submitting. No automated checks are implemented.

**Why not chosen:** A manual checklist is only useful if it is used. The automation
value of EconFlow is that checks run unconditionally on every certification, covering
the analyses most likely to be submitted under deadline pressure. The checklist approach
relies on researcher discipline in exactly the cases where discipline is most under
pressure.

### Alternative 3: External Validation Library

Integrate with an external research integrity library (e.g., a p-hacking detection
library from the metascience literature).

**Why not chosen:** At the time of design, no stable, well-maintained Python library
for automated research integrity checking in panel econometrics exists. Depending on
an external library for a core platform capability would introduce an uncontrolled
dependency. The three built-in checks are well-defined, implementable in straightforward
statistical code, and cover the most common integrity concerns without requiring
external dependencies. Third-party checks can be added via the plugin system.

### Alternative 4: Statistical Disclosure Limitation (SDC)

Frame the integrity checks as statistical disclosure limitation: automated checks that
prevent potentially misleading results from being published.

**Why not chosen:** SDC as a concept is appropriate for protecting privacy in
administrative data. It is not an appropriate framing for research integrity checks.
Calling these checks "disclosure limitation" would imply that EconFlow is authorized
to limit what researchers may publish, which it is not. The correct framing is
"transparency" — EconFlow reports what it observes; the researcher decides what to do.

---

## Trade-offs

**Accepted costs:**

- The `pvalue_distribution` check has known false positive rates. A study with a
  genuinely strong treatment effect may produce all-significant p-values and trigger
  a `fail` result. Researchers with such results must note and explain the check outcome
  in their replication package. This is an accepted cost: false positives that require
  explanation are preferable to false negatives that allow genuine anomalies to pass
  unreported.

- Running all integrity checks adds time to every `econflow certify` invocation.
  For a large result set with many estimated coefficients, the distribution-based
  checks require iterating over all p-values. This is expected to be negligible
  (milliseconds, not seconds) for any realistic estimation result set.

- The three built-in checks are conservative: their thresholds are set to flag only
  the most statistically implausible results. This is intentional — over-sensitive
  checks that flag legitimate results constantly will be dismissed by researchers and
  will lose their warning value.

**Realized benefits:**

- The `IntegrityCheckResult.message` field provides a human-readable explanation of
  what was checked and why the result has the status it does. A researcher who sees
  a `fail` result can read the message and understand whether the concern is applicable
  to their study.

- The plugin architecture allows domain specialists to contribute new integrity checks
  without modifying EconFlow core. A macroeconomist might contribute a check for
  Granger causality pre-testing; a labor economist might contribute a check for
  balance table anomalies. These checks follow the same registration pattern as
  estimators and renderers.

- The `overall_status` field of `ReproducibilityCertificate` gives journals and
  data repositories a single machine-readable signal: this replication package either
  passed all integrity checks or it did not.

---

## Consequences

**Immediate consequences:**

1. Every new integrity check must be a `BaseIntegrityCheck` subclass that implements
   `run(result: EstimationResult) -> IntegrityCheckResult`. The `run()` method must
   never raise an exception (it must catch internal errors and return `skip` status
   with an appropriate message).

2. The `fail` status must not cause the pipeline to halt, throw an exception, or
   prevent the certificate from being written. Enforcement is by code review.

3. `ReproducibilityCertificate.overall_status` is computed as the maximum severity
   across all check results. The severity ordering is `pass < skip < warn < fail`.
   `skip` is less severe than `warn` because a skipped check provides no information
   about the result; a warning provides diagnostic information.

4. The integrity framework must be documented in the replication package README as a
   disclosure to reviewers. A replication package produced by EconFlow must state
   that automated integrity checks were run and provide the outcome.

**Architectural constraints imposed:**

- Integrity checks may read but not modify `EstimationResult` objects. The `run()`
  method receives the result by reference; any mutation is a programming error.

- Integrity check thresholds must be configurable via the check's constructor parameters.
  Hard-coded thresholds that cannot be adjusted are unacceptable: a researcher with
  legitimate reasons to use a different threshold must be able to specify it.

---

## Future Implications

**ADR-006-F1 (Under consideration):** Pre-analysis plan integration. A future extension
would allow researchers to register a pre-analysis plan — a specification of the
hypotheses and tests they committed to before seeing the data — and have EconFlow
verify that the final analysis matches the plan. This is the gold standard for
addressing researcher-degrees-of-freedom concerns and is within scope for a future
sprint.

**ADR-006-F2 (Planned):** Integrity results in the replication package README.
The replication package README must include a human-readable summary of all integrity
check results (see V1_RELEASE_CRITERIA §7.2). A `fail`-status package must include a
visible warning section in the README.

**ADR-006-F3 (Under consideration):** Multiple-comparisons correction check. A check
that flags analyses where many hypotheses are tested without correction for multiple
comparisons (Bonferroni, Benjamini-Hochberg). This is a common researcher-
degrees-of-freedom concern in studies with many control variables or many specifications.

---

## Cross References

- `src/econflow/integrity/` — package containing all integrity framework code
- `src/econflow/integrity/base.py` — `BaseIntegrityCheck` abstract class
- `src/econflow/integrity/registry.py` — integrity check registry
- `src/econflow/integrity/certificate.py` — `ReproducibilityCertificate`
- `src/econflow/integrity/plugins/` — three built-in integrity check implementations
- `src/econflow/commands/certify_cmd.py` — `econflow certify` CLI command
- `docs/architecture/INTEGRITY_FRAMEWORK.md` — integrity framework architecture document
- `docs/architecture/MILESTONE_v0.7.md` §1.7 — research integrity capability assessment
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §7 — integrity framework release criteria
- ADR-001 — Plugin Registry (registration mechanism for integrity checks)
- ADR-003 — Provenance-First Architecture (certificate as provenance artifact)
