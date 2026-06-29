# EconFlow v1.0 — Release Criteria

**Document type:** Technical Steering Committee Governing Document  
**Date issued:** 2026-06-28  
**Authority:** This document defines the minimum necessary and sufficient conditions for
an EconFlow v1.0 release. No version may carry the label `1.0` unless every requirement
marked **Blocking** is verified complete. Requirements marked **Non-blocking** must be
Partial or Complete at release and must reach Complete in the first patch cycle.

This document is not a backlog. It does not describe desired features. It describes the
state the software must be in before EconFlow makes the implicit promise that v1.0 carries:
that the public API is stable, that the platform is suitable for use in published research,
and that third-party authors can build on it with confidence.

---

## How to Read This Document

Each requirement is stated as a falsifiable condition. The Verification Method describes
exactly how a reviewer confirms the condition is met — not how to implement it. Status
reflects the state of the repository at the time of the v0.7 milestone review
(2026-06-28).

**Status definitions:**

- **Complete** — Condition is fully met; no further work required.
- **Partial** — Condition is substantially met but with documented gaps.
- **Missing** — Condition is not met; substantive work required.

**Blocking** — release is prohibited unless this requirement reaches Complete.  
**Non-blocking** — release is permitted if Partial; must reach Complete by v1.0.1.

---

## Section 1: Architecture

### 1.1 Generic Pipeline Dispatches Through the Estimator Registry

**Blocking**

**Requirement.** `pipeline_generic.py::run_from_config()` must obtain all estimator
instances by calling `estimation.registry.get_estimator(id)`. No direct import of
`linearmodels`, `statsmodels`, or any computational backend is permitted inside the
pipeline module. The pipeline may not know the name of any specific estimator. All
estimator IDs must come from the YAML configuration.

**Why it matters.** The plugin architecture for estimation is the central extensibility
promise of EconFlow. A `@register("my_estimator")` plugin that a researcher writes must
be reachable from `econflow run` without modifying any EconFlow source file. This is
currently false: `pipeline_generic.py` imports `linearmodels` directly, making the
estimation registry decorative rather than functional in the primary user-facing workflow.
An architecture whose primary code path bypasses its own plugin system is not
ready for a v1.0 commitment.

**Verification method.** Install EconFlow in a clean virtual environment. Write a minimal
`@register("test_pass_through")` estimator that returns a known constant for all
coefficients. Create a `models.yaml` that specifies `estimator: test_pass_through`.
Run `econflow run`. Confirm that the pipeline executes the custom estimator and produces
output containing the known constant. Confirm that no `import linearmodels` or
`import statsmodels` statement appears at module level in `pipeline_generic.py`.

**Status:** Missing.

---

### 1.2 Single Exception Hierarchy

**Blocking**

**Requirement.** The project must expose exactly one exception hierarchy rooted at
`EconFlowCoreError`. The `APRPError` name must be fully removed from the public API
(not merely deprecated with an alias). All internal exception sites must raise
sub-classes of `EconFlowCoreError`.

**Why it matters.** A caller who writes `except APRPError` has been writing against a
public API name. If that name still exists at v1.0, it remains a public API name whether
or not it is marked deprecated. If it is removed after v1.0, that is a breaking change.
The correct resolution is to remove it before v1.0, when the semver promise has not yet
been made. After v1.0, the exception hierarchy is frozen.

**Verification method.** `grep -r "APRPError" src/`. The command must return zero
results. `grep -r "EconFlowCoreError" src/econflow/core/exceptions.py` must return the
class definition. Run the full test suite; no test may reference `APRPError` except in
a test that verifies the name no longer exists.

**Status:** Partial. `APRPError` is a live deprecated alias, not yet removed.

---

### 1.3 Dead Artifacts Deleted

**Blocking**

**Requirement.** The repository must contain no unreachable, deprecated, or superseded
production code. Specifically: `cli_scaffold/` must be deleted; root-level stub files
`src/econflow/ingestion/oecd.py`, `src/econflow/ingestion/pwt.py`, and
`src/econflow/ingestion/world_bank.py` must be deleted; `pipeline.py` (the
paper-specific legacy pipeline) must either be deleted or clearly moved to
`examples/ai_productivity_paper/` and explicitly excluded from the public API.

**Why it matters.** Dead code is not neutral. It creates confusion for contributors who
cannot determine which of two implementations is canonical. The root-level ingestion stubs
coexist with `connectors/` implementations that supersede them; a new contributor reading
the directory structure cannot tell which to use. `cli_scaffold/` appears to be an
alternative CLI implementation. Shipping either of these in a v1.0 release signals that
the project does not know what it is.

**Verification method.** `find src/ -name "oecd.py" -o -name "pwt.py" -o -name
"world_bank.py" | grep -v connectors` must return zero results.
`ls cli_scaffold/` must return "No such file or directory". `python3 -c "from
econflow.ingestion import oecd"` at the root package level must raise `ImportError`
(the connector is reachable only at `econflow.ingestion.connectors.oecd`).

**Status:** Missing.

---

### 1.4 `load_config()` Implemented and in Use

**Blocking**

**Requirement.** `core/config.py::load_config(path)` must return a fully validated
`Settings` object. Every CLI command that accepts a `--config` flag must obtain its
configuration through `load_config()`. No CLI command may call `_load_yaml()` directly.
Invalid configuration values must raise `ConfigurationError` with a message that
identifies the specific field and its invalid value, before any pipeline code executes.

**Why it matters.** `load_config()` raises `NotImplementedError` at v0.7. This means
configuration validation is structural (the YAML parses) rather than semantic (the values
are valid). A researcher who supplies `year_start: "not a year"` or a nonexistent
column name receives a cryptic runtime error during pipeline execution rather than an
early, clear rejection. Early rejection is not a convenience; it is the difference
between a pipeline that fails fast with a useful error and one that silently produces
wrong results.

**Verification method.** Create a `config.yaml` with `year_start: -999`. Run
`econflow validate`. Confirm that the command exits non-zero and prints an error message
containing the field name and the invalid value before executing any pipeline logic.
Create a valid `config.yaml`. Run `econflow run`. Confirm with a debugger or log
statement that `load_config()` is called and returns a `Settings` object. Confirm that
`_load_yaml()` is not called in the CLI layer.

