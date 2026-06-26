"""
econflow.estimation.quantile — Panel quantile regression.

Estimates conditional quantile functions for panel data, allowing
heterogeneous AI-productivity effects across the TFP growth distribution.

Implementation approaches (once implemented)
---------------------------------------------
* **Powell (2016)** — Panel quantile regression via instrumental-variables
  approach (consistent with fixed effects).
* **Machado-Santos Silva (2019)** — Method of moments quantile regression
  (MMQR) via ``linearmodels`` (if supported).
* **Koenker (2004)** — Penalised fixed-effects quantile regression.

Usage (once implemented)
-------------------------
    from econflow.estimation.quantile import PanelQuantile
    model = PanelQuantile(
        dependent="tfp_growth",
        regressors=["aipi", "log_hc"],
        quantiles=[0.1, 0.25, 0.5, 0.75, 0.9],
    )
    results = model.fit(panel)   # returns dict[float, EstimationResult]
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult

QuantileMethod = Literal["powell", "mmqr", "koenker"]


class PanelQuantile(BaseEstimator):
    """
    Panel quantile regression estimator.

    Parameters
    ----------
    dependent:
        Dependent variable column name.
    regressors:
        Explanatory variable column names.
    quantiles:
        Target quantiles in (0, 1).  Defaults to deciles [0.1, …, 0.9].
    method:
        Estimation method.
    entity_col / time_col:
        Panel dimension identifiers.
    n_bootstrap:
        Bootstrap replications for SE estimation (0 disables bootstrap SEs).
    """

    estimator_name = "panel_quantile"

    def __init__(
        self,
        dependent: str,
        regressors: list[str],
        quantiles: list[float] | None = None,
        method: QuantileMethod = "mmqr",
        entity_col: str = "iso3",
        time_col: str = "year",
        n_bootstrap: int = 200,
    ) -> None:
        super().__init__(dependent, regressors, entity_col, time_col, cluster=None)
        self.quantiles = quantiles or [0.1, 0.25, 0.5, 0.75, 0.9]
        self.method = method
        self.n_bootstrap = n_bootstrap

    # ------------------------------------------------------------------
    # BaseEstimator interface
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> dict[float, EstimationResult]:  # type: ignore[override]
        """
        Estimate quantile models for all requested *quantiles*.

        Returns
        -------
        dict[float, EstimationResult]
            Mapping of quantile → result.

        Raises
        ------
        econflow.core.exceptions.ConvergenceError
            If any quantile optimisation fails.
        """
        raise NotImplementedError

    def coefficient_plot_data(
        self, results: dict[float, EstimationResult], variable: str
    ) -> pd.DataFrame:
        """
        Extract per-quantile estimates for *variable* into a tidy DataFrame
        suitable for a coefficient path plot.
        """
        raise NotImplementedError
