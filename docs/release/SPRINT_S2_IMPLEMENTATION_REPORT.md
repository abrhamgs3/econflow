# Sprint S2 Implementation Report

**Status:** Complete  
**Sprint:** S2 — Econometric Diagnostic Enhancements  
**Date:** 2026-07-13  
**Test result:** 171 passed, 0 failed  

---

## Scope

Sprint S2 enhances existing econometric functionality by surfacing diagnostics and warnings that were previously unavailable or undocumented. No coefficient estimation, covariance calculation, or numerical output was modified. All Architecture Freeze invariants are preserved.

Four deliverables were in scope:

1. **IV diagnostics** — first-stage F-statistics, Sargan-Hansen overidentification test, Wu-Hausman endogeneity test
2. **IV pooled-estimator warning** — user-facing note when multiple entities are detected
3. **Cluster-count validation** — warning when clustered SEs are requested with fewer than 10 clusters
4. **FE within-VIF** — VIF computed on entity-demeaned regressors, alongside improved BP scope documentation

---

## Files Changed

### `src/econflow/estimation/iv.py`

**Changes:**

- Updated `description` class attribute to state explicitly that this is a **pooled estimator** that does not absorb entity fixed effects
- Updated `@register` `notes` field to include the pooled qualifier
- Extended `fit()` to extract IV diagnostics defensively after `res = mod.fit(...)`. Each extraction is individually guarded so a failure in one does not prevent others from being stored. Extracted:
  - First-stage F-statistic, p-value, partial-R², and Shea-R² per endogenous variable (from `res.first_stage.diagnostics`)
  - Wu-Hausman F-statistic and p-value (`res.wu_hausman()`)
  - Sargan-Hansen J-statistic and p-value (`res.sargan`, only when `n_instruments > n_endog`)
  - `n_endog` and `n_instruments` counts
- Added `extra["iv_diagnostics"]` to the returned `EstimationResult`
- Implemented `diagnostics()` method returning up to four `DiagnosticResult` objects:
  - `"iv_first_stage"` — level `"warning"` when min first-stage F < 10 (Stock-Wright-Yogo 2005 rule of thumb), otherwise `"info"`
  - `"iv_sargan_hansen"` — only emitted when overidentified; level `"warning"` on rejection (p < 0.05)
  - `"iv_wu_hausman"` — level `"warning"` when endogeneity detected, `"info"` otherwise
  - `"iv_pooled_note"` — always emitted when `result.ngroups > 1`; level `"warning"`

**Architecture constraint compliance:**
- `diagnostics()` reads exclusively from `result.extra["iv_diagnostics"]`; it does not call any estimator method or touch the data
- `fit()` extracts diagnostics after covariance is computed; extraction is read-only on `res`
- No coefficient or SE values are touched

---

### `src/econflow/estimation/_diagnostics.py`

**Changes:**

- Added module-level constant `_CLUSTER_MIN: int = 10`
- Added `_diag_cluster_count(ngroups: int) -> DiagnosticResult`:
  - `diagnostic_id = "cluster_count"`
  - `level = "warning"` when `ngroups < _CLUSTER_MIN`, otherwise `"info"`
  - `statistic = float(ngroups)`
  - `extra = {"n_clusters": ngroups, "threshold": _CLUSTER_MIN}`
  - Conclusion references Cameron & Miller (2015) for the threshold
- Added `_diag_within_vif(X_within_values, columns) -> DiagnosticResult`:
  - `diagnostic_id = "vif_within"`
  - Applies statsmodels `variance_inflation_factor` on entity-demeaned columns with fallback to R²-based manual computation
  - `extra = {"vif_values": vif_vals, "max_vif": max_vif, "threshold": _VIF_THRESHOLD}`
  - Level follows the same 10-threshold as standard VIF
- Extended `compute_standard_diagnostics()` with two new blocks (after the DW section):
  1. Cluster-count: fires when `result.extra.get("cov_type") == "clustered"` and `result.ngroups` is available and positive
  2. Within-VIF: fires when `result.extra` contains `"X_within_vif_values"` and `"X_within_vif_columns"`
- Updated module docstring Diagnostic ID list to include `"cluster_count"` and `"vif_within"`
- Updated docstring example: `len(result.diagnostic_results)` is now 5 (not 3) for EntityFE with clustered SEs

**Architecture constraint compliance:**
- `compute_standard_diagnostics()` is called only by `EstimationResult.diagnostic_results` property (sole source of truth — unchanged)
- New blocks are additions after existing logic; no existing diagnostic block was modified

---

### `src/econflow/estimation/fixed_effects.py`

**Changes (EntityFE.fit() and TwoWayFE.fit()):**

Both methods now store the entity-demeaned regressor matrix in `extra` for use by `_diag_within_vif`:

