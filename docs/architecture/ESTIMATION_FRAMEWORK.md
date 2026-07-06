# Estimation Framework

**EconFlow — Sprint 5 Architecture**

This document describes the plugin-based estimation framework introduced in Sprint 5.
Every estimator is a first-class object: it validates its inputs, fits a model,
runs diagnostics, and returns a rich, serialisable result — all through a single
`run()` call.

---

## Design Goals

**Uniformity** — every estimator exposes the same `run(data) → EstimationResult`
interface regardless of the underlying library.

**Discoverability** — `@register()` makes new estimators appear in `econflow info`,
`econflow validate`, and `list_estimators()` automatically — no manual registry
updates.

**Reproducibility** — `EstimationResult` embeds full provenance: estimator id,
EconFlow version, UTC timestamp, and run parameters.

**Extensibility** — add an estimator by creating one file and one decorator; add a
diagnostic by creating one file and one decorator.

**Backward compatibility** — `from econflow.estimation.base import EstimationResult`
continues to work; the class has moved to `result.py` but is re-exported.

---

## Module Map

```
src/econflow/estimation/
├── __init__.py          Public API re-exports; imports all built-ins (triggers @register())
├── registry.py          @register() decorator, get_estimator(), list_estimators()
├── base.py              BaseEstimator ABC, EstimatorError (re-exports result types)
├── result.py            EstimationResult, DiagnosticResult dataclasses
├── ols.py               PooledOLS          [implemented]
├── fixed_effects.py     EntityFE, TwoWayFE [implemented]
├── random_effects.py    RandomEffects      [implemented]
├── first_difference.py  FirstDifference    [implemented]
├── iv.py                IV2SLS             [implemented]
├── gmm.py               SystemGMM          [stub]
└── quantile.py          PanelQuantile      [stub]

src/econflow/diagnostics/
├── __init__.py          Public API; imports all plugins (triggers @register_diagnostic())
├── registry.py          @register_diagnostic(), get_diagnostic(), list_diagnostics()
├── base.py              BaseDiagnostic ABC, DiagnosticError
└── plugins/
    ├── __init__.py      Imports all 6 plugins to trigger registration
    ├── hausman.py       Hausman endogeneity test       [implemented]
    ├── breusch_pagan.py Breusch-Pagan heteroskedasticity [implemented]
    ├── pesaran_cd.py    Pesaran cross-sectional dependence [implemented]
    ├── vif.py           Variance Inflation Factor       [implemented]
    ├── wooldridge.py    Wooldridge serial correlation   [stub]
    └── serial_correlation.py  AR(1)/AR(2) test          [stub]
```

---

## Estimator Registry

### Registration

```python
from econflow.estimation.registry import register
from econflow.estimation.base import BaseEstimator

@register(
    "myfe",
    label="My Fixed Effects",
    status="implemented",
    notes="Entity FE via statsmodels",
    supported_data=["balanced_panel"],
)
class MyFE(BaseEstimator):
    ...
```

The decorator runs at import time. `econflow.estimation.__init__` imports all
built-in modules, so they are registered as soon as `import econflow.estimation`
runs. Third-party plugins register on their own import.

### Resolution

```python
from econflow.estimation.registry import get_estimator

cls = get_estimator("twfe")   # raises RegistryError if not found
result = cls(params).run(data)
```

### Introspection

```python
from econflow.estimation.registry import list_estimators

for entry in list_estimators():
    print(entry["id"], entry["status"], entry["label"])
```

`list_estimators()` drives both `econflow info` (estimator table) and
`econflow validate` (`_SUPPORTED_ESTIMATORS` frozenset). Neither module
hard-codes estimator IDs.

---

## BaseEstimator

