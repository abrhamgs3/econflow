# Release Sprint R1 — Exception Hierarchy Unification Report

**Sprint:** R1  
**Status:** COMPLETE  
**Date:** 2026-07-13  
**Author:** Principal Software Architect, EconFlow

---

## 1. Executive Summary

Release Sprint R1 resolved Critical Blocker C-1 from the API Freeze Report: two independent `ModelSpecificationError` class objects existing with different inheritance hierarchies, causing silent `isinstance()` failures across module boundaries.

**Result:** Single canonical exception hierarchy. 219 tests pass. Zero regressions.

---

## 2. Pre-Sprint State (C-1 Defect)

### Two independent class definitions

| Location | Base class | `estimator_id` kwarg |
|---|---|---|
| `econflow/exceptions.py` | `EconFlowError` | No |
| `econflow/estimation/base.py` | `EstimatorError(Exception)` | Yes |

### Failure mode

```python
# pipeline_generic.py imports from exceptions.py
from econflow.exceptions import ModelSpecificationError as MSE_pipeline

# fixed_effects.py imports from estimation.base
from econflow.estimation.base import ModelSpecificationError as MSE_estimator

# These are DIFFERENT class objects:
MSE_pipeline is MSE_estimator   # False
isinstance(MSE_estimator("x"), MSE_pipeline)  # False — silent catch failure
```

A bare `except ModelSpecificationError:` in pipeline code would silently miss exceptions raised by estimators.

---

## 3. Design Decision

### Target MRO

```
ModelSpecificationError
  → EstimatorError
    → EconFlowError
      → Exception
```

**Rationale:**
- `EstimatorError` unifies all estimator-layer failures under the root EconFlow hierarchy, enabling a single `except EconFlowError:` at application level to catch all framework errors.
- `ModelSpecificationError → EstimatorError` preserves the pre-existing relationship from `estimation/base.py` that the Sprint S2 test suite already asserts (`issubclass(ModelSpecificationError, EstimatorError)` — test line 1057 in `test_estimation_diagnostics_phase3.py`).
- Canonical home is `econflow/exceptions.py` — the designated exception registry, not inside a domain subpackage.

### Backward compatibility

`econflow/estimation/base.py` re-exports both classes from `econflow.exceptions` so all existing `from econflow.estimation.base import EstimatorError` imports continue to work unchanged.

---

## 4. Implementation

### 4.1 `econflow/exceptions.py` — canonical definitions

Added `EstimatorError(EconFlowError)` with `estimator_id` and `cause` keyword arguments. Changed `ModelSpecificationError` to inherit from `EstimatorError`. Both classes have complete docstrings with usage examples and backward-compatibility notes.

```
EconFlowError (Exception)
├── DataValidationError
├── MergeError
├── PipelineError
└── EstimatorError           ← NEW location (was econflow.estimation.base)
    └── ModelSpecificationError  ← CHANGED base (was EconFlowError directly)
```

### 4.2 `econflow/estimation/base.py` — re-exports only

Removed both local class definitions. Added:

```python
from econflow.exceptions import EstimatorError, ModelSpecificationError  # noqa: E402
```

Added both to `__all__`. All existing raise sites in `fixed_effects.py` use `estimator_id=self.estimator_id` kwarg — these work unchanged because `EstimatorError.__init__` still accepts that kwarg.

### 4.3 `econflow/estimation/__init__.py` — surface the API

Added `ModelSpecificationError` to the import line and to `__all__` so `from econflow.estimation import ModelSpecificationError` works as a first-class API.

### 4.4 Raise sites

No raise sites required modification:
- `fixed_effects.py` lines 135, 325: raise `ModelSpecificationError(..., estimator_id=self.estimator_id)` — valid, `EstimatorError.__init__` accepts `estimator_id`.
- `pipeline_generic.py` lines 513, 520: raise `ModelSpecificationError(...)` without `estimator_id` — valid, the kwarg defaults to `""`.

---

## 5. Test Coverage