**Status:** Missing.

---

### 1.5 No Circular Imports

**Non-blocking**

**Requirement.** `python3 -c "import econflow"` must complete without any import cycle
warning or error under Python 3.10, 3.11, 3.12, and 3.13.

**Why it matters.** Import cycles produce `ImportError` for users who import EconFlow
sub-packages in unusual orders and are a sign of architectural coupling that is
inconsistent with a modular plugin design.

**Verification method.** Run `python3 -c "import econflow; print('OK')"` under each
supported Python version in a clean virtual environment. Run
`pydeps src/econflow --no-output --max-bacon 3` and confirm no cycles in the
dependency graph.

**Status:** Complete (no known cycles at v0.7; verify under 3.12 and 3.13 explicitly).

---

## Section 2: Public API Stability

### 2.1 Stable Public API Surface Declared

**Blocking**

**Requirement.** Every sub-package's `__init__.py` must define `__all__` listing
exactly the symbols that are part of the public API. Any symbol not in `__all__` is
considered internal and may change without notice. The public API must be listed in
the Plugin SDK document (see Section 3). The TSC must review and formally approve the
`__all__` lists before release.

**Why it matters.** Without a declared public API, every internal class and function
becomes implicitly public by convention. After v1.0, any change to any importable name
is a potential breaking change. Declaring `__all__` before v1.0 is the only opportunity
to limit the surface area of the backward compatibility commitment.

**Verification method.** Run `grep -r "__all__" src/econflow/*/`. Every `__init__.py`
in every sub-package must contain an `__all__` definition. Cross-reference every name
in `__all__` against the Plugin SDK document and confirm it is documented there.

**Status:** Partial. Some sub-packages define `__all__`; others do not. No TSC review
of the combined surface has been conducted.

---

### 2.2 No Use of `_private` Names Across Package Boundaries

**Blocking**

**Requirement.** No module may import a name beginning with `_` from a different
sub-package. Cross-package references must use only the declared public API.

**Why it matters.** A `from econflow.estimation._helpers import _coerce_params` in the
diagnostics package is an undeclared dependency on an internal implementation detail.
After v1.0, changing `_coerce_params` breaks the diagnostics package without the
estimation package author knowing. Enforcing this boundary before release makes the
sub-package contracts real.

**Verification method.** `grep -rn "from econflow\.[a-z_]*\._" src/econflow/` must
return zero results (excluding legitimate same-package internal references).

**Status:** Partial. Requires audit.

---

### 2.3 Semver Commitment Documented

**Blocking**

**Requirement.** A `VERSIONING.md` document must exist at the repository root that
states: (a) EconFlow follows Semantic Versioning 2.0.0; (b) what constitutes a breaking
change (signature changes in `__all__` symbols, removal of `__all__` symbols, changes
to YAML schema required keys, changes to JSON artifact schema without version bump,
changes to plugin base class abstract methods, changes to CLI command names or
required arguments); (c) what is explicitly excluded from the breaking change definition
(internal `_private` names, stub implementations, documentation, error message text);
(d) the deprecation policy (minimum one minor version with `DeprecationWarning` before
removal).

**Why it matters.** Without a published definition of breaking change, the semver promise
is unenforceable. Researchers who build on EconFlow need to know whether updating to
v1.1 will break their plugins or YAML configurations. The definition must exist before
v1.0 is released because v1.0 is the moment the promise begins.

**Verification method.** `cat VERSIONING.md` at the repository root. The document must
address all four points listed in the requirement.

**Status:** Missing.

---

## Section 3: Plugin SDK

### 3.1 Plugin SDK Document Published

**Blocking**

**Requirement.** `docs/plugin_sdk/PLUGIN_SDK.md` must exist and document: (a) how to
install the EconFlow Plugin SDK (i.e., install EconFlow as a dependency); (b) the stable
interface for each of the five plugin types — `AbstractConnector`, `BaseEstimator`,
`BaseDiagnostic`, `BaseRenderer`, `BaseIntegrityCheck`; (c) the complete method
signatures for each abstract method, including parameter types and return types; (d) the
registration decorator for each type and where to import it from; (e) a minimal
working example for each of the five plugin types that can be copy-pasted and run;
(f) what happens when a plugin is incompatible (which exception is raised, from where);
(g) the backward compatibility guarantee (which interface elements are frozen, which may
change).

**Why it matters.** The plugin architecture is EconFlow's core extensibility mechanism.
A plugin architecture that is not documented is not accessible. Researchers who want to
add a connector for a proprietary database, a specialized estimator, or a custom
integrity check must have a document they can read without understanding the EconFlow
internals. The Plugin SDK is what makes EconFlow a platform rather than a set of
examples.

**Verification method.** Copy the connector example from the Plugin SDK into an empty
Python file in a new directory (not inside the EconFlow source tree). Install EconFlow
as a pip dependency. Import the custom connector and call
`econflow.ingestion.registry.get_connector("my_connector")`. Confirm it returns the
expected class. Repeat for each of the five plugin types.

**Status:** Missing.

---

### 3.2 Plugin Interfaces Are Frozen

**Blocking**

**Requirement.** The abstract method signatures of `AbstractConnector`,
`BaseEstimator`, `BaseDiagnostic`, `BaseRenderer`, and `BaseIntegrityCheck` must not
change between the v1.0 RC and the v1.0 release. Any change to these signatures
constitutes a breaking change. The TSC must review all five interfaces and issue a
written sign-off before RC1 is tagged.

**Why it matters.** A plugin author who writes against the RC1 interface must not need
to change their code for the v1.0 release. This is the minimum requirement for "stable"
to mean anything.

**Verification method.** Tag RC1. Write a test plugin for each of the five types against
the RC1 interface. Run those test plugins against the v1.0 binary without modification.
All five must work.

**Status:** Missing (RC1 has not been tagged; TSC sign-off has not been issued).

---

### 3.3 Plugin Discovery via Entry Points

**Non-blocking**

**Requirement.** A third-party package must be able to register an EconFlow plugin
without the user manually importing it. EconFlow must discover and load plugins
declared in the `[project.entry-points."econflow.plugins"]` section of a third-party
`pyproject.toml`.

