# EconFlow Architecture Freeze v1

**Status:** FROZEN  
**Date:** 2026-07-10  
**Applies to:** All changes between Phase 0 and Phase 7 of the EstimationDispatcher migration  
**Authority:** Principal architect  
**Enforcement:** Every PR that touches a frozen interface must include a checklist sign-off (§4)

This document defines the stable public contracts that must not change during the migration. It is the authoritative reference for dispute resolution when a proposed change conflicts with migration safety. Read it before writing a single line of migration code.

---

## 1. Stable Interfaces

### 1.1 `BaseEstimator` (`econflow.estimation.base`)

**What it is.** The abstract base class every estimator plugin must inherit from. The migration wires `EstimationDispatcher` to call `.run(df)` on instances of this class. Any change to the abstract interface forces a change to every concrete estimator simultaneously — a coordination hazard that defeats the purpose of a phased migration.

**Frozen abstract methods:**

```python
def validate(self, data: pd.DataFrame | Dataset) -> None: ...
def fit(self, data: pd.DataFrame | Dataset) -> EstimationResult: ...
def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]: ...
```

Each method's signature, return type, and contract (validate raises on invalid data; fit returns an EstimationResult; diagnostics returns a list, possibly empty) are frozen.

**Frozen concrete method:**

```python
def run(self, data: pd.DataFrame | Dataset) -> EstimationResult:
    # calls validate(), fit(), diagnostics() in that order
    # attaches diagnostic_results to the returned EstimationResult
```

`run()` is the single callable that `EstimationDispatcher.dispatch()` invokes. Its three-step chain (validate → fit → diagnostics) must not be reordered or interrupted.

**Frozen class attributes:**

```python
backend: str = "unknown"       # overridden by each concrete class
estimator_id: str              # set by @register_estimator(); do not set manually
```

**Frozen helper methods** (called by concrete estimators; must remain compatible):

```python
def _resolve_dataframe(self, data) -> pd.DataFrame: ...
def _to_panel(self, df, entity_col, time_col) -> pd.DataFrame: ...   # deprecated alias, keep
def _backend_capabilities(self) -> dict: ...
def _provenance_stamp(self) -> dict: ...
```

**Frozen registration decorator:**

```python
from econflow.estimation import register_estimator

@register_estimator("my_id", label="...", backend="linearmodels")
class MyEstimator(BaseEstimator): ...
```

`register_estimator` is the canonical name. `register` is kept as a deprecated alias and must not be removed during the migration. The `backend=` keyword argument must continue to be optional (falls back to `cls.backend`).

**What may change:** docstrings, internal implementation of concrete helper methods (not signatures), addition of new optional keyword arguments to `_provenance_stamp()`.

---

### 1.2 `EstimationResult` (`econflow.estimation.result`)

**What it is.** The dataclass returned by every estimator's `fit()` and `run()` methods. It is consumed by diagnostics, renderers, integrity checks, and (after Phase 5) the pipeline. Changing its field names or types breaks every one of those consumers simultaneously.

**Frozen dataclass fields (names, types, defaults):**

```python
@dataclass
class EstimationResult:
    estimator_id:       str
    estimator_name:     str               = ""
    params:             pd.Series         = ...   # coefficients, indexed by regressor name
    std_err:            pd.Series         = ...   # NOT std_errors (linearmodels uses std_errors)
    conf_int:           pd.DataFrame      = ...   # pd.DataFrame field, NOT a method
    pvalues:            pd.Series         = ...
    nobs:               int               = 0
    ngroups:            int | None        = None
    df_resid:           float | None      = None
    rsquared:           float             = 0.0
    rsquared_adj:       float             = 0.0
    f_statistic:        float | None      = None
    f_pvalue:           float | None      = None
    entity_col:         str               = "entity"
    time_col:           str               = "time"
    entities:           list              = field(default_factory=list)
    time_periods:       list              = field(default_factory=list)
    diagnostic_results: list              = field(default_factory=list)
    warnings:           list[str]         = field(default_factory=list)
    provenance:         dict              = field(default_factory=dict)
    extra:              dict              = field(default_factory=dict)
```

**Critical naming invariant:** the field is `std_err`, not `std_errors`. The linearmodels library uses `result.std_errors` (a property on PanelResults). EconFlow's `EstimationResult` uses `std_err` (singular). Conflating these is the single most likely source of silent data errors during the migration. Every code path that touches standard errors must use the correct name for the correct object.

