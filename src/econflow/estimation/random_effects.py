"""
econflow.estimation.random_effects — Random-effects GLS estimator.

Implements the Swamy-Arora feasible GLS estimator for one-way random effects.
Wraps ``linearmodels.RandomEffects`` and exposes the between, within, and
overall R-squared statistics.

The random-effects model is estimated alongside fixed effects so that the
Hausman test (:mod:`econflow.diagnostics.specification`) can compare the two
specifications and guide model selection.

Usage (once implemented)
-------------------------
    from econflow.estimation.random_effects import RandomEffectsGLS
    model = RandomEffectsGLS(dependent="tfp_growth", regressors=["aipi", "log_hc"])
    result = model.fit(panel)
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult


class RandomEffectsGLS(BaseEstimator):
    """
    One-way random-effects GLS (Swamy-Arora FGLS).

    Parameters
    ----------
    dependent:
        Dependent variable column name.
    regressors:
        Explanatory variable column names.
    entity_col / time_col:
        Panel dimension identifiers.
    cluster:
        Column for robust SE clustering.  ``None`` uses the default HC
        covariance from ``linearmodels``.
    """

    estimator_name = "random_effects_gls"

    def __init__(
        self,
        dependent: str,
        regressors: list[str],
        entity_col: str = "iso3",
        time_col: str = "year",
        cluster: str | None = None,
    ) -> None:
        super().__init__(dependent, regressors, entity_col, time_col, cluster)

    # ------------------------------------------------------------------
    # BaseEstimator interface
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> EstimationResult:
        """
        Estimate the random-effects GLS model on *df*.

        Stores between-R-squared, within-R-squared, and overall R-squared
        in ``result.extra``.
        """
        raise NotImplementedError
