"""
econflow.estimation.fixed_effects — Entity FE and Two-Way FE estimators.

Two estimators are registered:

* ``"fe"``   — Entity fixed effects (within estimator).
* ``"twfe"`` — Two-way fixed effects (entity + time).

Both use ``linearmodels.PanelOLS`` with cluster-robust standard errors.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult, EstimatorError
from econflow.estimation.registry import register
from econflow.estimation.result import DiagnosticResult

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _fit_panel_ols(
    data: pd.DataFrame,
    dep: str,
    regs: list[str],
    entity_col: str,
    time_col: str,
    entity_effects: bool,
    time_effects: bool,
    cov_type: str,
    cluster_entity: bool,
    estimator_id: str,
) -> tuple[Any, pd.DataFrame, list, list]:
    """Run linearmodels.PanelOLS and return (result, panel_df, entities, times)."""
    from linearmodels import PanelOLS  # noqa: PLC0415

    panel = data.dropna(subset=[dep, *regs])
    panel = panel.set_index([entity_col, time_col]).sort_index()
    y = panel[dep]
    X = panel[regs]

    try:
        mod = PanelOLS(y, X, entity_effects=entity_effects, time_effects=time_effects)
        if cov_type == "clustered":
            res = mod.fit(cov_type="clustered", cluster_entity=cluster_entity)
        else:
            res = mod.fit(cov_type="robust")
    except Exception as exc:
        raise EstimatorError(
            f"PanelOLS fitting failed: {exc}",
            estimator_id=estimator_id,
            cause=exc,
        ) from exc

    entities = sorted(panel.index.get_level_values(0).unique().tolist())
    times = sorted(panel.index.get_level_values(1).unique().tolist())
    return res, panel, entities, times


# ---------------------------------------------------------------------------
# Entity Fixed Effects
# ---------------------------------------------------------------------------

@register(
    "fe",
    label="Fixed Effects (entity within)",
    status="implemented",
    notes="linearmodels.PanelOLS with EntityEffects; cluster-robust SEs",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class EntityFE(BaseEstimator):
    """
    Entity fixed-effects estimator (within transformation).

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Required.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    cov_type : str   ``"clustered"`` (default) or ``"robust"``.
    cluster_entity : bool   Default ``True``.
    """

    estimator_id = "fe"
    name = "Entity Fixed Effects"
    description = (
        "Within estimator with entity fixed effects.  Controls for all "
        "time-invariant unobserved heterogeneity across entities."
    )
    supported_data = ["balanced_panel", "unbalanced_panel"]
    required_parameters = ["dependent", "regressors"]
    optional_parameters = {
        "entity_col": "entity",
        "time_col": "time",
        "cov_type": "clustered",
        "cluster_entity": True,
    }

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent", "regressors")
        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        self._require_columns(data, dep, entity_col, time_col, *regs)

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        cov_type = self.params.get("cov_type", "clustered")
        cluster_entity = self.params.get("cluster_entity", True)

        res, panel, entities, times = _fit_panel_ols(
            data, dep, regs, entity_col, time_col,
            entity_effects=True, time_effects=False,
            cov_type=cov_type, cluster_entity=cluster_entity,
            estimator_id=self.estimator_id,
        )
        ci = pd.DataFrame(
            res.conf_int().values,
            index=res.params.index, columns=["lower", "upper"],
        )
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
            extra={"effects": "entity", "cov_type": cov_type},
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return []


# ---------------------------------------------------------------------------
# Two-Way Fixed Effects
# ---------------------------------------------------------------------------

@register(
    "twfe",
    label="Two-Way Fixed Effects",
    status="implemented",
    notes="linearmodels.PanelOLS with EntityEffects + TimeEffects; cluster-robust SEs",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class TwoWayFE(BaseEstimator):
    """
    Two-way fixed-effects estimator (entity + time FE).

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Required.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    cov_type : str   ``"clustered"`` (default) or ``"robust"``.
    cluster_entity : bool   Default ``True``.
    """

    estimator_id = "twfe"
    name = "Two-Way Fixed Effects"
    description = (
        "Entity + time fixed effects via the within transformation.  "
        "Controls for unobserved entity heterogeneity and common time shocks."
    )
    supported_data = ["balanced_panel", "unbalanced_panel"]
    required_parameters = ["dependent", "regressors"]
    optional_parameters = {
        "entity_col": "entity",
        "time_col": "time",
        "cov_type": "clustered",
        "cluster_entity": True,
    }

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent", "regressors")
        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        self._require_columns(data, dep, entity_col, time_col, *regs)

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        dep = self.params["dependent"]
        regs = self.params["regressors"]
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        cov_type = self.params.get("cov_type", "clustered")
        cluster_entity = self.params.get("cluster_entity", True)

        res, panel, entities, times = _fit_panel_ols(
            data, dep, regs, entity_col, time_col,
            entity_effects=True, time_effects=True,
            cov_type=cov_type, cluster_entity=cluster_entity,
            estimator_id=self.estimator_id,
        )
        ci = pd.DataFrame(
            res.conf_int().values,
            index=res.params.index, columns=["lower", "upper"],
        )
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
            extra={"effects": "entity+time", "cov_type": cov_type},
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return []