**Why it matters.** Currently, a third-party plugin is only available if the user imports
it before running the pipeline. This is not a viable distribution model. Entry point
discovery is the standard Python mechanism for plugin distribution and is required for
EconFlow to have a realistic third-party ecosystem.

**Verification method.** Create a minimal Python package that declares an EconFlow
entry point in `pyproject.toml`. Install the package with `pip install`. Run
`econflow info` and confirm the third-party estimator/connector appears in the output
without any explicit import by the user.

**Status:** Missing.

---

## Section 4: Estimation Framework

### 4.1 All Registered Estimators Are Implemented

**Blocking**

**Requirement.** Every estimator ID returned by `list_estimators()` must return a
`BaseEstimator` subclass whose `fit()` method does not raise `NotImplementedError`.
Stub estimators must either be fully implemented or removed from the registry before
v1.0. System GMM and Panel Quantile Regression are currently stubs; both must be
resolved.

**Why it matters.** `econflow info` reports the available estimators. A researcher who
reads that list, selects `gmm` in their `models.yaml`, and runs `econflow run` must not
receive a `NotImplementedError`. Shipping registered stubs is shipping broken
functionality under a legitimate name. It is preferable to have four working estimators
than six estimators of which two are non-functional.

**Verification method.** For every ID in `list_estimators()`: create a synthetic panel
dataset with at least 50 units and 5 time periods; call `get_estimator(id).run(data,
params)`; assert that the return value is an `EstimationResult` and that `params` is
a non-empty `pd.Series`. Zero `NotImplementedError` exceptions are permitted.

**Status:** Partial. GMM and Panel Quantile are stubs.

---

### 4.2 `EstimationResult` Schema Is Frozen

**Blocking**

**Requirement.** The `EstimationResult` dataclass fields — `params`, `std_err`,
`pvalues`, `nobs`, `rsq`, `estimator_id`, `diagnostic_results` — must not change in
name, type, or nullability between RC1 and v1.0. Additional optional fields may be
added in v1.x minor releases. No existing field may be removed or renamed in a
v1.x release.

**Why it matters.** `EstimationResult` is the central data carrier of EconFlow. It is
referenced by every diagnostic, every table builder, and every integrity check. Freezing
its schema at v1.0 is freezing the contract between estimation and everything downstream.
Without this freeze, a minor update to the estimation layer would cascade silently into
every plugin and every downstream consumer.

**Verification method.** Code review of `EstimationResult` definition. TSC sign-off on
the final schema before RC1 is tagged. Confirm that the schema matches what is
documented in the Plugin SDK.

**Status:** Partial. The dataclass exists and is consistent, but has not been formally
reviewed and approved by the TSC.

---

### 4.3 Estimator Output Is Numerically Verified

**Non-blocking**

**Requirement.** For each of the six implemented estimators, a regression test must
exist that compares the coefficients and standard errors produced by `BaseEstimator.run()`
against a known reference implementation (e.g., Stata, R `plm`, or `linearmodels`
directly) on the same dataset. The tolerance for coefficient comparison must be no
larger than `1e-6` for identical data and identical options.

**Why it matters.** EconFlow's estimators wrap `linearmodels` and `statsmodels`. The
wrapper could silently apply transformations, subset data, or handle missing values in
ways that alter the numerical output. Researchers publish numbers. If EconFlow produces
different numbers than the reference implementation, the platform is introducing error
into published work.

**Verification method.** `pytest tests/regression/ -k estimator_numerical` must pass.
Each test loads a reference dataset, runs the corresponding estimator, and compares
against stored reference values with `np.allclose(atol=1e-6)`.

**Status:** Missing. The regression test suite covers the original paper's outputs but
not numerical verification of individual estimators.

---

## Section 5: Connector Framework

### 5.1 All Registered Connectors Are Implemented

**Blocking**

**Requirement.** Every connector ID returned by `list_connectors()` must return an
`AbstractConnector` subclass whose `download()` method does not raise
`NotImplementedError`. All five currently registered connectors (`csv`, `world_bank`,
`oecd`, `pwt`, `fred`) are already implemented; this requirement forbids adding new
connector IDs as stubs before v1.0.

**Why it matters.** Same rationale as 4.1. A registered connector that raises
`NotImplementedError` is broken functionality with a legitimate name.

**Verification method.** For each connector ID: instantiate the connector with valid
parameters, run `connector.validate()` and `connector.metadata()` against a local
or cached dataset, confirm both return without error. For network connectors, test
against a cached response to avoid external dependency in the test suite.

**Status:** Complete (all five connectors are implemented).

---

### 5.2 Network Connectors Declared in `pyproject.toml` Dependencies

**Blocking**

**Requirement.** `requests` and `openpyxl` must be listed as required dependencies in
`pyproject.toml`. They must not be optional extras. If it is desired to make network
connectors optional (i.e., `pip install econflow[network]`), then the connectors
themselves must be conditionally importable and must raise a clear `ImportError` with
installation instructions when the optional dependency is absent.

**Why it matters.** At v0.7, `requests` and `openpyxl` are used by four of the five
connectors but are not listed in `pyproject.toml`. A researcher who installs EconFlow
from PyPI and runs `econflow fetch --connector world_bank` receives a traceback ending
in `ModuleNotFoundError: No module named 'requests'`. This is a packaging defect that
makes the software appear broken on a standard install. It must be resolved before
any public release.

**Verification method.** `pip install econflow` in a clean virtual environment with no
other packages installed. Run `econflow fetch --connector world_bank --dataset
SP.POP.TOTL --params country=USA`. The command must either succeed or fail with a
network error — never with an `ImportError` or `ModuleNotFoundError`.

**Status:** Missing.

---

### 5.3 OECD Connector Handles Non-Standard Dimension Structures

**Non-blocking**

**Requirement.** The OECD SDMX-JSON parser must not raise an unhandled exception when
encountering a dataflow whose dimension structure differs from the standard
LOCATION/MEASURE/TIME_PERIOD arrangement. When an unexpected structure is encountered,
the connector must raise `ConnectorError` with a message that identifies the dataflow ID
and the unexpected dimension, rather than raising `IndexError` or `KeyError`.