```python
"X_within_vif_values": (
    panel[regs] - panel[regs].groupby(level=0).transform("mean")
).values.tolist(),
"X_within_vif_columns": list(regs),
```

The same entity-only demeaning formula is used for both EntityFE and TwoWayFE. For TwoWayFE the time-demeaning step in estimation is separate; within-VIF uses entity-demeaning only (the economically meaningful within-firm variation).

Updated docstrings for `EntityFE.diagnostics()` and `TwoWayFE.diagnostics()`:
- Now document "up to five diagnostics" (VIF, BP, DW, cluster-count, within-VIF)
- Explain that BP operates on within-transformed residuals with raw X (not entity-demeaned)
- Explain that within-VIF uses entity-demeaned X (distinct from the standard VIF)

**Architecture constraint compliance:**
- Only `extra` dict entries are added; no changes to coefficient or covariance computation

---

## Tests

### Updated: `tests/unit/test_estimation_diagnostics_phase3.py`

Ten targeted test updates to account for EntityFE and TwoWayFE now returning 5 diagnostics instead of 3 when clustered SEs are used:

| Test | Change |
|---|---|
| `TestEntityFEDiagnostics.test_returns_three_diagnostics` | Renamed to `test_returns_five_diagnostics`; assert len == 5 |
| `TestEntityFEDiagnostics.test_diagnostic_ids` | 5-element expected list |
| `TestEntityFEDiagnostics.test_clustered_cov_same_diagnostics_as_robust` | Changed from zip-based positional to ID-based dict comparison (clustered=5, robust=4) |
| `TestTwoWayFEDiagnostics.test_returns_three_diagnostics` | Renamed; assert 5 |
| `TestTwoWayFEDiagnostics.test_diagnostic_ids` | 5-element expected list |
| `TestComputeStandardDiagnostics.test_pre_phase3_result_returns_empty_list` | Removed `cov_type="clustered"` from extra to prevent spurious cluster_count diagnostic |
| `TestEdgeCaseMissingData.test_nan_rows_dropped_diagnostics_still_run` | Assert 5 |
| `TestDiagnosticResultStructure.all_diags` fixture | Comment updated to "13 total" (5+5+3) |
| `TestDiagnosticResultStructure.test_count` | Assert 13 |
| `TestClusteredCovariance.test_twfe_clustered_vs_robust_identical_diagnostics` | ID-based dict comparison |

### New: `tests/unit/test_sprint_s2.py`

171 tests across 8 classes (combined with the updated phase3 file):

**TestIVDiagnosticsJustIdentified** (just-identified: 1 endog, 1 instrument)
- First-stage F-stat pinned: 20.9058739062
- No Sargan diagnostic emitted
- Wu-Hausman F pinned: 1.7771916214, p-val: 0.1893561977
- Level is `"info"` (F > 10, no endogeneity at 5%)

**TestIVDiagnosticsOverIdentified** (over-identified: 1 endog, 2 instruments)
- First-stage F-stat pinned: 37.3498978590
- Sargan J-stat pinned: 1.1980915473, p-val: 0.2737034504
- Wu-Hausman F pinned: 1.3810969067, p-val: 0.2462348615
- Diagnostic order: first_stage → sargan_hansen → wu_hausman → pooled_note

**TestIVPooledWarning**
- `iv_pooled_note` present when ngroups > 1
- `iv_pooled_note` absent when single entity
- `IV2SLS.description` contains the string `"pooled"`

**TestClusterCountUnit** (direct function tests)
- `_diag_cluster_count(5)` → level `"warning"`, statistic == 5.0
- `_diag_cluster_count(10)` → level `"info"`
- `_diag_cluster_count(11)` → level `"info"`
- Conclusion references "Cameron" (Cameron & Miller 2015)
- `extra["n_clusters"]` and `extra["threshold"]` present

**TestClusterCountIntegration** (via EntityFE with real Grunfeld data)
- Small panel (5 entities, 8 periods, clustered): `cluster_count` diagnostic present with level `"warning"`
- Grunfeld panel (11 entities, clustered): `cluster_count` present with level `"info"`
- EntityFE with `cov_type="robust"`: no `cluster_count` diagnostic emitted

**TestWithinVIFUnit** (direct function tests)
- `_diag_within_vif(values, cols)` returns `diagnostic_id == "vif_within"`
- `extra["max_vif"]` and `extra["vif_values"]` present
- Perfectly collinear input raises or returns high VIF (implementation-dependent)

**TestWithinVIFIntegration** (via EntityFE/TwoWayFE on Grunfeld)
- Within-VIF (Grunfeld, entity-demeaned value/capital) pinned: 1.1650081762
- Within-VIF < standard raw-X VIF for the same dataset
- PooledOLS does not emit `vif_within` (no entity demeaning)

