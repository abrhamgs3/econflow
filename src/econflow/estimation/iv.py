"""
econflow.estimation.iv — Instrumental variables (2SLS) estimator.

Uses ``linearmodels.IV2SLS`` for the second-stage regression.

Sprint S2 notes
---------------
This estimator is **pooled**: it does not absorb entity fixed effects.
When the panel contains multiple entities and entity-level heterogeneity
is correlated with the instruments or regressors, coefficient estimates may
be inconsistent.  A fixed-effects IV or Hausman-Taylor estimator should be
considered in that case.

Diagnostics exposed (Sprint S2):

* ``"iv_first_stage"``   — per-endogenous-variable first-stage F-statistic,
  partial-R², and Shea partial-R².  Weak-instrument warning when min F < 10
  (Stock-Wright-Yogo 2005 rule of thumb).
* ``"iv_sargan_hansen"`` — Sargan-Hansen J-test for overidentification
  (only when n_instruments > n_endog).  Rejection indicates at least one
  instrument may be invalid.
* ``"iv_wu_hausman"``    — Wu-Hausman F-test for endogeneity.  Non-rejection
  suggests OLS may be consistent.
* ``"iv_pooled_note"``   — Warning emitted whenever ``ngroups > 1``, reminding
  the user that this is a pooled (not FE-IV) estimator.
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult, EstimatorError
from econflow.estimation.registry import register
from econflow.estimation.result import DiagnosticResult


@register(
    "iv",
    label="IV / 2SLS",
    status="implemented",
    notes="linearmodels.IV2SLS (pooled — no entity FE); requires instruments in params['instruments']",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class IV2SLS(BaseEstimator):
    """
    Two-stage least squares with instrumental variables — **pooled estimator**.

    .. warning::
        This estimator is pooled: it does **not** absorb entity fixed effects.
        When multiple entities are present and entity-level unobserved
        heterogeneity is correlated with the instruments or regressors,
        coefficient estimates will be inconsistent.  The ``"iv_pooled_note"``
        diagnostic is automatically emitted whenever ``ngroups > 1``.

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Exogenous regressors.  Required.
    endog : list[str]   Endogenous regressors.  Required.
    instruments : list[str]   Instruments (excluded).  Required.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    cov_type : str   Default ``"robust"``.

    Diagnostics (Sprint S2)
    -----------------------
    ``diagnostics()`` returns up to four ``DiagnosticResult`` objects:

    iv_first_stage
        First-stage F-statistic, p-value, partial-R², and Shea-R² for each
        endogenous variable.  Level ``"warning"`` when min F < 10 (weak
        instruments, Stock-Wright-Yogo 2005 rule of thumb).
    iv_sargan_hansen
        Sargan J-test for overidentification (only when n_instruments > n_endog).
        Rejection indicates at least one instrument may be invalid.
    iv_wu_hausman
        Wu-Hausman F-test for endogeneity.  Non-rejection suggests OLS may be
        consistent; rejection supports using IV.
    iv_pooled_note
        Always emitted when ``ngroups > 1``.  Warns that this pooled estimator
        does not control for entity fixed effects.
    """

    estimator_id = "iv"
    backend = "linearmodels"
    name = "IV / 2SLS"
    description = (
        "Two-stage least squares — pooled estimator (does not absorb entity "
        "fixed effects).  Addresses endogeneity via excluded instruments.  "
        "When entity-level unobserved heterogeneity is correlated with "
        "regressors, coefficient estimates may be inconsistent; consider a "
        "fixed-effects IV or Hausman-Taylor estimator for panel data.  "
        "Requires params['endog'] and params['instruments']."
    )
    supported_data = ["balanced_panel", "unbalanced_panel"]
    required_parameters = ["dependent", "regressors", "endog", "instruments"]
    optional_parameters = {
        "entity_col": "entity",
        "time_col": "time",
        "cov_type": "robust",
    }

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent", "regressors", "endog", "instruments")
        dep = self.params["dependent"]
        regs = self.params["regressors"]
        endog = self.params["endog"]
        instruments = self.params["instruments"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        self._require_columns(data, dep, entity_col, time_col,
                              *regs, *endog, *instruments)
        if len(instruments) < len(endog):
            raise EstimatorError(
                "Order condition violated: need at least as many instruments "
                "as endogenous regressors.",
                estimator_id=self.estimator_id,
            )

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        data = self._resolve_dataframe(data)
        from linearmodels.iv import IV2SLS as _IV2SLS  # noqa: PLC0415

        dep = self.params["dependent"]
        regs = self.params["regressors"]
        endog = self.params["endog"]
        instruments = self.params["instruments"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        cov_type = self.params.get("cov_type", "robust")

        panel = data.dropna(subset=[dep, *regs, *endog]).copy()
        panel = panel.set_index([entity_col, time_col]).sort_index()

        try:
            import numpy as np  # noqa: PLC0415
            # Exogenous regressors = all regressors minus any endogenous ones.
            # Passing endogenous variables in both exog and endog causes a
            # rank deficiency error in linearmodels.
            endog_set = set(endog)
            exog_regs = [r for r in regs if r not in endog_set]
            const = np.ones((len(panel), 1))
            if exog_regs:
                exog = pd.DataFrame(
                    const, index=panel.index, columns=["const"]
                ).join(panel[exog_regs])
            else:
                exog = pd.DataFrame(const, index=panel.index, columns=["const"])
            mod = _IV2SLS(panel[dep], exog, panel[endog], panel[instruments])
            res = mod.fit(cov_type=cov_type)
        except Exception as exc:
            raise EstimatorError(
                f"IV2SLS fitting failed: {exc}",
                estimator_id=self.estimator_id, cause=exc,
            ) from exc

        ci = pd.DataFrame(
            res.conf_int().values,
            index=res.params.index, columns=["lower", "upper"],
        )
        entities = sorted(panel.index.get_level_values(0).unique().tolist())
        times = sorted(panel.index.get_level_values(1).unique().tolist())
        # --- Sprint S1: Correct rsquared_adj (was incorrectly copying rsquared) ---
        # IV2SLS R² is the standard IV R² (1 - SS_res/SS_tot on original dep var).
        # Adjusted R² uses the same OLS-style formula (N-1)/df_resid.
        # Note: IV R² can be negative; adj-R² inherits that property.
        _nobs = int(res.nobs)
        _df_resid = int(res.df_resid)
        _rsq = float(res.rsquared)
        _rsq_adj = 1.0 - (1.0 - _rsq) * (_nobs - 1) / _df_resid

        # --- Sprint S2: Extract IV diagnostics defensively ---
        # Each piece is individually guarded so a failure in one does not
        # prevent others from being stored.  All values flow through
        # result.extra["iv_diagnostics"] → diagnostics() reads them back.
        iv_diags: dict = {}

        # First-stage: F-stat, p-val, partial-R², Shea-R² per endog variable.
        try:
            fs_df = res.first_stage.diagnostics  # DataFrame indexed by endog name
            first_stage: dict[str, dict] = {}
            for var in fs_df.index:
                row = fs_df.loc[var]
                first_stage[str(var)] = {
                    "f_stat": float(row["f.stat"]),
                    "f_pval": float(row["f.pval"]),
                    "shea_r2": float(row["shea.rsquared"]),
                    "partial_r2": float(row["partial.rsquared"]),
                }
            iv_diags["first_stage"] = first_stage
        except Exception:
            pass  # first_stage absent → iv_first_stage diagnostic silently omitted

        # Wu-Hausman endogeneity F-test.
        try:
            wh = res.wu_hausman()
            iv_diags["wu_hausman"] = {
                "stat": float(wh.stat),
                "pval": float(wh.pval),
            }
        except Exception:
            pass

        # Sargan-Hansen overidentification test (only when overidentified).
        # res.sargan is an InvalidTestStatistic (stat=NaN) when just-identified.
        n_overid = len(instruments) - len(endog)
        if n_overid > 0:
            try:
                sar = res.sargan
                sar_stat = float(sar.stat)
                if sar_stat == sar_stat:  # guard against NaN
                    iv_diags["sargan"] = {
                        "stat": sar_stat,
                        "pval": float(sar.pval),
                        "n_overid": n_overid,
                    }
            except Exception:
                pass

        iv_diags["n_endog"] = len(endog)
        iv_diags["n_instruments"] = len(instruments)

        return EstimationResult(
            estimator_id=self.estimator_id,
            estimator_name=self.name,
            params=res.params,
            std_err=res.std_errors,
            conf_int=ci,
            pvalues=res.pvalues,
            nobs=_nobs,
            ngroups=len(entities),
            df_resid=_df_resid,
            rsquared=_rsq,
            rsquared_adj=_rsq_adj,
            entity_col=entity_col,
            time_col=time_col,
            entities=[str(e) for e in entities],
            time_periods=times,
            provenance=self._provenance_stamp(),
            extra={
                "endog": endog,
                "instruments": instruments,
                "cov_type": cov_type,
                "iv_diagnostics": iv_diags,
            },
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        """
        Post-estimation diagnostics for IV / 2SLS.

        Returns
        -------
        list[DiagnosticResult]
            Up to four diagnostics, in order:

            1. ``iv_first_stage`` — first-stage F-statistics (always present
               when linearmodels returned first-stage results).
            2. ``iv_sargan_hansen`` — Sargan overidentification J-test (only
               when n_instruments > n_endog).
            3. ``iv_wu_hausman`` — Wu-Hausman endogeneity F-test.
            4. ``iv_pooled_note`` — pooled-estimator warning (always present
               when result.ngroups > 1).

        Notes
        -----
        All data is read from ``result.extra["iv_diagnostics"]``, which is
        populated by ``fit()``.  Each piece is individually guarded, so a
        missing item silently omits that diagnostic rather than raising.

        The ``iv_pooled_note`` diagnostic is architecture-safe: it does not
        alter any coefficient or standard-error computation; it is purely
        informational metadata added after estimation.

        References
        ----------
        Stock, J. H., J. H. Wright, and M. Yogo (2005).
        "Testing for Weak Instruments in Linear IV Regression."
        *Identification and Inference for Econometric Models*, Cambridge.

        Sargan, J. D. (1958).
        "The Estimation of Economic Relationships Using Instrumental Variables."
        *Econometrica* 26(3), 393–415.
        """
        diags: list[DiagnosticResult] = []
        iv_diags: dict = result.extra.get("iv_diagnostics", {})

        # ---- First-stage F-statistics ----------------------------------------
        first_stage: dict = iv_diags.get("first_stage", {})
        if first_stage:
            f_stats = [v["f_stat"] for v in first_stage.values() if "f_stat" in v]
            min_f = min(f_stats) if f_stats else float("nan")

            var_summaries = [
                (
                    f"{var}: F={s['f_stat']:.3f} (p={s['f_pval']:.4f}), "
                    f"partial-R²={s['partial_r2']:.4f}, Shea-R²={s['shea_r2']:.4f}"
                )
                for var, s in first_stage.items()
            ]
            detail = "; ".join(var_summaries)

            _threshold_f = 10.0
            if min_f == min_f and min_f < _threshold_f:  # not NaN and weak
                conclusion = (
                    f"Weak instrument concern: min first-stage F={min_f:.3f} < "
                    f"{_threshold_f} (Stock-Wright-Yogo 2005 rule of thumb). "
                    f"{detail}"
                )
                level = "warning"
            else:
                conclusion = (
                    f"Instruments appear adequate: min first-stage F={min_f:.3f} "
                    f">= {_threshold_f}. {detail}"
                )
                level = "info"

            diags.append(DiagnosticResult(
                diagnostic_id="iv_first_stage",
                diagnostic_name="IV First-Stage Diagnostics",
                statistic=float(min_f) if min_f == min_f else None,
                conclusion=conclusion,
                level=level,
                extra={
                    "first_stage": first_stage,
                    "min_f_stat": float(min_f) if min_f == min_f else None,
                    "threshold": _threshold_f,
                },
            ))

        # ---- Sargan-Hansen overidentification test ----------------------------
        sargan: dict | None = iv_diags.get("sargan")
        if sargan:
            s_stat = sargan["stat"]
            s_pval = sargan["pval"]
            s_df = sargan["n_overid"]
            if s_pval < 0.05:
                conclusion = (
                    f"Sargan-Hansen test rejected (stat={s_stat:.4f}, "
                    f"p={s_pval:.4f}, df={s_df}): at least one instrument "
                    "may be endogenous or mis-specified."
                )
                level = "warning"
            else:
                conclusion = (
                    f"Sargan-Hansen test not rejected (stat={s_stat:.4f}, "
                    f"p={s_pval:.4f}, df={s_df}): instruments appear valid "
                    "under the null."
                )
                level = "info"

            diags.append(DiagnosticResult(
                diagnostic_id="iv_sargan_hansen",
                diagnostic_name="IV Sargan-Hansen Overidentification Test",
                statistic=s_stat,
                pvalue=s_pval,
                conclusion=conclusion,
                level=level,
                extra={"sargan_stat": s_stat, "sargan_pval": s_pval, "df": s_df},
            ))

        # ---- Wu-Hausman endogeneity test --------------------------------------
        wu_hausman: dict | None = iv_diags.get("wu_hausman")
        if wu_hausman:
            wh_stat = wu_hausman["stat"]
            wh_pval = wu_hausman["pval"]
            if wh_pval < 0.05:
                conclusion = (
                    f"Endogeneity detected (Wu-Hausman F={wh_stat:.4f}, "
                    f"p={wh_pval:.4f}): IV estimation is warranted."
                )
                level = "warning"
            else:
                conclusion = (
                    f"No significant endogeneity (Wu-Hausman F={wh_stat:.4f}, "
                    f"p={wh_pval:.4f}): OLS may be consistent."
                )
                level = "info"

            diags.append(DiagnosticResult(
                diagnostic_id="iv_wu_hausman",
                diagnostic_name="IV Wu-Hausman Endogeneity Test",
                statistic=wh_stat,
                pvalue=wh_pval,
                conclusion=conclusion,
                level=level,
                extra={"wu_hausman_stat": wh_stat, "wu_hausman_pval": wh_pval},
            ))

        # ---- Pooled-estimator warning ----------------------------------------
        # Emitted whenever multiple entities are detected, regardless of whether
        # the user is aware this estimator is pooled.  Does not alter any
        # coefficient or covariance computation.
        ngroups = getattr(result, "ngroups", None)
        if ngroups is not None and ngroups > 1:
            diags.append(DiagnosticResult(
                diagnostic_id="iv_pooled_note",
                diagnostic_name="IV Pooled Estimator Note",
                conclusion=(
                    f"This IV estimator is pooled ({ngroups} entities detected). "
                    "It does not absorb entity fixed effects. If unobserved "
                    "entity-level heterogeneity is correlated with the instruments "
                    "or regressors, coefficient estimates may be inconsistent. "
                    "Consider a fixed-effects IV or Hausman-Taylor estimator."
                ),
                level="warning",
                extra={"ngroups": ngroups},
            ))

        return diags
