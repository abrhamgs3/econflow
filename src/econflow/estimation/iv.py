"""
econflow.estimation.iv — Instrumental-Variables estimator (2SLS).

Implements Two-Stage Least Squares for panel data using
``linearmodels.IV2SLS`` / ``linearmodels.IVLIML``.  Addresses potential
endogeneity of the AI Proxy Index by instrumenting with:

* Lagged AI adoption indicators (t-2, t-3).
* Geographic/linguistic distance-weighted peer-country adoption (Bartik-style).
* Historical telecommunications infrastructure as an adoption shifter.

Usage (once implemented)
-------------------------
    from econflow.estimation.iv import IVEstimator
    model = IVEstimator(
        dependent="tfp_growth",
        regressors=["log_capital", "log_hc"],
        endog=["aipi"],
        instruments=["aipi_lag2", "bartik_ai"],
    )
    result = model.fit(panel)
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult


class IVEstimator(BaseEstimator):
    """
    Two-Stage Least Squares (2SLS) panel estimator.

    Parameters
    ----------
    dependent:
        Dependent variable column name.
    regressors:
        Exogenous explanatory variable column names.
    endog:
        Endogenous explanatory variable column names.
    instruments:
        Excluded instrument column names.
    entity_col / time_col:
        Panel dimension identifiers.
    cluster:
        Column on which to cluster SEs.
    method:
        IV method: ``"2sls"`` (default) or ``"liml"``.
    absorb_entity:
        Whether to absorb entity fixed effects prior to IV estimation.
    absorb_time:
        Whether to absorb time fixed effects.
    """

    estimator_name = "iv_2sls"

    def __init__(
        self,
        dependent: str,
        regressors: list[str],
        endog: list[str],
        instruments: list[str],
        entity_col: str = "iso3",
        time_col: str = "year",
        cluster: str | None = None,
        method: str = "2sls",
        absorb_entity: bool = True,
        absorb_time: bool = True,
    ) -> None:
        super().__init__(dependent, regressors, entity_col, time_col, cluster)
        self.endog = endog
        self.instruments = instruments
        self.method = method
        self.absorb_entity = absorb_entity
        self.absorb_time = absorb_time

    # ------------------------------------------------------------------
    # BaseEstimator interface
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> EstimationResult:
        """
        Estimate the IV model on *df*.

        Stores the first-stage F-statistic (Cragg-Donald / Kleibergen-Paap)
        in ``result.extra["first_stage_f"]``.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # IV-specific diagnostics (delegates to ai_productivity.diagnostics)
    # ------------------------------------------------------------------

    def first_stage_summary(self, df: pd.DataFrame) -> dict:
        """
        Return first-stage regression results for each endogenous variable.
        """
        raise NotImplementedError