**Critical type invariant:** `conf_int` is a `pd.DataFrame` field on `EstimationResult`. It is NOT a method. Contrast with linearmodels `PanelResults`, where `conf_int` is a method that must be called as `res.conf_int()`. Any code reading confidence intervals from a linearmodels result object must call `res.conf_int()` before assigning to `EstimationResult.conf_int`.

**Frozen property:**

```python
@property
def tvalues(self) -> pd.Series:
    return self.params / self.std_err
```

**Frozen methods:**

```python
def summary_frame(self) -> pd.DataFrame: ...
def to_dict(self) -> dict: ...
def to_json(self, *, indent: int = 2) -> str: ...
```

**What may change:** addition of new optional fields with default values (additive, backward-compatible); docstrings.

---

### 1.3 `DiagnosticResult` (`econflow.estimation.result`)

**What it is.** The dataclass returned by each `BaseDiagnostic.run()` call, assembled into a list by `BaseEstimator.diagnostics()`, and stored in `EstimationResult.diagnostic_results`.

**Frozen dataclass fields:**

```python
@dataclass
class DiagnosticResult:
    diagnostic_id:   str
    diagnostic_name: str
    statistic:       float | None = None
    pvalue:          float | None = None
    conclusion:      str          = ""
    level:           str          = "info"    # "info" | "warning" | "error" | "skip"
    # Corrected 2026-07-18 against src/econflow/estimation/result.py and a
    # repo-wide grep confirming "warn"/"fail" occur zero times in source.
    estimator_id:    str          = ""        # set in Sprint 6 RC2 fix; must not be removed
    extra:           dict         = field(default_factory=dict)
```

**Frozen methods:**

```python
def to_dict(self) -> dict: ...
@classmethod
def from_dict(cls, data: dict) -> DiagnosticResult: ...
```

---

### 1.4 `PipelineContext` (to be created in Phase 2 at `econflow.estimation.dispatcher`)

**What it is.** A frozen dataclass carrying project-level configuration that the dispatcher needs to inject into each estimator's params dict. It does not exist yet. Its specification is frozen here so that Phase 2 implementation has no design latitude — it must match exactly.

**Frozen specification:**

```python
@dataclass(frozen=True)
class PipelineContext:
    entity_col: str
    time_col:   str
```

No other fields. `frozen=True` is mandatory — `PipelineContext` instances must be immutable so that dispatcher calls cannot mutate shared state. If additional project-level parameters are needed in a later phase, they are added as optional fields with defaults; the `frozen=True` constraint stays.

**Export requirement:** `PipelineContext` must be exported from `econflow.estimation.__init__` after Phase 2.

---

### 1.5 `EstimationDispatcher` (to be created in Phase 2 at `econflow.estimation.dispatcher`)

**What it is.** The single authoritative translator between YAML model specs and instantiated estimators. It does not exist yet. Its API is frozen here.

**Frozen method signatures:**

```python
class EstimationDispatcher:

    @staticmethod
    def resolve_id(spec: dict) -> str:
        """
        Translate a YAML estimator string to a registry key.

        Rules (applied in order):
        1. Lowercase the input.
        2. "fe" with entity_effects=True, time_effects=True  → "twfe"
        3. "fe" with entity_effects=False, time_effects=False → "ols" + DeprecationWarning
        4. All other strings: pass through as-is.
        """

    @staticmethod
    def build(spec: dict, context: PipelineContext) -> BaseEstimator:
        """
        Resolve the estimator class and return an instantiated (unrun) estimator.

        Merges context.entity_col and context.time_col into the params dict.
        Translates the YAML cluster field:
            cluster: "entity" → cov_type: "clustered", cluster_entity: True
            cluster: "time"   → cov_type: "clustered", cluster_time: True
            absent             → cov_type: "robust"   (current pipeline default)
        """

    @staticmethod
    def dispatch(spec: dict, df: pd.DataFrame, context: PipelineContext) -> EstimationResult:
        """
        Build the estimator and call estimator.run(df). Two lines exactly:
            estimator = EstimationDispatcher.build(spec, context)
            return estimator.run(df)
        """
```

**Cluster-translation invariant.** The covariance defaults produced by `build()` must reproduce the current pipeline_generic.py defaults exactly. As of the Phase 0 baseline:

