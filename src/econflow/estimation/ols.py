"""
econflow.estimation.ols — Pooled OLS estimator.

Wraps ``linearmodels.OLS`` (or ``statsmodels.OLS``) with cluster-robust
standard errors and APRP's :class:`~econflow.estimation.base.EstimationResult`
output contract.

Pooled OLS ignores the panel structure and is included as a baseline
specification alongside fixed- and random-effects models.  Cluster-robust
SEs (clustered at the entity level) partially correct for within-entity
serial correlation.

Usage (once implemented)
-------------------------
    from econflow.estimation.ols import PooledOLS
    model = PooledOLS(dependent="tfp_growth", regressors=["aipi", "log_gdp"])
    result = model.fit(panel)
    print(result.summary_frame())
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult


class PooledOLS(BaseEstimator):
    """
    Pooled Ordinary Least Squares with optional cluster-robust SEs.

    Parameters
    ----------
    dependent:
        Dependent variable column name.
    regressors:
        Explanatory variable column names.
    add_constant:
        Whether to include an intercept.  Defaults to ``True``.
    cluster:
        Column on which to cluster SEs (typically the entity identifier).
    entity_col / time_col:
        Panel dimension identifiers.
    """

    estimator_name = "pooled_ols"

    def __init__(
        self,
        dependent: str,
        regressors: list[str],
        add_constant: bool = True,
        entity_col: str = "iso3",
        time_col: str = "year",
        cluster: str | None = None,
    ) -> None:
        super().__init__(dependent, regressors, entity_col, time_col, cluster)
        self.add_constant = add_constant

    # ------------------------------------------------------------------
    # BaseEstimator interface
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> EstimationResult:
        """
        Estimate pooled OLS on *df*.

        Returns
        -------
        EstimationResult
            Populated with coefficients, cluster-robust SEs, and
            model-level statistics.
        """
        raise NotImplementedError
