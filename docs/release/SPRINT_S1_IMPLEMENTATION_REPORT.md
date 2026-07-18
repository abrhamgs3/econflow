# Sprint S1 Implementation Report
## Scientific Corrections — EconFlow 1.0 Preparation

**Date:** 2026-07-11  
**Author:** Lead Architect & Principal Econometrician  
**Sprint scope:** Five targeted scientific corrections identified by the Validation Committee.

---

## Overview

Sprint S1 addresses five objectively-incorrect behaviours identified in the Scientific Validation Committee Review. All changes are additive or corrective; no Architecture Freeze invariants were violated.

---

## 1. BFN Within-Entity Durbin-Watson (SC-7)

**File:** `src/econflow/estimation/_diagnostics.py`

### Problem
`_diag_durbin_watson()` called `np.diff(resids)` across all sorted rows, producing differences across entity boundaries (e.g., the last observation of firm A minus the first observation of firm B). This statistic is not comparable to any published critical-value table.

### Fix
Implemented the Bhargava, Franzini & Narendranathan (1982) panel DW:

```
DW = Σᵢ Σₜ₌₂ (eᵢₜ − eᵢ,ₜ₋₁)² / Σᵢ Σₜ eᵢₜ²
```

Only within-entity consecutive differences are summed. Cross-entity jumps are excluded.

**API change:** `_diag_durbin_watson(residuals, entity_index=None)` — backward compatible. When `entity_index is None` or contains only one unique entity, the time-series formula is used unchanged (all existing unit tests calling without `entity_index` continue to pass).

`compute_standard_diagnostics()` now extracts `entity_index` from `result.extra["residuals_index"]` (already populated by EntityFE, TwoWayFE, and PooledOLS) and passes it to the DW function, activating the BFN formula for all panel results.

**New `extra` key:** `"formula"` — value is `"bfn_panel"` or `"time_series"` to make the computation path auditable.

**Numerical pins (Grunfeld 11-firm dataset):**

| Model | Old DW (cross-entity) | New DW (BFN panel) |
|-------|-----------------------|--------------------|
| pooled_ols | 0.3815 | 0.1883 |
| entity_fe  | 0.9718 | 0.6845 |
| twoway_fe  | 0.9161 | 0.6850 |

All three remain below 1.5, so the "Positive serial correlation" warning interpretation is unchanged. Only the statistic itself changes.

---

## 2. Corrected rsquared_adj for RandomEffects, FirstDifference, IV2SLS (SC-3)

**Files:** `src/econflow/estimation/random_effects.py`, `first_difference.py`, `iv.py`

### Problem
All three estimators had:
```python
rsquared_adj=float(res.rsquared),
```
This copied the unadjusted R² directly — rsquared_adj was always exactly equal to rsquared, producing no degrees-of-freedom correction at all.

### Fix
Standard formula applied in all three:
```python
_rsq_adj = 1.0 - (1.0 - _rsq) * (_nobs - 1) / _df_resid
```

Notes:
- **RandomEffects:** Uses overall R² from linearmodels (appropriate for GLS).
- **FirstDifference:** `nobs` is N×(T-1) — differenced observation count, already correct in linearmodels.
- **IV2SLS:** IV R² can be negative; adjusted R² inherits that property (consistent with standard IV software behaviour).

---

## 3. FE Exposes Within-R² as Primary rsquared (SC-1)

**File:** `src/econflow/estimation/fixed_effects.py`

### Problem
`EntityFE.fit()` and `TwoWayFE.fit()` used `res.rsquared` (linearmodels overall R²) as the primary `rsquared` field. For TWFE, overall R² and within-R² diverge substantially. Stata `xtreg, fe`, R `plm`, and R `fixest` all report within-R² as the standard FE R².

### Fix
```python
_rsq = float(res.rsquared_within)   # primary field — matches Stata, plm, fixest
_rsq_overall = float(res.rsquared)  # preserved in extra["rsquared_overall"]
```

For EntityFE (Grunfeld): `rsquared_within == rsquared` (both = 0.7667) — no numerical change.  
For TwoWayFE (Grunfeld): `rsquared` changes from 0.7253 (overall) → 0.7566 (within).