**Why it matters.** OECD publishes over 1,000 dataflows. The current parser makes
assumptions about dimension ordering and dimension IDs that hold for the most common
macro dataflows but will fail silently or cryptically on others. A researcher who
specifies a non-standard dataflow must receive a diagnostic error that tells them what
to do, not a Python traceback.

**Verification method.** Construct a synthetic SDMX-JSON payload where the LOCATION
dimension is replaced by a PARTNER dimension. Pass it to `OECDConnector._parse_sdmx_json()`.
Confirm that `ConnectorError` is raised, not `IndexError` or `KeyError`. Confirm that
the error message names the unexpected dimension.

**Status:** Partial. The parser is implemented but is known to make hard assumptions
about dimension structure.

---

### 5.4 Cache Key Stability Guaranteed

**Blocking**

**Requirement.** The cache key algorithm for every connector must be documented and
frozen at v1.0. A change to the cache key algorithm is a breaking change — it
invalidates all existing user caches. If the algorithm must change, a cache migration
utility must be provided. The FRED connector's exclusion of `api_key` from the cache
key hash must be documented in the Plugin SDK as a reference implementation of
security-aware cache key design.

**Why it matters.** Researchers rely on the cache for reproducibility. A `force=False`
download must return the same data as it did six months ago if the cache key is stable.
If the cache key algorithm changes without notice, every researcher's cache silently
stops being used, and the "offline reproducibility" guarantee is broken.

**Verification method.** Write a test that stores a known dataset under its cache key,
upgrades EconFlow to v1.0, and retrieves the same dataset using the same parameters.
The cache hit must succeed. The cache key string produced by the v0.7 and v1.0
connectors must be identical for the same input parameters.

**Status:** Partial. The algorithm is implemented but not formally documented or frozen.

---

## Section 6: Reporting Engine

### 6.1 All Registered Renderers Are Implemented

**Blocking**

**Requirement.** Every renderer ID returned by `list_renderers()` must return a
`BaseRenderer` subclass whose `render(table)` method produces non-empty output. All
five currently registered renderers (`csv`, `html`, `json`, `latex`, `markdown`) are
implemented; this requirement forbids adding new renderer IDs as stubs before v1.0.

**Verification method.** For each renderer ID: construct a minimal `ReportTable` with
at least one row and two columns; call `get_renderer(id).render(table)`; assert the
return value is a non-empty string containing at least one cell value.

**Status:** Complete.

---

### 6.2 All Registered Figure Builders Are Implemented

**Blocking**

**Requirement.** Every figure builder class accessible through the `outputs` package
must produce a non-empty figure when given a valid `EstimationResult`. The five stubs
— `DistributionPlot`, `EventStudyPlot`, `ResidualPlot`, `HeteroscedasticityPlot`,
`PanelTrendsPlot` — must either be fully implemented or removed from the package
before v1.0.

**Why it matters.** Same rationale as 4.1. An `econflow report` command that generates
a publication bundle containing zero figures because all figure builders raise
`NotImplementedError` is not a reporting engine.

**Verification method.** Instantiate each figure builder class. Call `build(result)`
with a valid `EstimationResult`. Assert that the return value is a `ReportFigure` with
a non-None `figure` attribute. Zero `NotImplementedError` exceptions permitted.

**Status:** Missing. Five of seven figure builders are stubs.

---

### 6.3 LaTeX Output Compiles Without Errors

**Non-blocking**

**Requirement.** The LaTeX produced by the `latex` renderer for any `ReportTable` must
compile without errors under `pdflatex` with the `booktabs` package loaded. The test
suite must include at least one test that runs `pdflatex` against the renderer's output
(where `pdflatex` is available) and asserts a zero exit code.

**Why it matters.** A LaTeX renderer that produces invalid LaTeX is worse than no LaTeX
renderer. Researchers who use EconFlow's LaTeX output and include it in a journal
submission must be able to rely on it compiling.

**Verification method.** `pytest tests/integration/ -k test_latex_renders_valid_pdf`
must pass when `pdflatex` is available in the environment.

**Status:** Missing.

---

## Section 7: Research Integrity

### 7.1 All Registered Integrity Checks Are Implemented

**Blocking**

**Requirement.** Every integrity check ID returned by `list_integrity_checks()` must
return a `BaseIntegrityCheck` subclass whose `run(result)` method returns an
`IntegrityCheckResult` with a status of `pass`, `warn`, `fail`, or `skip`. All three
currently registered checks (`coefficient_stability`, `pvalue_distribution`,
`sample_size`) are implemented; this requirement forbids adding check IDs as stubs.

**Verification method.** For each check ID: call `get_integrity_check(id).run(result)`
with a valid `EstimationResult`. Assert the return value is an `IntegrityCheckResult`.
Assert `result.status` is one of the four permitted values.

**Status:** Complete.

---

### 7.2 Integrity Check Results Are Included in the Replication Package

**Blocking**

**Requirement.** The `ReplicationPackage` produced by `econflow package` must contain
the `ReproducibilityCertificate` JSON file, which must contain the results of all
integrity checks. The package README (auto-generated) must summarize the integrity
check outcomes in human-readable form. A package produced from a run with one or more
`fail`-status checks must include a visible warning in the README.

**Why it matters.** Integrity checks are only meaningful if they are visible to the
reviewers of the replication package, not just to the researcher during the run. A
certificate buried in a JSON file that no one reads is not an integrity mechanism.

**Verification method.** Create a synthetic `EstimationResult` whose p-value
distribution triggers the `pvalue_distribution` check at `fail` status. Run
`econflow package`. Open the generated archive. Confirm the certificate JSON is present
and contains the `fail` result. Confirm the README contains a section titled
"Integrity Warnings" or equivalent.

**Status:** Partial. The certificate is written and contains check results; the
auto-generated README section and visible warning are not yet implemented.

---

### 7.3 Integrity Checks Run Automatically at Certification

**Non-blocking**

**Requirement.** `econflow certify` must run all registered integrity checks
automatically without the user specifying `--run-checks`. Running checks must not be
opt-in. The certificate may not be written if any check raises an unhandled exception
(as distinct from returning a `fail` status, which should still produce a certificate).

**Why it matters.** If integrity checking is opt-in, researchers who are in a hurry will
skip it. The value of integrity checks is that they run on every certification, covering
the runs where they are most inconvenient.