```
BaseEstimator (abstract)
├── Class attributes: estimator_id, name, description,
│                     supported_data, required_parameters, optional_parameters
├── __init__(params: dict | None)
├── validate(data: pd.DataFrame) → None          [abstract]
├── fit(data: pd.DataFrame) → EstimationResult   [abstract]
├── diagnostics(result: EstimationResult)
│       → list[DiagnosticResult]                 [abstract]
├── predict(result, newdata=None) → pd.Series    [raises NotImplementedError]
├── run(data) → EstimationResult                 [concrete: validate→fit→diagnostics]
└── Helpers
    ├── _require_params(*keys)     raises EstimatorError on missing param
    ├── _require_columns(df, *cols) raises EstimatorError on missing column
    ├── _to_panel(df, entity, time) → MultiIndex DataFrame (sorted)
    └── _provenance_stamp()        → dict with estimator_id, version, timestamp
```

### The `run()` chain

```python
def run(self, data):
    self.validate(data)          # raises EstimatorError on bad input
    result = self.fit(data)      # raises EstimatorError on fitting failure
    result.diagnostic_results = self.diagnostics(result)
    return result
```

All three steps are mandatory. `validate()` should check params and columns;
`fit()` does the econometric work; `diagnostics()` can return `[]` for simple
estimators.

---

## Result Objects

### EstimationResult

Rich dataclass returned by every `fit()` call.

| Field | Type | Description |
|-------|------|-------------|
| `estimator_id` | `str` | Registry key |
| `estimator_name` | `str` | Human label |
| `params` | `pd.Series` | Coefficient vector |
| `std_err` | `pd.Series` | Standard errors |
| `conf_int` | `pd.DataFrame` | Columns `["lower", "upper"]` |
| `pvalues` | `pd.Series` | Two-sided p-values |
| `nobs` | `int` | Observations used |
| `ngroups` | `int` | Entities in panel |
| `df_resid` | `int` | Residual df |
| `rsquared` | `float` | Within/overall R² |
| `rsquared_adj` | `float` | Adjusted R² |
| `f_statistic` | `float\|None` | F-statistic |
| `f_pvalue` | `float\|None` | F p-value |
| `entity_col` | `str` | Entity column name |
| `time_col` | `str` | Time column name |
| `entities` | `list[str]` | Unique entity ids |
| `time_periods` | `list` | Unique time periods |
| `diagnostic_results` | `list[DiagnosticResult]` | Attached diagnostics |
| `warnings` | `list[str]` | Non-fatal warnings |
| `provenance` | `dict` | Stamp from `_provenance_stamp()` |
| `extra` | `dict` | Estimator-specific metadata |

Computed properties: `tvalues` (`params / std_err`), `summary_frame()` (6-column DataFrame).
Serialisation: `to_dict()`, `to_json()`.

### DiagnosticResult

| Field | Type | Description |
|-------|------|-------------|
| `diagnostic_id` | `str` | Registry key |
| `diagnostic_name` | `str` | Human label |
| `statistic` | `float\|None` | Test statistic |
| `pvalue` | `float\|None` | P-value |
| `conclusion` | `str` | Plain-English verdict |
| `level` | `str` | `"info"`, `"warn"`, `"error"`, `"skip"` |
| `extra` | `dict` | Diagnostic-specific payload |

Serialisation: `to_dict()`, `to_json()`, `from_dict()`.

---

## Built-in Estimators

| ID | Class | Library | Status |
|----|-------|---------|--------|
| `ols` | `PooledOLS` | `linearmodels.PooledOLS` | implemented |
| `fe` | `EntityFE` | `linearmodels.PanelOLS(entity_effects=True)` | implemented |
| `twfe` | `TwoWayFE` | `linearmodels.PanelOLS(entity+time effects)` | implemented |
| `re` | `RandomEffects` | `linearmodels.RandomEffects` | implemented |
| `fd` | `FirstDifference` | `linearmodels.FirstDifferenceOLS` | implemented |
| `iv` | `IV2SLS` | `linearmodels.iv.IV2SLS` | implemented |
| `gmm` | `SystemGMM` | — | stub |
| `quantile` | `PanelQuantile` | — | stub |