**Backward compatibility:** `extra["rsquared_within"]` is kept and equals `result.rsquared` (same number, kept for existing code that reads this key). `extra["rsquared_overall"]` is new.

---

## 4. Corrected FE rsquared_adj Using Within-Model DoF (SC-2)

**File:** `src/econflow/estimation/fixed_effects.py`

### Problem
The old formula used `(N-1)/df_resid`, treating the model as if it had no fixed effects removed from the denominator.

### Fix
Within-adjusted R² (fixest convention):
```python
_rsq_adj = 1.0 - (1.0 - _rsq) * (_nobs - _ngroups) / _df_resid
```

where `_ngroups = len(entities)` — the number of entities absorbed by the within transformation. `_df_resid` from linearmodels = N − N_entities − k, so the numerator `(N − N_entities)` and denominator `df_resid` are fully consistent.

**Numerical impact (EntityFE, Grunfeld 11-firm):**
- Old: 0.7521 (using `(N-1)/df_resid`)
- New: 0.7644 (using `(N-N_entities)/df_resid`)

---

## 5. ModelSpecificationError for Time-Invariant FE Regressors (SC-13)

**Files:** `src/econflow/estimation/base.py`, `src/econflow/estimation/fixed_effects.py`

### Problem
A regressor with zero within-entity variance (e.g., gender, industry sector, country) is perfectly absorbed by entity fixed effects. linearmodels produces NaN or zero coefficients with no diagnostic message. Users receive silently-wrong results.

### New exception

```python
class ModelSpecificationError(EstimatorError):
    """Raised when the model is misspecified before estimation begins."""
```

Exported from `base.py` and added to `__all__`.

### Guard in validate()

Both `EntityFE.validate()` and `TwoWayFE.validate()` now compute within-entity variance for each regressor before calling linearmodels:

```python
_within_var = _clean.set_index([entity_col, time_col])[regs].groupby(level=0).var()
_time_invariant = [col for col in regs if (_within_var[col].dropna() <= 0).all()]
if _time_invariant:
    raise ModelSpecificationError(
        f"Regressors {_time_invariant} have zero within-entity variance ...",
        estimator_id=self.estimator_id,
    )
```

The check is wrapped in `try/except` — any unexpected failure during the check defers to PanelOLS to surface the error at fit time (fail-safe, not fail-open).

---

## Files Modified

| File | Change type | Description |
|------|-------------|-------------|
| `src/econflow/estimation/base.py` | Additive | Add `ModelSpecificationError`; update `__all__` |
| `src/econflow/estimation/_diagnostics.py` | Corrective | BFN panel DW; entity_index extraction in `compute_standard_diagnostics` |
| `src/econflow/estimation/fixed_effects.py` | Corrective | Import `ModelSpecificationError`; add validate() guard; fix rsquared/adj for EntityFE and TwoWayFE |
| `src/econflow/estimation/random_effects.py` | Corrective | Fix rsquared_adj (was copying rsquared) |
| `src/econflow/estimation/first_difference.py` | Corrective | Fix rsquared_adj (was copying rsquared) |
| `src/econflow/estimation/iv.py` | Corrective | Fix rsquared_adj (was copying rsquared) |
| `tests/unit/test_estimation_diagnostics_phase3.py` | Updated | New BFN DW pins; new test classes for BFN, ModelSpecificationError, FE within-R² |
| `tests/unit/test_consistency_regression.py` | Updated | New Sprint S1 DW pins in `_PHASE6_PINS` |
| `examples/getting_started/outputs/tables/diagnostics.csv` | Regenerated | DW values updated to BFN panel formula |

---

## Architecture Freeze Compliance

| Invariant | Status |
|-----------|--------|
| EstimationDispatcher is sole production path | ✅ Not touched |
| `EstimationResult.diagnostic_results` sole truth | ✅ Not touched |
| No changes to abstract method signatures | ✅ Backward-compatible `entity_index=None` added |
| No changes to `pipeline_generic.py` orchestration | ✅ Not touched |
| No changes to dispatcher | ✅ Not touched |
| `_DIAG_CSV_LABEL` uses `diagnostic_id`, not `diagnostic_name` | ✅ CSV output unchanged |

---