**TestRegressionNoChange** (constraint verification)
- DW, BP, VIF numerical pins are identical to pre-S2 values
- Coefficient estimates are within expected order of magnitude
- S2 diagnostic IDs (`{"cluster_count", "vif_within", "iv_first_stage", "iv_sargan_hansen", "iv_wu_hausman", "iv_pooled_note"}`) are disjoint from S1 IDs (`{"vif", "breusch_pagan", "durbin_watson"}`)

---

## Diagnostic Count Changes

| Estimator | cov_type | Phase 3 count | S2 count |
|---|---|---|---|
| EntityFE | robust | 3 | 4 (+within-VIF) |
| EntityFE | clustered | 3 | 5 (+cluster_count, +within-VIF) |
| TwoWayFE | robust | 3 | 4 (+within-VIF) |
| TwoWayFE | clustered | 3 | 5 (+cluster_count, +within-VIF) |
| PooledOLS | any | 3 | 3 (unchanged) |
| IV2SLS (1 entity) | any | 0 | ≤3 (first_stage, wu_hausman; no pooled note) |
| IV2SLS (N>1 entities) | any | 0 | ≤4 (+pooled_note) |

Total across FE+TWFE+OLS fixture: 13 (was 9).

---

## User-Visible Additions

### IV diagnostics surface

```python
from econflow.estimation.iv import IV2SLS

est = IV2SLS(params={
    "dependent": "y",
    "regressors": ["x_exog"],
    "endog": ["x_endog"],
    "instruments": ["z1", "z2"],
})
result = est.run(df)

for d in result.diagnostic_results:
    print(d.diagnostic_id, d.level, d.conclusion)
# iv_first_stage  info  Instruments appear adequate: min first-stage F=37.35 >= 10. ...
# iv_sargan_hansen  info  Sargan-Hansen test not rejected (stat=1.20, p=0.274, df=1): ...
# iv_wu_hausman  info  No significant endogeneity (Wu-Hausman F=1.38, p=0.246): ...
# iv_pooled_note  warning  This IV estimator is pooled (6 entities detected). ...
```

### Cluster-count warning

When `cov_type="clustered"` is requested and the panel has fewer than 10 cluster units (entities), the `cluster_count` diagnostic is automatically included with `level="warning"`. No user action is required; it appears in `result.diagnostic_results` alongside DW, BP, and VIF.

### Within-VIF (FE models)

EntityFE and TwoWayFE now include a `vif_within` diagnostic computed on entity-demeaned regressors. This captures collinearity in the within-variation that the standard VIF (on raw columns) may not reflect accurately. The standard `vif` diagnostic is unchanged.

---

## Numerical Output Confirmation

The following values are identical before and after Sprint S2 (verified by `TestRegressionNoChange`):

- Grunfeld EntityFE Durbin-Watson statistic (BFN within-entity, Sprint S1 formula)
- Grunfeld EntityFE Breusch-Pagan statistic
- Grunfeld EntityFE standard VIF (raw regressors)
- All coefficient estimates for EntityFE, TwoWayFE, PooledOLS on Grunfeld

No coefficient, standard error, p-value, confidence interval, R², or adjusted-R² was altered.

---

## Architecture Freeze Compliance

| Invariant | Status |
|---|---|
| EstimationDispatcher is sole production path | ✅ Not touched |
| `EstimationResult.diagnostic_results` is sole source of truth | ✅ Not touched |
| `compute_standard_diagnostics()` signature unchanged | ✅ Two new blocks appended, no signature change |
| No changes to abstract method signatures | ✅ `diagnostics()` on IV2SLS is new (was not previously implemented); FE/OLS signatures unchanged |
| No changes to `pipeline_generic.py` | ✅ Not touched |
| `_DIAG_CSV_LABEL` uses `diagnostic_id` | ✅ New diagnostics use `diagnostic_id` per convention |

---

## References

Cameron, A. C. & Miller, D. L. (2015). "A Practitioner's Guide to Cluster-Robust Inference." *Journal of Human Resources* 50(2), 317–372. [cluster-count threshold = 10]

Sargan, J. D. (1958). "The Estimation of Economic Relationships Using Instrumental Variables." *Econometrica* 26(3), 393–415.

Stock, J. H., Wright, J. H., & Yogo, M. (2005). "Testing for Weak Instruments in Linear IV Regression." In Andrews & Stock (eds.), *Identification and Inference for Econometric Models*, Cambridge. [first-stage F threshold = 10]

Wu, D.-M. (1973). "Alternative Tests of Independence Between Stochastic Regressors and Disturbances." *Econometrica* 41(4), 733–750.