All implemented estimators accept `entity_col`, `time_col`, `cov_type` in params;
defaults are `"entity"`, `"time"`, `"robust"`.

**IV-specific params**: `endog` (list of endogenous regressors), `instruments`
(excluded instruments). Order condition enforced in `validate()`: `len(instruments) >= len(endog)`.

**Exog/endog split**: `IV2SLS.fit()` computes `exog_regs = regressors − endog` to
avoid passing the same variable to both the exogenous and endogenous matrices.

---

## Diagnostic Plugin System

### Registration

```python
from econflow.diagnostics.registry import register_diagnostic
from econflow.diagnostics.base import BaseDiagnostic

@register_diagnostic("myhausman", label="My Hausman Variant")
class MyHausman(BaseDiagnostic):
    supported_estimators = ["fe", "twfe"]

    def run(self, result, **kwargs):
        ...
        return DiagnosticResult(...)
```

### BaseDiagnostic

```
BaseDiagnostic (abstract)
├── Class attributes: diagnostic_id, name, description,
│                     supported_estimators, required_assumptions, output_schema
├── run(result, **kwargs) → DiagnosticResult   [abstract]
├── supports(estimator_id) → bool
│     True if supported_estimators == ["*"] or estimator_id in list
└── _not_applicable(reason) → DiagnosticResult(level="skip")
```

### Built-in diagnostics

| ID | Class | Supports | Status |
|----|-------|---------|--------|
| `hausman` | `HausmanTest` | `fe`, `twfe` | implemented |
| `breusch_pagan` | `BreuschPagan` | `ols`, `fe`, `twfe`, `re` | implemented |
| `pesaran_cd` | `PesaranCD` | `ols`, `fe`, `twfe`, `re`, `fd` | implemented |
| `vif` | `VIFCheck` | `*` (all) | implemented |
| `wooldridge` | `WooldridgeTest` | `fe`, `twfe` | stub |
| `serial_correlation` | `SerialCorrelationTest` | `fe`, `twfe` | stub |

---

## Configuration Integration

In a YAML models file:

```yaml
models:
  - id: baseline
    label: "Baseline TWFE"
    estimator: twfe           # resolved via get_estimator()
    dependent: ln_gdp_pc
    regressors: [ai_index, ln_capital, ln_labor]
    entity_col: country
    time_col: year
    cov_type: clustered
    cluster_col: country
```

The pipeline resolves `estimator: twfe` via `get_estimator("twfe")`, instantiates
with the YAML params dict, and calls `run(data)`.

---

## Backward Compatibility

All existing imports continue to work:

```python
# These all resolve to the same class
from econflow.estimation.base import EstimationResult    # ← re-export
from econflow.estimation.result import EstimationResult  # ← canonical
from econflow.estimation import EstimationResult         # ← public API

from econflow.estimation.base import DiagnosticResult    # ← re-export
```

`commands/info.py` no longer hard-codes `ESTIMATOR_REGISTRY`; it calls
`list_estimators()` at import time and exposes the result as `ESTIMATOR_REGISTRY`
for any external code that imports it. `commands/validate.py` derives
`_SUPPORTED_ESTIMATORS` from `list_estimators()` rather than the old list.

---

## Testing

```bash
# Sprint 5 tests only
pytest tests/unit/test_estimation_result.py      # 27 tests  — result dataclasses
pytest tests/unit/test_estimation_registry.py    # 21 tests  — estimator registry
pytest tests/unit/test_estimation_base.py        # 29 tests  — BaseEstimator + run chain
pytest tests/unit/test_diagnostic_registry.py    # 23 tests  — diagnostic registry + BaseDiagnostic
pytest tests/integration/test_estimator_run.py   # 21 tests  — OLS/FE/TWFE/RE/FD/IV on synthetic panel
pytest tests/integration/test_diagnostic_run.py  # 24 tests  — Hausman/BP/CD/VIF + stubs + registry

# Milestone 3 protocol tests
pytest tests/unit/test_estimator_protocol.py     # protocol conformance + backend + registry

# Full suite
pytest                                           # 1100+ tests total
```