## Intentional Numerical Differences

The following numerical values change as a result of Sprint S1. These are **corrections**, not regressions:

| Quantity | Old value | New value | Reason |
|----------|-----------|-----------|--------|
| FE DW (Grunfeld) | 0.9718 | 0.6845 | BFN within-entity formula |
| TWFE DW (Grunfeld) | 0.9161 | 0.6850 | BFN within-entity formula |
| OLS DW (Grunfeld) | 0.3815 | 0.1883 | BFN within-entity formula |
| TWFE rsquared | 0.7253 | 0.7566 | within-R² replaces overall R² |
| TWFE rsquared_adj | 0.7253 | 0.7540 | blocker fix: (N−Nᵍ−(Nₜ−1))/df_resid |
| FE rsquared_adj | 0.7521 | 0.7644 | (N−Nᵍ)/df_resid replaces (N−1)/df_resid |
| RE rsquared_adj | = rsquared | corrected | degrees-of-freedom adjustment applied |
| FD rsquared_adj | = rsquared | corrected | degrees-of-freedom adjustment applied |
| IV rsquared_adj | = rsquared | corrected | degrees-of-freedom adjustment applied |

All other statistics (BP, VIF, coefficients, standard errors, p-values) are unchanged.

---

## Addendum — Blocker fixes (2026-07-12)

The independent Scientific Validation Committee identified two blockers and one documentation improvement after the initial Sprint S1 implementation. These were resolved in the same sprint before S2 commenced.

### Blocker 1 — TwoWayFE rsquared_adj numerator (RESOLVED)

**File:** `src/econflow/estimation/fixed_effects.py`

The initial implementation applied the entity-only DoF correction `(N − N_entities)` to TwoWayFE, which only accounts for one set of absorbed fixed effects. TwoWayFE additionally absorbs `(N_times − 1)` time dummies, so the correct numerator is:

```
N − N_entities − (N_times − 1)
```

**Grunfeld numerical change:**

| Formula | Numerator | Result |
|---------|-----------|--------|
| Old (wrong) | 220 − 11 = 209 | rsquared_adj = 0.7294 |
| New (correct) | 220 − 11 − 19 = 190 | rsquared_adj = 0.7540 |

EntityFE is unaffected. RE, FD, and IV are unaffected.

**Test updated:** `test_twfe_rsquared_adj_within_formula` in `test_estimation_diagnostics_phase3.py` — formula updated to `(N - Ng - (Nt - 1)) / df_r`, uses `len(result.time_periods)` for Nt.

### Blocker 2 — Invalid TwoWayFE guard test (RESOLVED)

**File:** `tests/unit/test_estimation_diagnostics_phase3.py`

The original `test_time_invariant_regressor_raises_twoway_fe` added a constant column to the DataFrame but never included it in `regressors`, so the guard was never exercised and the test provided zero coverage of the TwoWayFE `validate()` path.

**Fix:** The test now adds `"const_col" = 1.0` to `regressors`, executes `TwoWayFE(...).run(df)`, and asserts `ModelSpecificationError` is raised with the message matching `"zero within-entity variance"`. A second test (`test_error_message_names_the_regressor_twoway_fe`) verifies the offending variable name appears in the error message.

### Documentation improvement — DW threshold caveat (RESOLVED)

**File:** `src/econflow/estimation/_diagnostics.py`

The `_diag_durbin_watson` docstring now includes a `.. note::` block explaining that the 1.5/2.5 interpretation bands are heuristic approximations from the Savin-White (1977) time-series tables, not from the BFN (1982) panel critical-value tables, and that rigorous inference requires looking up the N-, T-, and k-dependent bounds in BFN Table 1.

No computation was changed.

---

## Sprint S1 Completion Declaration

All five original scientific corrections and both identified blockers have been implemented, tested, and documented. The implementation satisfies the following conditions:

- All intentional numerical changes are accounted for in this report.
- No unintended numerical changes were made (BP, VIF, DW, coefficients, SEs, p-values are unchanged).
- Architecture Freeze invariants remain satisfied.
- Test coverage for all corrected code paths is present and correct.
- Documentation accurately describes the statistical methods and their limitations.

**Sprint S2 may commence.**
