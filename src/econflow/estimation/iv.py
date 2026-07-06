"""
econflow.estimation.iv — Instrumental variables (2SLS) estimator.

Uses ``linearmodels.IV2SLS`` for the second-stage regression.
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
    notes="linearmodels.IV2SLS; requires instruments in params['instruments']",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class IV2SLS(BaseEstimator):
    """
    Two-stage least squares with instrumental variables.

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Exogenous regressors.  Required.
    endog : list[str]   Endogenous regressors.  Required.
    instruments : list[str]   Instruments (excluded).  Required.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    cov_type : str   Default ``"robust"``.
    """

    estimator_id = "iv"
    name = "IV / 2SLS"
    description = (
        "Two-stage least squares.  Addresses endogeneity via excluded "
        "instruments.  Requires params['endog'] and params['instruments']."
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

        return EstimationResult(
            estimator_id=self.estimator_id,
            estimator_name=self.name,
            params=res.params,
            std_err=res.std_errors,
            conf_int=ci,
            pvalues=res.pvalues,
            nobs=int(res.nobs),
            ngroups=len(entities),
            df_resid=int(res.df_resid),
            rsquared=float(res.rsquared),
            rsquared_adj=float(res.rsquared),
            entity_col=entity_col,
            time_col=time_col,
            entities=[str(e) for e in entities],
            time_periods=times,
            provenance=self._provenance_stamp(),
            extra={"endog": endog, "instruments": instruments, "cov_type": cov_type},
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return []
