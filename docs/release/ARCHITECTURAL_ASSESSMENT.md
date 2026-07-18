# EconFlow — Independent Architectural Assessment

**Scope:** `Desktop/econflow/` as a standalone repository  
**Assessment date:** 2026-07-10  
**Reviewer role:** Independent software architect, release engineer, and research software reviewer  
**Methodology:** Static analysis from first principles. No assumptions from prior development sessions. All evidence cited directly from source files.

---

## Preamble

This assessment treats the EconFlow repository as if it were encountered for the first time by an external reviewer who has cloned it, read the documentation, and audited the source tree. It evaluates internal consistency, architectural soundness, packaging correctness, and readiness for public beta. No code has been modified; this is an assessment only.

---

## Part I — Findings by Severity

### CRITICAL

---

#### C-1: Pipeline Bypasses the Estimation Framework Entirely

**Evidence.** `src/econflow/pipeline_generic.py` is the module invoked by `econflow run` for all standard pipeline executions. It contains:

```python
from linearmodels.panel import PanelOLS, PooledOLS
```

It does not import `econflow.estimation` anywhere. The module's `_run_models()` function dispatches on a raw string: `if estimator_type == "OLS": ... elif estimator_type == "FE": ...`. Any model type other than those two falls through to a logged warning or silent skip.

`src/econflow/estimation/` is a complete plugin framework: `BaseEstimator` ABC, `EstimatorProtocol`, 8 registered estimators (pooled OLS, entity FE, two-way FE, random effects, first differences, IV, system GMM, panel quantile), a `@register_estimator()` decorator, and an `EstimationResult` dataclass. None of this code is reached during a standard pipeline run.

**Root cause.** The `estimation/` subsystem was developed as a plugin framework but was never integrated as the dispatch layer for `pipeline_generic.py`. The pipeline predates or grew in parallel with the framework, and the wiring step was never completed.

**Architectural impact.** This is the most fundamental gap in the repository. The README advertises "FE, two-way FE, RE, IV estimators via linearmodels," and the package-level exports present 8 estimators as first-class citizens. In reality, the production execution path supports only two (OLS and FE). The entire `estimation/` subpackage — its registry, its ABC, its protocol, its plugin extension point — is dead code at runtime. A user who writes `estimator: twfe` in their models.yaml will not get two-way fixed effects from the registered `TwoWayFE` class; they will get either a pipeline error or fallthrough behavior.

**Recommended solution.** Replace `pipeline_generic.py`'s inline linearmodels dispatch with a call through the estimation registry. Specifically: look up the registered estimator class by the string key from config, instantiate it, call `estimator.run(data, spec)`, and consume the `EstimationResult`. This is the integration the framework was designed for. The inline `PanelOLS`/`PooledOLS` calls and the custom `_run_diagnostics()` should be removed once the `estimation/` and `diagnostics/` frameworks absorb their roles.

---

#### C-2: Coverage Configuration Excludes All Production Subpackages

**Evidence.** `pyproject.toml`, `[tool.coverage.run]`:

```toml
omit = [
    "src/econflow/core/*",
    "src/econflow/data/*",
    "src/econflow/diagnostics/*",
    "src/econflow/estimation/*",
    "src/econflow/outputs/*",
    "src/econflow/ingestion/base.py",
    ...
]
```

An inline comment labels these "Dead-code stub packages." They are not dead code — they are the primary production subsystems: the estimation framework, diagnostics plugins, output renderers, data connectors. The `[tool.coverage.report]` section sets `fail_under = 70`, but this threshold applies only to the slice of code not omitted.

**Root cause.** The omit list was written when these subpackages were stubs. As they were implemented across subsequent sprints, the omit list was never updated.

**Architectural impact.** The coverage badge and CI gate give a false picture of test completeness. The actual test coverage of production code is unknown and could be near zero for the `estimation/`, `diagnostics/`, `outputs/`, and `ingestion/` subsystems.

**Recommended solution.** Remove all production subpackages from the `omit` list. Expect the reported coverage to drop significantly initially. Address coverage gaps before any public release.

---

#### C-3: ARCHITECTURE.md Is Materially Stale and Actively Misleading

