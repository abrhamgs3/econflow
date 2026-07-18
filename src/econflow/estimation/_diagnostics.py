"""
econflow.estimation._diagnostics — Shared post-estimation diagnostic helpers.

Phase 3 of the pipeline-estimation integration migration.

This module is the SINGLE authoritative implementation of the standard
diagnostics that every linearmodels-backed estimator (EntityFE, TwoWayFE,
PooledOLS) computes after fitting:

1. **VIF** (Variance Inflation Factor) — multicollinearity detection (raw X)
2. **Breusch-Pagan** — heteroskedasticity test
3. **Durbin-Watson** (AR(1) proxy) — serial correlation detection
4. **Cluster Count** (Sprint S2) — validates that enough clusters exist when
   clustered standard errors are requested
5. **Within-VIF** (Sprint S2) — VIF on entity-demeaned regressors (FE only)

Phase 6 (2026-07-10): ``pipeline_generic._run_diagnostics()`` has been
deleted.  ``pipeline_generic._write_diagnostics()`` is now the sole CSV
writer; it reads ``EstimationResult.diagnostic_results`` produced here.
This module is therefore the sole diagnostic computation path.

Architecture notes
------------------
* ``compute_standard_diagnostics(result)`` is the public entry point.
  Estimators call it from their ``diagnostics()`` methods.
* The function reads ``result.extra["residuals"]``, ``result.extra["X_vif_values"]``
  and ``result.extra["X_vif_columns"]`` — stored by ``fit()`` in each estimator.
* No data argument is required by ``diagnostics(self, result)`` (Architecture
  Freeze §1.6 forbids signature changes to the abstract method).  All data
  needed for diagnostics must travel through ``result.extra``.
* All diagnostics are individually guarded with try/except; a failure
  in one does not prevent the others from running.  An empty list is returned
  if all diagnostics fail (not an exception).

Numeric fidelity to the pipeline baseline
------------------------------------------
Cross-checked against ``tests/integration/fixtures/baseline/diagnostics.csv``
for the Grunfeld dataset.  Accepted tolerances: 1e-4 (4 decimal places, matching
the ``round(..., 4)`` used in the pipeline CSV writer).

The formulas below matched ``pipeline_generic._run_diagnostics()`` (now deleted).
This module is the sole authoritative implementation; formulas are:

    VIF: max over regressors of statsmodels variance_inflation_factor;
         fallback to manual R² auxiliary-regression VIF.
         Computed on RAW (non-within-transformed) regressors.

    BP:  statsmodels.stats.diagnostic.het_breuschpagan(residuals, X_const)
         where residuals = model residuals (within-transformed for FE),
         X_const = [1 | raw_X] (NOT within-transformed).
         For FE/TWFE models, this is a mixed test of effects heteroskedasticity
         and regressor-related heteroskedasticity (within residuals, raw X).

    DW:  Bhargava-Franzini-Narendranathan (1982) panel DW when
         residuals_index is available (entity_index derived from it):
           Σᵢ Σₜ₌₂ (eᵢₜ − eᵢ,ₜ₋₁)² / Σᵢ Σₜ eᵢₜ²  (within-entity diffs only)
         Falls back to standard time-series DW (np.diff over all rows)
         when no entity information is provided.

    Cluster Count (Sprint S2):
         Emitted when cov_type="clustered" is stored in result.extra.
         Warns when ngroups < 10 (Cameron & Miller 2015 rule of thumb).

    Within-VIF (Sprint S2):
         VIF computed on entity-demeaned (within-transformed) regressors.
         X_demeaned = panel[regs] − entity_mean.
         Only emitted when "X_within_vif_values" is present in result.extra
         (populated by EntityFE.fit() and TwoWayFE.fit()).

Diagnostic IDs
--------------
* ``"vif"``
* ``"breusch_pagan"``
* ``"durbin_watson"``
* ``"cluster_count"``   (Sprint S2)
* ``"vif_within"``      (Sprint S2)
"""

from __future__ import annotations

