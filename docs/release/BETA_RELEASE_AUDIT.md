# EconFlow Beta Release Audit

**Role:** Independent software architect  
**Date:** 2026-07-07  
**Version reviewed:** 0.1.0 (`ef52ea7`)  
**Scope:** Public beta release readiness across 10 dimensions  
**Premise:** I have no prior EconFlow context. I am evaluating this codebase
as an outside architect asked to answer one question: *Is this safe to release
to the public today?*

---

## Executive Summary

EconFlow has a coherent design philosophy, strong internal documentation, and a
well-structured config-driven pipeline. Several subsystems (validation framework,
integrity chain, replication engine) are genuinely production-quality. The
open-source scaffolding is complete and professional.

However, four critical defects prevent public release today. A first-time user
cannot install the package from PyPI, cannot complete the README Quick Start
without hitting an error, cannot produce valid LaTeX output, and cannot use the
`econflow report` command that is advertised as the primary publication
deliverable. These are not quality concerns — they are functional blockers.

**Verdict: Do not release publicly today. Fix the four critical blockers first.**

---

## Severity Legend

| Level    | Definition |
|----------|-----------|
| CRITICAL | Prevents a core user workflow from completing; blocks release |
| HIGH     | Significantly degrades user experience; should block release |
| MEDIUM   | Correctness or quality concern; can ship but should be tracked |
| LOW      | Polish issue; defer to minor release |

---

## 1. Architecture

### Overall Assessment

The architecture is layered and intentional. The config-driven pipeline
(`pipeline_generic.py`, 522 lines) is well-structured, with a clear sequence
of stages: config loading → data loading → estimation → diagnostics → output
rendering → integrity certification. Eight Architecture Decision Records (ADRs)
document the key design choices. The plugin registry pattern (`@register`,
`@register_diagnostic`, `@register_renderer`, `@register_connector`) is
consistent across all four subsystems.

The weakest point is the boundary between the live implementation and a large
body of stub and dead code that coexists in the same tree.

---

### A-1 — Dual Pipeline (HIGH)

**Evidence:**  
Two top-level pipeline entry points coexist:
- `src/econflow/pipeline.py` (274 lines) — legacy AI&P paper-specific pipeline, hardcoded to expect `country`, `ln_ai`, `ln_tfp` columns.
- `src/econflow/pipeline_generic.py` (522 lines) — the production config-driven implementation.

The CLI `econflow run` dispatches to the legacy pipeline when `--data-path` is
passed and to the generic pipeline when `--config` is passed. The README Quick
Start uses `--data-path`.

**Root cause:** The legacy pipeline was never removed after the generic one was
built. The README was not updated to point to the generic path.

**Recommendation:** Delete `pipeline.py` or move it to
`examples/ai_productivity_paper/`. Update the README Quick Start to use
`--config`. This eliminates a footgun that is the proximate cause of
CRITICAL-D1.

---

### A-2 — Exception Hierarchy Fragmentation (HIGH)

**Evidence:**  
Five production exception classes do not inherit from `EconFlowError`:

```python
EstimatorError(Exception)       # estimation/base.py
DiagnosticError(Exception)      # diagnostics/base.py
ConnectorError(Exception)       # ingestion/base.py
CacheCorruptionError(Exception) # ingestion/cache.py
RendererError(Exception)        # outputs/base.py
```

Verification:

```python
issubclass(EstimatorError, EconFlowError)  # False
issubclass(DiagnosticError, EconFlowError) # False
issubclass(ConnectorError, EconFlowError)  # False
issubclass(CacheCorruptionError, EconFlowError) # False
issubclass(RendererError, EconFlowError)   # False
```

A caller who catches `except EconFlowError` will silently miss every exception
raised by estimation, diagnostics, connectors, the cache, and renderers — the
five most operationally active subsystems.