**Evidence.** `ARCHITECTURE.md` describes the package structure as containing modules including `cli_scaffold/` ("Future multi-command CLI — Sprint 6"), `visualization/`, `reporting/`, `sensitivity/`, `features/`, and `econometrics/`. None of these paths exist in `src/econflow/`. The document makes no mention of `ingestion/`, `diagnostics/`, `replication/`, `integrity/`, `commands/`, or `core/` — all of which exist in production code.

**Root cause.** The document was last updated early in development and was not maintained as new subpackages were added.

**Architectural impact.** A contributor reading `ARCHITECTURE.md` would form a completely incorrect mental model of the package. The document is worse than absent: it is confidently wrong.

**Recommended solution.** Rewrite `ARCHITECTURE.md` to reflect the actual `src/econflow/` tree. Reference the ADR documents in `docs/architecture/adr/` which contain accurate design decisions.

---

#### C-4: Two Publicly Exported Estimators Raise `NotImplementedError` at Runtime

**Evidence.** `src/econflow/estimation/gmm.py`:

```python
class SystemGMM(BaseEstimator):
    def fit(self, data, spec):
        raise NotImplementedError("SystemGMM is a stub — planned for v1.0")
```

`src/econflow/estimation/quantile.py`:

```python
class PanelQuantile(BaseEstimator):
    def fit(self, data, spec):
        raise NotImplementedError("PanelQuantile is a stub — planned for v1.0")
```

Both are registered under keys `"gmm"` and `"quantile"`, exported from `estimation/__init__.py`, included in `KNOWN_ESTIMATORS` in `config/models.py`, and would therefore pass `econflow validate`. A user who specifies either estimator in their models.yaml will pass configuration validation, reach the estimation step, and crash at runtime.

Note: Due to C-1, these estimators are not reached by the current `pipeline_generic.py` anyway (which only handles OLS/FE). However, once C-1 is fixed and the pipeline is wired to the registry, C-4 would become an active user-facing crash.

**Root cause.** Stubs were registered and exported in anticipation of future implementation but were not hidden from the public API or from config validation.

**Recommended solution.** Either (a) remove stub estimators from the registry and from `KNOWN_ESTIMATORS` until they are implemented, or (b) add a `status` field check in the config validator so that `econflow validate` emits a warning when a stub estimator is referenced, and the pipeline refuses to run rather than crashing.

---

#### C-5: `requests` Not Declared as a Dependency

**Evidence.** `src/econflow/ingestion/connectors/fred.py` uses `import requests`. `src/econflow/ingestion/connectors/worldbank.py` also uses `requests`. The `pyproject.toml` `[project] dependencies` list does not include `requests`.

**Root cause.** The `requests` library was available in the development environment (likely installed as a transitive dependency of another tool), so the missing declaration was not caught.

**Architectural impact.** A clean `pip install -e ".[dev]"` from a fresh environment, followed by `econflow fetch --connector fred`, would raise `ModuleNotFoundError: No module named 'requests'`. Data ingestion via FRED and World Bank connectors is silently broken for clean installs.

**Recommended solution.** Add `"requests>=2.28"` to `[project] dependencies` in `pyproject.toml`.

---

### HIGH

---

#### H-1: Diagnostics Framework Bypassed by Pipeline

**Evidence.** `pipeline_generic.py` implements `_run_diagnostics()` with its own VIF calculation (via `statsmodels.stats.outliers_influence`), Breusch-Pagan test, and Durbin-Watson serial correlation test. None of these call into `econflow.diagnostics.*`.

`src/econflow/diagnostics/` contains a plugin-registered framework with Hausman, Breusch-Pagan, Pesaran CD, VIF, and AR(1) implementations, each behind a `@register_diagnostic()` decorator. Users who extend the diagnostics framework will find their extensions silently ignored by `econflow run`.

This is the diagnostics analogue of C-1. Root cause and resolution are the same: the framework was built but not wired into the pipeline.

---

#### H-2: `AIProdError` Exported in Public `__all__`

**Evidence.** `src/econflow/__init__.py`:

```python
__all__ = [
    ...
    "AIProdError",  # deprecated — removed v0.3.0
    ...
]
```

`AIProdError` is a deprecated alias for `EconFlowError` with a paper-specific name ("AI Productivity Research Platform"). It appears in `__all__`, so it surfaces in IDE autocomplete, `help(econflow)`, and auto-generated API documentation for every user.

