"""
econflow.estimation.gmm — GMM estimators (Arellano-Bond / Blundell-Bond).

Implements difference-GMM (Arellano-Bond 1991) and system-GMM
(Blundell-Bond 1998) for dynamic panel models of the form:

    y_{it} = ρ·y_{i,t-1} + β·X_{it} + α_i + u_{it}

These estimators are appropriate when the lagged dependent variable is
included as a regressor, making within-group (FE) estimates inconsistent for
short-T panels (Nickell bias).

Internal moment conditions use lagged levels (AB) or lagged differences (BB)
as instruments for the first-differenced equation.

Usage (once implemented)
-------------------------
    from econflow.estimation.gmm import GMMEstimator
    model = GMMEstimator(
        dependent="tfp_growth",
        regressors=["aipi", "log_hc"],
        lag_dep=True,
        gmm_type="system",
        max_lag_instruments=4,
    )
    result = model.fit(panel)
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult

GMMType = Literal["difference", "system"]


class GMMEstimator(BaseEstimator):
    """
    Dynamic panel GMM estimator (Arellano-Bond or Blundell-Bond).

    Parameters
    ----------
    dependent:
        Dependent variable column name.
    regressors:
        Strictly exogenous explanatory variable column names.
    lag_dep:
        Include the lagged dependent variable as a right-hand-side regressor.
    gmm_type:
        ``"difference"`` for Arellano-Bond; ``"system"`` for Blundell-Bond.
    max_lag_instruments:
        Maximum lag depth used for internal GMM instruments (default: 4).
    entity_col / time_col:
        Panel dimension identifiers.
    cluster:
        Column on which to cluster SEs.
    """

    estimator_name = "gmm"

    def __init__(
        self,
        dependent: str,
        regressors: list[str],
        lag_dep: bool = True,
        gmm_type: GMMType = "system",
        max_lag_instruments: int = 4,
        entity_col: str = "iso3",
        time_col: str = "year",
        cluster: str | None = None,
    ) -> None:
        super().__init__(dependent, regressors, entity_col, time_col, cluster)
        self.lag_dep = lag_dep
        self.gmm_type = gmm_type
        self.max_lag_instruments = max_lag_instruments

    # ------------------------------------------------------------------
    # BaseEstimator interface
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> EstimationResult:
        """
        Estimate the GMM model on *df*.

        Stores the Sargan-Hansen J-statistic and AR(1)/AR(2) test results
        in ``result.extra``.

        Raises
        ------
        econflow.core.exceptions.ConvergenceError
            If the GMM optimisation fails to converge.
        """
        raise NotImplementedError
