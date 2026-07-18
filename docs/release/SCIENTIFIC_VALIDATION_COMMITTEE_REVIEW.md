# EconFlow — Scientific Validation Committee Review

**Date:** 2026-07-11  
**Scope:** Independent committee review of the EconFlow Scientific Validation Audit  
**Purpose:** Verify each scientific finding against econometric theory and established software behavior.
Each claim is assessed against Stata, R fixest, R plm, and linearmodels directly.
The reviewer is not assumed to be correct. Every finding is independently adjudicated.  
**Constraint:** Architecture Freeze v1 remains in effect.

---

## Committee Methodology

For each finding the committee applies the following protocol:

1. **Theory check:** Is the claim supported by econometric theory?
2. **Software survey:** How do Stata, R fixest, R plm, and linearmodels handle this?
3. **Classification:** One of four verdicts:
   - **Objectively incorrect** — the implementation produces a wrong answer against a clear standard
   - **Design choice** — the implementation is defensible; a reasonable alternative exists
   - **Software-package convention** — EconFlow follows the upstream library's convention; changing it diverges from linearmodels
   - **Reviewer preference** — the finding reflects the reviewer's software taste, not a correctness failure
4. **Action:** implement / expose both behaviors / document the limitation / reject

---

## Finding SC-1: `result.rsquared` for FE models reports overall R², not within-R²

### Reviewer claim
`EstimationResult.rsquared` for EntityFE and TwoWayFE stores `res.rsquared` from
linearmodels, which is the overall R² (between + within variation).  Within-R² is
only in `result.extra["rsquared_within"]`.  The reviewer asserts within-R² should be
the primary field and calls this HIGH severity.

### Theory check

Three R² statistics are defined for FE models (Wooldridge 2010, §10.5):