import numpy as np

from econflow.estimation.result import DiagnosticResult, EstimationResult

# Threshold constants — single location; mirrors the pipeline hard-coded thresholds.
_VIF_THRESHOLD: float = 10.0   # VIF > 10 flagged as multicollinearity concern
_DW_LOW: float = 1.5           # DW < 1.5 → positive autocorrelation
_DW_HIGH: float = 2.5          # DW > 2.5 → negative autocorrelation
_BP_ALPHA: float = 0.05        # significance level for BP conclusion
# Sprint S2: cluster-count threshold (Cameron & Miller 2015 rule of thumb)
_CLUSTER_MIN: int = 10         # < 10 clusters → clustered SE inference unreliable


# ---------------------------------------------------------------------------
# Individual diagnostic functions
# ---------------------------------------------------------------------------


def _diag_vif(
    X_values: list[list[float]],
    columns: list[str],
) -> DiagnosticResult:
    """
    Variance Inflation Factor (VIF).

    Purpose
    -------
    Detects multicollinearity in the regressor matrix.  High VIF indicates
    that a regressor is nearly linearly dependent on others, inflating its
    standard error.

    Assumptions
    -----------
    * At least 2 regressors (VIF is undefined for a single regressor).
    * More observations than regressors (invertible X'X).

    Interpretation
    --------------
    VIF < 5: no concern.
    VIF 5–10: moderate collinearity — monitor.
    VIF > 10: strong collinearity — coefficient estimates unreliable.

    Limitations
    -----------
    * VIF is computed on the RAW (non-within-transformed) regressors.
    * Constant terms are excluded; only named regressors appear in VIF.
    * Uses X from the fitted sample, not the full dataset.

    Parameters
    ----------
    X_values:
        2-D list (nobs × k) — raw regressor values from fit().
    columns:
        Ordered list of regressor column names (no const).

    Returns
    -------
    DiagnosticResult
        diagnostic_id="vif", statistic=max_vif.
    """
    _id = "vif"
    _name = "Variance Inflation Factor (max)"

    # Strip constant terms — same filter as pipeline
    regs = [c for c in columns if c.lower() not in ("const", "intercept", "constant")]

    if len(regs) < 2:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion="VIF not meaningful with fewer than 2 regressors.",
            level="info",
            extra={"vif_values": {}, "max_vif": float("nan"),
                   "threshold": _VIF_THRESHOLD},
        )

    X_arr = np.array(X_values, dtype=float)

    # Restrict to the reg columns (columns list may include extras)
    # X_values columns correspond to `columns` in order.
    col_idx = {c: i for i, c in enumerate(columns)}
    reg_idx = [col_idx[r] for r in regs if r in col_idx]
    if not reg_idx:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion="Regressor columns not found in stored X.",
            level="info",
            extra={"vif_values": {}, "max_vif": float("nan"),
                   "threshold": _VIF_THRESHOLD},
        )

    X_data = X_arr[:, reg_idx]
    if X_data.shape[0] <= X_data.shape[1]:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion="Insufficient observations to compute VIF.",
            level="info",
            extra={"vif_values": {}, "max_vif": float("nan"),
                   "threshold": _VIF_THRESHOLD},
        )

    vif_vals: dict[str, float] = {}
    try:
        from statsmodels.stats.outliers_influence import (  # noqa: PLC0415
            variance_inflation_factor,
        )
        X_c = np.column_stack([np.ones(len(X_data)), X_data])
        vif_vals = {
            r: float(variance_inflation_factor(X_c, i + 1))
            for i, r in enumerate(regs)
        }
    except Exception:
        # Fallback: manual R² auxiliary-regression approach (same as pipeline)
        for i, var in enumerate(regs):
            other = [j for j in range(len(regs)) if j != i]
            try:
                y_v = X_data[:, i]
                Xo = np.column_stack([np.ones(len(X_data)), X_data[:, other]])
                beta = np.linalg.lstsq(Xo, y_v, rcond=None)[0]
                yhat = Xo @ beta
                ss_res = float(np.sum((y_v - yhat) ** 2))
                ss_tot = float(np.sum((y_v - y_v.mean()) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                vif_vals[var] = 1.0 / (1.0 - r2) if r2 < 1 else float("inf")
            except Exception:
                vif_vals[var] = float("nan")

    finite_vals = [v for v in vif_vals.values() if v == v and v != float("inf")]
    max_vif = max(finite_vals) if finite_vals else float("nan")
    flagged = [v for v, val in vif_vals.items() if val > _VIF_THRESHOLD]

    if flagged:
        conclusion = (
            f"Multicollinearity concern: {flagged} "
            f"have VIF > {_VIF_THRESHOLD} (max={max_vif:.2f})"
        )
        level = "warning"
    else:
        conclusion = f"No multicollinearity concern (max VIF = {max_vif:.2f} < {_VIF_THRESHOLD})"
        level = "info"

    return DiagnosticResult(
        diagnostic_id=_id,
        diagnostic_name=_name,
        statistic=float(max_vif) if max_vif == max_vif else None,
        conclusion=conclusion,
        level=level,
        extra={"vif_values": vif_vals, "max_vif": max_vif,
               "threshold": _VIF_THRESHOLD},
    )


def _diag_breusch_pagan(
    residuals: list[float],
    X_values: list[list[float]],
) -> DiagnosticResult:
    """
    Breusch-Pagan test for heteroskedasticity.

    Purpose
    -------
    Tests H₀: the residual variance is constant across observations
    (homoskedasticity).  Rejection indicates heteroskedastic errors; robust
    or clustered standard errors should be used.

    Assumptions
    -----------
    * Residuals approximately normally distributed under H₀.
    * More observations than regressors.
    * For FE/TWFE models, residuals are the within-transformed residuals
      from linearmodels; X is the raw (non-within-transformed) regressor matrix.
      The test is therefore a joint test of both effects heteroskedasticity
      and regressor-related heteroskedasticity.

    Interpretation
    --------------
    p-value < 0.05 → reject H₀ → evidence of heteroskedasticity.
    p-value ≥ 0.05 → fail to reject H₀ → no strong evidence.

    Limitations
    -----------
    * Requires statsmodels.  Returns a "not applicable" result if unavailable.
    * Small-sample power may be low.
    * Uses the simplified LM statistic, not the White test.

    Parameters
    ----------
    residuals:
        Flat list of residual values (model residuals from fit()).
    X_values:
        2-D list (nobs × k) — raw regressor values.

    Returns
    -------
    DiagnosticResult
        diagnostic_id="breusch_pagan", statistic=LM stat, pvalue=LM p-value.
    """
    _id = "breusch_pagan"
    _name = "Breusch-Pagan Heteroskedasticity Test"

    resids = np.array(residuals, dtype=float)
    X_arr = np.array(X_values, dtype=float)

    if len(resids) <= X_arr.shape[1] + 1:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion="Insufficient observations for Breusch-Pagan test.",
            level="info",
        )

    try:
        from statsmodels.stats.diagnostic import het_breuschpagan  # noqa: PLC0415

        # X_aligned = [const | raw_X] — same construction as pipeline
        X_aligned = np.column_stack([np.ones(len(resids)), X_arr])
        lm, lm_pval, _fstat, _fpval = het_breuschpagan(resids, X_aligned)
        lm = float(lm)
        lm_pval = float(lm_pval)

        if lm_pval < _BP_ALPHA:
            conclusion = (
                f"Heteroskedasticity detected (p={lm_pval:.4f} < {_BP_ALPHA}) "
                "— use robust SEs"
            )
            level = "warning"
        else:
            conclusion = f"No heteroskedasticity concern (p={lm_pval:.4f})"
            level = "info"

        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            statistic=lm,
            pvalue=lm_pval,
            conclusion=conclusion,
            level=level,
            extra={"lm_stat": lm, "lm_pvalue": lm_pval},
        )

    except Exception as exc:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion=f"Breusch-Pagan test failed: {exc}",
            level="info",
        )