New file: `tests/unit/test_r1_exception_hierarchy.py` — 48 tests across 9 classes.

| Test class | What it guards |
|---|---|
| `TestSingleClassIdentity` | All 4 import paths resolve to the same class object |
| `TestMROChain` | Full chain MSE → EstimatorError → EconFlowError → Exception |
| `TestEconFlowErrorCatchesAll` | Root exception catches every subtype |
| `TestEstimatorErrorScope` | Catches estimation errors; does NOT catch PipelineError/DataValidationError |
| `TestModelSpecificationErrorCrossPathCatch` | C-1 regression guard: exception raised via one import path, caught via another |
| `TestKeywordArguments` | `estimator_id` and `cause` kwargs work |
| `TestStrFormatting` | `__str__` prefix and cause chain formatting |
| `TestIsinstanceConsistency` | Cross-path `isinstance()` checks |
| `TestRealEstimatorRaises` | `EntityFE` raises an exception catchable at all three hierarchy levels |

---

## 6. Regression Verification

```
219 passed, 0 failed, 13 warnings
```

Key pre-existing tests confirmed passing:
- `TestSprintS1ModelSpecificationError::test_model_specification_error_is_subclass_of_estimator_error` (phase3 suite, line 1057) — asserts `issubclass(MSE, EstimatorError)`. Passes because the new MRO includes `EstimatorError`.
- All 171 Sprint S1/S2 tests — no regressions.

---

## 7. Files Changed

| File | Change |
|---|---|
| `src/econflow/exceptions.py` | Added `EstimatorError`; changed `ModelSpecificationError` base to `EstimatorError` |
| `src/econflow/estimation/base.py` | Removed local class defs; added re-exports from `econflow.exceptions` |
| `src/econflow/estimation/__init__.py` | Added `ModelSpecificationError` to import and `__all__` |
| `tests/unit/test_r1_exception_hierarchy.py` | New — 48 regression tests |
| `docs/release/API_FREEZE_REPORT.md` | Pre-existing — documents C-1 as the blocker this sprint resolves |

**Unmodified (constraint satisfied):** `pipeline_generic.py`, `fixed_effects.py`, `iv.py`, `ols.py`, `_diagnostics.py`, all other exception classes, all other public APIs.

---

## 8. Independent Architecture Review

*Reviewer: Principal Release Engineer perspective*

### Correctness

The MRO chain is unambiguous and correct. Python's MRO resolution guarantees that `except ModelSpecificationError:` will catch exactly those exceptions, and `except EstimatorError:` will catch `ModelSpecificationError` and any other future `EstimatorError` subclass.

### API surface

`ModelSpecificationError` is now accessible via three equivalent paths:

```python
from econflow.exceptions import ModelSpecificationError           # canonical
from econflow.estimation.base import ModelSpecificationError      # backward compat
from econflow.estimation import ModelSpecificationError           # package API (new)
```

All three resolve to the same class object. The test suite verifies this explicitly.

### Constraint compliance

The sprint constraint was "do not modify unrelated exceptions or APIs." `DataValidationError`, `MergeError`, `PipelineError`, `EconFlowCoreError`, and all estimator classes are unchanged.

### Remaining C-2 and C-3 blockers

This sprint resolves C-1. The API Freeze Report identifies two remaining pre-freeze blockers:
- **C-2:** `AIProdError` still in `__all__` in `econflow/__init__.py` — requires a separate, minimal edit.
- **C-3:** `ValidationIssue` naming collision between `econflow.config` and `econflow.integrity` — requires a rename in one of the two modules.

Neither was in R1 scope.

### Architecture Freeze status

With C-1 resolved, the exception hierarchy is stable and ready to freeze. The `EconFlowError → EstimatorError → ModelSpecificationError` chain satisfies the Architecture Freeze invariant that all errors be catchable at a single root.

**Verdict: R1 COMPLETE. C-1 blocker resolved. Zero regressions. Ready for C-2/C-3 follow-on work.**