- `cluster: "entity"` → `cov_type="clustered"`, `cluster_entity=True` (used by entity_fe and twoway_fe)
- absent `cluster` → `cov_type="unadjusted"` for PooledOLS, `cov_type="robust"` for others

Any deviation from these defaults will produce coefficients that match the Phase 0 baseline but standard errors that diverge. The Phase 5 regression gate will catch this.

---

### 1.6 CLI Contract (`econflow` entry point, `econflow.cli:app`)

**What it is.** The user-facing command surface. Researchers build scripts, makefiles, and replication packages around these commands. Renaming, removing, or changing the required arguments of any command is a breaking change for users.

**Frozen commands and their required arguments:**

| Command | Required arguments |
|---|---|
| `econflow run` | `--config`, `--models`, `--outputs` |
| `econflow validate` | none required (accepts `--config`) |
| `econflow init [DIRECTORY]` | directory is optional |
| `econflow doctor` | none |
| `econflow info` | none |
| `econflow report [OUTPUT_DIR]` | output_dir is optional |
| `econflow certify` | `--project-name`, `--data`, `--config` |
| `econflow verify` | `--baseline` |
| `econflow package` | `--certificate` |
| `econflow fetch <CONNECTOR_ID>` | connector id positional |
| `econflow cache list\|inspect\|clear\|purge` | subcommand positional |
| `econflow datasets` | none |
| `econflow release-check` | none |

**Frozen exit codes:** 0 = success, 1 = any error or failed check. These must not change — CI pipelines depend on them.

**What may change:** adding new optional flags to existing commands; adding new commands entirely (additive); changing help text and docstrings.

**What must not change:** removing commands; removing required positional arguments; renaming commands; changing the registered entry-point `econflow.cli:app`.

---

### 1.7 YAML Configuration Schema

**What it is.** The three-file configuration schema that every EconFlow project uses. The migration must not require users to update their existing config files.

**Frozen `config.yaml` keys:**

```yaml
project:
  name:        str      # required
  description: str      # optional

data:
  path:             str          # required
  entity_col:       str          # required
  time_col:         str          # required
  required_columns: list[str]    # optional

sample:
  start_year: int    # optional
  end_year:   int    # optional

variables:
  dependent:  str         # required
  regressors: list[str]   # required
```

**Frozen `models.yaml` keys:**

```yaml
models:
  - id:             str       # required, unique
    label:          str       # optional
    estimator:      str       # required; one of "OLS", "FE", "TWFE", "RE", "FD", "IV", or registry key
    dependent:      str       # required
    regressors:     list[str] # required
    entity_effects: bool      # optional, default false
    time_effects:   bool      # optional, default false
    cluster:        str       # optional; "entity" | "time" | absent
    description:    str       # optional
```

**Frozen `outputs.yaml` keys:**

```yaml
outputs:
  base_dir: str    # relative path

  tables:
    dir:     str
    formats: list[str]    # e.g. ["csv", "latex"]
    comparison_table:
      filename: str
      models:   list[str]
      stars:    bool
      se_type:  str

  figures:
    dir:     str
    enabled: bool
```

**What must not change:** the key names above; the semantics of `entity_effects`/`time_effects` (they control FE adapter logic in `EstimationDispatcher.resolve_id()`); the `cluster` field semantics.

**What may change:** adding new optional keys with documented defaults (backward-compatible); relaxing strict validation to accept additional formats.

---

### 1.8 Plugin SDK

**What it is.** The public API through which external packages extend EconFlow. PLUGIN_SDK.md v1.0 is the authoritative specification. The contracts below are the minimum required for migration safety.

**Frozen plugin entry-point group:** `econflow.plugins`

**Frozen plugin base classes and registration decorators:**

| Plugin type | Base class | Canonical decorator | Import path |
|---|---|---|---|
| Estimator | `BaseEstimator` | `@register_estimator(id)` | `econflow.estimation` |
| Connector | `AbstractConnector` | `@register_connector(id)` | `econflow.ingestion` |
| Diagnostic | `BaseDiagnostic` | `@register_diagnostic(id)` | `econflow.diagnostics` |
| Integrity check | `BaseIntegrityCheck` | `@register_integrity_check(id)` | `econflow.integrity` |
| Renderer | `BaseRenderer` | `@register_renderer(id)` | `econflow.outputs` |

**Deprecated aliases that must not be removed during migration:**

- `register` (alias for `register_estimator` in `econflow.estimation.registry`)