def _diag_durbin_watson(
    residuals: list[float],
    entity_index: list | None = None,
) -> DiagnosticResult:
    """
    Durbin-Watson serial correlation statistic.

    Sprint S1 — Two computation paths:

    **Panel path (BFN, default when entity_index is supplied)**
        Implements the Bhargava, Franzini, and Narendranathan (1982) panel
        Durbin-Watson statistic:

            DW = Σᵢ Σₜ₌₂ (eᵢₜ − eᵢ,ₜ₋₁)² / Σᵢ Σₜ eᵢₜ²

        Only consecutive *within-entity* differences enter the numerator.
        Cross-entity differences (last obs of entity i → first obs of entity i+1)
        are excluded.  The critical-value tables published in BFN (1982) apply
        to this statistic.

        The panel path is chosen automatically when ``entity_index`` is
        provided and contains more than one unique entity.

    **Time-series path (fallback)**
        Used when ``entity_index`` is None or contains only one entity:

            DW = Σₜ (eₜ − eₜ₋₁)² / Σₜ eₜ²

        This is the standard Durbin-Watson formula and is appropriate for
        a single cross-section or true time-series regression.

    Purpose
    -------
    Provides a quick check for AR(1) serial correlation in the residuals.
    DW ≈ 2 indicates no autocorrelation; DW < 1.5 indicates positive
    autocorrelation; DW > 2.5 indicates negative autocorrelation.

    Assumptions
    -----------
    * Residuals are ordered by the panel's (entity, time) MultiIndex, which
      is guaranteed by the fit() implementation (panel is always sort_index()ed).
    * At least 3 observations (need at least one diff).
    * For the panel path: at least 2 time periods per entity that has any
      within-entity difference.

    Interpretation
    --------------
    DW ∈ [1.5, 2.5]: no strong serial correlation — no action required.
    DW < 1.5: positive autocorrelation likely — consider clustered SEs or
              lag structure in the model.
    DW > 2.5: negative autocorrelation possible — inspect model specification.

    .. note::
        The 1.5 and 2.5 thresholds are heuristic approximations derived from
        the Savin-White (1977) time-series critical-value tables.  They are
        **not** exact panel critical values.  The Bhargava, Franzini, and
        Narendranathan (1982) paper provides separate panel DW critical-value
        tables (Table 1) whose lower and upper bounds (dL, dU) depend on the
        number of entities (N), the number of time periods (T), and the number
        of regressors (k).  For rigorous inference use the BFN (1982) tables
        rather than the 1.5/2.5 bands shown in the conclusion text.

    Parameters
    ----------
    residuals:
        Flat list of residual values in (entity, time) sorted order.
    entity_index:
        Optional list of entity IDs corresponding to each residual, in the
        same order.  When provided with multiple distinct entities the BFN
        panel formula is used; otherwise the time-series formula is used.

    Returns
    -------
    DiagnosticResult
        diagnostic_id="durbin_watson", statistic=DW value.

    References
    ----------
    Bhargava, A., L. Franzini, and W. Narendranathan (1982).
    "Serial Correlation and the Fixed Effects Model."
    *Review of Economic Studies* 49(4), 533–549.
    """
    _id = "durbin_watson"

    resids_arr = np.array(residuals, dtype=float)

    if len(resids_arr) < 3:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name="Serial Correlation — Durbin-Watson",
            conclusion="Insufficient observations for Durbin-Watson test.",
            level="info",
        )

    ss_resids = float(np.sum(resids_arr ** 2))
    if ss_resids == 0.0:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name="Serial Correlation — Durbin-Watson",
            conclusion="All residuals are zero — DW undefined.",
            level="info",
            extra={"dw": float("nan")},
        )

    # ------------------------------------------------------------------
    # Choose formula based on whether entity information is available
    # ------------------------------------------------------------------
    use_panel = (
        entity_index is not None
        and len(entity_index) == len(residuals)
        and len(set(entity_index)) > 1
    )

    if use_panel:
        # BFN (1982) panel Durbin-Watson — within-entity differences only
        _name = "Serial Correlation — Durbin-Watson (BFN Panel)"
        entity_arr = np.asarray(entity_index)
        sq_diffs: list[float] = []
        for eid in dict.fromkeys(entity_index):  # preserves (entity, time) order
            mask = entity_arr == eid
            e_resids = resids_arr[mask]
            if len(e_resids) > 1:
                sq_diffs.extend((np.diff(e_resids) ** 2).tolist())
        if not sq_diffs:
            return DiagnosticResult(
                diagnostic_id=_id,
                diagnostic_name=_name,
                conclusion="No within-entity differences available — DW undefined.",
                level="info",
                extra={"dw": float("nan")},
            )
        dw = float(sum(sq_diffs) / ss_resids)
        formula = "bfn_panel"
    else:
        # Standard time-series Durbin-Watson (single entity or no index)
        _name = "Serial Correlation — Durbin-Watson"
        diff = np.diff(resids_arr)
        dw = float(np.sum(diff ** 2) / ss_resids)
        formula = "time_series"

    if dw < _DW_LOW:
        conclusion = (
            f"Positive serial correlation likely (DW={dw:.4f} < {_DW_LOW}) — "
            "consider clustered SEs or lag structure"
        )
        level = "warning"
    elif dw > _DW_HIGH:
        conclusion = f"Negative serial correlation possible (DW={dw:.4f} > {_DW_HIGH})"
        level = "warning"
    else:
        conclusion = f"No strong serial correlation (DW={dw:.4f})"
        level = "info"

    return DiagnosticResult(
        diagnostic_id=_id,
        diagnostic_name=_name,
        statistic=dw,
        conclusion=conclusion,
        level=level,
        extra={"dw": dw, "formula": formula},
    )