**Recommended solution.** Remove `AIProdError` from `__all__`. Keep it importable (for backward compatibility) but hidden from the public namespace.

---

#### H-3: `KNOWN_ESTIMATORS` Frozenset Is Decoupled from the Live Registry

**Evidence.** `src/econflow/config/models.py` defines:

```python
KNOWN_ESTIMATORS: frozenset[str] = frozenset({"ols", "fe", "twfe", "re", "fd", "iv", "gmm", "quantile"})
```

This is a hardcoded list used by the Pydantic config validator. It has no connection to the live plugin registry in `estimation/`. If a user registers a custom estimator with `@register_estimator("myestimator")`, `econflow validate` will reject their config with "unknown estimator: myestimator."

This defeats the plugin architecture's primary value proposition: allowing users to drop in custom estimators without modifying platform code.

**Recommended solution.** Change the config validator to consult the live registry (`get_registered_estimators()`) rather than a static frozenset. Mark stub estimators as excluded from validation using their existing `status` field.

---

#### H-4: `__author__` Truncated to `"Ab"`

**Evidence.** `src/econflow/__init__.py`:

```python
__author__ = "Ab"
```

The correct value, as used in the BibTeX citation block in README.md, is `"Abrha Megos Meressa"`. The truncated value will appear in wheel METADATA, PyPI package metadata, and any tooling that reads the author field.

---

#### H-5: README CLI Reference Missing the `docs` Command

**Evidence.** The README CLI Reference section lists 16 commands. `src/econflow/cli.py` registers 17, including `econflow docs`. The `docs` command is the primary in-tool help mechanism but is absent from the first thing a new user reads.

---

#### H-6: `MIGRATION_CHECKLIST.md` at Repository Root

**Evidence.** `MIGRATION_CHECKLIST.md` exists at the repo root. A copy also exists at `docs/development/MIGRATION_CHECKLIST.md`. The root copy is a development process artifact with no value to external users or contributors.

**Recommended solution.** Remove `MIGRATION_CHECKLIST.md` from the repo root. The `docs/development/` copy suffices.

---

#### H-7: No `py.typed` Marker

There is no `py.typed` marker file in `src/econflow/`. Without it, `mypy` and `pyright` will treat EconFlow as an untyped package and will not check type annotations in downstream user code that imports from it. For a library that uses Pydantic v2 and has Protocol definitions, this is a significant omission.

**Recommended solution.** Add an empty `src/econflow/py.typed` file and declare it in `pyproject.toml` under `[tool.hatch.build.targets.wheel] artifacts`.

---

### MEDIUM

---

#### M-1: `.gitignore` Comment Contradicts Behavior for `uv.lock`

**Evidence.** `.gitignore`:

```
# EconFlow is a library — lock file is intentionally excluded.
# uv.lock
```

The comment states the lock file is excluded, but the `uv.lock` line is commented out, which means `uv.lock` IS tracked by git. The comment and the configuration say opposite things. The conventional practice for library packages is to not commit `uv.lock` (application repos commit lock files; libraries do not, to allow downstream dependency resolution). The current state commits the lock file while claiming not to.

**Recommended solution.** Either uncomment `# uv.lock` in `.gitignore` and remove `uv.lock` from git history, or update the comment to accurately reflect the decision to commit the lock file.

---

#### M-2: `PipelineError` Defined in Two Separate Modules

**Evidence.** Both `src/econflow/exceptions.py` and `src/econflow/core/exceptions.py` define a class named `PipelineError`. They are unrelated classes: the first inherits from `EconFlowError`, the second from `EconFlowCoreError`. Code that does `from econflow.exceptions import PipelineError` and code that does `from econflow.core.exceptions import PipelineError` will catch different exception types. An `except PipelineError` block will not catch the other module's `PipelineError`.

**Recommended solution.** Consolidate the exception hierarchy. The `core/exceptions.py` hierarchy should subsume the top-level `exceptions.py`, or vice versa. The two-layer structure adds confusion without value.

---

#### M-3: Getting Started Example Missing `decimal_places` Field

**Evidence.** `examples/getting_started/config/outputs.yaml` does not include a `decimal_places` key, which was added as a config field in Sprint 11F. The pipeline handles the missing key gracefully (via a default), but the Getting Started tutorial — the primary learning resource for new users — does not demonstrate the field's existence.