**Frozen entry-point auto-loading behaviour:** plugins declared under `[project.entry-points."econflow.plugins"]` are auto-loaded when `econflow.estimation.registry` is first imported. This behaviour must not change — removing it silently breaks all installed plugins.

---

### 1.9 Reporting Interfaces (`econflow.outputs`)

**What it is.** The table/figure model layer that decouples builders from renderers. The migration does not touch this layer, but any Phase 5 or Phase 6 diagnostic output that flows into reports must produce `ReportTable` and `ReportFigure` objects conforming to these contracts.

**Frozen `BaseRenderer` interface:**

```python
class BaseRenderer(abc.ABC):
    renderer_id:    str = "base"
    name:           str = "BaseRenderer"
    file_extension: str = ".txt"

    @abc.abstractmethod
    def render(self, table: ReportTable, **kwargs) -> str: ...

    def render_to_file(self, table: ReportTable, path: Path, *, encoding="utf-8", **kwargs) -> Path: ...
```

**Frozen `ReportTable` dataclass fields:**

```python
@dataclass
class ReportTable:
    title:      str
    table_type: str    # "regression" | "summary_stats" | "diagnostics" | ...
    columns:    list[str]
    rows:       list[TableRow]
    footer:     list[str]
    subtitle:   str
    notes:      str
    metadata:   dict
```

**Frozen `TableRow` dataclass fields:**

```python
@dataclass
class TableRow:
    label:    str
    cells:    dict[str, str]
    sub_cells: dict[str, str] | None
    row_type: str    # "data" | "separator" | "stats" | "header"
    bold:     bool
    italic:   bool
```

**Frozen `ReportFigure` dataclass fields:**

```python
@dataclass
class ReportFigure:
    title:       str
    figure_type: str
    data:        dict
    config:      dict
    metadata:    dict
```

---

### 1.10 Integrity Interfaces (`econflow.integrity`)

**What it is.** The reproducibility certificate and drift-detection layer. The migration does not modify this layer. Phase 7 may add integrity checks for dispatcher-vs-pipeline output equivalence — those checks must conform to the frozen interface below.

**Frozen `BaseIntegrityCheck` interface:**

```python
class BaseIntegrityCheck(abc.ABC):
    check_id:              str       # set by @register_integrity_check()
    name:                  str
    description:           str
    supported_estimators:  list[str] # ["*"] means all

    @abc.abstractmethod
    def run(self, result: EstimationResult, **kwargs) -> IntegrityCheckResult: ...

    def supports(self, estimator_id: str) -> bool: ...
```

**Frozen `IntegrityCheckResult` dataclass fields:**

```python
@dataclass
class IntegrityCheckResult:
    check_id: str
    name:     str
    status:   str    # "pass" | "warn" | "fail" | "skip"
    message:  str
    extra:    dict
```

**Frozen fingerprint factories (used to build reproducibility certificates):**

```python
EnvironmentFingerprint.capture(*, repo_root=None) -> EnvironmentFingerprint
DataFingerprint.from_path(path: str | Path) -> DataFingerprint
ConfigFingerprint.from_path(path: str | Path) -> ConfigFingerprint
```

---

## 2. Architectural Invariants

These are properties that must hold true at the end of every phase. A phase that violates any invariant is not complete, regardless of whether its tests pass.

**I-1: Numerical identity.** At every phase boundary, `run_from_config()` on the getting-started example must produce output within 1e-10 of the Phase 0 baseline for all coefficients, standard errors, t-statistics, p-values, confidence intervals, R² values, and log-likelihoods. Diagnostic statistics must be within 1e-6. `test_pipeline_baseline.py` is the enforcement mechanism.

**I-2: Single execution path.** At any given phase, there is exactly one code path that executes a model: either the legacy `_run_model()` in `pipeline_generic.py` (Phases 0–4), or `EstimationDispatcher.dispatch()` (Phases 5–7). There is no phase where both paths execute simultaneously for the same model. Shadowing, fallback chains, and A/B routing are forbidden.

**I-3: Provenance completeness.** Every run that produces output must also produce a `run_metadata.json` containing all required provenance keys: `run_id`, `timestamp`, `econflow_version`, `python_version`, `platform`, `inputs`, `input_hashes`, `models_run`. The set of required keys must not shrink.