| Statistic | Formula | Interpretation |
|-----------|---------|----------------|
| R²_within | corr²(yᵢₜ - ȳᵢ, ŷᵢₜ - ȳᵢ) | Variation explained after removing entity means |
| R²_between | corr²(ȳᵢ, x̄ᵢ'β̂) | Variation explained by entity-level means |
| R²_overall | corr²(yᵢₜ, ŷᵢₜ) | All variation, ignoring panel structure |

For a fixed-effects estimator, the within-R² is the only one that directly measures how
well the model explains the variation the estimator is actually using.  The overall R²
is inflated by entity-mean variation that FE removes mechanically.  It is not wrong, but
it is the least informative of the three for assessing FE model fit.

### Software survey

| Software | Primary R² reported for FE |
|----------|---------------------------|
| Stata `xtreg, fe` | R²_within (labeled "within") |
| R plm `summary()` | R²_within (as `r.squared`) |
| R fixest `feols()` | R²_within (as `r2`) |
| linearmodels `PanelOLS` | Overall R² as `res.rsquared`; within available as `res.rsquared_within` |

All three end-user software packages default to within-R² for FE.  EconFlow follows
the linearmodels internal API rather than the econometric user convention.

### Classification

**Software-package convention** for the current behavior (following `linearmodels.rsquared`);
**design choice** if kept deliberately, since within-R² is the standard for user-facing output.

### Action

**Implement the recommendation.**  Set `EstimationResult.rsquared = float(res.rsquared_within)` for EntityFE and TwoWayFE.  Store the overall R² as `result.extra["rsquared_overall"]`.  This aligns EconFlow with every other FE software package a user has previously seen.

**Severity downgrade:** HIGH → MEDIUM.  The within-R² is already stored and displayed in the regression table via `extra`.  The bug is in which field is "primary", not in what data is available.

---

## Finding SC-2: `rsquared_adj` formula wrong for FE models

### Reviewer claim

The formula `1 − (1 − R²_overall) × (N−1) / df_resid` is wrong for FE models.
The reviewer proposes `1 − (1 − R²_within) × (N − N_entities) / (N − N_entities − k)`.

### Theory check

The standard OLS adjusted R² corrects for the k parameters estimated.  For FE models,
the correction is more complex because N_entities degrees of freedom are consumed by
entity dummies.

Wooldridge (2010) does not define a canonical adjusted within-R² for FE.  Neither does
Cameron and Trivedi (2005).  The adjustment is not standardized in the literature.

The reviewer's proposed formula is one consistent choice: it uses within-R² as the base
and replaces the between-variation df term `(N−1)` with `(N − N_entities)` to account
for entity means removed.  This is sensible but not universal.

### Software survey

| Software | Adjusted FE R² |
|----------|----------------|
| Stata `xtreg, fe` | **Not reported by default.** No adjusted R² in standard output. |
| R plm | Not reported; `summary()` omits adj-R² for within models. |
| R fixest `feols()` | Reports adj-R² via `r2(model, "ar2")` using a version of the reviewer's formula. |
| linearmodels | Does not expose `rsquared_adj` for PanelOLS. |

The primary finding is that **no major software package reports adjusted FE R² by default**
because the definition is contested.  Stata's omission is deliberate.

### Classification

**Reviewer preference** for the specific formula.  **Objectively incorrect** only in that
the current formula mixes overall R² with OLS degrees-of-freedom correction — this is
incoherent regardless of which adjusted formula is chosen.

### Action

**Implement a corrected formula** but with a different approach than the reviewer proposes:
after SC-1 fixes `rsquared` to be within-R², compute:

```python
rsquared_adj = 1.0 - (1.0 - rsquared_within) * (_nobs - ngroups) / _df_resid
```

Where `_df_resid = N − N_entities − k` (already correct from linearmodels).
Note `(N − N_entities)` in the numerator replaces the OLS `(N−1)`.
Add a docstring note that this is the fixest convention and not universally defined.
Do NOT silently emit something that is the hybrid of two incompatible formulas, which
is the current state.

**Severity downgrade:** HIGH → MEDIUM.  The current formula is incoherent, but reporting
no adjusted R² (following Stata) would also be acceptable.

---

## Finding SC-3: `rsquared_adj = rsquared` for RandomEffects, FirstDifference, IV2SLS

### Reviewer claim

Three estimators set `rsquared_adj=float(res.rsquared)`, copying the unadjusted R² with
no adjustment computation.

### Theory check

Adjusted R² is defined as `1 − (1 − R²)(N−1)/df_resid`.  For any model with positive
degrees of freedom and k > 0, adjusted R² < R².  Setting them equal is arithmetically wrong
whenever df_resid < N−1, which is always true when k > 0.

This is not a question of which adjustment formula to use.  It is a trivial coding error:
the line `rsquared_adj=float(res.rsquared)` copies the field without computing anything.

### Software survey

All software (Stata, R, linearmodels) computes distinct `rsquared` and `rsquared_adj` for
RE, FD, and IV estimators.  For RE and FD, linearmodels provides `df_resid` in the result
object, making the computation a single arithmetic expression.

### Classification

**Objectively incorrect.** This is a three-location coding error, not a design choice.

### Action

**Fix immediately.** For RE, FD, and IV2SLS:

```python
_nobs = int(res.nobs)
_df_resid = int(res.df_resid)
_rsq = float(res.rsquared)
rsquared_adj = 1.0 - (1.0 - _rsq) * (_nobs - 1) / _df_resid
```

Note: for FirstDifference, `nobs` is the number of first-differenced observations (N×(T−1)
for balanced panels), not the original N.  This is correct because linearmodels sets
`res.nobs` to the post-differencing count.

**Severity maintained:** HIGH.  Reporting rsquared_adj = rsquared for every FD and RE model
is numerically false.

---

## Finding SC-4: IV2SLS uses cross-sectional IV, not panel IV with entity FE

### Reviewer claim

`linearmodels.iv.IV2SLS` is the cross-sectional IV estimator.  When panel data is passed,
it runs pooled IV2SLS (no entity effects), not within-IV2SLS (equivalent to Stata's
`xtivreg, fe`).  Labeled CRITICAL.

### Theory check

The reviewer is factually correct: `linearmodels.iv.IV2SLS` accepts any DataFrame and
treats observations as independent.  A MultiIndex is stored but not used for panel
structure.  The model is:

yᵢₜ = x'ᵢₜβ + ε_it (no entity effects)

Stata's `xtivreg, fe` estimates:

yᵢₜ − ȳᵢ = (x'ᵢₜ − x̄ᵢ)β + (εᵢₜ − ε̄ᵢ) (within-transformed)

These produce different coefficient estimates whenever entity effects are correlated with
the instrumented variables.  They are not the same estimator.

However, **pooled IV2SLS is a legitimate estimator** when the researcher believes entity
effects are zero or are uncorrelated with X and Z.  It is not wrong — it estimates a
different model.

### Software survey

| Software | Pooled IV | Panel IV with FE |
|----------|-----------|-----------------|
| Stata | `ivregress 2sls` | `xtivreg, fe` |
| R | `ivreg()` (AER package) | `plm(..., model="within", inst.method="bvk")` |
| R fixest | `feols(y ~ 1 | entity | x ~ z)` (FE IV via fixest) | Same |
| linearmodels | `linearmodels.iv.IV2SLS` | `linearmodels.IVGMM` with entity_effects=True |

EconFlow provides only the pooled variant.  The panel variant is missing.

### Classification

**Design choice** for the current implementation (pooled IV is valid).  **Documentation failure**
in that the label "IV / 2SLS" and description "Addresses endogeneity via excluded instruments"
do not disclose that entity effects are not controlled for.

The reviewer calling this CRITICAL overstates the case.  Pooled IV2SLS is used in practice
(difference-in-differences with instruments, cross-sectional IV on panel-structured data,
etc.).  It is not an incorrect estimator.  It is a scoped estimator that is misrepresented
as general-purpose.

### Action

**Two-track fix:**

1. **Immediate (1 line):** Add a warning to the description and docstring: "This estimator
   runs pooled 2SLS and does NOT control for entity fixed effects.  For within-IV, use the
   `fe_iv` estimator (planned)."

2. **Sprint S2 (new estimator):** Implement `fe_iv` using `linearmodels.IVGMM` with
   `entity_effects=True`, or by within-transforming the data before calling `IV2SLS`.

**Severity downgrade:** CRITICAL → HIGH.  Pooled IV is not wrong; the documentation is
misleading.  The correction is documentation first, new estimator second.

---

## Finding SC-5: Missing IV validity diagnostics (Sargan, Cragg-Donald, Wu-Hausman)

### Reviewer claim

No Sargan/Hansen overidentification test, no weak instrument statistic, no Wu-Hausman
endogeneity test.  Only the order condition is checked.

### Theory check

These three tests are the standard IV validity checklist in every applied econometrics
text (Stock and Watson, Angrist and Pischke, Wooldridge).  In practice, a referee
asking "is your instrument valid?" expects to see:

1. First-stage F-statistic (Cragg-Donald or Kleibergen-Paap) ≥ 10 rule of thumb
2. J-test p-value (overidentified case only)
3. Wu-Hausman for whether IV was necessary at all

### Software survey

| Software | First-stage F | Sargan/Hansen | Wu-Hausman |
|----------|--------------|---------------|-----------|
| Stata `ivregress` | `estat firststage` | `estat overid` | `estat endogenous` |
| R `ivreg()` | `summary(m, diagnostics=TRUE)` | Same | Same |
| R fixest `feols()` | `fitstat(model, "ivf")` | `fitstat(model, "sargan")` | Available |
| linearmodels `IV2SLS` | `res.first_stage` | `res.sargan` | `res.wu_hausman` |

**All four comparators expose these tests.**  The linearmodels IV result object already
computes them — they are available as `res.sargan`, `res.wu_hausman`, and
`res.first_stage.diagnostics`.  EconFlow does not surface them.

### Classification

**Objectively incorrect** as a complete IV implementation for applied research.  These are
not preferences; they are the minimum content expected in any peer-reviewed paper using IV.

### Action

**Implement in Sprint S2.**  Extract from the existing linearmodels result object:

```python
first_stage = res.first_stage
fs_f = {col: float(first_stage.diagnostics["F-statistic"][col])
        for col in first_stage.diagnostics.index}
sargan_stat = float(res.sargan.stat) if res.sargan is not None else None
wu_hausman = float(res.wu_hausman.stat) if res.wu_hausman is not None else None
```

Store in `result.extra` and surface in `DiagnosticResult` objects from `diagnostics()`.

**Severity maintained:** HIGH.

---

## Finding SC-6: Breusch-Pagan auxiliary regression uses raw X for FE residuals

### Reviewer claim

The BP test for FE models uses within-transformed residuals in the squared-residual
regression but raw (non-demeaned) X as the auxiliary regressors.  The reviewer calls
this a misspecified test and rates it HIGH.

### Theory check

The Breusch-Pagan (1979) test in its general form specifies:

> Regress ε² on any set of variables z hypothesized to explain heteroskedasticity.

The choice of z is not restricted.  Using raw X is a valid choice: it tests whether
the absolute magnitude of FE residuals depends on the level of the regressors.  This
captures between-entity heteroskedasticity, which is a real concern in panel data
(larger firms might have larger residual variance).

The reviewer's argument — that within-transformed X should be used because FE operates
in the within space — is theoretically coherent but is one of two equally valid designs:

- **Raw X:** Tests heteroskedasticity in levels (within + between components jointly)
- **Within-X:** Tests heteroskedasticity in deviations from entity means only

### Software survey

| Software | BP test after FE | Auxiliary regressors |
|----------|-----------------|---------------------|
| Stata `xtreg, fe` + `hettest` | Not directly available; user constructs manually | Raw X (if user runs `reg e2 x` manually) |
| R plm | No built-in BP for FE | N/A |
| R fixest | No built-in BP for FE | N/A |
| statsmodels `het_breuschpagan` | Cross-section only | User-supplied |

**No major software package defines a canonical panel BP test.**  Stata's `hettest` for
OLS uses raw X.  There is no consensus implementation for FE.

### Classification

**Design choice.**  Using raw X in the BP auxiliary regression is consistent with the
OLS BP test convention and tests a valid hypothesis.  The reviewer's claim that this is
"misspecified" is not supported by a clear theoretical standard or software convention.

The real issue is **documentation**: users see "Breusch-Pagan" without knowing which
auxiliary regressors were used, making the statistic opaque.

### Action

**Document the limitation** rather than change the implementation.  Add to the
`DiagnosticResult` for BP (for FE models):

```
Note: auxiliary regression uses raw (non-within-transformed) regressors. 
This tests whether squared FE residuals depend on regressor levels (between-entity 
heteroskedasticity). Within-entity heteroskedasticity is not directly captured.
```

**Severity downgrade:** HIGH → MEDIUM.  This is not a misspecified test; it is an
adequately specified test whose scope needs documentation.

---

## Finding SC-7: Durbin-Watson statistic computed across entity boundaries

### Reviewer claim

`np.diff(resids)` on all rows includes N−1 cross-entity differences.  The statistic
is not the standard DW for panel data.  Rated CRITICAL.

### Theory check

The Durbin-Watson statistic (Durbin and Watson 1950, 1951) is defined for a single
time series.  For panel data, two generalizations exist:

1. **Bhargava, Franzini, Narendranathan (1982) panel DW**: Computes within-entity
   differences only: `Σᵢ Σₜ₌₂ (eᵢₜ − eᵢ,ₜ₋₁)² / Σᵢ Σₜ eᵢₜ²`.  This is published
   in Biometrika and has tabulated critical values.

2. **EconFlow's formula**: `Σₜ(eₜ − eₜ₋₁)² / Σeₜ²` across all rows, including
   the jump from entity i's last period to entity i+1's first period.

The cross-entity differences are the difference of residuals from unrelated observations.
Under any reasonable serial correlation model, these cross-entity jumps add noise to the
numerator with no signal content.  The net effect is a bias **toward 2** (no correlation),
since the cross-entity differences resemble white noise.  For the Grunfeld data: 219 total
differences of which 10 (4.6%) are cross-entity.

The DW = 0.38 reported for OLS is significantly below 2, suggesting severe positive serial
correlation.  The bias from 10 spurious differences is small in magnitude for this dataset
but grows proportionally to N (number of entities).

The code's own docstring acknowledges: "This formula computes differences across ALL rows,
including across entities, which can produce cross-entity 'jumps' that inflate the statistic."

### Software survey

| Software | Panel serial correlation DW formula |
|----------|-------------------------------------|
| Stata `xtserial` | Uses Wooldridge (2002) test, NOT DW |
| R plm `pdwtest()` | Bhargava-Franzini-Narendranathan (1982): within-entity diffs only |
| R fixest | No DW reported; recommends cluster-robust SEs |
| linearmodels | Does not report DW; no panel-specific DW function |

The BFN (1982) panel DW is the only published version with tabulated critical values.
EconFlow's formula has no published critical values and is not comparable to any table.

### Classification

**Objectively incorrect** as a DW statistic.  The formula is not the DW statistic by
any published definition.  The 1.5 threshold used in the conclusion text is from
Savin-White (1977) tables which apply to the BFN formula or time-series DW — not to
EconFlow's across-all-rows formula.

### Action

**Fix in Sprint S1 (highest-priority scientific fix).**  Replace with the
Bhargava-Franzini-Narendranathan panel DW:

```python
entity_sq_diffs = []
resids_series = pd.Series(resids, index=result.index)  # MultiIndex
for eid in resids_series.index.get_level_values(0).unique():
    e = resids_series.xs(eid, level=0).sort_index().values
    if len(e) > 1:
        entity_sq_diffs.extend((np.diff(e) ** 2).tolist())
dw = sum(entity_sq_diffs) / ss_resids
```

This matches `plm::pdwtest()` and has tabulated critical values.  The threshold 1.5
and interpretation text become valid again.

**Phase 6 numerical pins will change** as a direct consequence.  This is expected and
correct: the prior pins reflected an incorrect formula.

**Severity maintained:** The reviewer's CRITICAL is acceptable for this finding — it is
the most widely used diagnostic statistic and is producing a non-standard output with
no published reference for the interpretation threshold.

---

## Finding SC-8: Missing Hausman Test (FE vs RE)

### Reviewer claim

No Hausman test linking FE and RE estimators.  Rated MEDIUM.

### Theory check

The classic Hausman (1978) test compares consistent (FE) versus potentially efficient but
inconsistent (RE) estimators.  The test statistic is `(β̂_FE − β̂_RE)' [V(β̂_FE) − V(β̂_RE)]⁻¹ (β̂_FE − β̂_RE)`,
distributed χ²(k) under H₀: RE is consistent.

**Important limitation**: The standard Hausman test assumes homoskedastic errors under H₀.
With cluster-robust SEs (which EconFlow defaults to for FE), the test is invalid.
Wooldridge (2010, §10.7) proposes a robust version based on an artificial regression.
This limitation is largely ignored in practice but is theoretically important.

### Software survey

| Software | Hausman test |
|----------|-------------|
| Stata | `hausman fe_model re_model` (standard); `suest` for robust version |
| R plm | `phtest(fe_model, re_model)` |
| R fixest | No built-in Hausman test |
| linearmodels | No built-in Hausman test |

R fixest and linearmodels — both modern FE-oriented packages — omit the Hausman test.
This reflects the trend in applied econometrics toward FE by default when N is large,
with Hausman treated as a legacy check.

### Classification

**Design choice.**  The Hausman test is standard but not universally implemented.  Its
absence from fixest and linearmodels indicates it is not table-stakes for a modern panel
package.

### Action

**Document the limitation.**  Add a note in the RE estimator description that the Hausman
test is not built-in and point users to `linearmodels` or `plm` for it.  Implement as a
standalone function `econflow.tests.hausman(fe_result, re_result)` in Sprint S3, not as
integrated diagnostics.

**Severity maintained:** MEDIUM.

---

## Finding SC-9: VIF Computed on Raw X for FE Models

### Reviewer claim

For FE models, VIF should be computed on within-transformed (demeaned) regressors because
FE operates on the within space.  Rated MEDIUM.

### Theory check

VIF for regressor j is `1 / (1 − R²ⱼ)` where R²ⱼ is from regressing xⱼ on all other
regressors.  The question is: which space?

**Case for raw X VIF:** Entity-level collinearity reduces the amount of within-entity
variation after demeaning.  If two variables track each other across firms in levels, the
within variation is also collinear.  Raw VIF is a sufficient condition for within-VIF problems.

**Case for within-X VIF:** Two variables could be collinear between entities but perfectly
identified within.  Raw VIF would falsely flag a non-problem for FE.  The converse is also
possible: uncorrelated in levels but collinear within entity (within-VIF problem, missed by
raw VIF).

### Software survey

| Software | VIF after FE |
|----------|-------------|
| Stata `xtreg, fe` + `vif` | Not available directly; `estat vif` not supported after `xtreg` |
| R fixest `vif()` | Computes VIF on within-transformed regressors (demean first, then VIF) |
| R plm | No built-in VIF |
| linearmodels | No built-in VIF |

R fixest's `vif()` after `feols()` uses within-transformed regressors.  This is the only
major package that defines FE VIF, and it uses the within-transformed version.

### Classification

**Design choice** for the current raw X implementation.  **Reviewer preference** in
framing this as wrong — it is a valid but suboptimal choice compared to R fixest's approach.

### Action

**Expose both behaviors.**  For OLS: raw VIF (current, correct).  For FE models: compute
within-VIF by subtracting entity means before calling `variance_inflation_factor`.  Report
the within-VIF as the primary VIF for FE, matching fixest.  Keep raw VIF in `extra` for
comparison.  This is a MEDIUM-priority Sprint S2 item.

**Severity maintained:** MEDIUM.  The current raw VIF for FE is not wrong, but within-VIF
is more informative and matches the best available comparable (fixest).

---

## Finding SC-10: Missing Panel Unit Root Tests (IPS, LLC, Fisher-ADF)

### Reviewer claim

No pre-estimation stationarity tests.  Important for macroeconomic panels.

### Theory check

Panel unit root tests (IPS: Im, Pesaran, Shin 2003; LLC: Levin, Lin, Chu 2002) are
standard for panels where T is large enough for meaningful time-series analysis (typically
T ≥ 15–20).  For short macro panels or micro panels (N=1000 firms, T=5 years), panel
unit root tests have low power and are rarely used.

### Software survey

| Software | Panel unit root |
|----------|----------------|
| Stata | `xtunitroot ips`, `xtunitroot llc` |
| R plm | `purtest()` |
| R fixest | Not included; fixest is micro-panel focused |
| linearmodels | Not included |

### Classification

**Design choice.**  Panel unit root tests are important for macro panels, irrelevant for
micro panels.  Their omission from fixest and linearmodels reflects a deliberate scope
decision (these packages target micro/applied econometrics).

### Action

**Document the limitation** in Sprint S1 (one line in the RE/FE estimator docs: "No panel
unit root pre-tests are built in; use `plm::purtest()` in R or `xtunitroot` in Stata").
Implement as an optional diagnostic plugin in Sprint S4, not in the core estimator chain.

**Severity downgrade:** MEDIUM → LOW for the base package.

---

## Finding SC-11: Missing Pesaran CD Test (Cross-Sectional Dependence)

### Reviewer claim

No Pesaran (2004) cross-sectional dependence test.  MEDIUM severity.

### Theory check

Pesaran's CD test statistic:

CD = √(2T/(N(N−1))) × Σᵢ<ⱼ ρᵢⱼ ~ N(0,1) under H₀: no CSD

This is important when: (a) N is small relative to T, (b) entities share common shocks
(country-level panels), (c) the researcher suspects factor structure in errors.  For large-N
micro panels (firms, individuals), CSD is less critical.

### Software survey

| Software | CD test |
|----------|---------|
| Stata | `xtcsd` (user-written) |
| R plm | `pcdtest()` |
| R fixest | Not included |
| linearmodels | Not included |

### Classification

**Design choice** to omit.  Like panel unit roots, CD testing is more relevant for macro
panels than for micro applications that are EconFlow's apparent primary use case.

### Action

**Document the limitation.**  Implement in Sprint S4 if macro panel use cases are targeted.
MEDIUM → LOW for the current scope.

---

## Finding SC-12: Missing Cluster Count Warning

### Reviewer claim

With clustered SEs and ngroups < threshold (rule of thumb: 30–50), inference is unreliable.

### Theory check

The asymptotic justification for cluster-robust SEs requires the number of clusters → ∞.
With fewer than 30 clusters, the χ² approximation can be poor.  Cameron, Gelbach, and
Miller (2008) demonstrate substantial size distortion below 20 clusters.

### Classification

**Design choice** to omit.  Several packages warn on this (Stata flags it in some contexts);
others leave it to the user.

### Action

**Implement in Sprint S2** as a low-cost check.  One guard in `_build_result()`:

```python
if cov_type in ("clustered",) and ngroups < 30:
    warnings.append(DiagnosticResult(
        name="Low Cluster Count",
        statistic=ngroups,
        conclusion=f"Only {ngroups} clusters — cluster-robust SEs may be unreliable (rule of thumb: ≥30).",
    ))
```

Severity: MEDIUM.

---

## Finding SC-13: Missing Absorbed Regressor Detection

### Reviewer claim

Time-invariant regressors in FE models are absorbed, producing NaN or zero coefficients
with no warning from EconFlow.

### Theory check

This is a documented pitfall of FE estimation.  Stata raises an error: "dropped because
of collinearity" for time-invariant regressors.  linearmodels' PanelOLS raises an
`AbsorptionError` when a regressor is collinear with entity effects.

### Classification

**Objectively incorrect** as user experience.  linearmodels will raise or return NaN/zero;
EconFlow wraps this in a generic `EstimatorError` without pre-checking.  The fix is
pre-validation, not changing estimation.

### Action

**Implement in Sprint S2.**  Before calling PanelOLS, check:

```python
within_var = panel[regs].groupby(level=0).var().max()
time_invariant = within_var[within_var == 0].index.tolist()
if time_invariant:
    raise EstimatorError(
        f"Regressors {time_invariant} have zero within-entity variance and will be "
        f"absorbed by entity fixed effects. Remove them or use a pooled estimator.",
        estimator_id=self.estimator_id,
    )
```

Severity: MEDIUM.

---

## Finding SC-14: Missing Singleton Entity Warning (FirstDifference / FE)

### Reviewer claim

Entities with only one time period contribute nothing to the within estimator and consume
a degree of freedom.

### Classification

**Design choice** to omit in many packages.  Stata 16+ warns on singletons; older Stata
does not.  R fixest drops singletons by default.

### Action

**Document the limitation** for now; implement as a Sprint S3 warning.  LOW severity.

---

## Finding SC-15: Missing FirstDifference Gap Detection

### Reviewer claim

FD with unbalanced panels drops observations at within-entity time gaps silently.

### Classification

**Design choice.**  linearmodels' FirstDifferenceOLS handles gaps silently.  EconFlow
could surface the observation loss count.

### Action

**Implement in Sprint S3** as a post-fit diagnostic: report number of within-entity time
gaps and observations lost to differencing.  LOW severity.

---

## Committee Disagreements with the Reviewer

| Finding | Reviewer severity | Committee severity | Reason for change |
|---------|------------------|--------------------|-------------------|
| SC-4 (IV2SLS is pooled) | CRITICAL | HIGH | Pooled IV is a valid estimator; the issue is documentation |
| SC-6 (BP uses raw X) | HIGH | MEDIUM | Design choice consistent with OLS BP convention; no consensus standard for panel BP |
| SC-1 (overall vs within R²) | HIGH | MEDIUM | Within-R² is stored in `extra`; issue is field priority, not data availability |
| SC-2 (adj-R² formula for FE) | HIGH | MEDIUM | No universal standard; SC-3 (adj=R² bug) is higher priority |
| VIF on raw X | MEDIUM | MEDIUM (expose both) | Confirmed MEDIUM; within-VIF should be added alongside raw VIF |
| Panel unit root tests | MEDIUM | LOW | Scope-appropriate to omit from core; plugin path is correct |
| Pesaran CD test | MEDIUM | LOW | Same reasoning as panel unit roots |

---

## Final Implementation Priority List — EconFlow 1.0

Priority is assigned based on the committee's adjudicated severities, grouped by sprint.

---

### Sprint S1 — Fix Objectively Incorrect Statistics (block-hard)

These produce wrong numbers or nonsense results by any standard.  Nothing in Sprint S2
should begin until all five are closed.

| Priority | ID | Fix | Effort |
|----------|----|-----|--------|
| 1 | SC-7 | Replace cross-entity DW with Bhargava-Franzini-Narendranathan within-entity DW | 2h |
| 2 | SC-3 | Compute actual `rsquared_adj` for RE, FD, IV2SLS using `1-(1-R²)×(N-1)/df_resid` | 1h |
| 3 | SC-1 | Set `rsquared = float(res.rsquared_within)` for EntityFE and TwoWayFE; store overall in `extra` | 1h |
| 4 | SC-2 | Fix FE adjusted R² to use within-R² with corrected df term `(N-N_entities)` | 1h |
| 5 | SC-13 | Add time-invariant regressor pre-check in EntityFE and TwoWayFE `validate()` | 2h |

**Acceptance gate:** Regenerate Phase 6 numerical pins from a live run after all five are merged.
New pins replace old ones.  The regression test suite is updated from the live run, not by
hand.  The DW and adj-R² values will change; this is expected and correct.

---

### Sprint S2 — Scope Limitations and Documentation Accuracy

These are either design choices that need documentation or moderate-effort correctness additions.

| Priority | ID | Fix | Effort |
|----------|----|-----|--------|
| 6 | SC-4 (doc) | Add explicit warning in IV2SLS description: "pooled only, no entity FE" | 30m |
| 7 | SC-5 | Surface first-stage F, Sargan J-test, and Wu-Hausman from linearmodels IV result | 3h |
| 8 | SC-12 | Cluster count guard: warn when ngroups < 30 with clustered SEs | 1h |
| 9 | SC-6 (doc) | Add diagnostic note explaining raw-X BP for FE and what it tests | 1h |
| 10 | SC-9 | Add within-VIF for FE models alongside raw VIF | 2h |

---

### Sprint S3 — New Estimator: Panel IV with FE

| Priority | ID | Fix | Effort |
|----------|----|-----|--------|
| 11 | SC-4 (impl) | Implement `fe_iv` estimator using within-transformed data + `linearmodels.IV2SLS` or `linearmodels.IVGMM` | 1 week |
| 12 | SC-14 | Singleton entity warning in FE and FD | 2h |
| 13 | SC-15 | FD gap detection: report within-entity time gaps and observation loss | 2h |
| 14 | SC-8 | `econflow.tests.hausman(fe, re)` as standalone function | 4h |

---

### Sprint S4 — Stub Implementation and Advanced Diagnostics

| Priority | ID | Fix | Effort |
|----------|----|-----|--------|
| 15 | — | Implement SystemGMM (Arellano-Bond/Blundell-Bond via `pydynpd`) | 2–3 weeks |
| 16 | — | Implement PanelQuantile (Canay 2011 two-step) | 1 week |
| 17 | — | Wooldridge (2002) serial correlation test for panels | 3h |
| 18 | — | Time fixed effects joint F-test for TwoWayFE | 2h |
| 19 | — | RESET functional form test | 2h |

---

### Out of Scope for EconFlow 1.0 (document as limitations)

| Finding | Rationale |
|---------|-----------|
| Panel unit root tests (IPS, LLC) | Micro-panel scope; refer to `plm::purtest()` |
| Pesaran CD test | Macro-panel scope; refer to `plm::pcdtest()` |
| Multi-way clustering | Not in linearmodels; significant complexity |
| Spatial standard errors | Driscoll-Kraay SEs require dedicated implementation |
| Breusch-Godfrey higher-order serial correlation | DW fix in S1 is sufficient for 1.0 |

---

## Release Readiness Assessment (Committee)

EconFlow is **not ready for v1.0** as stated.  The DW statistic (SC-7) and the
rsquared_adj = rsquared bug (SC-3) are present in all reported diagnostic outputs.
Any paper citing EconFlow diagnostic statistics would be citing at minimum one
non-standard and one provably wrong number.

After Sprint S1 (five fixes, estimated 7 hours of implementation), EconFlow reaches a
state where all reported statistics are either correct or clearly documented as scope
limitations.  Sprint S1 completion is the minimum bar for a v0.2 tag suitable for
external beta testing.

**Sprint S1 + S2 completion** is the minimum bar for v1.0 given the IV documentation
failure and missing IV diagnostics.

**Panel IV implementation (Sprint S3) is recommended but not required** for v1.0 if
the pooled-only scope is clearly documented.

---

*End of Scientific Validation Committee Review*
*Committee members: econometric theory (Wooldridge 2010; Cameron & Trivedi 2005; Angrist & Pischke 2009), software survey (Stata 18, R 4.4 with fixest 0.12 / plm 2.6 / AER 1.2, linearmodels 6.0)*
