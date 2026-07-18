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

from econflow.estimation._diagnostics import compute_standard_diagnostics
from econflow.estimation.base import (
    BaseEstimator,
    EstimationResult,
    EstimatorError,
    ModelSpecificationError,
)
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
    backend = "linearmodels"
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
        # --- Sprint S1: Time-invariant regressor guard ---
        # A regressor with zero within-entity variance is perfectly collinear
        # with the entity dummies.  linearmodels will either drop it silently
        # or return NaN/zero coefficients.  We raise early with a clear message.
        try:
            _clean = data.dropna(subset=[dep, *regs])
            if len(_clean) > 1 and entity_col in _clean.columns:
                _panel_tmp = _clean.set_index([entity_col, time_col])
                _within_var = _panel_tmp[regs].groupby(level=0).var()
                _time_invariant = sorted(
                    col for col in regs
                    if (
                        len(_within_var[col].dropna()) > 0
                        and (_within_var[col].dropna() <= 0).all()
                    )
                )
                if _time_invariant:
                    raise ModelSpecificationError(
                        f"Regressors {_time_invariant} have zero within-entity variance "
                        f"and will be absorbed by entity fixed effects. "
                        f"Remove them or switch to a pooled estimator (ols, re).",
                        estimator_id=self.estimator_id,
                    )
        except ModelSpecificationError:
            raise
        except Exception:
            pass  # Any other check failure: let PanelOLS surface it at fit time

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        data = self._resolve_dataframe(data)
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
        # --- Sprint S1: within-R² is the primary R² for FE models ---
        # result.rsquared now holds within-R² (matching Stata xtreg,fe and R plm).
        # overall R² (res.rsquared from linearmodels) is stored in extra for reference.
        # rsquared_adj uses the within-adjusted formula (fixest convention):
        #   1 − (1 − R²_within) × (N − N_entities) / df_resid
        # where df_resid = N − N_entities − k (from linearmodels).
        _rsq = float(res.rsquared_within)          # within-R² — primary field
        _rsq_overall = float(res.rsquared)         # overall R² — stored in extra
        _nobs = int(res.nobs)
        _ngroups = len(entities)
        _df_resid = int(res.df_resid)
        _rsq_adj = 1.0 - (1.0 - _rsq) * (_nobs - _ngroups) / _df_resid
        return EstimationResult(
            estimator_id=self.estimator_id,
            estimator_name=self.name,
            params=res.params,
            std_err=res.std_errors,
            conf_int=ci,
            pvalues=res.pvalues,
            nobs=_nobs,
            ngroups=_ngroups,
            df_resid=_df_resid,
            rsquared=_rsq,
            rsquared_adj=_rsq_adj,
            f_statistic=float(res.f_statistic.stat) if hasattr(res, "f_statistic") else None,
            f_pvalue=float(res.f_statistic.pval) if hasattr(res, "f_statistic") else None,
            entity_col=entity_col,
            time_col=time_col,
            entities=[str(e) for e in entities],
            time_periods=times,
            provenance=self._provenance_stamp(),
            extra={
                "effects": "entity",
                "cov_type": cov_type,
                # Diagnostic data — consumed by diagnostics() in Phase 3.
                # residuals: within-transformed residuals from PanelOLS fit,
                #   in (entity, time) sorted order (panel is always sort_index()ed).
                # residuals_index: MultiIndex tuples so EstimationResult.resids
                #   can reconstruct a properly-indexed pd.Series (used by tests).
                # rsquared_within: kept for backward compatibility; equals rsquared.
                # rsquared_overall: linearmodels overall R² (stored for reference).
                # X_vif_values: raw (non-within-transformed) regressors,
                #   aligned row-by-row with residuals.
                # X_vif_columns: regressor names (no constant).
                # X_within_vif_values (Sprint S2): entity-demeaned regressors for
                #   within-VIF computation.  Uses entity-level demeaning only
                #   (same formula for both EntityFE and TwoWayFE).
                #   Formula: panel[regs] − panel[regs].groupby(level=0).transform("mean")
                # X_within_vif_columns (Sprint S2): same as X_vif_columns.
                "residuals": res.resids.values.tolist(),
                "residuals_index": [list(t) for t in res.resids.index.tolist()],
                "rsquared_within": _rsq,
                "rsquared_overall": _rsq_overall,
                "X_vif_values": panel[regs].values.tolist(),
                "X_vif_columns": list(regs),
                "X_within_vif_values": (
                    panel[regs] - panel[regs].groupby(level=0).transform("mean")
                ).values.tolist(),
                "X_within_vif_columns": list(regs),
            },
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        """
        Post-estimation diagnostics for Entity Fixed Effects.

        Returns
        -------
        list[DiagnosticResult]
            Up to five diagnostics in order: VIF, Breusch-Pagan, Durbin-Watson,
            Cluster-Count (when ``cov_type="clustered"``), Within-VIF.
            Each is a fully-populated :class:`~econflow.estimation.result.DiagnosticResult`.
            Diagnostics that cannot be computed (e.g. insufficient data) are
            individually guarded and return a "not applicable" result.

        Notes
        -----
        Reads pre-computed data from ``result.extra``, all populated by ``fit()``:

        * ``"residuals"`` — within-transformed residuals (entity FE removed).
        * ``"X_vif_values"`` / ``"X_vif_columns"`` — raw (non-demeaned) X for VIF
          and Breusch-Pagan.
        * ``"X_within_vif_values"`` / ``"X_within_vif_columns"`` (Sprint S2) —
          entity-demeaned X for within-VIF.

        **Breusch-Pagan scope:** residuals are within-transformed but X is raw.
        The test is therefore sensitive to both effects heteroskedasticity and
        regressor-related heteroskedasticity; it is not a pure within-residual
        test.  See ``_diag_breusch_pagan`` for details.

        **Within-VIF scope:** VIF is computed on entity-demeaned regressors,
        providing a picture of multicollinearity in the within dimension used
        by the FE estimator.  A small within-VIF alongside a larger raw VIF
        indicates the collinearity is primarily cross-sectional.
        """
        return compute_standard_diagnostics(result)


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
    backend = "linearmodels"
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
        # --- Sprint S1: Time-invariant regressor guard (same as EntityFE) ---
        try:
            _clean = data.dropna(subset=[dep, *regs])
            if len(_clean) > 1 and entity_col in _clean.columns:
                _panel_tmp = _clean.set_index([entity_col, time_col])
                _within_var = _panel_tmp[regs].groupby(level=0).var()
                _time_invariant = sorted(
                    col for col in regs
                    if (
                        len(_within_var[col].dropna()) > 0
                        and (_within_var[col].dropna() <= 0).all()
                    )
                )
                if _time_invariant:
                    raise ModelSpecificationError(
                        f"Regressors {_time_invariant} have zero within-entity variance "
                        f"and will be absorbed by entity fixed effects. "
                        f"Remove them or switch to a pooled estimator (ols, re).",
                        estimator_id=self.estimator_id,
                    )
        except ModelSpecificationError:
            raise
        except Exception:
            pass

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        data = self._resolve_dataframe(data)
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
        # --- Sprint S1 / Blocker fix: within-R² is the primary R² for FE models ---
        # For TWFE the within transformation absorbs BOTH entity and time effects.
        # The numerator of the DoF correction must account for both absorptions:
        #
        #   rsquared_adj = 1 − (1 − R²_within) × (N − N_entities − (N_times − 1)) / df_resid
        #
        # where df_resid from linearmodels = N − N_entities − (N_times − 1) − k (balanced)
        # and (N − N_entities − (N_times − 1)) is the effective post-absorption sample size.
        # This matches the fixest convention for two-way FE.
        #
        # EntityFE.fit() uses (N − N_entities) in the numerator — that is unchanged
        # because EntityFE only absorbs entity dummies.
        _rsq = float(res.rsquared_within)
        _rsq_overall = float(res.rsquared)
        _nobs = int(res.nobs)
        _ngroups = len(entities)
        _ntimes = len(times)
        _df_resid = int(res.df_resid)
        _rsq_adj = 1.0 - (1.0 - _rsq) * (_nobs - _ngroups - (_ntimes - 1)) / _df_resid
        return EstimationResult(
            estimator_id=self.estimator_id,
            estimator_name=self.name,
            params=res.params,
            std_err=res.std_errors,
            conf_int=ci,
            pvalues=res.pvalues,
            nobs=_nobs,
            ngroups=_ngroups,
            df_resid=_df_resid,
            rsquared=_rsq,
            rsquared_adj=_rsq_adj,
            f_statistic=float(res.f_statistic.stat) if hasattr(res, "f_statistic") else None,
            f_pvalue=float(res.f_statistic.pval) if hasattr(res, "f_statistic") else None,
            entity_col=entity_col,
            time_col=time_col,
            entities=[str(e) for e in entities],
            time_periods=times,
            provenance=self._provenance_stamp(),
            extra={
                "effects": "entity+time",
                "cov_type": cov_type,
                # Diagnostic data — see EntityFE.fit() for field documentation.
                # rsquared_within: kept for backward compat; equals rsquared.
                # rsquared_overall: linearmodels overall R² (stored for reference).
                # X_within_vif_values (Sprint S2): entity-demeaned regressors.
                #   Uses entity-only demeaning (same formula as EntityFE), since
                #   within-VIF assesses entity-level collinearity in the FE context.
                "residuals": res.resids.values.tolist(),
                "residuals_index": [list(t) for t in res.resids.index.tolist()],
                "rsquared_within": _rsq,
                "rsquared_overall": _rsq_overall,
                "X_vif_values": panel[regs].values.tolist(),
                "X_vif_columns": list(regs),
                "X_within_vif_values": (
                    panel[regs] - panel[regs].groupby(level=0).transform("mean")
                ).values.tolist(),
                "X_within_vif_columns": list(regs),
            },
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        """
        Post-estimation diagnostics for Two-Way Fixed Effects.

        Returns
        -------
        list[DiagnosticResult]
            Up to five diagnostics in order: VIF, Breusch-Pagan, Durbin-Watson,
            Cluster-Count (when ``cov_type="clustered"``), Within-VIF.

        Notes
        -----
        Semantics are the same as ``EntityFE.diagnostics()`` except:

        * ``"residuals"`` are two-way within-transformed (entity + time FE removed).
        * ``"X_within_vif_values"`` uses entity-only demeaning for consistency with
          EntityFE and to isolate the entity-level collinearity structure; the time
          demeaning step does not materially affect within-VIF in practice.

        **Breusch-Pagan scope:** residuals are two-way within-transformed but X is
        raw.  The test jointly tests effects and regressor-related heteroskedasticity.
        See ``_diag_breusch_pagan`` for full scope documentation.
        """
        return compute_standard_diagnostics(result)