---

#### M-4: `econflow report` Beta Status Not Surfaced in README

The `econflow report` command's own docstring marks it as `[beta]`, but the README CLI reference table lists it without caveat. Users running `econflow report` on production data may be surprised to find it is not considered stable.

---

#### M-5: CI Pipeline Lacks Wheel Build Verification and Coverage Upload

The `.github/workflows/ci.yml` runs pytest and ruff but does not: (a) build the wheel with `python -m build` and verify it installs cleanly, (b) upload coverage to a reporting service, or (c) run a publish workflow. A broken wheel or packaging metadata error could be committed undetected.

---

#### M-6: `econflow docs` Fails Silently for Undocumented Topics

`econflow docs models` and `econflow docs outputs` produce runtime errors. The command accepts a bare `topic: str` argument with no validation. There is no help text that tells the user which topics are supported; they discover the limitation at runtime.

**Recommended solution.** Add topic validation with a helpful error message listing supported topics, or complete the `models` and `outputs` topic implementations.

---

#### M-7: Internal Sprint Documents in `docs/` Root

`docs/SPRINT_MIGRATION_ROADMAP.md`, `docs/MIGRATION_PLAN.md`, and `docs/SPRINT6_RC1_REVIEW.md` are committed in `docs/`. External contributors expect `docs/` to contain user-facing documentation. Internal sprint planning artifacts should be in `docs/development/` (where some copies already exist) or removed entirely from the public repo.

---

#### M-8: `outputs/` Committed with Generated Content

`outputs/provenance/REPRODUCIBILITY_REPORT.md` is committed via an explicit gitignore exception (`!outputs/provenance/REPRODUCIBILITY_REPORT.md`). While the gitignore design is intentional, a committed generated file at the repo root level creates confusion about what is source vs. artifact in a freshly cloned repository.

---

### LOW

---

#### L-1: Module Docstring Says `pip install econflow`

`src/econflow/__init__.py` opens with a docstring that includes the install instruction `pip install econflow`. The package is not on PyPI. This inaccuracy is reproduced in any auto-generated API documentation.

---

#### L-2: Legacy `--data-path` Pipeline Path Still Active in CLI

The `run` command in `cli.py` retains a `--data-path` flag that routes to the old `econflow.pipeline` module, marked for removal at v0.3.0. The presence of two pipeline paths (`pipeline_generic.py` and the legacy `econflow.pipeline`) creates maintenance overhead and risk of behavioral divergence.

---

#### L-3: `econflow report` and `pipeline_generic.py` Output Paths Are Disconnected

`pipeline_generic.py` writes tables independently via its own output logic. `econflow report` creates a `PublicationBundle` through the `outputs/` subpackage's renderer pipeline. The two are not connected: running `econflow run` then `econflow report` may produce inconsistent or redundant output sets.

---

#### L-4: `ai_productivity_paper/` as a Bundled Example

`examples/ai_productivity_paper/` ships the specific research project that motivated EconFlow's creation. For a general-purpose platform, the primary example should be research-neutral. Including a specific, unpublished academic study as a bundled example conflates personal research artifact with platform showcase and could create exposure risk if the underlying paper has not been peer-reviewed.

---

#### L-5: `my_test_study/` Present on Disk at Repository Root

A workspace directory `my_test_study/` (created by `econflow init` during development) exists at the repo root. It is correctly gitignored. Its presence signals that the developer workspace and the repository root are the same filesystem location, which is a project hygiene concern.

---

#### L-6: Module-Level `__init__.py` Does Not Re-Export Subpackage APIs

`src/econflow/__init__.py` exports only exceptions. Users who want to use the estimation framework, ingestion connectors, or replication engine must know the internal subpackage paths (e.g., `from econflow.estimation import EntityFE`). A well-structured library re-exports its primary public API at the package root.

---

## Part II — Area-by-Area Assessment

### 1. Repository Structure

The top-level layout is clean: `src/` layout, `tests/`, `examples/`, `docs/`, `outputs/`. The `src/econflow/` tree is well-organized and uses recognizable subpackage names. The main structural concern is the presence of development artifacts at the root (`MIGRATION_CHECKLIST.md`, `my_test_study/`) and the committed `.venv/` directory, which indicate the repo root doubles as the active development workspace.

