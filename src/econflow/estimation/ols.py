"""
econflow.estimation.ols — Pooled OLS estimator.

Uses ``linearmodels.PooledOLS`` with heteroskedasticity-robust or
cluster-robust standard errors.  Pooled OLS ignores panel structure and
serves as the baseline specification; cluster-robust SEs (by entity)
partially correct for within-entity serial correlation.
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult, EstimatorError
from econflow.estimation.registry import register
from econflow.estimation.result import DiagnosticResult


@register(
    "ols",
    label="Pooled OLS",
    status="implemented",
    notes="linearmodels.PooledOLS; cluster-robust SEs by entity",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class PooledOLS(BaseEstimator):
    """
    Pooled Ordinary Least Squares.

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str
        Dependent variable column name.  Required.
    regressors : list[str]
        Explanatory variable column names.  Required.
    entity_col : str
        Entity dimension column.  Default ``"entity"``.
    time_col : str
        Time dimension column.  Default ``"time"``.
    cov_type : str
        ``"robust"`` (default) or ``"clustered"``.
    cluster_entity : bool
        Cluster by entity when ``cov_type="clustered"``.  Default ``True``.
    """

    estimator_id = "ols"
    backend = "linearmodels"
    name = "Pooled OLS"
    description = (
        "Pooled ordinary least squares.  Ignores panel structure; "
        "provides the baseline against which FE and RE models are compared."
    )
    supported_data = ["balanced_panel", "unbalanced_panel"]
    required_parameters = ["dependent", "regressors"]
    optional_parameters = {
        "entity_col": "entity",
        "time_col": "time",
        "cov_type": "robust",
        "cluster_entity": True,
    }

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent", "regressors")
        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        self._require_columns(data, dep, entity_col, time_col, *regs)
        if data[dep].isna().all():
            raise EstimatorError(
                f"Dependent variable '{dep}' is all NaN.",
                estimator_id=self.estimator_id,
            )

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        data = self._resolve_dataframe(data)
        from linearmodels import PooledOLS as _PooledOLS  # noqa: PLC0415

        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        cov_type = self.params.get("cov_type", "robust")
        cluster_entity = self.params.get("cluster_entity", True)

        panel = self._to_panel(data.dropna(subset=[dep, *regs]), entity_col, time_col)
        y = panel[dep]
        X = panel[regs]

        try:
            mod = _PooledOLS(y, X)
            if cov_type == "clustered":
                res = mod.fit(cov_type="clustered", cluster_entity=cluster_entity)
            else:
                res = mod.fit(cov_type="robust")
        except Exception as exc:
            raise EstimatorError(
                f"PooledOLS fitting failed: {exc}",
                estimator_id=self.estimator_id,
                cause=exc,
            ) from exc

        ci = pd.DataFrame(
            res.conf_int().values,
            index=res.params.index,
            columns=["lower", "upper"],
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
            f_statistic=float(res.f_statistic.stat) if hasattr(res, "f_statistic") else None,
            f_pvalue=float(res.f_statistic.pval) if hasattr(res, "f_statistic") else None,
            entity_col=entity_col,
            time_col=time_col,
            entities=[str(e) for e in entities],
            time_periods=times,
            provenance=self._provenance_stamp(),
            extra={"cov_type": cov_type},
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return []