**I-4: Data hash stability.** The SHA-256 of `grunfeld.csv` must equal `d73bb76112ccf74ef6c85d4780e7dc0fb7ded7c671f1f51cd94831b3472f2ff9` for any run that uses that dataset. Any run producing a different hash is operating on corrupted or substituted data.

**I-5: Formatted output stability.** The string content of `comparison_table.csv`, `comparison_table.tex`, `comparison_table.md`, and `comparison_table.html` must be character-identical to the Phase 0 baseline files at every phase boundary. Formatting functions (`_stars()`, `_fmt_coef()`, `_fmt_se()`, `_fmt_r2()`) must not change during the migration.

**I-6: Estimator registry integrity.** The three estimators exercised by the getting-started example must remain registered and resolvable at all times: `econflow.estimation.registry.get_estimator()` must not raise `RegistryError` for the registry keys `"ols"`, `"fe"`, and `"twfe"` at any point during the migration. (Corrected 2026-07-18: `pooled_ols`, `entity_fe`, and `twoway_fe` are the model-*instance* `id:` values in `examples/getting_started/config/models.yaml`, not registry keys — `get_estimator("pooled_ols")` raises `RegistryError`. The dispatcher resolves each model spec's `estimator:` field, or infers from `entity_effects`/`time_effects`, to one of the three canonical registry keys above; see `dispatcher.py`'s `resolve_id()`.)

**I-7: No silent failures.** Any exception raised inside `BaseEstimator.run()` must propagate to the caller. Neither the dispatcher nor the pipeline may swallow exceptions and return a synthetic result. The only permitted exception-handling is at the pipeline level where a per-model failure is logged and the run continues with remaining models (if that is the existing behaviour).

**I-8: Plugin backward compatibility.** Any estimator plugin written against PLUGIN_SDK.md v1.0 and installed via `econflow.plugins` entry point must continue to load, register, and execute correctly after each migration phase. The migration must not require plugin authors to update their code.

---

## 3. Forbidden Changes

The following changes are explicitly prohibited during Phases 1–7. If a proposed change appears on this list, it requires a separate design review outside the migration process.

**F-1: Do not rename `EstimationResult.std_err`.** The field name `std_err` is baked into every diagnostic plugin, every test that asserts on standard errors, and every renderer that formats them. Renaming it to `std_errors` (to match linearmodels) would require a coordinated update across 20+ files and invalidates the Phase 0 fixture assertions.

**F-2: Do not change `EstimationResult.conf_int` from a field to a method.** It is a `pd.DataFrame` field. Any code that calls `result.conf_int()` (as if it were a method) has a bug. The field must remain a field.

**F-3: Do not modify `pipeline_generic.py` formatting functions.** `_stars()`, `_fmt_coef()`, `_fmt_se()`, `_fmt_r2()`, `_write_latex()`, `_write_markdown()`, `_write_html()` determine the string content of every formatted output. Any change to these functions invalidates the Phase 0 baseline and requires recapturing all fixture files before migration can continue.

**F-4: Do not add required arguments to `BaseEstimator.validate()`, `fit()`, or `diagnostics()`.** The signatures are `validate(self, data)`, `fit(self, data) -> EstimationResult`, `diagnostics(self, result) -> list[DiagnosticResult]`. Existing plugins call them with exactly these arguments.

**F-5: Do not change the `run_from_config()` public entry point signature.** Code that calls `run_from_config()` directly (scripts, CI pipelines, tests) must continue to work without modification.

**F-6: Do not remove the `register` alias from `econflow.estimation.registry`.** It is a deprecated but still-functional alias for `register_estimator`. Removing it during the migration breaks any plugin that was written before the canonical name was established.

**F-7: Do not change the provenance required-keys schema.** The set of required keys in `run_metadata.json` is asserted by `TestProvenance` in `test_pipeline_baseline.py`. Removing or renaming keys causes that test to fail, which blocks all subsequent phases.

**F-8: Do not introduce non-determinism.** No migration phase may introduce random seeds, shuffled data structures, or timestamp-dependent logic into the model execution path. Results must be byte-for-byte reproducible given the same inputs and package versions.

**F-9: Do not modify `decimal_places` defaults.** The pipeline defaults to `decimal_places=4`. The Phase 0 fixture files were captured with this value. Changing the default changes every formatted output string and invalidates five fixture files simultaneously.