Severity of issues: H-6, L-5.

---

### 2. Packaging

`pyproject.toml` is correctly structured with hatchling as the build backend, `src/` layout declared, entry points defined, and metadata populated. Version is `0.1.0`. The `[project] dependencies` list covers core dependencies. The primary gap is the missing `requests` dependency (C-5). The `uv.lock` commit/exclusion inconsistency is medium severity (M-1). No `py.typed` marker (H-7). Wheel build is not verified in CI (M-5).

Overall: installable from source, but a clean install will break on FRED/WorldBank data fetch.

---

### 3. Public API

`econflow.__init__.__all__` exports only exceptions. There is no re-export of estimation, ingestion, or outputs APIs at the package root. The exception hierarchy has a naming collision (`PipelineError` in two modules — M-2) and a deprecated alias in the public namespace (`AIProdError` — H-2). The `__author__` field is truncated (H-4).

The `estimation/__init__.py` public API is well-designed: it exports the ABC, the protocol, the result dataclasses, all built-in estimators, and the registry functions with clear deprecated aliases.

---

### 4. CLI

17 commands implemented in a 2056-line `cli.py`. The commands have thorough docstrings with examples, common mistakes, and expected outputs. The Windows UTF-8 compatibility fix is present. Pre-flight config validation runs before `econflow run`. The main gaps: `docs` command absent from README (H-5), beta status of `report` not surfaced (M-4), `docs` topic validation incomplete (M-6), legacy `--data-path` path still active (L-2).

The CLI is functionally strong for the commands that connect through to `pipeline_generic.py`.

---

### 5. Documentation

The README is well-structured: installation, quick start, project layout, CLI reference, examples, citation. The CI, Python, and license badges are present. The primary gap: `ARCHITECTURE.md` is materially stale (C-3). The `docs/` directory has extensive ADRs, release audit documents, and architecture reference documents — far more documentation infrastructure than most v0.1.0 projects. The quality concern is that some of this documentation describes aspirational or incorrect state.

---

### 6. Plugin Architecture

The plugin system (`@register_estimator`, `@register_diagnostic`, `@register_ingestion`, `@register_output`) is a coherent design, correctly using a module-level registry with side-effect imports at the subpackage `__init__.py` level. The `register`/`unregister` deprecation aliases are handled cleanly with runtime warnings. The critical gap is that the plugin registry is not consulted by the production pipeline (C-1, H-1). The `KNOWN_ESTIMATORS` frozenset in config validation is decoupled from the registry (H-3), which would reject valid custom estimator configs.

The plugin architecture design is correct; it is simply unconnected to the code path that users actually run.

---

### 7. Estimation Framework

`BaseEstimator` ABC, `EstimatorProtocol`, `EstimationResult` and `DiagnosticResult` dataclasses, 8 registered estimators. Two estimators are fully implemented (EntityFE, TwoWayFE using linearmodels). Two are stubs that raise `NotImplementedError` (SystemGMM, PanelQuantile — C-4). The status of the remaining four (PooledOLS, RandomEffects, FirstDifferences, IV) was not individually verified in this assessment but can be inferred from the registration pattern.

The framework design is sound. It is not used at runtime (C-1).

---

### 8. Reporting Engine

The `outputs/` subpackage implements table and figure renderers for CSV, LaTeX, Markdown, HTML, and JSON. The `report` command creates a `PublicationBundle`. These are implemented independently of `pipeline_generic.py`'s output writing logic (L-3). The `decimal_places` config field was added in Sprint 11F and is handled correctly in `pipeline_generic.py` with a default fallback. The getting_started example does not demonstrate the field (M-3). The `report` command is marked beta (M-4).

---

### 9. Replication Engine

`src/econflow/replication/` implements inspect, reproduce, and compare capabilities. The CLI surfaces these as `econflow inspect`, `econflow reproduce`, and `econflow compare`. The `examples/blind_replication/` example exists and has a replication report. The integrity chain (`certify` → `verify` → `package` → `reproduce`) is implemented end-to-end. This appears to be one of the more complete subsystems in the repository.

---

### 10. Integrity Framework