# ---------------------------------------------------------------------------
# Sprint S2 — Cluster-count validation
# ---------------------------------------------------------------------------


def _diag_cluster_count(ngroups: int) -> DiagnosticResult:
    """
    Cluster-count validation for clustered standard errors.

    Purpose
    -------
    When clustered standard errors are requested, reliable asymptotic inference
    requires a sufficient number of clusters.  With very few clusters the
    cluster-robust variance estimator is severely biased downward, producing
    spuriously small standard errors and over-rejection of true null hypotheses.

    Assumptions
    -----------
    * Standard asymptotic theory for clustered SEs applies when N_clusters
      is large; with small N_clusters, wild bootstrap or other finite-sample
      corrections should be used.

    Interpretation
    --------------
    N_clusters ≥ 10: inference is broadly reliable (Cameron & Miller 2015).
    N_clusters < 10: substantial downward bias in clustered SEs; consider
                     wild bootstrap (Roodman et al. 2019) or feasible GLS.

    Limitations
    -----------
    * The threshold of 10 is a rule of thumb, not a formal test.
    * Problem severity increases as N_clusters decreases below 10.
    * For macro panels with very few countries/regions, even 10 may be
      insufficient; consult simulation evidence for your specific design.

    Parameters
    ----------
    ngroups:
        Number of clusters (unique entities) in the fitted model.

    Returns
    -------
    DiagnosticResult
        diagnostic_id="cluster_count", statistic=float(ngroups).

    References
    ----------
    Cameron, A. C. and D. L. Miller (2015).
    "A Practitioner's Guide to Cluster-Robust Inference."
    *Journal of Human Resources* 50(2), 317–372.
    """
    _id = "cluster_count"
    _name = "Cluster Count Validation"

    if ngroups < _CLUSTER_MIN:
        conclusion = (
            f"Few clusters (N={ngroups} < {_CLUSTER_MIN}): clustered standard "
            "errors may be unreliable due to downward bias in the variance "
            "estimator.  Consider wild bootstrap (Roodman et al. 2019) or "
            "increasing the panel dimension.  "
            "Reference: Cameron & Miller (2015), JHR 50(2)."
        )
        level = "warning"
    else:
        conclusion = (
            f"Cluster count adequate for inference (N={ngroups} >= {_CLUSTER_MIN}). "
            "Reference: Cameron & Miller (2015), JHR 50(2)."
        )
        level = "info"

    return DiagnosticResult(
        diagnostic_id=_id,
        diagnostic_name=_name,
        statistic=float(ngroups),
        conclusion=conclusion,
        level=level,
        extra={"n_clusters": ngroups, "threshold": _CLUSTER_MIN},
    )