---

## Architecture Stabilization — Milestone 3: Library-Agnostic EstimatorProtocol

**Status:** Implemented (2026-07-06)

### Problem

The previous `BaseEstimator` ABC coupled the *interface* to the `linearmodels`
library in two ways:

1. **`_to_panel()`** — a helper that creates a `(entity, time)` `MultiIndex`
   specifically required by `linearmodels`.  This method lived in `BaseEstimator`
   but has no meaning for `statsmodels`, `pyfixest`, `DoubleML`, or `PyMC` backends.

2. **Type annotations** — `validate(data: pd.DataFrame)`, `fit(data: pd.DataFrame)`
   suggested that `pd.DataFrame` was the only accepted input, even though the
   Dataset abstraction (Milestone 2) had extended the interface.

### Solution

#### `EstimatorProtocol` (structural typing)

`src/econflow/estimation/protocol.py` defines a `@runtime_checkable Protocol`:

```python
from econflow.estimation.protocol import EstimatorProtocol

# Any class with fit/validate/diagnostics/run + estimator_id/name/backend satisfies it
assert isinstance(my_estimator, EstimatorProtocol)
```

Key properties:
- **Structural, not nominal** — no inheritance required.  A statsmodels wrapper,
  a pyfixest wrapper, or a fully custom class all satisfy the Protocol as long as
  they implement the four methods and three attributes.
- **`@runtime_checkable`** — `isinstance(est, EstimatorProtocol)` works at runtime.
- **Future-proof** — new backends can be added without modifying `BaseEstimator`.

#### `BACKEND_*` constants

```python
from econflow.estimation.protocol import (
    BACKEND_LINEARMODELS,  # "linearmodels"
    BACKEND_STATSMODELS,   # "statsmodels"
    BACKEND_PYFIXEST,      # "pyfixest"
    BACKEND_DOUBLEML,      # "doubleml"
    BACKEND_PYMC,          # "pymc"
    BACKEND_CUSTOM,        # "custom"
    KNOWN_BACKENDS,        # frozenset of all six
)
```

#### `BackendCapabilities` dataclass

Advertises what a backend supports:

```python
from econflow.estimation.protocol import BackendCapabilities

caps = estimator._backend_capabilities()
if caps.supports_iv:
    run_iv_robustness_check(estimator)
```

Fields: `supports_panel`, `supports_cross_section`, `supports_time_series`,
`supports_spatial`, `supports_bayesian`, `supports_iv`, `supports_quantile`,
`supports_gmm`.

#### Backend mixin classes (`src/econflow/estimation/backends/`)

| Mixin | Backend | Status | Key helpers |
|-------|---------|--------|-------------|
| `LinearmodelsMixin` | `linearmodels` | **Implemented** | `_to_panel()`, `_check_linearmodels()`, `_backend_capabilities()` |
| `StatsmodelsMixin` | `statsmodels` | Planned M4 | `_to_formula()` stub |
| `PyfixestMixin` | `pyfixest` | Planned M4 | `_to_fixest_formula()` stub |
| `DoubleMLMixin` | `doubleml` | Planned M5 | `_to_doubleml_data()` stub |
| `PyMCMixin` | `pymc` | Planned M6 | `_build_pymc_model()` stub |

New estimators inherit from `BaseEstimator` + the appropriate mixin:

```python
from econflow.estimation.base import BaseEstimator
from econflow.estimation.backends.linearmodels import LinearmodelsMixin
from econflow.estimation.protocol import BACKEND_LINEARMODELS

class MyPanelEstimator(BaseEstimator, LinearmodelsMixin):
    backend = BACKEND_LINEARMODELS

    def fit(self, data):
        data = self._resolve_dataframe(data)         # Dataset → pd.DataFrame
        panel = self._to_panel(data.dropna(...), ...) # from LinearmodelsMixin
        ...
```