**F-10: Do not move the active CLI entry point.** The entry point `econflow = "econflow.cli:app"` in `pyproject.toml` must not change. The scaffold CLI at `cli_scaffold/main.py` is the future CLI (Phase 4) but must not be registered as `econflow` until that phase is explicitly executed and the Phase 0 tests are re-verified against it.

---

## 4. PR Review Checklist

Every pull request that touches any of the following paths must have this checklist completed in the PR description before merge:

**Paths that require checklist sign-off:**

- `src/econflow/estimation/`
- `src/econflow/pipeline_generic.py`
- `src/econflow/outputs/`
- `src/econflow/integrity/`
- `src/econflow/cli.py`
- `src/econflow/commands/`
- `tests/integration/`
- `pyproject.toml` (entry-points section)

---

```
## Architecture Freeze Checklist

### Numerical Baseline (mandatory for any estimation or pipeline change)
- [ ] `test_pipeline_baseline.py` passes with zero failures
- [ ] No coefficient, SE, p-value, or R² has changed relative to Phase 0 baseline
      (or: this phase intentionally changes the execution path, and the MIGRATION_ROADMAP.md
       explicitly permits this phase to alter numerical output — cite the section)

### Interface Stability
- [ ] No abstract method of BaseEstimator has had its signature changed
- [ ] No field of EstimationResult has been renamed, removed, or had its type changed
- [ ] EstimationResult.std_err is still named std_err (not std_errors)
- [ ] EstimationResult.conf_int is still a pd.DataFrame field (not a method)
- [ ] DiagnosticResult.estimator_id is still present
- [ ] All forbidden changes F-1 through F-10 have been checked and none applies

### CLI and Configuration
- [ ] No CLI command has been renamed or had a required argument removed
- [ ] No YAML config key has been renamed or removed
- [ ] The entry point econflow.cli:app is unchanged in pyproject.toml

### Plugin Compatibility
- [ ] The register_estimator decorator still works with just an id argument
- [ ] The register alias still works (not removed)
- [ ] Auto-loading via econflow.plugins entry-point group still fires on first import
- [ ] A plugin written against PLUGIN_SDK.md v1.0 would still work unchanged

### Provenance and Integrity
- [ ] run_metadata.json still contains all required keys from provenance_schema.json
- [ ] SHA-256 of grunfeld.csv is unchanged (d73bb76112...)
- [ ] BaseIntegrityCheck.run() signature is unchanged

### Test Coverage
- [ ] New or modified code paths have corresponding tests
- [ ] No existing test has been deleted (only additions and modifications permitted)
- [ ] If a test was modified: the modification makes it stricter, not more permissive

### Phase Gate
- [ ] This PR corresponds to exactly one phase in MIGRATION_ROADMAP.md (cite the phase)
- [ ] The completion criteria for that phase are all met
- [ ] The next phase's preconditions are satisfied by this PR's changes
```

---

## Appendix: Interface Provenance

| Interface | Source file | First implemented |
|---|---|---|
| `BaseEstimator` | `src/econflow/estimation/base.py` | Sprint 5 |
| `EstimationResult` | `src/econflow/estimation/result.py` | Sprint 5 |
| `DiagnosticResult` | `src/econflow/estimation/result.py` | Sprint 5; `estimator_id` field added Sprint 6 RC2 |
| `PipelineContext` | `src/econflow/estimation/dispatcher.py` | Phase 2 (2026-07-10) |
| `EstimationDispatcher` | `src/econflow/estimation/dispatcher.py` | Phase 2 (2026-07-10) |
| CLI contract | `src/econflow/cli.py` | Sprint 3B |
| YAML schema | `examples/getting_started/config/*.yaml` | Sprint 11 |
| Plugin SDK | `docs/sdk/PLUGIN_SDK.md` | v1.0 (2026-07-06) |
| `BaseRenderer` / `ReportTable` | `src/econflow/outputs/base.py`, `model.py` | Sprint 6 |
| `BaseIntegrityCheck` | `src/econflow/integrity/checks/base.py` | Sprint 7 |
| Fingerprint factories | `src/econflow/integrity/fingerprint.py` | Sprint 7 |

| Baseline fixture | Location | SHA captured |
|---|---|---|
| `numerical_results.json` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
| `diagnostics_full.json` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
| `diagnostics.csv` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
| `comparison_table.csv` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
| `comparison_table.tex` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
| `comparison_table.md` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
| `comparison_table.html` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
| `provenance_schema.json` | `tests/integration/fixtures/baseline/` | 2026-07-10 |
