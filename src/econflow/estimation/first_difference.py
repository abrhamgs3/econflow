"""
econflow.estimation.first_difference — First-difference estimator.

Eliminates entity fixed effects by differencing consecutive observations.
Uses ``linearmodels.FirstDifferenceOLS``.
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult, EstimatorError
from econflow.estimation.registry import register
from econflow.estimation.result import DiagnosticResult


@register(
    "fd",
    label="First Difference",
    status="implemented",
    notes="linearmodels.FirstDifferenceOLS; eliminates entity FE by differencing",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class FirstDifference(BaseEstimator):
    """
    First-difference estimator.

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Required.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    cov_type : str   Default ``"robust"``.
    """

    estimator_id = "fd"
    name = "First Difference"
    description = (
        "First-difference estimator.  Eliminates entity fixed effects by "
        "differencing consecutive time periods.  Consistent under strict "
        "exogeneity; less efficient than FE when T > 2."
    )
    supported_data = ["balanced_panel", "unbalanced_panel"]
    required_parameters = ["dependent", "regressors"]
    optional_parameters = {
        "entity_col": "entity",
        "time_col": "time",
        "cov_type": "robust",
    }

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent", "regressors")
        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        self._require_columns(data, dep, entity_col, time_col, *regs)

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        from linearmodels import FirstDifferenceOLS as _FD  # noqa: PLC0415

        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        cov_type = self.params.get("cov_type", "robust")

        panel = data.dropna(subset=[dep, *regs])
        panel = panel.set_index([entity_col, time_col]).sort_index()
        y = panel[dep]
        X = panel[regs]

        try:
            mod = _FD(y, X)
            res = mod.fit(cov_type=cov_type)
        except Exception as exc:
            raise EstimatorError(
                f"FirstDifferenceOLS fitting failed: {exc}",
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
            extra={"cov_type": cov_type},
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return []