**Verification method.** Run `econflow certify --config config.yaml` without any
`--checks` flag. Confirm the output contains the results of all three registered
integrity checks. Confirm the certificate JSON contains `check_results`.

**Status:** Complete.

---

## Section 8: Reproducibility

### 8.1 Drift Detection Covers All Eight Axes

**Blocking**

**Requirement.** `ReproducibilityCertificate.detect_drift(other)` must compare: git
commit hash, git tree dirty status, Python version, package versions, data file SHA-256
hashes, data file row counts, data file presence/absence, and configuration file SHA-256.
Each axis must have an independently reported status of `none`, `warn`, or `fail`.
The method must not raise an exception when comparing certificates with different sets
of input files (new files added or old files removed).

**Verification method.** Create two certificates: one from a run on dataset A, one from
a run on dataset B. Call `detect_drift()`. Assert that the data hash axis reports
`fail`. Modify the git commit field of the second certificate and call `detect_drift()`.
Assert the git axis reports `fail`. Each of the eight axes must be independently
exercisable by this method.

**Status:** Complete.

---

### 8.2 Provenance Record and Dataset Manifest Are Linked

**Blocking**

**Requirement.** The `run_metadata.json` produced by `ProvenanceRecorder` must contain
a field `manifest_path` pointing to the `DatasetManifest` JSON file written during the
same run. If no manifest was written (no `econflow fetch` was called in the run), the
field must be `null` rather than absent.

**Why it matters.** A replication reviewer who reads `run_metadata.json` must be able
to locate the manifest that records which datasets were acquired, from which connectors,
with which parameters, and with which validation outcomes. Without the link, the two
records are disconnected, and a reviewer must search the archive to find the manifest.

**Verification method.** Run `econflow run` with a configuration that includes a data
fetch step. Open `run_metadata.json`. Assert that `manifest_path` is a non-null
string. Confirm that the file at that path exists and is a valid `DatasetManifest` JSON.

**Status:** Missing.

---

### 8.3 Certificate Schema Backward Compatibility Is Tested

**Non-blocking**

**Requirement.** The test suite must contain a test that loads a certificate produced
by the earliest version of EconFlow that introduced `ReproducibilityCertificate` and
confirms that `ReproducibilityCertificate.from_json()` succeeds without raising an
exception. The test data must be committed to the repository as a fixture.

**Why it matters.** Schema version `1.0.0` is a commitment. It means that a certificate
written today can be read by v1.3 or v2.0 of EconFlow. Without a test that validates
backward compatibility against a real historical artifact, the commitment is
unverifiable.

**Verification method.** `pytest tests/regression/ -k test_certificate_backward_compat`
must pass. The fixture file must be a real certificate produced by a previous version.

**Status:** Missing.

---

## Section 9: Documentation

### 9.1 README Is Accurate and Current

**Blocking**

**Requirement.** The `README.md` must accurately describe: the current test count (878
as of v0.7; must be updated before v1.0), all twelve CLI commands, the five plugin
types and how to register one, the reproducibility and integrity features, and the
research workflow from `econflow init` to `econflow package`. The README must not
contain any text that was accurate only for a prior version or prior scope.

**Verification method.** A reviewer unfamiliar with the project reads the README and
then attempts to run the full workflow (`init` → `fetch` → `run` → `certify` →
`package`) on a new project. The reviewer encounters zero cases where the README
describes a command, flag, or behavior that does not exist as described.

**Status:** Missing. README reports 100 tests, does not mention integrity layer, data
ecosystem, or nine of twelve CLI commands.

---

### 9.2 All CLI Commands Have `--help` Text

**Blocking**

**Requirement.** Every CLI command and sub-command must produce non-empty, meaningful
output when run with `--help`. The help text must describe all options, provide an
example invocation, and state the command's exit code semantics.

**Verification method.** `econflow <command> --help` for each of: `init`, `doctor`,
`validate`, `info`, `run`, `report`, `certify`, `verify`, `package`, `fetch`,
`datasets`, `cache list`, `cache inspect`, `cache clear`, `cache purge`. Each must
print text describing all options. None may print only the auto-generated Typer default.

**Status:** Partial. Help text exists for all commands but examples and exit code
semantics are missing for several.

---

### 9.3 Architecture Documents Are Current

**Non-blocking**

**Requirement.** The five architecture documents in `docs/architecture/` must reflect
the v1.0 state of the codebase. Any section that describes a capability as "planned"
or "stub" must either be updated to reflect the implementation or removed.

**Verification method.** Read all five architecture documents. For each claim about
implementation status, verify against the source code. Zero discrepancies permitted.

**Status:** Partial. `DATA_ECOSYSTEM.md` was written in Sprint 8 and is current.
`MILESTONE_v0.7.md` is current. Earlier documents may contain stale information.

---

### 9.4 CHANGELOG Is Complete Through v1.0

**Non-blocking**

**Requirement.** `CHANGELOG.md` must document every sprint from Sprint 1 through the
sprint that closes the v1.0 blockers. The `## [1.0.0]` section must list the specific
issues resolved that met the v1.0 release criteria.

**Verification method.** `grep "## \[1.0.0\]" CHANGELOG.md` must return a result.
The section must reference this release criteria document.

**Status:** Partial. CHANGELOG is maintained through Sprint 8; v1.0 section does not
yet exist.

---

## Section 10: Testing

### 10.1 Test Suite Covers the Generic Pipeline End-to-End

**Blocking**

**Requirement.** At least one integration test must execute the complete workflow via
the `econflow` CLI: `init` a project, populate a `config.yaml`, run
`econflow fetch --connector csv`, run `econflow run`, run `econflow certify`,
run `econflow package`. The test must assert that the package archive contains at
minimum: a CSV results table, a `run_metadata.json`, and a `certificate.json`.

**Why it matters.** The generic pipeline integration test currently covers sub-pipeline
steps in isolation. No test exercises the full workflow from CLI to replication package
using only public interfaces. This means a regression in the CLI-to-pipeline connection
would not be caught by the test suite.

**Verification method.** `pytest tests/integration/ -k test_full_cli_workflow` must
pass. The test must invoke `subprocess.run(["econflow", ...])` rather than importing
pipeline functions directly, so that the CLI layer is exercised.

**Status:** Missing.

---