`src/econflow/integrity/` provides provenance certificates, SHA-256 fingerprinting, and drift detection. The `certify`, `verify`, and `package` commands are implemented. The `outputs/provenance/` directory is kept with schema stubs committed. This subsystem appears well-implemented.

---

### 11. Data Ecosystem

`src/econflow/ingestion/` provides connectors for CSV, World Bank, OECD, PWT, and FRED. The connector framework with `CacheManager` and the `@register_ingestion()` plugin system is present. The `econflow fetch` and `econflow cache` commands are implemented. The critical gap is the missing `requests` dependency (C-5) which breaks FRED and World Bank connectors on clean installs. The FRED connector correctly excludes `api_key` from cache keys.

---

### 12. Testing

`tests/` contains `unit/` and `integration/` directories. `tests/conftest.py` provides synthetic panel fixtures (10 entities × 10 periods) and stubbed API fixtures for World Bank and OECD. The coverage configuration excludes all major production subpackages (C-2), meaning measured coverage is not representative. The CI runs pytest but does not enforce coverage on production code. The LaTeX compilation test in CI is present but narrow in scope. No tests for the plugin extension path (register a custom estimator, run it end-to-end) are visible.

---

### 13. CI/CD

Three CI jobs: pytest (3.10/3.11/3.12), ruff lint, LaTeX compilation. No coverage upload, no wheel build check, no PyPI publish workflow (M-5). The CI gate would pass even if all production subpackages had zero test coverage, because coverage is measured only over the unomitted slice (C-2).

---

### 14. Developer Experience