#### Updated `BaseEstimator`

Three additions, zero breaking changes:

1. `backend: str = "unknown"` — class attribute; all 8 concrete estimators now
   set `backend = "linearmodels"`.
2. `_backend_capabilities()` — concrete method returning `BackendCapabilities`.
   Falls back to `BackendCapabilities(backend="custom")` for unknown backends.
3. Updated type hints: `validate(data: pd.DataFrame | Any)` and
   `fit(data: pd.DataFrame | Any)` — documents that Dataset inputs are accepted.

`_to_panel()` remains in `BaseEstimator` for backward compat (deprecated in
favour of `LinearmodelsMixin._to_panel()`).

#### Updated `EstimatorRegistry`

`@register()` gains an optional `backend=` keyword argument:

```python
@register("myfe", backend="pyfixest", ...)
class MyFE(BaseEstimator, PyfixestMixin): ...
```

If omitted, the decorator reads `cls.backend`.  New registry function:

```python
from econflow.estimation.registry import list_by_backend

lm_estimators = list_by_backend("linearmodels")
# Returns all 8 built-in estimators
```

`list_estimators()` now includes a `"backend"` key in every entry dict.

### Module map additions

```
src/econflow/estimation/
├── protocol.py              EstimatorProtocol, BackendCapabilities, BACKEND_* constants
└── backends/
    ├── __init__.py          Exports all 5 mixins
    ├── linearmodels.py      LinearmodelsMixin  [implemented]
    ├── statsmodels.py       StatsmodelsMixin   [stub — Milestone 4]
    ├── pyfixest.py          PyfixestMixin      [stub — Milestone 4]
    ├── doubleml.py          DoubleMLMixin      [stub — Milestone 5]
    └── pymc.py              PyMCMixin          [stub — Milestone 6]
```

### Migration path for third-party estimators

```python
# Before Milestone 3: must subclass BaseEstimator
class OldCustomEstimator(BaseEstimator):
    def validate(self, data): ...
    def fit(self, data): ...
    def diagnostics(self, result): ...

# After Milestone 3: can satisfy protocol without BaseEstimator
class NewCustomEstimator:
    estimator_id = "my_custom"
    name         = "My Custom"
    backend      = "custom"

    def fit(self, data) -> EstimationResult:       ...
    def validate(self, data) -> None:              ...
    def diagnostics(self, result) -> list:         ...
    def run(self, data) -> EstimationResult:
        self.validate(data)
        result = self.fit(data)
        result.diagnostic_results = self.diagnostics(result)
        return result

# Register it
from econflow.estimation.registry import _REGISTRY
_REGISTRY["my_custom"] = NewCustomEstimator  # duck-typing accepted

# Protocol check passes
from econflow.estimation.protocol import EstimatorProtocol
assert isinstance(NewCustomEstimator(), EstimatorProtocol)
```

---

## Extension Guide

### Add an estimator

1. Create `src/econflow/estimation/myestimator.py`
2. Decorate with `@register("myid", label="My Estimator")`
3. Subclass `BaseEstimator`, implement `validate()`, `fit()`, `diagnostics()`
4. Import the module in `estimation/__init__.py` (or it self-registers on import)
5. Write tests in `tests/unit/test_estimation_myestimator.py`

The new estimator will immediately appear in `econflow info`, be accepted by
`econflow validate`, and be retrievable via `get_estimator("myid")`.

### Add a diagnostic

1. Create `src/econflow/diagnostics/plugins/mytest.py`
2. Decorate with `@register_diagnostic("mytest", label="My Test")`
3. Subclass `BaseDiagnostic`, implement `run(result, **kwargs) → DiagnosticResult`
4. Import the module in `diagnostics/plugins/__init__.py`
5. Write tests in `tests/integration/test_diagnostic_run.py`

See `CONTRIBUTING.md` for the full step-by-step connector and estimator guides.