### 10.2 Coverage Exclusions Are Justified and Minimized

**Blocking**

**Requirement.** Every entry in the coverage omit list in `pyproject.toml` must have
a documented reason. Stub files are a legitimate exclusion; production code is not.
By v1.0, when all stubs are implemented, the coverage omit list must contain only:
`tests/`, `examples/`, `cli_scaffold/` (if not yet deleted), and `docs/`. No
production module in `src/econflow/` may be in the omit list.

**Why it matters.** A coverage configuration that omits large portions of the
production codebase means that coverage metrics provide false confidence. If the
omit list is not cleaned up before v1.0, coverage numbers will continue to be
uninterpretable.

**Verification method.** Run `pytest --cov=econflow --cov-report=term`. The combined
statement coverage of all non-stub production modules must exceed 80%. No module in
`src/econflow/` that is not a stub may appear in the omit list.

**Status:** Partial. The omit list is extensive and covers production code alongside
stubs.

---

### 10.3 All Tests Pass on Windows, macOS, and Linux

**Blocking**

**Requirement.** The full test suite must pass without modification on: Ubuntu 22.04
LTS, macOS 14 (arm64), and Windows 11. Tests that rely on platform-specific behavior
must be explicitly marked and handled.

**Why it matters.** EconFlow is developed primarily on Windows NTFS. Researchers using
the platform use all three operating systems. The NTFS truncation bug discovered during
Sprint 7 demonstrates that platform-specific issues can be severe. The test suite is the
mechanism for catching these issues before release.

**Verification method.** CI run against all three platforms must produce zero failures.
GitHub Actions matrix: `[ubuntu-22.04, macos-14, windows-2022]`.

**Status:** Partial. Development is on Windows; CI coverage across macOS and Linux
is not confirmed.

---

### 10.4 Tests Do Not Require Network Access

**Blocking**

**Requirement.** The test suite must pass in a network-isolated environment. All
external API calls (World Bank, OECD, FRED, Harvard Dataverse) must be mocked.
Tests that require network access must be explicitly marked `@pytest.mark.network` and
must be skipped by default (`-m "not network"`).

**Verification method.** Run `pytest -m "not network"` in an environment with all
outbound network traffic blocked (e.g., `unshare --net`). Zero failures.

**Status:** Complete. All connector tests mock network calls via `unittest.mock.patch`.

---

### 10.5 Minimum Test Count and Tier Distribution

**Non-blocking**

**Requirement.** The test suite must contain at minimum: 200 unit tests, 50 integration
tests, 10 regression tests. Total count must exceed 878 (the v0.7 baseline) by at least
50 tests added to close the gaps identified in this document. Test count must be
reported in the README.

**Verification method.** `pytest --collect-only -q | tail -1` reports the test count.
`pytest tests/unit/ --collect-only -q | tail -1` must show ≥200.
`pytest tests/integration/ --collect-only -q | tail -1` must show ≥50.
`pytest tests/regression/ --collect-only -q | tail -1` must show ≥10.

**Status:** Partial. 878 total; regression tier is thin.

---

## Section 11: Performance

### 11.1 Full Pipeline Completes Within Defined Time Bounds

**Non-blocking**

**Requirement.** On a reference machine (4-core CPU, 8 GB RAM, SSD), the following
operations must complete within the stated time bounds with a dataset of 100 countries
× 30 years: `econflow run` (all six implemented estimators + all four diagnostics)
≤ 60 seconds; `econflow certify` ≤ 5 seconds; `econflow package` ≤ 10 seconds.

**Why it matters.** A reproducibility tool that takes twenty minutes to run on a typical
academic dataset is one that researchers will use once and abandon. The bounds stated
are conservative; they are floors, not targets.

**Verification method.** Benchmark test using the reference dataset from
`tests/regression/`. `pytest tests/performance/ -k test_full_pipeline_timing`. Each
benchmark must assert completion within the bound using `time.perf_counter()`.

**Status:** Missing. No performance benchmarks exist.

---

### 11.2 Cache Operations Are O(1) in Dataset Count

**Non-blocking**

**Requirement.** `CacheManager.retrieve()` and `CacheManager.store()` must not become
slower as the number of cached datasets grows. The implementation must not scan all
cached entries to perform a single lookup.

**Why it matters.** A researcher who has cached 500 datasets must not wait longer for
a cache hit than a researcher who has cached 5. The SHA-256–keyed directory structure
implies O(1) lookups; this must be verified.

**Verification method.** Populate a cache with 1, 10, 100, and 1000 synthetic entries.
Measure `retrieve()` time at each scale. Assert that the time ratio between 1000 and 1
entries is less than 2 (i.e., no super-linear scaling).

**Status:** Missing. No cache performance tests exist.

---

## Section 12: Packaging

### 12.1 `pyproject.toml` Is Accurate and Complete

**Blocking**

**Requirement.** `pyproject.toml` must: (a) list `requests` and `openpyxl` as
required dependencies; (b) specify Python `>=3.10` as the minimum version (currently
set correctly); (c) define `[project.scripts]` with `econflow = "econflow.cli:app"`;
(d) declare `version = "1.0.0"` (or use a dynamic version tool, not a static `0.1.0`);
(e) specify a valid SPDX license identifier (`MIT`); (f) include `homepage`,
`repository`, and `documentation` URLs in `[project.urls]`.

**Why it matters.** `pyproject.toml` is the manifest that PyPI, pip, and every
downstream packaging tool reads. An inaccurate manifest produces packages that install
without required dependencies, misidentify their license, or point to incorrect URLs.

**Verification method.** `pip install econflow` in a clean environment. `import requests`
and `import openpyxl` must succeed. `econflow --help` must execute. `pip show econflow`
must display the correct version, license, and URLs.

**Status:** Missing. `requests` and `openpyxl` absent; version is `0.1.0`.

---

### 12.2 Package Installs Cleanly in a New Virtual Environment

**Blocking**

**Requirement.** `pip install econflow` in a Python 3.10, 3.11, 3.12, and 3.13
virtual environment must succeed without errors, warnings about missing extras, or
post-install instructions required before use.

**Verification method.** Matrix of four Python versions × three platforms = twelve
clean-install tests. All must exit with code 0. Immediately after install, run
`econflow doctor` and confirm it produces output (even if some optional checks fail).

