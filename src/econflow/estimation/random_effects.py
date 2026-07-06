"""
econflow.estimation.random_effects — Random effects (GLS) estimator.

Uses ``linearmodels.RandomEffects`` (Swamy-Arora GLS).  The Hausman test
should be run first to verify that random effects is consistent for the
data at hand; rejection favours the FE estimator.
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult, EstimatorError
from econflow.estimation.registry import register
from econflow.estimation.result import DiagnosticResult


@register(
    "re",
    label="Random Effects (GLS)",
    status="implemented",
    notes="linearmodels.RandomEffects (Swamy-Arora); use Hausman test to validate",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class RandomEffects(BaseEstimator):
    """
    Random-effects GLS estimator (Swamy-Arora variance decomposition).

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Required.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    cov_type : str   ``"robust"`` (default) or ``"clustered"``.
    """

    estimator_id = "re"
    name = "Random Effects (GLS)"
    description = (
        "Random-effects GLS estimator assuming individual effects are "
        "uncorrelated with the regressors.  Run Hausman test to validate."
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
        data = self._resolve_dataframe(data)
        from linearmodels import RandomEffects as _RE  # noqa: PLC0415

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
            mod = _RE(y, X)
            res = mod.fit(cov_type=cov_type)
        except Exception as exc:
            raise EstimatorError(
                f"RandomEffects fitting failed: {exc}",
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