# ---------------------------------------------------------------------------
# Sprint S2 — Within-VIF
# ---------------------------------------------------------------------------


def _diag_within_vif(
    X_within_values: list[list[float]],
    columns: list[str],
) -> DiagnosticResult:
    """
    Variance Inflation Factor (VIF) on entity-demeaned (within-transformed) regressors.

    Purpose
    -------
    Detects multicollinearity in the within-transformed regressor matrix used
    by fixed-effects estimators.  The within transformation subtracts each
    entity's time-mean from every observation, so collinearity that exists only
    in the cross-sectional dimension may disappear after demeaning.  The
    within-VIF therefore provides a more targeted picture of multicollinearity
    for FE estimation than the raw-X VIF.

    Assumptions
    -----------
    * At least 2 regressors.
    * More observations than regressors (invertible X'X after demeaning).
    * X_within_values contains entity-demeaned regressors:
        X_demeaned = panel[regs] - panel[regs].groupby(entity_level).transform("mean")

    Interpretation
    --------------
    Same thresholds as raw VIF: < 5 no concern, 5–10 moderate, > 10 strong.

    Limitations
    -----------
    * Uses entity-demeaning only (not two-way demeaning), so within-VIF is the
      same for EntityFE and TwoWayFE given the same dataset and regressors.
    * Does not replace the raw VIF (``"vif"`` diagnostic); both are reported
      so users can compare within vs. raw multicollinearity.

    Parameters
    ----------
    X_within_values:
        2-D list (nobs × k) — entity-demeaned regressor values from fit().
    columns:
        Ordered list of regressor column names (no const).

    Returns
    -------
    DiagnosticResult
        diagnostic_id="vif_within", statistic=max_within_vif.
    """
    _id = "vif_within"
    _name = "Variance Inflation Factor — Within (max)"

    regs = [c for c in columns if c.lower() not in ("const", "intercept", "constant")]

    if len(regs) < 2:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion="Within-VIF not meaningful with fewer than 2 regressors.",
            level="info",
            extra={"vif_values": {}, "max_vif": float("nan"),
                   "threshold": _VIF_THRESHOLD},
        )

    X_arr = np.array(X_within_values, dtype=float)

    col_idx = {c: i for i, c in enumerate(columns)}
    reg_idx = [col_idx[r] for r in regs if r in col_idx]
    if not reg_idx:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion="Regressor columns not found in stored within-X.",
            level="info",
            extra={"vif_values": {}, "max_vif": float("nan"),
                   "threshold": _VIF_THRESHOLD},
        )

    X_data = X_arr[:, reg_idx]
    if X_data.shape[0] <= X_data.shape[1]:
        return DiagnosticResult(
            diagnostic_id=_id,
            diagnostic_name=_name,
            conclusion="Insufficient observations to compute within-VIF.",
            level="info",
            extra={"vif_values": {}, "max_vif": float("nan"),
                   "threshold": _VIF_THRESHOLD},
        )

    vif_vals: dict[str, float] = {}
    try:
        from statsmodels.stats.outliers_influence import (  # noqa: PLC0415
            variance_inflation_factor,
        )
        X_c = np.column_stack([np.ones(len(X_data)), X_data])
        vif_vals = {
            r: float(variance_inflation_factor(X_c, i + 1))
            for i, r in enumerate(regs)
        }
    except Exception:
        for i, var in enumerate(regs):
            other = [j for j in range(len(regs)) if j != i]
            try:
                y_v = X_data[:, i]
                Xo = np.column_stack([np.ones(len(X_data)), X_data[:, other]])
                beta = np.linalg.lstsq(Xo, y_v, rcond=None)[0]
                yhat = Xo @ beta
                ss_res = float(np.sum((y_v - yhat) ** 2))
                ss_tot = float(np.sum((y_v - y_v.mean()) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                vif_vals[var] = 1.0 / (1.0 - r2) if r2 < 1 else float("inf")
            except Exception:
                vif_vals[var] = float("nan")

    finite_vals = [v for v in vif_vals.values() if v == v and v != float("inf")]
    max_vif = max(finite_vals) if finite_vals else float("nan")
    flagged = [v for v, val in vif_vals.items() if val > _VIF_THRESHOLD]

    if flagged:
        conclusion = (
            f"Within-regressor multicollinearity concern: {flagged} "
            f"have within-VIF > {_VIF_THRESHOLD} (max={max_vif:.2f})"
        )
        level = "warning"
    else:
        conclusion = (
            f"No within-regressor multicollinearity concern "
            f"(max within-VIF = {max_vif:.2f} < {_VIF_THRESHOLD})"
        )
        level = "info"

    return DiagnosticResult(
        diagnostic_id=_id,
        diagnostic_name=_name,
        statistic=float(max_vif) if max_vif == max_vif else None,
        conclusion=conclusion,
        level=level,
        extra={"vif_values": vif_vals, "max_vif": max_vif,
               "threshold": _VIF_THRESHOLD},
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_standard_diagnostics(result: EstimationResult) -> list[DiagnosticResult]:
    """
    Compute post-estimation diagnostics from an EstimationResult.

    This is the canonical single entry point called by ``EntityFE.diagnostics()``,
    ``TwoWayFE.diagnostics()``, and ``PooledOLS.diagnostics()``.

    Requires ``result.extra`` to contain the following keys (populated by
    ``fit()`` in each estimator):

    ``"residuals"``
        ``list[float]`` — model residuals from ``linearmodels`` result,
        in (entity, time) sorted order.  For FE/TWFE: within-transformed.
        For OLS: standard OLS residuals.

    ``"X_vif_values"``
        ``list[list[float]]`` — raw (not within-transformed) regressor matrix,
        shape (nobs, k), aligned with the residuals by row.

    ``"X_vif_columns"``
        ``list[str]`` — column names corresponding to ``X_vif_values``.

    ``"cov_type"`` (optional, Sprint S2)
        When ``"clustered"``, the cluster-count validation diagnostic is
        appended.

    ``"X_within_vif_values"`` (optional, Sprint S2)
        ``list[list[float]]`` — entity-demeaned regressors, set by EntityFE
        and TwoWayFE.  When present, the within-VIF diagnostic is appended.

    ``"X_within_vif_columns"`` (optional, Sprint S2)
        ``list[str]`` — column names for ``X_within_vif_values``.

    If any key is absent (e.g. the result was produced by an older version
    of the estimator that predates Phase 3), the corresponding diagnostic is
    silently skipped.  The function never raises.

    Returns
    -------
    list[DiagnosticResult]
        Ordered: [VIF, Breusch-Pagan, Durbin-Watson, Cluster-Count?, Within-VIF?].
        Any diagnostic that fails is individually caught and the failure is
        recorded in the DiagnosticResult's ``conclusion`` field.  An empty list
        is only returned if all diagnostics are skipped or fail.

    Examples
    --------
    (Called automatically by ``estimator.run(data)`` via ``BaseEstimator.run``.)

    >>> from econflow.estimation import EntityFE
    >>> from statsmodels.datasets import grunfeld
    >>> df = grunfeld.load_pandas().data
    >>> result = EntityFE(params={
    ...     "dependent": "invest", "regressors": ["value", "capital"],
    ...     "entity_col": "firm", "time_col": "year",
    ...     "cov_type": "clustered", "cluster_entity": True,
    ... }).run(df)
    >>> len(result.diagnostic_results)
    5
    >>> result.diagnostic_results[0].diagnostic_id
    'vif'
    """
    diagnostics: list[DiagnosticResult] = []

    residuals: list[float] | None = result.extra.get("residuals")
    x_vals: list[list[float]] | None = result.extra.get("X_vif_values")
    x_cols: list[str] | None = result.extra.get("X_vif_columns", [])

    # Extract entity IDs for the BFN panel DW formula.
    # residuals_index is stored as [[entity, time], ...] by all estimators
    # that support diagnostics (OLS, EntityFE, TwoWayFE).
    residuals_index: list | None = result.extra.get("residuals_index")
    entity_index: list | None = (
        [row[0] for row in residuals_index]
        if residuals_index and len(residuals_index) > 0
        else None
    )

    # ---- VIF ---------------------------------------------------------------
    if x_vals is not None and x_cols is not None:
        try:
            diagnostics.append(_diag_vif(x_vals, x_cols))
        except Exception as exc:  # pragma: no cover
            diagnostics.append(DiagnosticResult(
                diagnostic_id="vif",
                diagnostic_name="Variance Inflation Factor (max)",
                conclusion=f"VIF computation failed unexpectedly: {exc}",
                level="info",
            ))

    # ---- Breusch-Pagan -----------------------------------------------------
    if residuals is not None and x_vals is not None:
        try:
            diagnostics.append(_diag_breusch_pagan(residuals, x_vals))
        except Exception as exc:  # pragma: no cover
            diagnostics.append(DiagnosticResult(
                diagnostic_id="breusch_pagan",
                diagnostic_name="Breusch-Pagan Heteroskedasticity Test",
                conclusion=f"Breusch-Pagan computation failed unexpectedly: {exc}",
                level="info",
            ))

    # ---- Durbin-Watson -----------------------------------------------------
    if residuals is not None:
        try:
            diagnostics.append(_diag_durbin_watson(residuals, entity_index))
        except Exception as exc:  # pragma: no cover
            diagnostics.append(DiagnosticResult(
                diagnostic_id="durbin_watson",
                diagnostic_name="Serial Correlation — Durbin-Watson",
                conclusion=f"DW computation failed unexpectedly: {exc}",
                level="info",
            ))

    # ---- Cluster-count validation (Sprint S2) --------------------------------
    # Only fires when the estimator requested clustered SEs (cov_type="clustered"
    # stored in result.extra by all relevant estimators).
    cov_type_val: str | None = result.extra.get("cov_type")
    if cov_type_val == "clustered":
        ngroups_val: int | None = getattr(result, "ngroups", None)
        if ngroups_val is not None and ngroups_val > 0:
            try:
                diagnostics.append(_diag_cluster_count(ngroups_val))
            except Exception as exc:  # pragma: no cover
                diagnostics.append(DiagnosticResult(
                    diagnostic_id="cluster_count",
                    diagnostic_name="Cluster Count Validation",
                    conclusion=f"Cluster count check failed unexpectedly: {exc}",
                    level="info",
                ))

    # ---- Within-VIF (Sprint S2) ---------------------------------------------
    # Only fires when the estimator stored entity-demeaned regressors in extra
    # (EntityFE and TwoWayFE do; PooledOLS and others do not).
    x_within_vals: list | None = result.extra.get("X_within_vif_values")
    x_within_cols: list | None = result.extra.get("X_within_vif_columns")
    if x_within_vals is not None and x_within_cols is not None:
        try:
            diagnostics.append(_diag_within_vif(x_within_vals, x_within_cols))
        except Exception as exc:  # pragma: no cover
            diagnostics.append(DiagnosticResult(
                diagnostic_id="vif_within",
                diagnostic_name="Variance Inflation Factor — Within (max)",
                conclusion=f"Within-VIF computation failed unexpectedly: {exc}",
                level="info",
            ))

    return diagnostics