**Status:** Missing. No CI clean-install matrix exists.

---

### 12.3 `cli_scaffold/` Is Excluded from the Distribution

**Blocking**

**Requirement.** The `cli_scaffold/` directory must not appear in the installed wheel.
If it is not deleted from the repository, it must be explicitly excluded in
`pyproject.toml` or `.hatchignore`.

**Verification method.** `pip install econflow`. `find $(pip show econflow | grep
Location | awk '{print $2}')/econflow -name "cli_scaffold" -type d` must return
nothing.

**Status:** Missing (the directory exists; exclusion is not verified).

---

## Section 13: Developer Experience

### 13.1 `econflow doctor` Reports Missing Optional Dependencies

**Non-blocking**

**Requirement.** `econflow doctor` must check for: `requests`, `openpyxl`, `pdflatex`
(for LaTeX rendering), and `git` (for provenance). Each check must be reported
separately with status `ok`, `missing` (but optional), or `missing` (required). Missing
required dependencies must cause `doctor` to exit non-zero.

**Verification method.** Uninstall `requests` from an EconFlow installation. Run
`econflow doctor`. Confirm the output reports `requests: MISSING (required)` and that
the exit code is non-zero.

**Status:** Partial. `doctor` runs but does not check all dependencies.

---

### 13.2 Error Messages Are Actionable

**Non-blocking**

**Requirement.** Every `EconFlowCoreError` subclass must produce a message that (a)
states what went wrong, (b) states what the user should do to fix it, and (c) does not
expose a Python traceback to the CLI user unless `--debug` is passed. The CLI must
catch all `EconFlowCoreError` subclasses and print only the message, not the traceback,
unless `--debug` is specified.

**Verification method.** Run `econflow fetch --connector nonexistent_id`. The output
must contain a user-readable message mentioning the connector ID and suggesting
`econflow datasets` to list valid IDs. The output must not contain "Traceback (most
recent call last)". Run again with `--debug`; the traceback must appear.

**Status:** Partial. Some commands catch exceptions and print clean messages; others
do not.

---

### 13.3 CONTRIBUTING.md Describes the Plugin Architecture

**Blocking**

**Requirement.** `CONTRIBUTING.md` must include a section on adding a new plugin of
each type, referencing the Plugin SDK document. It must describe the test requirements
for a new plugin (minimum: one unit test per abstract method), the lint requirements
(`ruff check`), and the process for proposing a new plugin type.

**Verification method.** Read `CONTRIBUTING.md`. Confirm it contains sections on
each plugin type with references to the Plugin SDK.

**Status:** Missing. `CONTRIBUTING.md` exists but predates the plugin architecture.

---

## Section 14: Open-Source Readiness

### 14.1 All Dependencies Are Open-Source Licensed

**Blocking**

**Requirement.** Every package in the `pyproject.toml` dependency list must be
released under an OSI-approved open-source license compatible with MIT. No GPL
dependency is permitted (GPL is incompatible with MIT distribution in most
interpretations). A license audit must be completed and documented.

**Verification method.** `pip-licenses --from=mixed --format=table` in an installed
environment. Every dependency must show an OSI-approved non-copyleft license (MIT, BSD,
Apache 2.0, LGPL are all acceptable; GPL is not).

**Status:** Partial. Likely compliant given the dependency set, but a formal audit has
not been completed.

---

### 14.2 SECURITY.md Is Current

**Non-blocking**

**Requirement.** `SECURITY.md` must describe: how to report a security vulnerability
(preferred disclosure channel, expected response time), which versions receive security
patches, and what constitutes a security-relevant bug in EconFlow (e.g., cache poisoning,
SHA-256 collision handling, API key exposure in logs).

**Verification method.** Read `SECURITY.md`. Confirm it addresses all three points.

**Status:** Partial. `SECURITY.md` exists but was written before the cache and API key
management features were added.

---

### 14.3 Example Study Is Self-Contained

**Non-blocking**

**Requirement.** `examples/ai_productivity_paper/` must contain everything needed to
replicate the study: data files (or a `fetch.sh` to download them), YAML configuration
files, and a `README.md` explaining how to run `econflow run` and `econflow package`.
The study must complete without errors on a clean EconFlow install.

**Verification method.** Start from a clean EconFlow install. Follow the instructions
in `examples/ai_productivity_paper/README.md` exactly. The pipeline must complete and
produce output consistent with the reference outputs in the directory.

**Status:** Partial. The example exists but its README predates the CLI and may not
be accurate for the current command interface.

---

## Section 15: Community Readiness

### 15.1 Issue Templates Are Configured

**Non-blocking**

**Requirement.** The repository must contain GitHub issue templates (or equivalent for
the hosting platform) for: bug report (including required fields: EconFlow version,
Python version, OS, YAML configuration, full error message); feature request; plugin
submission. Templates must request the minimum information needed to triage each issue
type.

**Verification method.** `.github/ISSUE_TEMPLATE/` must contain at least three files
corresponding to the three templates.

**Status:** Missing.

---

### 15.2 CI Is Configured and Required

**Non-blocking**

**Requirement.** A CI pipeline must run on every pull request and must: execute the
full test suite, run `ruff check`, run `ruff format --check`, and report failure if any
of these fail. The CI configuration must be committed to the repository. Merging a PR
that fails CI must be prohibited by branch protection.

**Verification method.** `.github/workflows/` (or equivalent) must contain a CI
configuration file. Attempting to merge a PR with a failing test must be rejected by
the repository host.

**Status:** Missing. No CI configuration is present in the repository.

---

### 15.3 Release Process Is Documented

**Non-blocking**

**Requirement.** `docs/development/RELEASE.md` must describe the complete release
process: how to run the release criteria checklist, how to tag a release, how to build
the wheel, how to upload to PyPI, and how to update the CHANGELOG and README.

**Verification method.** Read `RELEASE.md`. Confirm a new maintainer could follow the
instructions to produce a PyPI release without additional guidance.

**Status:** Missing.

---

## Current Readiness Score

The following assessment reflects the repository at the v0.7 milestone (2026-06-28).

### Blocking Requirements: 21 total