The repository has a thorough DX infrastructure: ADR documents, `DESIGN_PRINCIPLES.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `PULL_REQUEST_TEMPLATE.md`, a GitHub agent configuration (`econometrics.agent.md`), `econflow doctor` for environment checks, and a `release-check` command. The main DX concern is that `ARCHITECTURE.md` would immediately mislead a new contributor (C-3).

---

### 15. First-Time User Experience

The getting_started tutorial uses the Grunfeld investment panel (a standard econometrics dataset) and is well-chosen. The quick start in README is clear and follows the natural workflow. The `econflow doctor` command is a good first-run check. The `econflow docs config` command provides inline config reference. Gaps: the `docs` command is not in the CLI reference table (H-5), the getting_started example does not show the `decimal_places` field (M-3), and the `report` command's beta status is not communicated to new users (M-4). A new user who follows the README and tries `estimator: twfe` in their models.yaml will encounter undefined behavior (C-1).

---

### 16. Research Reproducibility

The provenance certificate system, SHA-256 fingerprinting, replication package format, and blind replication walkthrough are substantive features that set EconFlow apart from simpler analysis tools. The `REPRODUCIBILITY_REPORT.md` in `outputs/provenance/` is committed as a reference artifact. The `CITATION.cff` and BibTeX block in the README address academic citation needs. These are well-implemented.

---

## Part III — Final Questions

### 1. Is EconFlow internally consistent after repository separation?

Partially. The separation itself — moving the package from inside a parent project to its own repository — did not introduce new inconsistencies. All pre-existing architecture is preserved intact.

The repository has one major internal inconsistency that predates the separation: `pipeline_generic.py` (the actual production code path) and the `estimation/` + `diagnostics/` frameworks (the documented and exported architecture) are parallel implementations with no connection. The rest of the pipeline — config validation, integrity chain, ingestion, outputs, replication — is internally self-consistent.

The inconsistency is not a consequence of the separation. It existed before and was carried over.

---

### 2. Did the separation introduce regressions?

No regressions are detectable from static analysis. The source tree is intact, module import paths are unchanged, entry points point to the correct modules, and the `pyproject.toml` `src/` layout declaration is correct. There are no broken imports, missing `__init__.py` files, or circular dependency indicators in the source as read.

Verification requires a live `pytest` run in the new location, which was not available during this assessment. The risk of undetected import-path regressions from the separation is low but non-zero and should be confirmed before any public release.

---

### 3. Is the package installable from scratch?

Yes, with one caveat. A clean `git clone` followed by `pip install -e ".[dev]"` will succeed. The `pyproject.toml` build configuration is correct.

The caveat: `requests` is not declared as a dependency (C-5). A fresh install in an environment that does not already have `requests` (e.g., a clean venv with only EconFlow installed) will succeed, but `econflow fetch --connector fred` and `econflow fetch --connector worldbank` will raise `ModuleNotFoundError` at runtime.

Additionally, the package is not on PyPI. "Installable from scratch" requires cloning the git repository first.

---

### 4. Is it ready for public beta?

No. Three blockers must be resolved first:

**Blocker 1 (C-1).** `econflow run` only dispatches to OLS and FE models. Any user who specifies `twfe`, `re`, `fd`, or `iv` in their models.yaml — all advertised in the README — will not receive the documented behavior. This is the defining feature gap.

**Blocker 2 (C-1 / H-3).** The plugin architecture — the primary extensibility claim of the platform — is not connected to the production execution path. A researcher who registers a custom estimator via `@register_estimator()` and runs `econflow run` will find their plugin silently ignored. Advertising a plugin system that is not used at runtime is misleading.

**Blocker 3 (C-4).** Two exported, validating, non-functional estimators (`SystemGMM`, `PanelQuantile`) would crash any user who specifies them, once C-1 is fixed. They should be hidden from the public API until implemented, or the validator should refuse to proceed with a clear error.

What is close to release quality: the config validation system, the integrity and provenance chain, the replication engine, the data connectors (modulo C-5), the CLI for the commands that work, and the documentation infrastructure. The gap to public beta is architecturally narrow: it is primarily the wiring of `pipeline_generic.py` to dispatch through `estimation/` rather than inline linearmodels. Resolving C-1 would simultaneously unblock H-3, render C-4 actionable, allow H-1 to be addressed, and restore the plugin architecture's value. It is the single highest-leverage change in the repository.

---

## Summary Table

| ID | Area | Severity | One-Line Description |
|----|------|----------|----------------------|
| C-1 | Estimation | Critical | `econflow run` bypasses `estimation/` framework entirely |
| C-2 | Testing | Critical | Coverage omits all production subpackages — gate is meaningless |
| C-3 | Documentation | Critical | `ARCHITECTURE.md` describes non-existent modules |
| C-4 | Public API | Critical | `SystemGMM` and `PanelQuantile` are exported but raise `NotImplementedError` |
| C-5 | Packaging | Critical | `requests` not declared as dependency; FRED/WorldBank connectors fail on clean install |
| H-1 | Diagnostics | High | `econflow run` bypasses `diagnostics/` framework; custom diagnostic plugins ignored |
| H-2 | Public API | High | `AIProdError` (deprecated, paper-specific) exported in `__all__` |
| H-3 | Plugin Architecture | High | `KNOWN_ESTIMATORS` frozenset decoupled from live registry; rejects custom plugins |
| H-4 | Packaging | High | `__author__` is `"Ab"` — truncated, appears in wheel metadata |
| H-5 | Documentation | High | `econflow docs` command absent from README CLI reference |
| H-6 | Repository | High | `MIGRATION_CHECKLIST.md` at repo root — internal artifact in public view |
| H-7 | Packaging | High | No `py.typed` marker — downstream type checking disabled |
| M-1 | Repository | Medium | `.gitignore` comment says `uv.lock` is excluded; it is committed |
| M-2 | Public API | Medium | `PipelineError` defined in two modules; name collision |
| M-3 | Documentation | Medium | Getting Started example missing `decimal_places` field |
| M-4 | CLI | Medium | `report` command beta status not surfaced in README |
| M-5 | CI/CD | Medium | No wheel build check, no coverage upload in CI |
| M-6 | CLI | Medium | `econflow docs` fails at runtime for undocumented topics |
| M-7 | Documentation | Medium | Internal sprint documents in public `docs/` root |
| M-8 | Repository | Medium | Generated content committed via gitignore exception |
| L-1 | Documentation | Low | Module docstring says `pip install econflow` — package not on PyPI |
| L-2 | CLI | Low | Legacy `--data-path` pipeline path still active |
| L-3 | Architecture | Low | `report` command and `pipeline_generic.py` output paths not connected |
| L-4 | Examples | Low | `ai_productivity_paper/` example conflates personal research with platform showcase |
| L-5 | Repository | Low | `my_test_study/` workspace present at repo root |
| L-6 | Public API | Low | Package root does not re-export subpackage APIs |
