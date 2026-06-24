"""
econflow.estimation.fixed_effects — Two-way fixed-effects estimator.

Implements entity + time fixed effects via the within transformation
(demeaning).  Wraps ``linearmodels.PanelOLS`` with:

* ``EntityEffects`` and ``TimeEffects`` absorbers.
* Cluster-robust SEs (entity-cluster by default).
* Correct degrees-of-freedom adjustment for the number of absorbed effects.

The two-way FE specification is the preferred baseline model for the APRP
research because it controls for unobserved time-invariant country
heterogeneity and common macro shocks.

Usage (once implemented)
-------------------------
    from econflow.estimation.fixed_effects import TwoWayFE
    model = TwoWayFE(dependent="tfp_growth", regressors=["aipi", "log_capital"])
    result = model.fit(panel)
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult


class TwoWayFE(BaseEstimator):
    """
    Two-way fixed-effects estimator (entity FE + time FE).

    Parameters
    ----------
    dependent:
        Dependent variable column name.
    regressors:
        Explanatory variable column names (time-varying only; time-invariant
        variables are collinear with entity FE and must be excluded).
    entity_col / time_col:
        Panel dimension identifiers.
    cluster:
        Column on which to cluster SEs.  Defaults to entity clustering.
    absorb_entity:
        Whether to absorb entity effects.  ``True`` by default.
    absorb_time:
        Whether to absorb time effects.  ``True`` by default.
    """

    estimator_name = "two_way_fe"

    def __init__(
        self,
        dependent: str,
        regressors: list[str],
        entity_col: str = "iso3",
        time_col: str = "year",
        cluster: str | None = None,
        absorb_entity: bool = True,
        absorb_time: bool = True,
    ) -> None:
        super().__init__(dependent, regressors, entity_col, time_col, cluster)
        self.absorb_entity = absorb_entity
        self.absorb_time = absorb_time

    # ------------------------------------------------------------------
    # BaseEstimator interface
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> EstimationResult:
        """
        Estimate the two-way FE model on *df*.

        Sets the panel index to ``(entity_col, time_col)`` before calling
        ``linearmodels.PanelOLS`` and stores within-R-squared in
        ``result.rsquared``.
        """
        raise NotImplementedError