**Root cause:** Each subsystem defined its own exception root independently.
The unification sprint (task #251) fixed the `EconFlowCoreError` hierarchy
but did not propagate the change to the subsystem-level exceptions.

**Recommendation:** Change all five to inherit from `EconFlowError`:
`EstimatorError(EconFlowError)`, etc. This is a one-line change per class.
Add a test: `assert issubclass(X, EconFlowError) for X in [EstimatorError,
DiagnosticError, ConnectorError, CacheCorruptionError, RendererError]`.

---

### A-3 — Unused Abstract Base in `core/pipeline.py` (MEDIUM)

**Evidence:**  
`src/econflow/core/pipeline.py` defines `AbstractPipeline` and `PipelineStage`
with abstract methods. `pipeline_generic.py` does not inherit from
`AbstractPipeline` — it stands alone with no common interface contract.

**Root cause:** The abstraction was written before the generic implementation
and the two drifted apart.

**Recommendation:** Either wire `GenericPipeline` to inherit from
`AbstractPipeline`, or delete `core/pipeline.py`. The latter is faster and
removes dead code without a correctness risk.

---

## 2. API Stability

### Overall Assessment

The public API is in reasonable shape for a 0.1.0 pre-release. `__all__` in
`src/econflow/__init__.py` is curated and correct. `docs/API_STABILITY.md`
exists and describes the stability promise. The CHANGELOG follows Keep a
Changelog format and references Semantic Versioning. Two deprecated aliases
(`AIProdError`, `APRPError`) have explicit version removal targets (0.3.0).

---

### S-1 — Deprecated Alias in `__all__` (MEDIUM)

**Evidence:**  
`AIProdError` is exported in `__all__` and appears in `dir(econflow)`. It is
a paper-specific name from the AI&P predecessor project. A public release
causes this name to become part of the documented surface area, which creates
a backward-compatibility obligation.

```python
# src/econflow/__init__.py
from econflow.exceptions import (
    AIProdError,  # deprecated alias — kept for backward compat until v0.3.0
    ...
)
__all__ = [..., "AIProdError", ...]
```

**Root cause:** The deprecated alias was kept for backward compat with
internal callers. No external users exist yet, so the deprecation commitment
is self-imposed and can be revoked before 0.1.0 ships.

**Recommendation:** Remove `AIProdError` from `__all__` before 0.1.0 goes
public. The alias can stay in `exceptions.py` for a release or two, but
advertising it in `__all__` gives it undeserved stability status.

---

### S-2 — No Python API Docstrings on Key Entry Points (HIGH)

**Evidence:**  
`BaseEstimator.fit()` has no docstring. Calling `get_estimator('fe')().fit(df)`
raises `KeyError: 'dependent'` with no actionable message. The public Python
API (`from econflow.estimation import get_estimator`) is the only path for
programmatic use, but it has no usage documentation.

**Root cause:** Sprint priorities focused on CLI commands and architecture
documentation; programmatic API documentation was deferred.

**Recommendation:** Add minimal docstrings to `BaseEstimator.fit()` and
`BaseEstimator.run()` specifying required `params` keys. Add a one-page
"Python API" section to the README or a `docs/guides/python_api.md` document.

---

## 3. Plugin System

### Overall Assessment

The decorator-based registry is the best-designed subsystem in the codebase.
`@register`, `@register_diagnostic`, `@register_renderer`, and
`@register_connector` are consistent in signature and behaviour. Entry-point
auto-loading for third-party plugins is implemented in `estimation/registry.py`.
The pattern is extensible and well-documented in `docs/sdk/PLUGIN_SDK.md`.

---

### P-1 — Stub Plugins Registered Alongside Working Plugins (HIGH)

**Evidence:**  
`econflow info` shows all registered estimators and diagnostics. Two stubs are
registered in the same lists as working implementations:

Estimators listed by `list_estimators()`:
```
gmm       | System GMM              | linearmodels
quantile  | Panel Quantile Regression | linearmodels
```

Diagnostics listed by `list_diagnostics()`:
```
serial_correlation | Serial Correlation Test
wooldridge         | Wooldridge Autocorrelation Test
```

All four raise `NotImplementedError` at runtime. A user who reads `econflow
info`, sees GMM listed, adds `estimator: gmm` to `models.yaml`, passes
`econflow validate` (the linter does not flag `gmm` as unsupported for
generic config), and runs `econflow run` will receive:

```
NotImplementedError: SystemGMM.fit() is not yet implemented.
```

**Root cause:** Stubs were registered so they appear in the catalogue, but
the validation layer's `SUPPORTED_ESTIMATORS` set was not updated to exclude
them.

**Recommendation:** Either (a) remove stub plugins from the registry entirely
until implemented, or (b) add a pre-run validation check that rejects any
config referencing a stub estimator with a clear message: `"gmm is not yet
implemented. Use: ols, fe, twfe, fd, re, iv."`. Option (a) is safer.

---

### P-2 — Entry-Point Loading Implemented but Untestable (MEDIUM)

**Evidence:**  
`estimation/registry.py` calls `importlib.metadata.entry_points(group="econflow.plugins")`
at import time. However, `pyproject.toml` declares no `[project.entry-points]`
section. There are no tests that exercise the entry-point path.

**Root cause:** The mechanism was written for future third-party plugins but
the existing package does not use it, so it is never exercised.

**Recommendation:** Add a minimal test that registers a dummy entry point and
verifies it loads. If no test is feasible, add a comment marking this path as
integration-only and exclude it from coverage explicitly with `# pragma: no cover`.

---

## 4. Validation Framework

### Overall Assessment

The validation framework is the strongest subsystem in the codebase. The
four-stage pipeline (YAML syntax → Pydantic schema → semantic linting →
cross-file consistency, with optional data-layer verification) is well-designed.
`ConfigValidator` returns `ValidationResult` rather than raising, enabling
rich error reporting. The 13 lint rules (L-01 through L-13) cover meaningful
semantic invariants (e.g., L-11 catches IV with no instruments). Auto-generated
config reference docs (`econflow docs config`) is a standout feature.

No critical issues found.

---

### V-1 — `econflow validate .` Fails (HIGH)

**Evidence:**  
`econflow init my_study` creates the project in `my_study/config/`. Running
`econflow validate .` from the project root fails. Users must know to run
`econflow validate config/`. The CLI help text and README do not make this
clear.

```
econflow validate .
# Error: No config files found in '.'
# Expected: config.yaml, models.yaml, outputs.yaml
```

**Root cause:** `validate` searches for YAML files in the given directory
directly, not recursively. The idiomatic UX would be to search `config/` as a
fallback when no YAML files are found at the root.

**Recommendation:** When no YAML files are found in the provided directory,
check `<dir>/config/` as a fallback before failing. Alternatively, document
the `config/` argument prominently in `econflow init` output.

---

### V-2 — Data Path Resolves Relative to `config/`, Not Project Root (HIGH)

**Evidence:**  
`config.yaml` contains `data.path: data/processed/panel_clean.csv`. This path
resolves relative to the `config/` directory, not the project root. Users who
follow the tutorial and place data at `my_study/data/processed/panel_clean.csv`
receive a file-not-found error. The linter's L-02 data-file-exists check
follows the same incorrect resolution, so validation passes but the run fails.

**Root cause:** The path resolution was not updated when the project layout
moved from flat to `config/`-based.

**Recommendation:** Resolve `data.path` relative to the project root (the
directory containing `config/`). The `ConfigValidator` `_stage_data` already
receives the config file path and can compute the project root from it.

---

## 5. Documentation

### Overall Assessment

Internal/architecture documentation is excellent: 8 ADRs, 15 architecture
documents, a comprehensive Plugin SDK, auto-generated config reference, and
integrity framework documentation. However, user-facing documentation has
multiple failures that affect the most common workflows.

---

### D-1 — README Quick Start Fails (CRITICAL)

**Evidence:**  
The README instructs new users to run:

```bash
econflow run --data-path data/processed/panel_clean.csv
```

This dispatches to the legacy `pipeline.py`, which requires hardcoded columns
`country`, `ln_ai`, `ln_tfp`. Any other dataset produces:

```
RuntimeError: Required columns missing: ['country', 'ln_ai', 'ln_tfp']
```

**Root cause:** The legacy pipeline was never removed. The README was written
for the legacy path and never updated for the generic pipeline.

**Recommendation:** Replace the Quick Start example with the generic path:

```bash
econflow init my_study
cd my_study
econflow validate config/
econflow run --config config/config.yaml \
             --models config/models.yaml \
             --outputs config/outputs.yaml
```

This is a documentation change only — the generic pipeline works correctly.

---

### D-2 — LaTeX Output Broken (CRITICAL)

**Evidence:**  
Significance stars (`*`, `**`, `***`) are corrupted in LaTeX output. The
`_esc()` function in `latex_renderer.py` strips trailing stars, escapes the
coefficient string, and re-appends the stars. However, the upstream
`_fmt_coef()` in `regression.py` wraps stars in superscript notation before
they reach the renderer:

```
0.1145$^{***}$
```

After `_esc()` strips only literal `*` characters from the right, the `$^{`
prefix is passed to `_escape_latex()`, which escapes `{`, `}`, and `^`.
Rendered output:

```
0.1145$^{$^{$^{*}$^{*}$}$^{*}$}
```

**Root cause:** The star-stripping logic in `_esc()` was written assuming bare
`*` characters, not LaTeX math-mode superscript notation. The two functions are
coupled by an undocumented format contract.

**Recommendation:** Either (a) have `_fmt_coef()` return a `(coefficient_str, stars_str)` tuple so the renderer can append stars after escaping, or (b) write `_esc()` to detect and handle the `$^{...}$` pattern explicitly. Add a regression test asserting that `0.1145***` renders as `0.1145$^{***}$` in LaTeX output.

---

### D-3 — `econflow report` Always Produces Zero Tables (CRITICAL)

**Evidence:**  
`src/econflow/commands/report.py` contains this code:

```python
# TODO (Reproducibility sprint): deserialise EstimationResult objects
# and call table / figure builders here before writing the bundle:
#
#   reg_table = build_regression_table(results)
#   bundle.add_table(reg_table)
#   coef_plot = CoefficientPlot().build(results[0])
#   bundle.add_figure(coef_plot)

manifest = bundle.write()
n_tables = len(manifest.get("tables", []))
n_figures = len(manifest.get("figures", []))
console.print(f"  {OK}  Bundle written — {n_tables} table(s), {n_figures} figure(s)")
```

Every invocation prints `0 table(s), 0 figure(s)`. The pipeline (`run`) does
not serialise `EstimationResult` objects to disk, so `report` has nothing to
load. The issue is architectural: there is no persistence layer connecting
`run` to `report`.

**Root cause:** The Reproducibility Sprint implemented the certificate/verify/
package chain but deferred the `run` → `report` serialisation link.

**Recommendation:** This is the highest-effort critical blocker. Either (a)
implement `EstimationResult` serialisation (JSON/pickle) at the end of
`pipeline_generic.py` and deserialisation in `report.py`, or (b) have `report`
accept the results in-process (i.e., call `run` and `report` together in a
single pipeline invocation). Minimum viable fix: serialise as JSON after each
`model.run()` call and load them in `report.py`.

---

### D-4 — No Python API Documentation (HIGH)

**Evidence:**  
There is no `docs/guides/python_api.md` or equivalent. `BaseEstimator.fit()`
has no docstring. The example in `__init__.py`'s module docstring (`pip install
econflow`, `econflow init my_study`, etc.) describes only CLI usage.

**Root cause:** Documentation effort focused on CLI and architecture. The
programmatic API was assumed to be internal-only.

**Recommendation:** Add a minimal "Python API" section to the README showing
the three-line pattern:

```python
from econflow.estimation import get_estimator
est = get_estimator("fe")(params={"dependent": "y", "regressors": ["x1", "x2"], ...})
result = est.run(df)
```

Add docstrings to `BaseEstimator.fit()` and `BaseEstimator.run()` listing the
required `params` keys.

---

## 6. Testing

### Overall Assessment

1,341 tests is a substantial suite. CI runs on Python 3.10, 3.11, and 3.12
on ubuntu-latest. Ruff is enforced in CI. The issue is not the number of
tests — it is what those tests actually cover.

---

### T-1 — Coverage Metric is Misleading (HIGH)

**Evidence:**  
`pyproject.toml` sets `fail_under = 70` and omits from coverage measurement:

```toml
[tool.coverage.run]
omit = [
    "src/econflow/core/*",
    "src/econflow/data/*",
    "src/econflow/diagnostics/*",
    "src/econflow/estimation/*",
    "src/econflow/econometrics/*",
    "src/econflow/features/*",
    "src/econflow/ml/*",
    "src/econflow/processing/*",
    "src/econflow/reporting/*",
    "src/econflow/sensitivity/*",
    "src/econflow/outputs/*",
    "src/econflow/ingestion/base.py",
    "src/econflow/ingestion/cache.py",
    ...
    "src/econflow/pipeline.py",
]
```

The excluded modules represent the majority of production logic: all
estimation code, all diagnostic code, all output rendering, all ingestion
adapters, and all core utilities. The 70% threshold is met by measuring only
the commands layer against itself.

The pyproject.toml comment acknowledges this: `# Dead-code stub packages (all NotImplementedError -- see docs/development/TECHNICAL_DEBT.md)`.

**Root cause:** The exclusion list was created to prevent stubs from tanking
the coverage number. However, it now also excludes the live implementations
(e.g., `estimation/fixed_effects.py` is live but excluded).

**Recommendation:** Remove live implementations from the omit list:
`estimation/fixed_effects.py`, `estimation/ols.py`, `estimation/fd.py`,
`estimation/iv.py`, `estimation/random_effects.py`,
`diagnostics/plugins/hausman.py`, `diagnostics/plugins/breusch_pagan.py`,
`diagnostics/plugins/pesaran_cd.py`, `diagnostics/plugins/vif.py`,
`outputs/renderers/`, `outputs/tables/regression.py`,
`outputs/tables/summary_stats.py`. Keep stubs excluded. Expect the coverage
number to drop; set a realistic `fail_under = 40` and track improvement.

---

### T-2 — No Test Covering the `--data-path` Legacy Path (MEDIUM)

**Evidence:**  
The integration test suite tests the generic pipeline (`--config` path) but
does not test `econflow run --data-path`. This means the README Quick Start
failure (CRITICAL-D1) was never caught by the test suite.

**Recommendation:** Add a test that runs the legacy path against the
`examples/ai_productivity_paper/` fixture and asserts it fails with a clear
error when non-legacy data is provided, or remove the legacy path entirely.

---

### T-3 — CI Only Targets Ubuntu (LOW)

**Evidence:**  
`.github/workflows/ci.yml` runs only on `ubuntu-latest`. The development
environment is Windows (NTFS), where `git.index.lock` bugs and path separator
issues have already been encountered during this project. No macOS runner is
included.

**Recommendation:** Add `windows-latest` and `macos-latest` to the matrix.
This is a single-line change per OS. If wheel builds or path-separator bugs
exist, they will be caught before a user reports them.

---

## 7. Reproducibility

### Overall Assessment

The integrity/reproducibility chain (`certify` → `verify` → `package` →
`reproduce`) is a genuine differentiator for an academic research tool. The
certificate format captures git SHA, environment fingerprint, and config hash.
Drift detection is implemented. Blind replication works end-to-end. The one
critical gap is the `report` command, covered in D-3.

---

### R-1 — `econflow report` Does Not Connect to `econflow run` (CRITICAL)

See D-3 above. The reproducibility certificate proves that a specific run
occurred, but `econflow report` cannot render the outputs from that run
because the results are not persisted. This means the full chain:

```
run → certify → verify → report
```

is broken at the final step. The certificate proves reproducibility of a
computation whose outputs cannot be rendered.

---

### R-2 — `dirty: true` in Certificate Has No User-Facing Explanation (LOW)

**Evidence:**  
When a project has uncommitted changes, the certificate includes `dirty: true`
with no explanation in the terminal output or documentation. A researcher
submitting this certificate to a journal review does not know what `dirty`
means.

**Recommendation:** Add a warning to `econflow certify` output when
`dirty: true`:

```
⚠  Working directory has uncommitted changes.
   Certificate marks results as potentially non-reproducible.
   Run 'git commit -a' before certifying for submission.
```

---

## 8. Packaging

### Overall Assessment

The package structure is clean. `cli_scaffold/` is correctly excluded from the
wheel. `pyproject.toml` is well-formed. Dependencies are pinned with lower
bounds. Python 3.10+ requirement is appropriate.

---

### K-1 — Not Published to PyPI (CRITICAL)

**Evidence:**  
`pip install econflow` fails — the package is not on PyPI. Every installation
instruction in the README requires either `git clone` + `pip install -e .` or
access to a source archive.

**Root cause:** The package has not been uploaded to PyPI. `dist/` artifacts
exist (the wheel was built in a previous sprint), but upload has not occurred.

**Recommendation:** Run `twine upload dist/econflow-0.1.0*.whl` after
resolving the four critical defects. Register the package name on PyPI before
announcing the release.

---

### K-2 — No `[project.entry-points]` for Plugin System (MEDIUM)

**Evidence:**  
The entry-point auto-loading mechanism in `estimation/registry.py` reads from
`group="econflow.plugins"`, but `pyproject.toml` declares no
`[project.entry-points."econflow.plugins"]` section. Third-party plugin authors
cannot use the advertised mechanism.

**Recommendation:** Add a placeholder entry-points section to `pyproject.toml`
with a comment explaining the extension point:

```toml
# [project.entry-points."econflow.plugins"]
# my-plugin = "my_package.estimators"  # example
```

This makes the mechanism discoverable without registering internal estimators
as entry points.

---

## 9. Open-Source Readiness

### Overall Assessment

The repository has a complete open-source scaffolding: MIT LICENSE,
CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md with a response timeline,
bug report and feature request issue templates, PR template, and a CHANGELOG.
Eight ADRs document architectural decisions at a depth unusual for a 0.1.0
project. This dimension has no critical issues.

---

### O-1 — No Windows/macOS in CI (LOW)

See T-3 above. The path-separator and NTFS issues observed during development
suggest Windows coverage in CI would be valuable.

---

### O-2 — No Dependency Security Audit in CI (LOW)

**Evidence:**  
CI runs `pytest` and `ruff check` only. There is no `pip-audit`, `safety`, or
`dependabot` configuration. EconFlow depends on pandas, numpy, linearmodels,
and statsmodels — libraries with occasional CVEs.

**Recommendation:** Add `pip-audit` or enable GitHub Dependabot in
`.github/dependabot.yml`.

---

## 10. Community Readiness

### Overall Assessment

Community infrastructure is nascent but structurally sound. GitHub Discussions
is configured as the support channel (referenced in the issue template config).
A ROADMAP exists. The Plugin SDK documentation enables extension. There are
no external contributors yet — this is a solo academic project.

---

### C-1 — No Announcement Strategy (LOW)

**Evidence:**  
There is no documentation of where the release will be announced (GitHub
release, SSRN, Economics listservs, academic Twitter/Bluesky, etc.). For an
academic tool, the user acquisition path determines whether a community forms.

**Recommendation:** Write a one-page release announcement targeting the primary
academic economics community. Plan a GitHub Release with a curated change
description. Consider a link from the companion paper's replication package.

---

### C-2 — No Changelog for API Consumers (MEDIUM)

**Evidence:**  
`CHANGELOG.md` documents internal sprint work (implementation details, test
counts, sprint milestones). An external API consumer reading it cannot quickly
determine what changed in the public API between releases.

**Recommendation:** Add a `### Public API Changes` section to each release
entry listing only: new CLI commands, changed/removed commands, new Python
API symbols, and removed/renamed symbols. Keep the detailed sprint notes
below it.

---

## Summary of Findings

### Critical Blockers — Release is Gated on These

| ID     | Dimension       | Issue |
|--------|-----------------|-------|
| D-1    | Documentation   | README Quick Start fails — `--data-path` triggers legacy pipeline, errors on any non-AI&P dataset |
| D-2    | Documentation   | LaTeX output corrupted — significance stars rendered as `$^{$^{$^{*}$^{*}$}$^{*}$}` |
| D-3    | Documentation   | `econflow report` always produces 0 tables — TODO stub, no persistence layer connecting `run` to `report` |
| K-1    | Packaging       | Not on PyPI — `pip install econflow` fails |

### High-Severity Issues — Strongly Recommended Before Release

| ID     | Dimension       | Issue |
|--------|-----------------|-------|
| A-2    | Architecture    | Exception hierarchy fragmented — 5 classes don't inherit from `EconFlowError` |
| P-1    | Plugin system   | Stub estimators/diagnostics (GMM, quantile, serial_correlation, wooldridge) registered alongside working ones |
| S-2    | API stability   | No docstrings on `BaseEstimator.fit()` / `.run()`; programmatic API is unusable without trial-and-error |
| T-1    | Testing         | Coverage exclusions make the 70% threshold meaningless — live estimation/diagnostics/output code excluded |
| V-1    | Validation      | `econflow validate .` fails — must use `econflow validate config/` |
| V-2    | Validation      | Data path resolves relative to `config/`, not project root |
| D-4    | Documentation   | No Python API documentation |

### Medium-Severity Issues — Can Ship, Should Track

| ID     | Dimension       | Issue |
|--------|-----------------|-------|
| A-3    | Architecture    | `AbstractPipeline` in `core/pipeline.py` unused by `pipeline_generic.py` |
| S-1    | API stability   | `AIProdError` (paper-specific name) still in `__all__` |
| P-2    | Plugin system   | Entry-point loading implemented but untestable |
| T-2    | Testing         | No test covers the `--data-path` legacy path |
| K-2    | Packaging       | No `[project.entry-points]` section despite Plugin SDK advertising the mechanism |
| C-2    | Community       | CHANGELOG documents internal sprint work, not API changes |

### Low-Severity Issues — Defer to 0.1.1

| ID     | Dimension       | Issue |
|--------|-----------------|-------|
| A-1    | Architecture    | Dual pipeline (`pipeline.py` dead but not removed) |
| T-3    | Testing         | CI targets ubuntu-latest only |
| R-2    | Reproducibility | `dirty: true` in certificate has no user-facing explanation |
| O-1    | Open-source     | No Windows/macOS in CI |
| O-2    | Open-source     | No dependency security audit in CI |
| C-1    | Community       | No release announcement strategy |

---

## Final Verdict

**EconFlow should NOT be released publicly today.**

The four critical blockers (D-1, D-2, D-3, K-1) collectively mean that a
first-time user:

1. Cannot install the package with `pip install econflow`.
2. Cannot complete the README Quick Start without hitting a runtime error.
3. Cannot produce valid LaTeX output for a publication table.
4. Cannot use the `econflow report` command advertised as the primary publication workflow.

These are not edge cases. They are the first four things any user will attempt
after reading the README.

**Minimum viable path to release:**

1. Publish to PyPI (K-1) — 30 minutes.
2. Fix the README Quick Start to use `--config` (D-1) — 15 minutes.
3. Fix the LaTeX star escaping bug (D-2) — 2–4 hours.
4. Implement `EstimationResult` serialisation and connect `run` to `report` (D-3) — 1–2 days.

Items 1, 2, and 3 can be done in a single session. Item 4 is the only
significant implementation task. Once all four are resolved, EconFlow is in
a defensible state for a 0.1.0 public beta. The high-severity issues should
be resolved in a 0.1.1 patch shortly after.

The project's architecture, documentation depth, and reproducibility
infrastructure are genuinely strong for a 0.1.0 release. The gap between
what the system can do internally and what users can discover through the
documented entry points is the only thing standing between this and a
credible public release.