| ID   | Requirement                                      | Status   |
|------|--------------------------------------------------|----------|
| 1.1  | Pipeline dispatches through estimator registry   | Missing  |
| 1.2  | Single exception hierarchy                       | Partial  |
| 1.3  | Dead artifacts deleted                           | Missing  |
| 1.4  | `load_config()` implemented                      | Missing  |
| 2.1  | Public `__all__` declared                        | Partial  |
| 2.2  | No cross-package `_private` imports              | Partial  |
| 2.3  | Semver commitment documented                     | Missing  |
| 3.1  | Plugin SDK document published                    | Missing  |
| 3.2  | Plugin interfaces frozen                         | Missing  |
| 4.1  | All estimators implemented                       | Partial  |
| 4.2  | `EstimationResult` schema frozen                 | Partial  |
| 5.2  | Network connectors in `pyproject.toml`           | Missing  |
| 5.4  | Cache key stability guaranteed                   | Partial  |
| 6.2  | All figure builders implemented                  | Missing  |
| 7.2  | Integrity results in replication package         | Partial  |
| 8.2  | Provenance and manifest linked                   | Missing  |
| 9.1  | README accurate and current                      | Missing  |
| 9.2  | All CLI `--help` text complete                   | Partial  |
| 10.1 | Full pipeline end-to-end integration test        | Missing  |
| 10.2 | Coverage exclusions justified                    | Partial  |
| 10.3 | Tests pass on Windows, macOS, and Linux          | Partial  |
| 12.1 | `pyproject.toml` accurate and complete           | Missing  |
| 12.2 | Clean install on all Python versions             | Missing  |
| 12.3 | `cli_scaffold/` excluded from distribution       | Missing  |
| 13.3 | `CONTRIBUTING.md` updated for plugin arch        | Missing  |
| 14.1 | All dependencies OSI-licensed                    | Partial  |

**Blocking Complete:** 0 / 26  
**Blocking Partial:** 10 / 26  
**Blocking Missing:** 16 / 26

**Overall v1.0 gate: CLOSED**

---

## Major Blockers

In order of architectural severity:

**Blocker 1: Pipeline-Registry Disconnection.** The primary user-facing workflow
(`econflow run`) bypasses the estimation registry. This is the central promise of the
platform's extensibility, and it is currently unmet. Nothing else in v1.0 matters more
than closing this gap.

**Blocker 2: Plugin SDK Absence.** Without a Plugin SDK document and frozen interfaces,
EconFlow cannot be a platform for third-party extension. The plugin architecture exists
in code; it does not yet exist as a contract. Releasing v1.0 without the Plugin SDK
would be releasing a platform with no documented extension point.

**Blocker 3: `load_config()` Unimplemented.** Every CLI command accepts `--config`
and silently ignores its configuration validation. This means a researcher who
misspells a column name or specifies an invalid year range receives a runtime error
rather than a configuration error. This is a reliability failure in the primary user
workflow.

**Blocker 4: Figure Builder Stubs.** Five of seven registered figure builders raise
`NotImplementedError`. The `econflow report` command cannot produce a complete
publication bundle. A reporting engine that cannot produce figures is not a reporting
engine.

**Blocker 5: Packaging Defects.** `requests` and `openpyxl` are absent from
`pyproject.toml`; the version number is `0.1.0`; CI does not exist. A package that
installs without its required dependencies, carries the wrong version number, and has
no automated test gate is not ready for public release.

---

## Recommended Order for Remaining Work

The following sequence minimizes integration risk and maximizes each sprint's
contribution to the release criteria.

**Sprint 9 (Integration and Configuration)**

1. Implement `load_config()` (Requirement 1.4). This unblocks semantic configuration
   validation in every CLI command and closes the most visible gap between the typed
   model and the running code.
2. Integrate `pipeline_generic.py` with the estimator registry (Requirement 1.1).
   This is the single highest-priority architectural item. It must be accompanied by
   a full-pipeline integration test (Requirement 10.1).
3. Link provenance record and dataset manifest (Requirement 8.2). Short implementation
   after the pipeline integration is complete.
4. Delete dead artifacts (Requirement 1.3). `cli_scaffold/`, root-level stubs, and the
   legacy `pipeline.py`.

**Sprint 10 (Stubs and SDK)**

5. Implement System GMM and Panel Quantile estimators (Requirement 4.1).
6. Implement all five figure builder stubs (Requirement 6.2).
7. Implement Wooldridge and serial correlation diagnostics (Requirement 4.1-parallel).
8. Write the Plugin SDK document and freeze interfaces (Requirements 3.1, 3.2).

**Sprint 11 (Packaging, CI, and API)**

9. Fix `pyproject.toml`: add `requests` and `openpyxl`, update version, add URLs
   (Requirement 12.1).
10. Configure CI for matrix testing on Windows, macOS, Linux, Python 3.10-3.13
    (Requirements 10.3, 12.2).
11. Write `VERSIONING.md` and conduct TSC review of `__all__` surfaces
    (Requirements 2.1, 2.3).
12. Audit cross-package private name references (Requirement 2.2).
13. Remove `APRPError` alias (Requirement 1.2).

**Sprint 12 (Documentation and Open-Source Readiness)**

14. Update README with accurate test count, all CLI commands, all features
    (Requirement 9.1).
15. Update `CONTRIBUTING.md` for plugin architecture (Requirement 13.3).
16. Write `VERSIONING.md`, `RELEASE.md`, issue templates, CI branch protection
    (Requirements 2.3, 15.2, 15.3).
17. Complete license audit (Requirement 14.1).
18. Update example study README (Requirement 14.3).

**Pre-release (RC1 Gate)**

19. TSC sign-off on `EstimationResult` schema (Requirement 4.2).
20. TSC sign-off on plugin interface freeze (Requirement 3.2).
21. Performance benchmarks (Requirement 11.1).
22. LaTeX compile test (Requirement 6.3).
23. Run full clean-install matrix; verify `econflow doctor` behavior (Requirements
    12.2, 13.1).
24. Update CHANGELOG with `## [1.0.0]` section referencing this document.

---

*This document is a governing instrument of the EconFlow Technical Steering Committee.
It supersedes all informal discussions of v1.0 requirements. Amendments require TSC
review and must be documented with the date of amendment and the rationale for change.*

*EconFlow Technical Steering Committee — 2026-06-28*
